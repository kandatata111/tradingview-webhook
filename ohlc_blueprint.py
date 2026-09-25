# -*- coding: utf-8 -*-
"""
ローソク足の受け箱 (/ohlc)  ― クラウド(Render)側に追加する部品

役割
  1. TradingViewのアラームから、確定した5分足(始値・高値・安値・終値)を受け取って一時保管する
  2. PC側のプログラムが「前回の続きから」取りに来られるようにする(PCが停止中でも取りこぼさない)

既存の /webhook や webhook_data.db には一切触れない(専用DB: ohlc_buffer.db)。

エンドポイント
  POST /ohlc          TradingViewから受信(本文JSONの "key" で認証)
  GET  /ohlc/pull     PCが取得(ヘッダ X-API-Key で認証)  ?after=<前回のseq>&limit=<件数>
                      応答の db_id は「DBの世代ID」。再起動で作り直されると変わる
  GET  /ohlc/status   保管状況の確認(ヘッダ X-API-Key で認証)

環境変数(Renderの Environment に設定)
  OHLC_API_KEY         必須。未設定だと全リクエストを拒否する(安全側)
  OHLC_RETENTION_DAYS  預かる日数(既定 30)
  OHLC_ALLOWED_TF      受け付ける時間足(既定 "5"。カンマ区切りで複数可)
"""
import os
import re
import time
import hmac
import sqlite3
import uuid
from flask import Blueprint, request, jsonify

ohlc_bp = Blueprint('ohlc', __name__)

_DB_PATH = None
_last_purge = 0.0
_SYMBOL_RE = re.compile(r'^[A-Z]{6}$')
_MIN_T = 946684800000    # 2000-01-01 (ms)
_MAX_T = 4102444800000   # 2100-01-01 (ms)


def _api_key():
    return os.getenv('OHLC_API_KEY', '')


def _key_ok(given):
    expected = _api_key()
    if not expected or not given:
        return False
    return hmac.compare_digest(str(given), expected)


def _allowed_tf():
    raw = os.getenv('OHLC_ALLOWED_TF', '5')
    return {x.strip() for x in raw.split(',') if x.strip()}


def _retention_days():
    try:
        return max(1, int(os.getenv('OHLC_RETENTION_DAYS', '30')))
    except ValueError:
        return 30


def _conn():
    return sqlite3.connect(_DB_PATH, timeout=10)


def _init_db():
    with _conn() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS ohlc_buffer (
                seq         INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol      TEXT    NOT NULL,
                tf          TEXT    NOT NULL,
                t           INTEGER NOT NULL,   -- 足の開始時刻(UTCのミリ秒)
                o REAL NOT NULL, h REAL NOT NULL, l REAL NOT NULL, c REAL NOT NULL,
                v           REAL    NOT NULL DEFAULT 0,
                received_at INTEGER NOT NULL,   -- 受信時刻(UTC秒)
                UNIQUE(symbol, tf, t)
            )""")
        c.execute("CREATE INDEX IF NOT EXISTS idx_ohlc_received ON ohlc_buffer(received_at)")
        # 世代ID: DBが新しく作られる(=再起動でデータが消える)たびに変わる。PCはこれで作り直しを検知する
        c.execute("CREATE TABLE IF NOT EXISTS ohlc_meta (k TEXT PRIMARY KEY, v TEXT)")
        c.execute("INSERT OR IGNORE INTO ohlc_meta(k, v) VALUES ('db_id', ?)", (uuid.uuid4().hex,))


def _db_id():
    with _conn() as c:
        return c.execute("SELECT v FROM ohlc_meta WHERE k='db_id'").fetchone()[0]


def _purge_if_due():
    """古いデータを1時間に1回だけ削除(預かり期間を超えたもの)。"""
    global _last_purge
    now = time.time()
    if now - _last_purge < 3600:
        return
    _last_purge = now
    limit = int(now - _retention_days() * 86400)
    with _conn() as c:
        c.execute("DELETE FROM ohlc_buffer WHERE received_at < ?", (limit,))


def _parse_bar(data):
    """受信JSONを検査して (symbol, tf, t, o, h, l, c, v) を返す。不正なら ValueError。"""
    symbol = str(data.get('symbol', '')).upper()
    if not _SYMBOL_RE.match(symbol):
        raise ValueError('symbol')
    tf = str(data.get('tf', ''))
    if tf not in _allowed_tf():
        raise ValueError('tf')
    t = int(data['t'])
    if not (_MIN_T < t < _MAX_T):
        raise ValueError('t')
    o, h, l, c = (float(data[k]) for k in ('o', 'h', 'l', 'c'))
    v = float(data.get('v', 0) or 0)
    if min(o, h, l, c) <= 0 or h < l or h < max(o, c) or l > min(o, c):
        raise ValueError('ohlc')
    return symbol, tf, t, o, h, l, c, v


@ohlc_bp.route('/ohlc', methods=['POST'])
def ohlc_receive():
    data = request.get_json(force=True, silent=True)
    if not isinstance(data, dict):
        return jsonify({'status': 'error', 'msg': 'bad json'}), 400
    if not _key_ok(data.get('key')):
        return jsonify({'status': 'error', 'msg': 'unauthorized'}), 401
    try:
        symbol, tf, t, o, h, l, c, v = _parse_bar(data)
    except (KeyError, TypeError, ValueError) as e:
        return jsonify({'status': 'error', 'msg': f'invalid field: {e}'}), 400

    # 同じ足が再送されたら置き換える(新しいseqが付くので、PCは訂正も受け取れる)
    with _conn() as conn:
        cur = conn.execute(
            "INSERT OR REPLACE INTO ohlc_buffer(symbol, tf, t, o, h, l, c, v, received_at) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (symbol, tf, t, o, h, l, c, v, int(time.time())))
        seq = cur.lastrowid
    _purge_if_due()
    return jsonify({'status': 'ok', 'seq': seq})


@ohlc_bp.route('/ohlc/pull', methods=['GET'])
def ohlc_pull():
    if not _key_ok(request.headers.get('X-API-Key')):
        return jsonify({'status': 'error', 'msg': 'unauthorized'}), 401
    try:
        after = int(request.args.get('after', 0))
        limit = min(max(int(request.args.get('limit', 5000)), 1), 20000)
    except ValueError:
        return jsonify({'status': 'error', 'msg': 'bad params'}), 400
    with _conn() as conn:
        rows = conn.execute(
            "SELECT seq, symbol, tf, t, o, h, l, c, v FROM ohlc_buffer "
            "WHERE seq > ? ORDER BY seq LIMIT ?", (after, limit + 1)).fetchall()
    has_more = len(rows) > limit
    rows = rows[:limit]
    last_seq = rows[-1][0] if rows else after
    return jsonify({'status': 'ok', 'db_id': _db_id(), 'rows': [list(r) for r in rows],
                    'last_seq': last_seq, 'has_more': has_more})


@ohlc_bp.route('/ohlc/status', methods=['GET'])
def ohlc_status():
    if not _key_ok(request.headers.get('X-API-Key')):
        return jsonify({'status': 'error', 'msg': 'unauthorized'}), 401
    with _conn() as conn:
        per = conn.execute(
            "SELECT symbol, tf, COUNT(*), MIN(t), MAX(t) FROM ohlc_buffer "
            "GROUP BY symbol, tf ORDER BY symbol, tf").fetchall()
        total, max_seq = conn.execute("SELECT COUNT(*), COALESCE(MAX(seq),0) FROM ohlc_buffer").fetchone()
    return jsonify({
        'status': 'ok', 'db_id': _db_id(), 'total': total, 'max_seq': max_seq,
        'retention_days': _retention_days(),
        'series': [{'symbol': s, 'tf': tf, 'count': n, 'first_t': a, 'last_t': b}
                   for s, tf, n, a, b in per]})


def register_ohlc(app, persistent_dir):
    """render_server.py から呼ぶ。専用DBを用意して入口を登録する。"""
    global _DB_PATH
    os.makedirs(persistent_dir, exist_ok=True)
    _DB_PATH = os.path.join(persistent_dir, 'ohlc_buffer.db')
    _init_db()
    app.register_blueprint(ohlc_bp)
    print(f'[OHLC] registered. db={_DB_PATH} retention={_retention_days()}d tf={sorted(_allowed_tf())} '
          f'key_set={bool(_api_key())}')
