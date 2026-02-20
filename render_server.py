from flask import Flask, request, jsonify, render_template, send_from_directory, make_response, Response
import os, sqlite3, json, base64, hashlib, shutil
from datetime import datetime
import threading
import time
import pytz
import requests
import urllib.request
import urllib.error
from flask_socketio import SocketIO, emit
import traceback
import subprocess
import re

# バックアップデータ定数をインポート
from backup_constants import HOURLY_DATA_BACKUP, FOUR_HOURLY_DATA_BACKUP

# ビジネスロジック関数をインポート
from ichimoku_utils import (
    calculate_trend, is_fx_market_open, _get_nth_weekday,
    _evaluate_rule_match, _find_cloud_field, _parse_time_to_ms,
    _normalize_actual, _compare_values,
    calculate_trend_strength, get_distance_level, get_multi_cloud_bonus,
    apply_decay_correction
)

# トレンド強度計算v2.0（パターン検出機能付き）をインポート
from trend_strength_calculator_v2 import calculate_trend_strength_v2

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# サーバー起動時刻を記録（ウォームアップ期間の判定用）
# init_db()で明示的に設定される
SERVER_START_TIME = None

# バックアップ取得ジョブ管理（非同期実行用）
# job_id -> {'status': 'running'|'completed'|'error', 'output': str, 'started_at': str}
_backup_jobs = {}

# 各タイムフレームの初回受信フラグ（再起動時の誤発火防止）
# True = 既に受信済み（通常評価）、False = 未受信（初回は状態記録のみ）
FIRST_RECEIVE_FLAGS = {}

# 通貨強弱の最弱・最強変更履歴記録用グローバル変数
# 形式: {'15m': {'weakest': 'USD', 'strongest': 'JPY'}, '1H': {...}, ...}
previous_extreme_currencies = {}

# IMMEDIATELY log the file path to confirm which render_server.py is running
with open(os.path.join(BASE_DIR, 'webhook_error.log'), 'a', encoding='utf-8') as _f:
    _f.write(f'\n====== LOADING render_server.py FROM: {__file__} ======\n')
    _f.write(f'====== BASE_DIR: {BASE_DIR} ======\n\n')

app = Flask(__name__, template_folder=os.path.join(BASE_DIR, 'templates'))
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
app.jinja_env.auto_reload = True
app.jinja_env.cache = {}
socketio = SocketIO(app, cors_allowed_origins="*")

# Render Diskの永続ストレージパスを環境変数から取得（未設定の場合はローカルパス）
PERSISTENT_DIR = os.getenv('PERSISTENT_STORAGE_PATH', BASE_DIR)
DB_PATH = os.path.join(PERSISTENT_DIR, 'webhook_data.db')
NOTE_IMAGES_DIR = os.path.expanduser(r'C:\Users\kanda\Desktop\NoteImages')

# 起動時にストレージ設定を確認し、ディレクトリを作成
print(f"[STORAGE] Persistent directory: {PERSISTENT_DIR}")
print(f"[STORAGE] Database path: {DB_PATH}")
print(f"[STORAGE] Directory exists: {os.path.exists(PERSISTENT_DIR)}")

# 永続ストレージディレクトリが存在しない場合は作成
if not os.path.exists(PERSISTENT_DIR):
    try:
        os.makedirs(PERSISTENT_DIR, exist_ok=True)
        print(f"[STORAGE] Created persistent directory: {PERSISTENT_DIR}")
    except Exception as e:
        print(f"[STORAGE ERROR] Failed to create directory: {e}")

print(f"[STORAGE] Database exists: {os.path.exists(DB_PATH)}")
if os.path.exists(DB_PATH):
    db_size_mb = os.path.getsize(DB_PATH) / (1024 * 1024)
    print(f"[STORAGE] Database size: {db_size_mb:.2f} MB")
    
    # DB が writable か確認
    try:
        test_conn = sqlite3.connect(DB_PATH)
        test_conn.execute("SELECT 1")
        test_conn.close()
        print(f"[STORAGE] Database is readable and writable")
    except Exception as e:
        print(f"[STORAGE ERROR] Database access failed: {e}")


@app.errorhandler(405)
def method_not_allowed(error):
    return jsonify({'status': 'error', 'msg': 'Method not allowed'}), 405

@app.errorhandler(500)
def internal_server_error(error):
    return jsonify({'status': 'error', 'msg': 'Internal server error'}), 500

# 画像アップロードエンドポイント
@app.route('/api/upload-note-image', methods=['POST'])
def upload_note_image():
    try:
        # ディレクトリが存在しなければ作成
        if not os.path.exists(NOTE_IMAGES_DIR):
            os.makedirs(NOTE_IMAGES_DIR, exist_ok=True)
            print(f'[NOTE] Created directory: {NOTE_IMAGES_DIR}')
        
        # Base64エンコード済みの画像データを取得
        data = request.get_json()
        image_data = data.get('imageData')
        
        if not image_data or ',' not in image_data:
            return jsonify({'status': 'error', 'msg': 'Invalid image data'}), 400
        
        # Base64データをデコード
        header, encoded = image_data.split(',', 1)
        image_bytes = base64.b64decode(encoded)
        
        # 画像データのハッシュ値を計算
        image_hash = hashlib.sha256(image_bytes).hexdigest()
        
        # ハッシュ値からファイル名を生成
        filename = f'note_image_{image_hash}.png'
        filepath = os.path.join(NOTE_IMAGES_DIR, filename)
        
        print(f'[NOTE] Upload attempt: {filename}')
        print(f'[NOTE] Target path: {filepath}')
        print(f'[NOTE] Directory exists: {os.path.exists(NOTE_IMAGES_DIR)}')
        print(f'[NOTE] Directory writable: {os.access(NOTE_IMAGES_DIR, os.W_OK)}')
        
        # ファイルが既に存在しない場合のみ保存
        if not os.path.exists(filepath):
            with open(filepath, 'wb') as f:
                f.write(image_bytes)
            file_size = len(image_bytes)
            print(f'[NOTE] [OK] Image saved: {filename} ({file_size} bytes)')
        else:
            print(f'[NOTE] Image already exists: {filename}')
        
        # 保存を確認
        saved_correctly = os.path.exists(filepath)
        print(f'[NOTE] Verification - File exists after save: {saved_correctly}')
        
        if saved_correctly:
            actual_size = os.path.getsize(filepath)
            print(f'[NOTE] Actual file size on disk: {actual_size} bytes')
        
        # ファイルパスをJSONで返す
        return jsonify({
            'status': 'success',
            'imageHash': image_hash,
            'filename': filename,
            'filepath': filepath,
            'fileExists': saved_correctly
        }), 200
    
    except Exception as e:
        print(f'[ERROR] Image upload failed: {e}')
        import traceback
        print(traceback.format_exc())
        return jsonify({'status': 'error', 'msg': str(e)}), 500

# 画像取得エンドポイント
@app.route('/api/note-image/<image_hash>')
def get_note_image(image_hash):
    try:
        # ファイル名を再構築
        filename = f'note_image_{image_hash}.png'
        filepath = os.path.join(NOTE_IMAGES_DIR, filename)
        
        # ファイルが存在するかチェック
        if not os.path.exists(filepath):
            return jsonify({'status': 'error', 'msg': 'Image not found'}), 404
        
        # ファイルを返す
        response = make_response(send_from_directory(NOTE_IMAGES_DIR, filename))
        
        # CORS ヘッダーを追加
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        
        # キャッシング設定
        response.headers['Cache-Control'] = 'public, max-age=31536000'  # 1年間キャッシュ
        response.headers['X-Content-Type-Options'] = 'nosniff'
        
        return response
    
    except Exception as e:
        print(f'[ERROR] Image fetch failed: {e}')
        return jsonify({'status': 'error', 'msg': str(e)}), 500

@app.route('/api/note-image/<image_hash>', methods=['OPTIONS'])
def note_image_options(image_hash):
    # CORS プリフライト対応
    response = make_response('', 204)
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    return response

# 外部サイトプロキシエンドポイント
@app.route('/api/proxy')
def proxy_external_site():
    """外部サイトをプロキシ経由で取得"""
    try:
        url = request.args.get('url', 'https://zai.diamond.jp/list/fxcolumn/hitsuji')
        
        # 許可するドメインをホワイトリスト化（セキュリティのため）
        allowed_domains = ['zai.diamond.jp']
        from urllib.parse import urlparse
        parsed = urlparse(url)
        if parsed.netloc not in allowed_domains:
            return jsonify({'status': 'error', 'msg': 'Domain not allowed'}), 403
        
        # 外部サイトからコンテンツを取得
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ja,en-US;q=0.7,en;q=0.3',
        }
        
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        
        # HTMLコンテンツを取得
        content = resp.text
        
        # ベースURLを追加してリソースが正しく読み込まれるようにする
        base_url = f"{parsed.scheme}://{parsed.netloc}"
        
        # <head>タグの直後に<base>タグを挿入
        if '<head>' in content:
            content = content.replace('<head>', f'<head><base href="{base_url}/">', 1)
        elif '<HEAD>' in content:
            content = content.replace('<HEAD>', f'<HEAD><base href="{base_url}/">', 1)
        
        # 相対URLを絶対URLに変換（一部）
        content = content.replace('href="/', f'href="{base_url}/')
        content = content.replace("href='/", f"href='{base_url}/")
        content = content.replace('src="/', f'src="{base_url}/')
        content = content.replace("src='/", f"src='{base_url}/")
        
        # レスポンスを返す
        response = Response(content, mimetype='text/html')
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Cache-Control'] = 'no-cache'
        
        return response
        
    except requests.exceptions.Timeout:
        return jsonify({'status': 'error', 'msg': 'Request timeout'}), 504
    except requests.exceptions.RequestException as e:
        print(f'[PROXY] Error fetching URL: {e}')
        return jsonify({'status': 'error', 'msg': str(e)}), 502
    except Exception as e:
        print(f'[PROXY] Unexpected error: {e}')
        return jsonify({'status': 'error', 'msg': str(e)}), 500

def cleanup_old_data():
    """
    古いデータを削除し、各通貨ペア・各時間足の最新レコードのみを保持する。
    これによりデータベースサイズを最小限に抑える。
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        # states テーブルから各(symbol, tf)の最新レコード以外を削除
        # PRIMARY KEY (symbol, tf) なので実際には古いレコードは上書きされているはずだが、
        # timestampが古いレコードがあれば削除
        c.execute('''
            DELETE FROM states 
            WHERE rowid NOT IN (
                SELECT MAX(rowid) 
                FROM states 
                GROUP BY symbol, tf
            )
        ''')
        deleted_states = c.rowcount
        
        # fire_history テーブルから30日より古いレコードを削除
        from datetime import datetime, timedelta
        import pytz
        jst = pytz.timezone('Asia/Tokyo')
        threshold = (datetime.now(jst) - timedelta(days=30)).isoformat()
        
        c.execute('DELETE FROM fire_history WHERE fired_at < ?', (threshold,))
        deleted_fire = c.rowcount
        
        conn.commit()
        conn.close()
        
        if deleted_states > 0 or deleted_fire > 0:
            print(f'[CLEANUP] Deleted {deleted_states} old state(s), {deleted_fire} old fire record(s)')
        else:
            print('[CLEANUP] No old data to clean up')
            
    except Exception as e:
        print(f'[CLEANUP ERROR] {e}')

# tf正規化マップ（全箇所で共通使用）
_TF_NORMALIZE_MAP = {
    '5m': '5', '5M': '5',
    '15m': '15', '15M': '15',
    '1H': '60', '1h': '60',
    '4H': '240', '4h': '240',
}

def _normalize_tf(tf):
    """tf文字列を正規化する（例: 15M→15, 1H→60, 4H→240）"""
    return _TF_NORMALIZE_MAP.get(tf, tf)


# 日足データのバックアップ（サーバー再起動時に自動復元用）
DAILY_DATA_BACKUP = [
    {"symbol":"GBPUSD","tf":"D","time":1769119200000,"daytrade":{"status":"上昇ダウ","bos":"BOS-1","time":"25/11/26/07:00"},"row_order":["Y","price","D","W","M"],"cloud_order":["D","W","M","Y"],"clouds":[{"label":"D","tf":"D","gc":True,"thickness":15.1526735576,"angle":35.8360348113,"elapsed":0,"cross_start_time":1769119200000,"elapsed_str":"26/01/23/07:00","in_cloud":False,"star":False,"distance_from_price":172.5436632212,"distance_from_prev":172.5436632212,"topPrice":1.3480432674,"bottomPrice":1.346528,"dauten":"up","bos_count":0,"dauten_start_time":1764108000000,"dauten_start_time_str":"25/11/26/07:00"}],"price":1.36454},
    {"symbol":"GBPAUD","tf":"D","time":1769119200000,"daytrade":{"status":"下降ダウ","bos":"-","time":"26/01/15/07:00"},"row_order":["M","W","D","price","Y"],"cloud_order":["D","W","M","Y"],"clouds":[{"label":"D","tf":"D","gc":False,"thickness":107.8509999539,"angle":-35.9219970308,"elapsed":24480,"cross_start_time":1767650400000,"elapsed_str":"26/01/06/07:00","in_cloud":False,"star":False,"distance_from_price":-189.1795000231,"distance_from_prev":-189.1795000231,"topPrice":2.0032705,"bottomPrice":1.9924854,"dauten":"down","bos_count":0,"dauten_start_time":1768428000000,"dauten_start_time_str":"26/01/15/07:00"}],"price":1.97896},
    {"symbol":"USDJPY","tf":"D","time":1769119200000,"daytrade":{"status":"下降ダウ","bos":"-","time":"26/01/23/07:00"},"row_order":["D","price","W","M","Y"],"cloud_order":["D","W","M","Y"],"clouds":[{"label":"D","tf":"D","gc":True,"thickness":24.098899093,"angle":-35.6387377562,"elapsed":50400,"cross_start_time":1766095200000,"elapsed_str":"25/12/19/07:00","in_cloud":False,"star":False,"distance_from_price":-180.4894495464,"distance_from_prev":-180.4894495464,"topPrice":157.6613889909,"bottomPrice":157.4204,"dauten":"down","bos_count":0,"dauten_start_time":1769119200000,"dauten_start_time_str":"26/01/23/07:00"}],"price":155.736},
    {"symbol":"AUDUSD","tf":"D","time":1769119200000,"daytrade":{"status":"上昇ダウ","bos":"BOS-2","time":"25/12/03/07:00"},"row_order":["Y","price","D","W","M"],"cloud_order":["D","W","M","Y"],"clouds":[{"label":"D","tf":"D","gc":True,"thickness":44.3299115491,"angle":35.8659696247,"elapsed":80640,"cross_start_time":1764280800000,"elapsed_str":"25/11/28/07:00","in_cloud":False,"star":False,"distance_from_price":152.1000442255,"distance_from_prev":152.1000442255,"topPrice":0.6766364912,"bottomPrice":0.6722035,"dauten":"up","bos_count":0,"dauten_start_time":1764712800000,"dauten_start_time_str":"25/12/03/07:00"}],"price":0.68963},
    {"symbol":"EURUSD","tf":"D","time":1769119200000,"daytrade":{"status":"上昇ダウ","bos":"BOS-1","time":"25/12/03/07:00"},"row_order":["price","Y","D","W","M"],"cloud_order":["D","W","M","Y"],"clouds":[{"label":"D","tf":"D","gc":True,"thickness":13.2038720124,"angle":35.7838381001,"elapsed":0,"cross_start_time":1769119200000,"elapsed_str":"26/01/23/07:00","in_cloud":False,"star":False,"distance_from_price":123.8380639938,"distance_from_prev":123.8380639938,"topPrice":1.1710463872,"bottomPrice":1.169726,"dauten":"up","bos_count":0,"dauten_start_time":1764712800000,"dauten_start_time_str":"25/12/03/07:00"}],"price":1.18277},
    {"symbol":"GBPJPY","tf":"D","time":1769119200000,"daytrade":{"status":"上昇ダウ","bos":"BOS-2","time":"25/11/18/07:00"},"row_order":["price","D","W","M","Y"],"cloud_order":["D","W","M","Y"],"clouds":[{"label":"D","tf":"D","gc":True,"thickness":55.9298926229,"angle":35.8298419899,"elapsed":102240,"cross_start_time":1762984800000,"elapsed_str":"25/11/13/07:00","in_cloud":True,"star":True,"distance_from_price":26.2300536886,"distance_from_prev":26.2300536886,"topPrice":212.5253489262,"bottomPrice":211.96605,"dauten":"up","bos_count":0,"dauten_start_time":1763416800000,"dauten_start_time_str":"25/11/18/07:00"}],"price":212.508},
    {"symbol":"EURGBP","tf":"D","time":1769119200000,"daytrade":{"status":"下降ダウ","bos":"-","time":"25/12/24/07:00"},"row_order":["W","D","price","M","Y"],"cloud_order":["D","W","M","Y"],"clouds":[{"label":"D","tf":"D","gc":True,"thickness":0.2165786254,"angle":-33.9077679764,"elapsed":1440,"cross_start_time":1769032800000,"elapsed_str":"26/01/22/07:00","in_cloud":False,"star":False,"distance_from_price":-18.3832893126,"distance_from_prev":-18.3832893126,"topPrice":0.8687291579,"bottomPrice":0.8687075,"dauten":"down","bos_count":0,"dauten_start_time":1766527200000,"dauten_start_time_str":"25/12/24/07:00"}],"price":0.86688},
    {"symbol":"EURAUD","tf":"D","time":1769119200000,"daytrade":{"status":"下降ダウ","bos":"BOS-2","time":"25/12/04/07:00"},"row_order":["W","M","D","price","Y"],"cloud_order":["D","W","M","Y"],"clouds":[{"label":"D","tf":"D","gc":False,"thickness":93.1999855205,"angle":-35.9169260801,"elapsed":43200,"cross_start_time":1766527200000,"elapsed_str":"25/12/24/07:00","in_cloud":False,"star":False,"distance_from_price":-200.0350072398,"distance_from_prev":-200.0350072398,"topPrice":1.7402635,"bottomPrice":1.7309435014,"dauten":"down","bos_count":0,"dauten_start_time":1764799200000,"dauten_start_time_str":"25/12/04/07:00"}],"price":1.7156},
    {"symbol":"EURJPY","tf":"D","time":1769119200000,"daytrade":{"status":"上昇ダウ","bos":"BOS-9","time":"25/05/01/06:00"},"row_order":["D","price","W","M","Y"],"cloud_order":["D","W","M","Y"],"clouds":[{"label":"D","tf":"D","gc":True,"thickness":48.7752291462,"angle":35.756856021,"elapsed":157020,"cross_start_time":1759698000000,"elapsed_str":"25/10/06/06:00","in_cloud":True,"star":True,"distance_from_price":-16.1176145731,"distance_from_prev":-16.1176145731,"topPrice":184.6290522915,"bottomPrice":184.1413,"dauten":"up","bos_count":0,"dauten_start_time":1746046800000,"dauten_start_time_str":"25/05/01/06:00"}],"price":184.224},
    {"symbol":"AUDJPY","tf":"D","time":1769119200000,"daytrade":{"status":"上昇ダウ","bos":"BOS-5","time":"25/09/03/06:00"},"row_order":["price","D","W","M","Y"],"cloud_order":["D","W","M","Y"],"clouds":[{"label":"D","tf":"D","gc":True,"thickness":85.3131107717,"angle":35.8977736312,"elapsed":157020,"cross_start_time":1759698000000,"elapsed_str":"25/10/06/06:00","in_cloud":False,"star":False,"distance_from_price":113.9534446141,"distance_from_prev":113.9534446141,"topPrice":106.6690311077,"bottomPrice":105.8159,"dauten":"up","bos_count":0,"dauten_start_time":1756846800000,"dauten_start_time_str":"25/09/03/06:00"}],"price":107.382}
]

def restore_from_json_backup_folder():
    """
    [DISABLED] 起動時のTradingViewBackup_JSONフォルダからの復元は廃止。
    RenderのSQLite DBはPersistent Diskに保存されるため、
    再起動後もDBのデータはそのまま残る。
    ローカル環境専用の機能であり、Renderではパスが存在しないため動作しないが、
    側面効果防止のため廃止。
    """
    print('[INIT_BACKUP] restore_from_json_backup_folder: DISABLED')
    return  # DISABLED - DB persists on Render persistent disk


def restore_missing_data():
    """
    [DISABLED] ハードコードバックアップでの起動時復元は廃止。
    RenderのSQLite DBはPersistent Diskに保存されるため、
    再起動後もDBのデータはそのまま残る。
    DAILY_DATA_BACKUP/FOUR_HOURLY_DATA_BACKUP/HOURLY_DATA_BACKUPを使った復元は
    古いデータで上書きする問題の原因となるため廃止。
    """
    print('[INIT] restore_missing_data: DISABLED')
    return  # DISABLED - DB persists on Render persistent disk


def save_dynamic_backup(symbol, tf, data):
    """
    [DISABLED] dynamic_backup.jsonへの保存は廃止。
    RenderのSQLite DBはPersistent Diskに保存されるため、
    再起動後もDBのデータはそのまま残る。
    このJSONバックアップは古いtf形式データの再挿入など問題の原因となるため無効化。
    """
    return  # DISABLED


def restore_from_dynamic_backup():
    """
    [DISABLED] dynamic_backup.jsonからの復元は廃止。
    RenderのSQLite DBはPersistent Diskに保存されるため、
    再起動後もDBのデータはそのまま残る。
    このJSONバックアップは古いtf形式データの再挿入など問題の原因となるため無効化。
    """
    print('[INIT] restore_from_dynamic_backup: DISABLED (DB persists on Render persistent disk)')
    return  # DISABLED


def init_db():
    global SERVER_START_TIME, FIRST_RECEIVE_FLAGS
    SERVER_START_TIME = datetime.now(pytz.UTC)
    
    # 各タイムフレームの初回受信フラグをリセット
    FIRST_RECEIVE_FLAGS = {}
    
    # ログに起動時刻を記録
    with open(os.path.join(BASE_DIR, 'webhook_error.log'), 'a', encoding='utf-8') as f:
        f.write(f'\n====== SERVER_START_TIME: {SERVER_START_TIME.isoformat()} ======\n')
        f.write(f'====== Starting init_db at {datetime.now(pytz.timezone("Asia/Tokyo")).isoformat()} ======\n')
        f.write(f'====== FIRST_RECEIVE_FLAGS reset ======\n\n')
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS states (
        symbol TEXT NOT NULL,
        tf TEXT NOT NULL,
        timestamp TEXT,
        price REAL,
        time INTEGER,
        state_flag TEXT,
        state_word TEXT,
        daytrade_status TEXT,
        daytrade_bos TEXT,
        daytrade_time TEXT,
        swing_status TEXT,
        swing_bos TEXT,
        swing_time TEXT,
        row_order TEXT,
        cloud_order TEXT,
        clouds_json TEXT,
        meta_json TEXT,
        PRIMARY KEY (symbol, tf)
    )''')
    conn.commit()
    
    # Add received_at column if it doesn't exist (for JSON received timestamp)
    try:
        c.execute('ALTER TABLE states ADD COLUMN received_at TEXT')
        conn.commit()
        print('[OK] received_at column added to states table')
    except Exception:
        pass  # Column already exists
    
    # Add sent_time column if it doesn't exist (for JSON sent_time field)
    try:
        c.execute('ALTER TABLE states ADD COLUMN sent_time TEXT')
        conn.commit()
        print('[OK] sent_time column added to states table')
    except Exception:
        pass  # Column already exists
    
    # Add trend-related columns if they don't exist
    try:
        c.execute('ALTER TABLE states ADD COLUMN trend_direction TEXT')
        conn.commit()
        print('[OK] trend_direction column added to states table')
    except Exception:
        pass
    
    try:
        c.execute('ALTER TABLE states ADD COLUMN trend_score INTEGER')
        conn.commit()
        print('[OK] trend_score column added to states table')
    except Exception:
        pass
    
    try:
        c.execute('ALTER TABLE states ADD COLUMN trend_percentage INTEGER')
        conn.commit()
        print('[OK] trend_percentage column added to states table')
    except Exception:
        pass
    
    try:
        c.execute('ALTER TABLE states ADD COLUMN trend_strength TEXT')
        conn.commit()
        print('[OK] trend_strength column added to states table')
    except Exception:
        pass
    
    try:
        c.execute('ALTER TABLE states ADD COLUMN trend_breakdown_json TEXT')
        conn.commit()
        print('[OK] trend_breakdown_json column added to states table')
    except Exception:
        pass
    
    conn.close()
    print('[OK] DB initialized')

    # rules テーブル（ルール保存用）
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS rules (
        id TEXT PRIMARY KEY,
        name TEXT,
        enabled INTEGER,
        scope_json TEXT,
        rule_json TEXT,
        created_at TEXT,
        updated_at TEXT
    )''')
    # Add updated_at column if it doesn't exist (for existing databases)
    try:
        c.execute('ALTER TABLE rules ADD COLUMN updated_at TEXT')
        conn.commit()
    except Exception:
        pass  # Column already exists
    # Add sort_order column if it doesn't exist
    try:
        c.execute('ALTER TABLE rules ADD COLUMN sort_order INTEGER DEFAULT 0')
        conn.commit()
    except Exception:
        pass  # Column already exists
    conn.commit()
    conn.close()
    print('[OK] Rules table ensured')
    
    # fire_history テーブル（発火履歴記録用）
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS fire_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        rule_id TEXT NOT NULL,
        symbol TEXT NOT NULL,
        tf TEXT NOT NULL,
        fired_at TEXT NOT NULL,
        conditions_snapshot TEXT,
        last_state_snapshot TEXT
    )''')
    # Add last_state_snapshot column if it doesn't exist
    try:
        c.execute('ALTER TABLE fire_history ADD COLUMN last_state_snapshot TEXT')
        conn.commit()
    except Exception:
        pass  # Column already exists
    conn.commit()
    conn.close()
    print('[OK] Fire history table ensured')
    
    # market_status テーブル（最後の受信時刻記録用）
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS market_status (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        last_receive_time TEXT
    )''')
    # Insert initial record if not exists
    c.execute('INSERT OR IGNORE INTO market_status (id, last_receive_time) VALUES (1, NULL)')
    conn.commit()
    conn.close()
    print('[OK] Market status table ensured')
    
    # currency_order テーブル（通貨ペアの表示順序管理用）
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS currency_order (
        symbol TEXT PRIMARY KEY,
        sort_order INTEGER NOT NULL,
        updated_at TEXT
    )''')
    conn.commit()
    conn.close()
    print('[OK] Currency order table ensured')
    
    # change_history テーブル（通貨強弱の最弱・最強変更履歴記録用）
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS change_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timeframe TEXT NOT NULL,
        weakest TEXT NOT NULL,
        strongest TEXT NOT NULL,
        weakest_percent INTEGER DEFAULT 0,
        strongest_percent INTEGER DEFAULT 0,
        timestamp TEXT NOT NULL,
        created_at TEXT NOT NULL
    )''')
    # timeframe でインデックス作成（検索高速化）
    c.execute('''CREATE INDEX IF NOT EXISTS idx_change_history_timeframe 
                 ON change_history(timeframe, created_at DESC)''')
    
    # 既存のテーブルに新しいカラムを追加（存在しない場合のみ）
    try:
        c.execute("ALTER TABLE change_history ADD COLUMN weakest_percent INTEGER DEFAULT 0")
        print('[OK] Added weakest_percent column to change_history table')
    except sqlite3.OperationalError as e:
        if 'duplicate column name' not in str(e).lower():
            print(f'[INFO] Column weakest_percent may already exist: {e}')
    
    try:
        c.execute("ALTER TABLE change_history ADD COLUMN strongest_percent INTEGER DEFAULT 0")
        print('[OK] Added strongest_percent column to change_history table')
    except sqlite3.OperationalError as e:
        if 'duplicate column name' not in str(e).lower():
            print(f'[INFO] Column strongest_percent may already exist: {e}')
    
    conn.commit()
    conn.close()
    print('[OK] Change history table ensured')
    
    # 古いデータのクリーンアップ（最新データのみ保持）
    cleanup_old_data()
    
    # ↓↓↓ 起動時の状態データ復元処理は全て廃止 ↓↓↓
    # RenderはSQLite DBをPersistent Diskに永続保存するため、
    # サーバー再起動後もデータはそのまま残る。
    # restore_from_json_backup_folder()  # DISABLED
    # restore_missing_data()             # DISABLED
    # restore_from_dynamic_backup()      # DISABLED

    # ルールバックアップJSONからの復元（DBにルールが0件のときのみ）
    # rules_backup.jsonはgitに含まれるため、デプロイ後にルールが消えても自動復元できる
    _restore_rules_from_backup()

    # ノートデータファイルの確認
    notes_path = os.path.join(BASE_DIR, 'notes_data.json')
    if os.path.exists(notes_path):
        try:
            with open(notes_path, 'r', encoding='utf-8') as f:
                notes_data = json.load(f)
            note_count = len(notes_data) if isinstance(notes_data, list) else 1
            print(f'[OK] Notes data file found with {note_count} page(s)')
        except Exception as e:
            print(f'[WARNING] Notes data file exists but could not be read: {e}')
    else:
        print('[INFO] No notes data file found, will be created on first save')

def _restore_rules_from_backup():
    """起動時: DBのrulesが0件のときのみ rules_backup.json から復元する（永続ストレージ優先）"""
    try:
        # 永続ストレージのバックアップを優先して探す（Render 等で PERSISTENT_DIR が設定されている場合）
        persistent_path = os.path.join(PERSISTENT_DIR, 'rules_backup.json')
        bundled_path = os.path.join(BASE_DIR, 'rules_backup.json')
        rules_backup_path = None

        if os.path.exists(persistent_path):
            rules_backup_path = persistent_path
            print(f'[RULES] Using persistent rules backup: {persistent_path}')
        elif os.path.exists(bundled_path):
            rules_backup_path = bundled_path
            print(f'[RULES] Using bundled rules backup: {bundled_path}')
        else:
            print('[RULES] No rules_backup.json found in persistent or bundled paths, skipping restore')
            return

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('SELECT COUNT(*) FROM rules')
        count = c.fetchone()[0]
        if count > 0:
            print(f'[RULES] DB already has {count} rules, skipping restore from backup')
            conn.close()
            return

        with open(rules_backup_path, 'r', encoding='utf-8') as f:
            backup = json.load(f)
        rules_list = backup.get('rules', [])
        if not rules_list:
            print('[RULES] rules_backup.json is empty, skipping')
            conn.close()
            return

        jst = pytz.timezone('Asia/Tokyo')
        now = datetime.now(jst).isoformat()
        restored = 0
        for rule in rules_list:
            rid = rule.get('id')
            if not rid:
                continue
            rule_data = {
                'voice': rule.get('voice', {}),
                'cloudAlign': rule.get('cloudAlign', {}),
                'conditions': rule.get('conditions', [])
            }
            c.execute('INSERT OR REPLACE INTO rules (id,name,enabled,scope_json,rule_json,created_at,updated_at,sort_order) VALUES (?,?,?,?,?,?,?,?)',
                (
                    rid, rule.get('name', 'unnamed'),
                    1 if rule.get('enabled', True) else 0,
                    json.dumps(rule.get('scope', {}), ensure_ascii=False),
                    json.dumps(rule_data, ensure_ascii=False),
                    rule.get('created_at', now), rule.get('updated_at', now),
                    rule.get('sort_order', 9999)
                ))
            restored += 1
        conn.commit()
        conn.close()
        print(f'[RULES] Restored {restored} rules from {rules_backup_path}')
    except Exception as e:
        print(f'[RULES] Failed to restore rules from backup: {e}')


def _save_rules_backup():
    """ルールをrules_backup.jsonに保存（gitに含めてデプロイ後の復元に備える）"""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('SELECT id, name, enabled, scope_json, rule_json, created_at, updated_at, sort_order FROM rules ORDER BY sort_order ASC, created_at ASC')
        rows = c.fetchall()
        conn.close()
        rules_list = []
        for r in rows:
            rule_data = json.loads(r[4]) if r[4] else {}
            obj = {
                'id': r[0], 'name': r[1], 'enabled': bool(r[2]),
                'scope': json.loads(r[3]) if r[3] else None,
                'created_at': r[5], 'updated_at': r[6], 'sort_order': r[7]
            }
            obj.update(rule_data)
            rules_list.append(obj)
        jst = pytz.timezone('Asia/Tokyo')
        backup = {
            'exported_at': datetime.now(jst).isoformat(),
            'count': len(rules_list),
            'rules': rules_list
        }
        persistent_path = os.path.join(PERSISTENT_DIR, 'rules_backup.json')
        bundled_path = os.path.join(BASE_DIR, 'rules_backup.json')

        # まず永続ストレージへ保存（できればこちらを最新にする）
        try:
            with open(persistent_path, 'w', encoding='utf-8') as f:
                json.dump(backup, f, ensure_ascii=False, indent=2)
            print(f'[RULES] Saved {len(rules_list)} rules to persistent backup: {persistent_path}')
        except Exception as e:
            print(f'[RULES] Failed to write persistent backup: {e} (path={persistent_path})')

        # 併せてアプリバンドル側にも保存しておく（デプロイ時の参照用 / git 運用との互換）
        try:
            with open(bundled_path, 'w', encoding='utf-8') as f:
                json.dump(backup, f, ensure_ascii=False, indent=2)
            print(f'[RULES] Also saved rules backup to bundled path: {bundled_path}')
        except Exception as e:
            print(f'[RULES] Failed to write bundled backup: {e} (path={bundled_path})')
    except Exception as e:
        print(f'[RULES] Failed to save rules backup: {e}')


@app.route('/Alarm/<path:filename>')
def serve_alarm_file(filename):
    return send_from_directory(os.path.join(BASE_DIR, 'Alarm'), filename)

@app.route('/api/chime_files')
def get_chime_files():
    """Alarmフォルダ内の音声ファイルリストを返す"""
    try:
        alarm_dir = os.path.join(BASE_DIR, 'Alarm')
        if not os.path.exists(alarm_dir):
            return jsonify({'status': 'success', 'files': []})
        
        files = []
        for filename in os.listdir(alarm_dir):
            if filename.lower().endswith(('.mp3', '.wav', '.ogg')):
                files.append(filename)
        
        files.sort()
        return jsonify({'status': 'success', 'files': files})
    except Exception as e:
        print(f'[ERROR] Getting chime files: {e}')
        return jsonify({'status': 'error', 'files': []})

@app.route('/')
def dashboard():
    print('[ACCESS] Dashboard request')
    try:
        response = make_response(render_template('dashboard.html'))
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response
    except Exception as e:
        print(f'[ERROR] Dashboard error: {e}')
        return f'Error: {e}', 500

@app.route('/test')
def test():
    return render_template('test.html')

@app.route('/debug_test')
def debug_test():
    """デバッグページ: baseTimeframe選択と実際のデータを確認"""
    try:
        response = make_response(render_template('debug_test.html'))
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response
    except Exception as e:
        print(f'[ERROR] Debug test error: {e}')
        return f'Error: {e}', 500

@app.route('/json_test_panel')
def json_test_panel():
    response = make_response(render_template('json_test_panel.html'))
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@app.route('/notes_window')
def notes_window():
    """ノート専用ウィンドウ"""
    response = make_response(render_template('notes_window.html'))
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@app.route('/settings_window')
def settings_window():
    """設定専用ウィンドウ"""
    response = make_response(render_template('settings_window.html'))
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@app.route('/economic_calendar_window')
def economic_calendar_window():
    """経済指標専用ウィンドウ"""
    response = make_response(render_template('economic_calendar_window.html'))
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@app.route('/shepherd_column_window')
def shepherd_column_window():
    """羊飼い専用ウィンドウ"""
    response = make_response(render_template('shepherd_column_window.html'))
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@app.route('/timer_window')
def timer_window():
    """確定タイマー専用ウィンドウ"""
    response = make_response(render_template('timer_window.html'))
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@app.route('/timer_showcase')
def timer_showcase():
    """タイマーデザイン一覧表示"""
    response = make_response(render_template('timer_showcase.html'))
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@app.route('/currency_strength_window')
def currency_strength_window():
    """通貨強弱専用ウィンドウ"""
    response = make_response(render_template('currency_strength_final.html'))
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@app.route('/currency_strength_final')
def currency_strength_final():
    """通貨強弱ページ（最終版）"""
    response = make_response(render_template('currency_strength_final.html'))
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@app.route('/test_api')
def test_api():
    """APIテストページ"""
    response = make_response(render_template('test_api.html'))
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    return response

@app.route('/debug_currency_strength')
def debug_currency_strength():
    """通貨強弱デバッグページ"""
    import os
    debug_file = os.path.join(BASE_DIR, '..', 'test_browser_debug.html')
    with open(debug_file, 'r', encoding='utf-8') as f:
        content = f.read()
    response = make_response(content)
    response.headers['Content-Type'] = 'text/html; charset=utf-8'
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    return response

@app.route('/test_simple')
def test_simple():
    """シンプルテストページ"""
    response = make_response(render_template('test_simple.html'))
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    return response

def calculate_currency_strength_data():
    """通貨強弱データを計算する（内部関数）"""
    jst = pytz.timezone('Asia/Tokyo')
    current_time = datetime.now(jst).strftime('%Y-%m-%d %H:%M:%S')
    print(f'[CURRENCY_STRENGTH] Calculating at {current_time}')
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # 全通貨ペアと全時間足のトレンドデータを取得
    c.execute('SELECT symbol, tf, row_order, clouds_json FROM states')
    rows = c.fetchall()
    conn.close()
    
    print(f'[CURRENCY_STRENGTH] Fetched {len(rows)} rows from database')
    
    # 通貨ペアの定義（実在するペアのみ）
    # 左の通貨が強い=上昇、右の通貨が強い=下降
    PAIR_DEFINITIONS = {
        'USDJPY': ('USD', 'JPY'),
        'EURUSD': ('EUR', 'USD'),
        'GBPUSD': ('GBP', 'USD'),
        'AUDUSD': ('AUD', 'USD'),
        'EURJPY': ('EUR', 'JPY'),
        'GBPJPY': ('GBP', 'JPY'),
        'AUDJPY': ('AUD', 'JPY'),
        'EURGBP': ('EUR', 'GBP'),
        'EURAUD': ('EUR', 'AUD'),
        'GBPAUD': ('GBP', 'AUD')
    }
    
    # 時間足ごとの通貨強弱を計算
    timeframes = ['5m', '15m', '1H', '4H', 'D']
    # データベースの実際の値とマッピング
    tf_map = {
        '5m': ['5'],
        '15m': ['15', '15M'],
        '1H': ['60', '1H'],
        '4H': ['240', '4H'],
        'D': ['D', '1440']
    }
    
    result = {}
    
    for tf_display in timeframes:
        tf_variants = tf_map[tf_display]
        currency_scores = {}  # 通貨ごとのスコア合計
        currency_breakdown = {}  # 通貨ごとの内訳（デバッグ用）
        
        for symbol, tf, row_order, clouds_json in rows:
            if tf not in tf_variants:
                continue
            
            if symbol not in PAIR_DEFINITIONS:
                continue
            
            base_currency, quote_currency = PAIR_DEFINITIONS[symbol]
            
            # トレンド強度を計算
            if not row_order or not clouds_json:
                continue
            
            try:
                clouds = json.loads(clouds_json) if clouds_json else []
                
                # state_dataを構築
                state_data = {
                    'clouds': clouds,
                    'row_order': row_order,
                    'clouds_json': clouds_json
                }
                
                trend_result = calculate_trend_strength_v2(
                    tf=tf,
                    state_data=state_data,
                    all_states=None
                )
                
                score = trend_result.get('score', 0)
                direction = trend_result.get('direction', 'range')
                strength = trend_result.get('strength', '横')
                
                # デバッグログ：計算されたスコアを出力
                print(f'[CURRENCY_STRENGTH] {symbol} tf={tf} (表示:{tf_display}): direction={direction}, score={score}, strength={strength}, row_order={row_order}')
                
                # レンジはスキップ
                if direction == 'range' or score == 0:
                    continue
                
                # 方向に応じてスコアを配分
                if direction == 'up':
                    # 上昇 = 左の通貨が強い
                    currency_scores[base_currency] = currency_scores.get(base_currency, 0) + score
                    currency_scores[quote_currency] = currency_scores.get(quote_currency, 0) - score
                    
                    # 内訳を記録
                    if base_currency not in currency_breakdown:
                        currency_breakdown[base_currency] = []
                    currency_breakdown[base_currency].append(f'{symbol} 上昇{score}点 (+{score})')
                    
                    if quote_currency not in currency_breakdown:
                        currency_breakdown[quote_currency] = []
                    currency_breakdown[quote_currency].append(f'{symbol} 上昇{score}点 (-{score})')
                    
                elif direction == 'down':
                    # 下降 = 右の通貨が強い
                    currency_scores[base_currency] = currency_scores.get(base_currency, 0) - score
                    currency_scores[quote_currency] = currency_scores.get(quote_currency, 0) + score
                    
                    # 内訳を記録
                    if base_currency not in currency_breakdown:
                        currency_breakdown[base_currency] = []
                    currency_breakdown[base_currency].append(f'{symbol} 下降{score}点 (-{score})')
                    
                    if quote_currency not in currency_breakdown:
                        currency_breakdown[quote_currency] = []
                    currency_breakdown[quote_currency].append(f'{symbol} 下降{score}点 (+{score})')
            
            except Exception as e:
                print(f'[CURRENCY_STRENGTH] Error calculating {symbol} {tf}: {e}')
                continue
        
        # スコアでソート（降順）
        sorted_currencies = sorted(currency_scores.items(), key=lambda x: x[1])
        
        # 内訳をログ出力
        print(f'\n[CURRENCY_STRENGTH] ===== {tf_display} =====')
        for currency, score in sorted_currencies:
            breakdown = currency_breakdown.get(currency, [])
            print(f'{currency} 合計: {int(score)}点')
            for item in breakdown:
                print(f'  - {item}')
        
        # %表示を追加（±100点=±100%）
        currencies_with_percent = []
        for currency, score in sorted_currencies:
            percentage = int((score / 100.0) * 100)
            currencies_with_percent.append({
                'currency': currency,
                'score': int(score),
                'percentage': percentage
            })
        
        result[tf_display] = {
            'currencies': currencies_with_percent,
            'raw_scores': currency_scores,
            'breakdown': currency_breakdown
        }
    
    # 平均を計算
    avg_scores = {}
    for tf_display in timeframes:
        if tf_display not in result:
            continue
        for item in result[tf_display]['currencies']:
            currency = item['currency']
            score = item['score']
            avg_scores[currency] = avg_scores.get(currency, 0) + score
    
    # 平均を時間足数で割る
    num_tfs = len([tf for tf in timeframes if tf in result])
    if num_tfs > 0:
        for currency in avg_scores:
            avg_scores[currency] = avg_scores[currency] / num_tfs
    
    sorted_avg = sorted(avg_scores.items(), key=lambda x: x[1])
    
    # 平均にも%表示を追加
    avg_with_percent = []
    for currency, score in sorted_avg:
        percentage = int((score / 400.0) * 100)
        avg_with_percent.append({
            'currency': currency,
            'score': int(score),
            'percentage': percentage
        })
    
    result['Av'] = {
        'currencies': avg_with_percent,
        'raw_scores': avg_scores
    }
    
    # 更新時刻を追加
    result['last_updated'] = current_time
    
    return result

def detect_and_record_extreme_changes(currency_data):
    """通貨強弱の最弱・最強の変更を検出してDBに記録"""
    global previous_extreme_currencies
    jst = pytz.timezone('Asia/Tokyo')
    
    try:
        current_time = datetime.now(jst).strftime('%y/%m/%d/%H:%M')
        
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        for timeframe, data in currency_data.items():
            try:
                if 'currencies' not in data or len(data['currencies']) == 0:
                    continue
                
                currencies = data['currencies']
                weakest = currencies[0]['currency']  # 最初（最弱）
                strongest = currencies[-1]['currency']  # 最後（最強）
                weakest_percent = currencies[0]['percentage']  # 最弱の%
                strongest_percent = currencies[-1]['percentage']  # 最強の%
                
                # 前回の値と比較
                previous = previous_extreme_currencies.get(timeframe)
                
                if previous is None:
                    # 初回：初期状態をDBに記録（サーバー再起動時の履歴保持のため）
                    try:
                        c.execute('''INSERT INTO change_history 
                                     (timeframe, weakest, strongest, weakest_percent, strongest_percent, timestamp, created_at) 
                                     VALUES (?, ?, ?, ?, ?, ?, ?)''',
                                  (timeframe, weakest, strongest, weakest_percent, strongest_percent, current_time, datetime.now(jst).isoformat()))
                        conn.commit()
                        print(f'[CHANGE_HISTORY] Initial state recorded for {timeframe}: {weakest}{weakest_percent:+d}%⇔{strongest}{strongest_percent:+d}%')
                        
                    except Exception as e:
                        print(f'[ERROR] Failed to record initial state for {timeframe}: {e}')
                    
                    # メモリにも保存
                    previous_extreme_currencies[timeframe] = {
                        'weakest': weakest,
                        'strongest': strongest
                    }
                else:
                    # 変更があった場合のみ記録
                    if previous['weakest'] != weakest or previous['strongest'] != strongest:
                        # DBに記録
                        try:
                            c.execute('''INSERT INTO change_history 
                                         (timeframe, weakest, strongest, weakest_percent, strongest_percent, timestamp, created_at) 
                                         VALUES (?, ?, ?, ?, ?, ?, ?)''',
                                      (timeframe, weakest, strongest, weakest_percent, strongest_percent, current_time, datetime.now(jst).isoformat()))
                            conn.commit()
                            print(f'[CHANGE_HISTORY] Recorded change for {timeframe}: {weakest}{weakest_percent:+d}%⇔{strongest}{strongest_percent:+d}%')
                            
                            # 各時間足ごとに最大1000件を維持（古い履歴を削除）
                            c.execute('''SELECT id FROM change_history 
                                         WHERE timeframe = ? 
                                         ORDER BY created_at DESC 
                                         LIMIT -1 OFFSET 1000''', (timeframe,))
                            old_ids = [row[0] for row in c.fetchall()]
                            if old_ids:
                                placeholders = ','.join(['?'] * len(old_ids))
                                c.execute(f'DELETE FROM change_history WHERE id IN ({placeholders})', old_ids)
                                conn.commit()
                                print(f'[CHANGE_HISTORY] Deleted {len(old_ids)} old records for {timeframe}')
                            
                        except Exception as e:
                            print(f'[ERROR] Failed to record change history for {timeframe}: {e}')
                        
                        # グローバル変数を更新
                        previous_extreme_currencies[timeframe] = {
                            'weakest': weakest,
                            'strongest': strongest
                        }
            except Exception as tf_error:
                print(f'[ERROR] Error processing timeframe {timeframe}: {tf_error}')
                continue
        
        conn.close()
        
    except Exception as e:
        print(f'[CRITICAL ERROR] detect_and_record_extreme_changes failed: {e}')
        import traceback
        traceback.print_exc()
        try:
            with open(os.path.join(BASE_DIR, 'webhook_error.log'), 'a', encoding='utf-8') as f:
                f.write(f'{datetime.now(jst).isoformat()} - [CRITICAL] detect_and_record_extreme_changes: {e}\n')
                f.write(traceback.format_exc())
        except:
            pass

@app.route('/api/currency_strength', methods=['GET'])
def api_currency_strength():
    """通貨強弱を計算して返す（APIエンドポイント）"""
    try:
        data = calculate_currency_strength_data()
        return jsonify({
            'status': 'success',
            'data': data
        }), 200
        
    except Exception as e:
        print(f'[ERROR][api/currency_strength] {e}')
        traceback.print_exc()
        return jsonify({'status': 'error', 'msg': str(e)}), 500

@app.route('/api/change_history', methods=['GET'])
def api_change_history():
    """通貨強弱の最弱・最強変更履歴を取得（APIエンドポイント）"""
    try:
        timeframe = request.args.get('timeframe')  # optional
        limit = int(request.args.get('limit', 5))
        
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        # テーブルのカラムを確認
        c.execute("PRAGMA table_info(change_history)")
        columns = [col[1] for col in c.fetchall()]
        has_percent = 'weakest_percent' in columns and 'strongest_percent' in columns
        
        result = {}
        
        if timeframe:
            # 特定の時間足のみ取得
            if has_percent:
                c.execute('''SELECT timeframe, weakest, strongest, weakest_percent, strongest_percent, timestamp, created_at 
                             FROM change_history 
                             WHERE timeframe = ? 
                             ORDER BY created_at DESC 
                             LIMIT ?''', (timeframe, limit))
            else:
                c.execute('''SELECT timeframe, weakest, strongest, timestamp, created_at 
                             FROM change_history 
                             WHERE timeframe = ? 
                             ORDER BY created_at DESC 
                             LIMIT ?''', (timeframe, limit))
            
            rows = c.fetchall()
            result[timeframe] = [
                {
                    'timestamp': row[5] if has_percent else row[3],
                    'weakest': row[1],
                    'strongest': row[2],
                    'weakest_percent': row[3] if has_percent else 0,
                    'strongest_percent': row[4] if has_percent else 0,
                    'created_at': row[6] if has_percent else row[4]
                }
                for row in rows
            ]
        else:
            # 全ての時間足を取得
            timeframes = ['15m', '1H', '4H', 'D', 'Av']
            for tf in timeframes:
                if has_percent:
                    c.execute('''SELECT timeframe, weakest, strongest, weakest_percent, strongest_percent, timestamp, created_at 
                                 FROM change_history 
                                 WHERE timeframe = ? 
                                 ORDER BY created_at DESC 
                                 LIMIT ?''', (tf, limit))
                else:
                    c.execute('''SELECT timeframe, weakest, strongest, timestamp, created_at 
                                 FROM change_history 
                                 WHERE timeframe = ? 
                                 ORDER BY created_at DESC 
                                 LIMIT ?''', (tf, limit))
                
                rows = c.fetchall()
                result[tf] = [
                    {
                        'timestamp': row[5] if has_percent else row[3],
                        'weakest': row[1],
                        'strongest': row[2],
                        'weakest_percent': row[3] if has_percent else 0,
                        'strongest_percent': row[4] if has_percent else 0,
                        'created_at': row[6] if has_percent else row[4]
                    }
                    for row in rows
                ]
        
        conn.close()
        
        return jsonify({
            'status': 'success',
            'data': result
        }), 200
        
    except Exception as e:
        print(f'[ERROR][api/change_history] {e}')
        traceback.print_exc()
        return jsonify({'status': 'error', 'msg': str(e)}), 500

@app.route('/api/generate_notification_sound', methods=['POST'])
def generate_notification_sound():
    """
    VOICEVOX APIを使用して日本語音声を生成し、オプションで電子音を前に追加する
    リクエスト: {
      "voice_actress": "nanami" or "keita",
      "message": "通知メッセージテキスト",
      "electronic_sound": "buzzer" or "bell" or "notification" or null
    }
    レスポンス: 音声ファイルのBase64データまたはURL
    """
    try:
        data = request.json
        voice_actress = data.get('voice_actress', 'nanami')  # デフォルト: 七海
        message = data.get('message', '')
        electronic_sound = data.get('electronic_sound', None)
        
        if not message:
            return jsonify({'status': 'error', 'msg': 'メッセージが空です'}), 400
        
        # VOICEVOX Speaker IDのマッピング
        speaker_map = {
            'nanami': 1,    # 七海（女性）
            'keita': 2      # 圭太（男性）- 実際のIDは確認が必要
        }
        
        speaker_id = speaker_map.get(voice_actress, 1)
        
        # VOICEVOX APIエンドポイント
        voicevox_url = 'http://127.0.0.1:50021'  # ローカルVOICEVOX
        
        try:
            # 音声合成クエリを作成
            query_response = requests.post(
                f'{voicevox_url}/audio_query',
                params={'text': message, 'speaker': speaker_id},
                timeout=10
            )
            
            if query_response.status_code != 200:
                # VOICEVOX が起動していない場合は、サイレント モード
                print(f'[WARNING] VOICEVOX not available. Returning silent placeholder.')
                response, status_code = _generate_silent_audio()
                return response, status_code
            
            query_data = query_response.json()
            
            # 音声を合成
            synthesis_response = requests.post(
                f'{voicevox_url}/synthesis',
                params={'speaker': speaker_id},
                json=query_data,
                timeout=10
            )
            
            if synthesis_response.status_code != 200:
                print(f'[ERROR] VOICEVOX synthesis failed: {synthesis_response.status_code}')
                response, status_code = _generate_silent_audio()
                return response, status_code
            
            # 音声バイナリデータ
            audio_data = synthesis_response.content
            
            # 電子音がある場合は前に追加（将来実装）
            if electronic_sound:
                audio_data = _prepend_electronic_sound(electronic_sound, audio_data)
            
            # Base64エンコード
            audio_base64 = base64.b64encode(audio_data).decode('utf-8')
            
            # Data URLとして返す
            data_url = f'data:audio/wav;base64,{audio_base64}'
            print(f'[INFO] Notification sound generated: {len(audio_base64)} bytes (Base64)')
            return jsonify({'status': 'success', 'audio': data_url}), 200
            
        except requests.exceptions.ConnectionError:
            print(f'[WARNING] VOICEVOX connection failed. Returning silent audio.')
            response, status_code = _generate_silent_audio()
            return response, status_code
        
    except Exception as e:
        print(f'[ERROR][generate_notification_sound] {e}')
        traceback.print_exc()
        return jsonify({'status': 'error', 'msg': str(e)}), 500

def _generate_silent_audio():
    """
    無音のWAV ファイル（1秒間）を生成してBase64で返す
    """
    import io
    import wave
    
    # 無音WAVを生成（1秒間、16kHz、モノラル）
    sample_rate = 16000
    duration = 1
    num_samples = sample_rate * duration
    
    wav_buffer = io.BytesIO()
    with wave.open(wav_buffer, 'wb') as wav_file:
        wav_file.setnchannels(1)  # モノラル
        wav_file.setsampwidth(2)  # 16ビット
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(b'\x00\x00' * num_samples)
    
    audio_data = wav_buffer.getvalue()
    audio_base64 = base64.b64encode(audio_data).decode('utf-8')
    data_url = f'data:audio/wav;base64,{audio_base64}'
    
    print(f'[INFO] Silent audio generated: {len(audio_base64)} bytes (Base64)')
    return jsonify({'status': 'success', 'audio': data_url}), 200

def _prepend_electronic_sound(sound_type, audio_data):
    """
    電子音を音声の前に追加（将来実装）
    現在は音声データをそのまま返す
    """
    # TODO: 電子音合成実装
    return audio_data

@app.route('/timer_preview/<int:design_num>')

def timer_preview(design_num):
    """タイマーデザインプレビュー"""
    design_names = {
        1: 'デフォルト',
        2: 'デジタル時計風',
        3: 'モダン太字',
        4: 'シンプル細字',
        5: 'レトロ風',
        6: 'ネオンブルー',
        7: 'エレガント',
        8: 'シンプルボックス'
    }
    
    design_name = design_names.get(design_num, 'デザイン')
    
    response = make_response(render_template('timer_preview.html', 
                                             design_num=design_num,
                                             design_name=design_name))
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

def _normalize_row_order(row_order_list):
    """
    row_order の時間足を正規化
    数値コード（60, 15, 240, 5）を文字列表記（1H, 15m, 4H, 5m）に変換
    
    例: ['60', '15', '240', 'price', 'D'] → ['1H', '15m', '4H', 'price', 'D']
    """
    if not row_order_list:
        return []
    
    tf_map = {
        '5': '5m',
        '15': '15m',
        '60': '1H',
        '240': '4H',
        '1440': 'D',
        '10080': 'W',
        '43200': 'M',
    }
    
    normalized = []
    for item in row_order_list:
        normalized.append(tf_map.get(item, item))
    
    return normalized

@app.route('/webhook', methods=['POST', 'OPTIONS'])
def webhook():
    # OPTIONSリクエストに対応（CORS プリフライト）
    if request.method == 'OPTIONS':
        response = make_response('', 204)
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        response.headers['Access-Control-Max-Age'] = '3600'
        return response
    
    try:
        data = request.json
        if not data:
            error_msg = 'No JSON data received'
            print(f'[WEBHOOK ERROR] {error_msg}')
            with open(os.path.join(BASE_DIR, 'webhook_error.log'), 'a', encoding='utf-8') as f:
                f.write(f'{datetime.now(pytz.timezone("Asia/Tokyo")).isoformat()} - {error_msg}\n')
            response = jsonify({'status': 'error', 'msg': error_msg})
            response.headers['Access-Control-Allow-Origin'] = '*'
            return response, 400
        
        # FX休場時は更新を無視（データ受信ベースなので常に保存）
        # 受信したら営業中と判定するため、チェックを削除
        
        # row_order を正規化（数値コード → 文字列表記）
        if 'row_order' in data and isinstance(data['row_order'], list):
            data['row_order'] = _normalize_row_order(data['row_order'])
        
        # 受信タイムスタンプをログ（JST）
        jst = pytz.timezone('Asia/Tokyo')
        symbol_val = data.get("symbol", "UNKNOWN")
        tf_val = data.get("tf", "5")
        sent_time_val = data.get("sent_time", "")  # JSONの送信時間（例: "26/02/19/00:30"）

        # sent_time を received_at として使う（形式: YY/MM/DD/HH:MM）
        received_at = datetime.now(jst).isoformat()  # デフォルト: サーバー受信時刻
        if sent_time_val:
            try:
                # "26/02/19/00:30" -> 2026-02-19 00:30:00 JST
                parts = sent_time_val.split('/')
                if len(parts) == 4:
                    yy, mm, dd, hhmm = parts
                    hh, mn = hhmm.split(':')
                    sent_dt = jst.localize(datetime(2000 + int(yy), int(mm), int(dd), int(hh), int(mn), 0))
                    received_at = sent_dt.isoformat()
            except Exception as _e:
                print(f'[WARNING] Cannot parse sent_time "{sent_time_val}": {_e}')

        print(f'[WEBHOOK RECEIVED] sent_time={sent_time_val} received_at={received_at} - {symbol_val}/{tf_val}')
        
        # ログをファイルに保存
        try:
            log_entry = f'{received_at} - {symbol_val}/{tf_val} (Sent: {sent_time_val}) - {json.dumps(data, ensure_ascii=False)}\n'
            with open(os.path.join(BASE_DIR, 'webhook_log.txt'), 'a', encoding='utf-8') as f:
                f.write(log_entry)
            # 同時にエラーログにも記録（トラッキング用）
            with open(os.path.join(BASE_DIR, 'webhook_error.log'), 'a', encoding='utf-8') as f:
                f.write(f'{received_at} - OK: {symbol_val}/{tf_val} (Sent: {sent_time_val})\n')
        except Exception as e:
            error_msg = f'[LOG ERROR] Failed to write logs: {str(e)}'
            print(error_msg)
            with open(os.path.join(BASE_DIR, 'webhook_error.log'), 'a', encoding='utf-8') as f:
                f.write(f'{datetime.now(jst).isoformat()} - {error_msg}\n')
        
        # 設定から更新遅延時間を取得
        settings_path = os.path.join(BASE_DIR, 'settings.json')
        delay_seconds = 10.0  # デフォルト
        try:
            if os.path.exists(settings_path):
                with open(settings_path, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
                delay_seconds = float(settings.get('update_delay_seconds', 10.0))
        except Exception as e:
            print(f'[WARNING] Failed to load settings: {e}')
        
        # ============================================================
        # スコア計算を実行（DB保存前）
        # ============================================================
        with open(os.path.join(BASE_DIR, 'webhook_error.log'), 'a', encoding='utf-8') as f:
            f.write(f'{datetime.now(jst).isoformat()} - [DEBUG_TREND] Starting trend calculation for {symbol_val}/{tf_val}\n')
            f.flush()
        
        try:
            tf_for_calc = tf_val
            # tf を正規化（'5' -> '5m', '15' -> '15m', '60' -> '1H', '240' -> '4H'）
            tf_map_norm = {'5': '5m', '15': '15m', '60': '1H', '240': '4H', 'D': 'D', 'W': 'W', 'M': 'M', 'Y': 'Y'}
            tf_for_calc = tf_map_norm.get(tf_val, tf_val)
            
            with open(os.path.join(BASE_DIR, 'webhook_error.log'), 'a', encoding='utf-8') as f:
                f.write(f'{datetime.now(jst).isoformat()} - [DEBUG_TREND] tf_for_calc={tf_for_calc}\n')
                f.flush()
            
            # row_order を文字列に変換（calculate_trend_strength_v2 が string を期待）
            row_order_for_calc = data.get('row_order', [])
            if isinstance(row_order_for_calc, list):
                row_order_for_calc = ','.join(row_order_for_calc)
            
            # データコピーを作成して calculate_trend_strength_v2 に渡す
            calc_data = dict(data)
            calc_data['row_order'] = row_order_for_calc
            
            with open(os.path.join(BASE_DIR, 'webhook_error.log'), 'a', encoding='utf-8') as f:
                f.write(f'{datetime.now(jst).isoformat()} - [DEBUG_TREND] row_order_for_calc={row_order_for_calc}\n')
                f.flush()
            
            # スコア計算を実行
            trend_result = calculate_trend_strength_v2(tf_for_calc, calc_data, None)
            
            with open(os.path.join(BASE_DIR, 'webhook_error.log'), 'a', encoding='utf-8') as f:
                f.write(f'{datetime.now(jst).isoformat()} - [DEBUG_TREND] Calculation result: direction={trend_result.get("direction")}, score={trend_result.get("score")}\n')
                f.flush()
            
            # 計算結果を meta に追加
            meta = data.get('meta', {})
            if isinstance(meta, dict):
                meta['trend_direction'] = trend_result.get('direction', 'range')
                meta['trend_score'] = trend_result.get('score', 0)
                meta['trend_strength'] = trend_result.get('strength', 'レンジ')
                meta['trend_breakdown'] = trend_result.get('breakdown', {})
                data['meta'] = meta
                
                with open(os.path.join(BASE_DIR, 'webhook_error.log'), 'a', encoding='utf-8') as f:
                    f.write(f'{datetime.now(jst).isoformat()} - [DEBUG_TREND] Meta updated: {symbol_val}/{tf_val}\n')
                    f.flush()
            
        except Exception as e:
            error_msg = f"{type(e).__name__}: {str(e)}"
            tb_msg = traceback.format_exc()
            
            # log に記録
            with open(os.path.join(BASE_DIR, 'webhook_error.log'), 'a', encoding='utf-8') as f:
                f.write(f'{datetime.now(jst).isoformat()} - [DEBUG_TREND_ERROR] {symbol_val}/{tf_val}: {error_msg}\n')
                f.write(f'{tb_msg}\n')
                f.flush()
            
            # meta に exception 情報を入れる
            meta = data.get('meta', {})
            if isinstance(meta, dict):
                meta['trend_direction'] = 'range'
                meta['trend_score'] = 0
                meta['trend_strength'] = 'レンジ'
                meta['exception_msg'] = error_msg
                data['meta'] = meta
        
        # ---- tf値の正規化（旧形式→正規化形式）----
        tf_val_normalized = _normalize_tf(tf_val)
        if tf_val_normalized != tf_val:
            print(f'[WEBHOOK] tf normalized: {tf_val} -> {tf_val_normalized} for {symbol_val}')
            tf_val = tf_val_normalized

        # ---- シグナルペイロード拒否: sent_timeが空かつcloudsが空の場合はDBを更新しない ----
        # TradingViewのシグナルアラートはclouds=[] + sent_time="" で送信されるケースがある。
        # このような空ペイロードが正常データを上書きするのを防ぐ。
        incoming_clouds = data.get('clouds', [])
        if not sent_time_val and not incoming_clouds:
            print(f'[WEBHOOK SKIP] Signal payload (no sent_time, no clouds) for {symbol_val}/{tf_val} - DB not updated')
            response = jsonify({'status': 'skipped', 'reason': 'signal_payload_no_clouds_no_senttime'})
            response.headers['Access-Control-Allow-Origin'] = '*'
            return response, 200
        # ---- シグナルペイロード拒否ここまで ----
        
        # 遅延処理を削除して即時保存
        try:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()

            # --- sent_time 同士を比較して古いペイロードをスキップ ---
            # 既存レコードの sent_time と受信データの sent_time を比較。
            # 既存の sent_time が空（スタブ）の場合は常に受け入れる。
            # 受信データの sent_time が既存より古い場合のみスキップ。
            try:
                c.execute('SELECT sent_time FROM states WHERE symbol = ? AND tf = ? ORDER BY rowid DESC LIMIT 1', (symbol_val, tf_val))
                row = c.fetchone()
                existing_sent_time = row[0] if row and row[0] else ''
                if existing_sent_time and sent_time_val:
                    # sent_time 形式: YY/MM/DD/HH:MM → 文字列比較可能な形式に変換
                    def parse_sent_time(s):
                        try:
                            parts = s.split('/')
                            if len(parts) == 4:
                                yy, mm, dd, hhmm = parts
                                hh, mn = hhmm.split(':')
                                return jst.localize(datetime(2000+int(yy), int(mm), int(dd), int(hh), int(mn)))
                        except Exception:
                            pass
                        return None
                    existing_dt = parse_sent_time(existing_sent_time)
                    incoming_dt = parse_sent_time(sent_time_val)
                    if existing_dt and incoming_dt and incoming_dt < existing_dt:
                        print(f"[WEBHOOK SKIP] Older sent_time for {symbol_val}/{tf_val}: existing={existing_sent_time} incoming={sent_time_val}")
                        conn.close()
                        response = jsonify({'status': 'skipped', 'reason': 'older_sent_time'})
                        response.headers['Access-Control-Allow-Origin'] = '*'
                        return response, 200
            except Exception:
                pass
            # --- sent_time 比較ここまで ---

            received_timestamp = datetime.now(jst).isoformat()  # 最終更新（サーバー受信時刻）
            # received_at は sent_time ベース（上で解析済み）
            c.execute('''INSERT OR REPLACE INTO states (
                        symbol, tf, timestamp, price, time,
                        state_flag, state_word,
                        daytrade_status, daytrade_bos, daytrade_time,
                        swing_status, swing_bos, swing_time,
                        row_order, cloud_order, clouds_json, meta_json, received_at, sent_time
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    (symbol_val, tf_val,
                     received_timestamp, float(data.get('price', 0)),
                     data.get('time', 0),
                     data.get('state', {}).get('flag', ''),
                     data.get('state', {}).get('word', ''),
                     data.get('daytrade', {}).get('status', ''),
                     data.get('daytrade', {}).get('bos', ''),
                     data.get('daytrade', {}).get('time', ''),
                     data.get('swing', {}).get('status', ''),
                     data.get('swing', {}).get('bos', ''),
                     data.get('swing', {}).get('time', ''),
                     ','.join(data.get('row_order', [])),
                     ','.join(data.get('cloud_order', [])),
                     json.dumps(data.get('clouds', []), ensure_ascii=False),
                     json.dumps(data.get('meta', {}), ensure_ascii=False),
                     received_at,      # ← sent_time ベース
                     sent_time_val))
            conn.commit()
            # WALモード有効時の即時書き込み確保
            try:
                c.execute('PRAGMA optimize')
            except:
                pass
            conn.close()
            
            # 【重要】ファイルレベルの同期（Renderで再起動時のデータ損失防止）
            try:
                fd = os.open(DB_PATH, os.O_RDONLY)
                os.fsync(fd)
                os.close(fd)
                print(f'[DB_SYNC] [OK] Forced disk sync for {symbol_val}/{tf_val}')
            except Exception as e:
                print(f'[DB_SYNC] ⚠ Sync failed: {e}')
            
            saved_at = datetime.now(jst).isoformat()
            print(f'[OK] Saved immediately: {symbol_val}/{tf_val} at {saved_at}')
            
            # 動的バックアップへの保存は廃止（DBがPersistent Diskに永続化されるため不要）
            # if tf_val in ['D', '240', '60']:
            #     save_dynamic_backup(symbol_val, tf_val, data)  # DISABLED
            
            with open(os.path.join(BASE_DIR, 'webhook_error.log'), 'a', encoding='utf-8') as f:
                f.write(f'{saved_at} - [CHECKPOINT 1] Before trend calculation block\n')
                f.flush()
            
            # トレンド強度計算v2（パターン検出含む）を実行
            try:
                with open(os.path.join(BASE_DIR, 'webhook_error.log'), 'a', encoding='utf-8') as f:
                    f.write(f'{saved_at} - [TREND_CALC] Calculating trend for {symbol_val}/{tf_val}...\n')
                    f.flush()
                print(f'[TREND_CALC] Calculating trend for {symbol_val}/{tf_val}...')
                # tf_valを正規化
                tf_normalized = tf_val
                if tf_val == '5':
                    tf_normalized = '5m'
                elif tf_val == '15':
                    tf_normalized = '15m'
                elif tf_val in ('1', '60'):
                    tf_normalized = '1H'
                elif tf_val in ('4', '240'):
                    tf_normalized = '4H'
                
                # DBから同じ通貨ペアの全タイムフレームデータを取得
                conn_trend = sqlite3.connect(DB_PATH)
                c_trend = conn_trend.cursor()
                c_trend.execute('SELECT * FROM states WHERE symbol = ?', (symbol_val,))
                rows = c_trend.fetchall()
                cols = [d[0] for d in c_trend.description] if c_trend.description else []
                conn_trend.close()
                
                # all_states構築: {tf_normalized: {clouds: [...]}, ...}
                all_states = {}
                for row in rows:
                    row_dict = dict(zip(cols, row))
                    row_tf = row_dict.get('tf', '')
                    # tfを正規化
                    row_tf_norm = row_tf
                    if row_tf == '5':
                        row_tf_norm = '5m'
                    elif row_tf == '15':
                        row_tf_norm = '15m'
                    elif row_tf in ('1', '60'):
                        row_tf_norm = '1H'
                    elif row_tf in ('4', '240'):
                        row_tf_norm = '4H'
                    
                    clouds_json = row_dict.get('clouds_json', '[]')
                    row_order = row_dict.get('row_order', '')
                    try:
                        clouds = json.loads(clouds_json)
                        all_states[row_tf_norm] = {
                            'clouds': clouds,
                            'clouds_json': clouds_json,
                            'row_order': row_order
                        }
                    except:
                        pass
                
                # state_dataは現在のタイムフレームデータ
                state_data = all_states.get(tf_normalized, {
                    'clouds': data.get('clouds', []),
                    'row_order': data.get('row_order', '')
                })
                
                # トレンド強度計算v2を実行
                trend_result = calculate_trend_strength_v2(tf_normalized, state_data, all_states)
                result_msg = f'[TREND_CALC] {symbol_val}/{tf_normalized}: {trend_result["strength"]} ({trend_result["score"]}点)'
                print(result_msg)
                # 詳細情報も出力
                if trend_result.get('details'):
                    print(f'[TREND_DETAILS] {symbol_val}/{tf_normalized}: {trend_result["details"]}')
                with open(os.path.join(BASE_DIR, 'webhook_error.log'), 'a', encoding='utf-8') as f:
                    f.write(f'{saved_at} - {result_msg}\n')
                    if trend_result.get('details'):
                        f.write(f'{saved_at} - [TREND_DETAILS] {json.dumps(trend_result["details"], ensure_ascii=False)}\n')
                    f.flush()
                
                # トレンド計算結果をデータベースに保存
                try:
                    conn_trend = sqlite3.connect(DB_PATH)
                    c_trend = conn_trend.cursor()
                    c_trend.execute('''UPDATE states SET 
                        trend_direction = ?,
                        trend_score = ?,
                        trend_percentage = ?,
                        trend_strength = ?,
                        trend_breakdown_json = ?
                        WHERE symbol = ? AND tf = ?''',
                        (trend_result.get('direction', 'range'),
                         trend_result.get('score', 0),
                         int((trend_result.get('score', 0) / 100.0) * 100),
                         trend_result.get('strength', ''),
                         json.dumps(trend_result.get('breakdown', {}), ensure_ascii=False),
                         symbol_val,
                         tf_val))
                    conn_trend.commit()
                    conn_trend.close()
                    print(f'[OK] Trend results saved to DB: {symbol_val}/{tf_val}')
                except Exception as db_err:
                    print(f'[WARNING] Failed to save trend results to DB: {db_err}')
                    
            except Exception as trend_err:
                error_msg = f'[ERROR] Trend calculation failed: {trend_err}'
                print(error_msg)
                with open(os.path.join(BASE_DIR, 'webhook_error.log'), 'a', encoding='utf-8') as f:
                    f.write(f'{saved_at} - {error_msg}\n')
                    f.flush()
                import traceback
                traceback.print_exc()
            
            # トレンド計算完了マーカー
            with open(os.path.join(BASE_DIR, 'webhook_error.log'), 'a', encoding='utf-8') as f:
                f.write(f'{saved_at} - [TREND_CALC_BLOCK] Trend calculation block completed\n')
                f.flush()
            
            # 全てのタイムフレーム（5, 15, 60, 240）でルール評価と発火を実行
            try:
                print(f'[DEBUG] RULE_EVAL_START for {symbol_val}/{tf_val}')
                with open(os.path.join(BASE_DIR, 'webhook_error.log'), 'a', encoding='utf-8') as f:
                    f.write(f'{saved_at} - RULE_EVAL_START for {symbol_val}/{tf_val}\n')
                    f.flush()
                evaluate_and_fire_rules(data, symbol_val, tf_val)
                print(f'[DEBUG] RULE_EVAL_END for {symbol_val}/{tf_val}')
                with open(os.path.join(BASE_DIR, 'webhook_error.log'), 'a', encoding='utf-8') as f:
                    f.write(f'{saved_at} - RULE_EVAL_END for {symbol_val}/{tf_val}\n')
                    f.flush()
            except Exception as e:
                print(f'[ERROR] Rule evaluation failed: {str(e)}')
                with open(os.path.join(BASE_DIR, 'webhook_error.log'), 'a', encoding='utf-8') as f:
                    f.write(f'{saved_at} - RULE ERROR for {symbol_val}/{tf_val}: {str(e)}\n')
                    import traceback
                    f.write(traceback.format_exc())
                    f.flush()
            
            print(f'[DEBUG] After rule evaluation, before emit for {symbol_val}/{tf_val}')
            
            # Socket.IOで即時更新通知（全クライアントに配信）
            print(f'[DEBUG] About to emit update_table for {symbol_val}/{tf_val}')
            socketio.emit('update_table', {'message': 'New data received', 'symbol': symbol_val, 'tf': tf_val})
            print(f'[DEBUG] update_table emitted successfully for {symbol_val}/{tf_val}')
            
            # 通貨強弱データを計算してemit
            try:
                currency_data = calculate_currency_strength_data()
                
                # 変更を検出してDBに記録（エラーが発生してもWebhook処理を継続）
                try:
                    detect_and_record_extreme_changes(currency_data)
                except Exception as history_error:
                    print(f'[ERROR] Change history recording failed (continuing): {history_error}')
                    import traceback
                    traceback.print_exc()
                    with open(os.path.join(BASE_DIR, 'webhook_error.log'), 'a', encoding='utf-8') as f:
                        f.write(f'{datetime.now(jst).isoformat()} - [HISTORY_ERROR] {history_error}\n')
                        f.write(traceback.format_exc())
                
                socketio.emit('currency_strength_update', {
                    'status': 'success',
                    'data': currency_data,
                    'timestamp': datetime.now(jst).isoformat()
                })
                print(f'[CURRENCY_STRENGTH] Emitted update via SocketIO')
            except Exception as e:
                print(f'[ERROR] Failed to emit currency strength: {e}')
                import traceback
                traceback.print_exc()
            
            # 市場ステータス更新通知
            market_open = is_fx_market_open()
            socketio.emit('market_status_update', {'market_open': market_open})
            
            # 最後の受信時刻を更新
            try:
                conn_time = sqlite3.connect(DB_PATH)
                c_time = conn_time.cursor()
                c_time.execute('UPDATE market_status SET last_receive_time = ? WHERE id = 1', 
                              (datetime.now(pytz.UTC).isoformat(),))
                conn_time.commit()
                conn_time.close()
                print(f'[OK] Updated last receive time')
            except Exception as e:
                print(f'[ERROR] Updating last receive time: {e}')
        except Exception as e:
            error_msg = f'Database save failed: {str(e)}'
            print(f'[ERROR] {error_msg}')
            with open(os.path.join(BASE_DIR, 'webhook_error.log'), 'a', encoding='utf-8') as f:
                f.write(f'{datetime.now(jst).isoformat()} - SAVE ERROR for {symbol_val}/{tf_val}: {str(e)}\n')
            response = jsonify({'status': 'error', 'msg': error_msg})
            response.headers['Access-Control-Allow-Origin'] = '*'
            return response, 500
        
        response = jsonify({'status': 'success'})
        response.headers['Access-Control-Allow-Origin'] = '*'
        return response, 200
    except Exception as e:
        error_msg = f'Webhook handler exception: {str(e)}'
        print(f'[ERROR] {error_msg}')
        jst = pytz.timezone('Asia/Tokyo')
        try:
            with open(os.path.join(BASE_DIR, 'webhook_error.log'), 'a', encoding='utf-8') as f:
                f.write(f'{datetime.now(jst).isoformat()} - {error_msg}\n')
        except:
            pass
        response = jsonify({'status': 'error', 'msg': error_msg})
        response.headers['Access-Control-Allow-Origin'] = '*'
        return response, 500

@app.route('/health', methods=['GET'])
def health_check():
    """ヘルスチェックエンドポイント（サーバーが起動しているか確認）"""
    try:
        jst = pytz.timezone('Asia/Tokyo')
        
        # データベース接続テスト
        try:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute('SELECT COUNT(*) FROM states')
            states_count = c.fetchone()[0]
            conn.close()
            db_ok = True
        except Exception as e:
            db_ok = False
            states_count = None
        
        # webhook_log.txt 確認
        webhook_log_exists = os.path.exists(os.path.join(BASE_DIR, 'webhook_log.txt'))
        
        return jsonify({
            'status': 'healthy',
            'server_time': datetime.now(jst).isoformat(),
            'database_ok': db_ok,
            'states_count': states_count,
            'webhook_log_exists': webhook_log_exists,
            'uptime_message': 'Server is running normally',
            'code_version': 'signal-payload-guard-v1'
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e)
        }), 500

@app.route('/current_states')
def current_states():
    print('[ACCESS] Current states request')
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        # 通貨ペアの表示順序を取得
        c.execute('SELECT symbol FROM currency_order ORDER BY sort_order ASC')
        ordered_symbols = [row[0] for row in c.fetchall()]
        
        c.execute('SELECT * FROM states')
        rows, cols = c.fetchall(), [d[0] for d in c.description]
        conn.close()
        
        print(f'[INFO] Found {len(rows)} states in DB')
        
        # デバッグ: GBPJPYのtfを表示
        gbpjpy_tfs = [dict(zip(cols, r)).get('tf') for r in rows if dict(zip(cols, r)).get('symbol') == 'GBPJPY']
        print(f'[DEBUG] GBPJPY timeframes in DB: {gbpjpy_tfs}')
        
        # まず全データを辞書化し、シンボルごとにグループ化
        all_data = []
        for r in rows:
            d = dict(zip(cols, r))
            d['clouds'] = json.loads(d.get('clouds_json', '[]'))
            d['meta'] = json.loads(d.get('meta_json', '{}'))
            all_data.append(d)
        
        # シンボルごとにall_statesを構築
        symbol_groups = {}
        for d in all_data:
            symbol = d.get('symbol')
            if symbol not in symbol_groups:
                symbol_groups[symbol] = {}
            tf = d.get('tf')
            # tf を正規化（'5' -> '5m', '15' -> '15m', '1'/'60' -> '1H', '4'/'240' -> '4H'）
            if tf in ('5', '15', '1', '60', '4', '240'):
                if tf == '5':
                    tf_normalized = '5m'
                elif tf == '15':
                    tf_normalized = '15m'
                elif tf in ('1', '60'):
                    tf_normalized = '1H'
                elif tf in ('4', '240'):
                    tf_normalized = '4H'
                else:
                    tf_normalized = tf
            else:
                tf_normalized = tf
            symbol_groups[symbol][tf_normalized] = {
                'clouds': d['clouds'],
                'clouds_json': d.get('clouds_json', '[]'),
                'row_order': d.get('row_order', ''),
                'time': d.get('time')
            }
        
        states = []
        for r in rows:
            d = dict(zip(cols, r))
            d['clouds'] = json.loads(d.get('clouds_json', '[]'))
            d['meta'] = json.loads(d.get('meta_json', '{}'))
            d['row_order'] = d.get('row_order', '').split(',') if d.get('row_order') else []
            d['cloud_order'] = d.get('cloud_order', '').split(',') if d.get('cloud_order') else []
            d['state'] = {'flag': d.get('state_flag', ''), 'word': d.get('state_word', '')}
            d['daytrade'] = {'status': d.get('daytrade_status', ''), 'bos': d.get('daytrade_bos', ''), 'time': d.get('daytrade_time', '')}
            d['swing'] = {'status': d.get('swing_status', ''), 'bos': d.get('swing_bos', ''), 'time': d.get('swing_time', '')}
            clouds_count = len(d['clouds']) if d['clouds'] else 0
            
            # ★ トレンド強度を計算（v2ロジック）
            symbol = d.get('symbol')
            tf = d.get('tf')
            # tf を正規化（'5' -> '5m', '15' -> '15m', '1'/'60' -> '1H', '4'/'240' -> '4H'）
            if tf in ('5', '15', '1', '60', '4', '240'):
                if tf == '5':
                    tf_normalized = '5m'
                elif tf == '15':
                    tf_normalized = '15m'
                elif tf in ('1', '60'):
                    tf_normalized = '1H'
                elif tf in ('4', '240'):
                    tf_normalized = '4H'
                else:
                    tf_normalized = tf
            else:
                tf_normalized = tf
            
            # ★ 返すデータに正規化済み tf も含める（HTMLでのマッチング用）
            d['tf_normalized'] = tf_normalized
            
            all_states = symbol_groups.get(symbol, {})
            state_data = all_states.get(tf_normalized, {
                'clouds': d['clouds'],
                'row_order': d.get('row_order', '')
            })
            
            try:
                # まずDBから保存済みトレンド値を読み込む
                db_trend_direction = d.get('trend_direction')
                db_trend_score = d.get('trend_score')
                db_trend_percentage = d.get('trend_percentage')
                
                # DBに値がある場合はそれを使用（再計算を避ける）
                if db_trend_direction and db_trend_score is not None:
                    d['trend_direction'] = db_trend_direction
                    d['trend_score'] = db_trend_score
                    d['trend_percentage'] = db_trend_percentage
                    d['trend_strength'] = d.get('trend_strength', '')
                    d['trend_breakdown'] = json.loads(d.get('trend_breakdown_json', '{}')) if d.get('trend_breakdown_json') else {}
                    print(f'[TREND] {symbol}/{tf}(→{tf_normalized}): Loaded from DB - score={db_trend_score}, direction={db_trend_direction}')
                else:
                    # DBに値がない場合は計算して保存
                    trend_result = calculate_trend_strength_v2(tf_normalized, state_data, all_states)
                    d['trend_strength'] = trend_result['strength']  # 横/弱/中/強/極
                    d['trend_score'] = trend_result['score']  # 0-100点
                    d['trend_direction'] = trend_result['direction']  # 'up', 'down', 'range'
                    d['trend_percentage'] = int((trend_result['score'] / 100.0) * 100)  # パーセント表示（0-100%）
                    d['trend_breakdown'] = trend_result.get('breakdown', {})  # 詳細内訳
                    print(f'[TREND] {symbol}/{tf}(→{tf_normalized}): Calculated - {trend_result["strength"]} ({trend_result["score"]}点) {trend_result["direction"]}')
                    
                    # 計算結果をDBに保存
                    try:
                        conn_save = sqlite3.connect(DB_PATH)
                        c_save = conn_save.cursor()
                        c_save.execute('''UPDATE states SET 
                            trend_direction = ?,
                            trend_score = ?,
                            trend_percentage = ?,
                            trend_strength = ?,
                            trend_breakdown_json = ?
                            WHERE symbol = ? AND tf = ?''',
                            (d['trend_direction'],
                             d['trend_score'],
                             d['trend_percentage'],
                             d['trend_strength'],
                             json.dumps(d['trend_breakdown'], ensure_ascii=False),
                             symbol,
                             tf))
                        conn_save.commit()
                        conn_save.close()
                    except Exception as save_err:
                        print(f'[WARNING] Failed to save trend to DB: {save_err}')
            except Exception as trend_err:
                print(f'[ERROR] Trend calculation failed for {symbol}/{tf}: {trend_err}')
                import traceback
                traceback.print_exc()
                d['trend_score'] = 0
                d['trend_percentage'] = 0
                d['trend_breakdown'] = {}
            
            print(f'[INFO] State: {d.get("symbol")}/{d.get("tf")} (clouds={clouds_count})')
            states.append(d)
        
        # 通貨ペアの表示順序に従ってソート
        if ordered_symbols:
            states.sort(key=lambda x: (ordered_symbols.index(x['symbol']) 
                                      if x['symbol'] in ordered_symbols 
                                      else len(ordered_symbols)))
        
        # レスポンス前にログ出力（最初の3つの state で trend 値を確認）
        for i, s in enumerate(states[:3]):
            print(f'[RESPONSE] State {i}: {s.get("symbol")}/{s.get("tf")} trend_direction={s.get("trend_direction")}, trend_score={s.get("trend_score")}')
        
        response = jsonify({'status': 'success', 'states': states})
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response, 200
    except Exception as e:
        print(f'[ERROR] {e}')
        import traceback
        traceback.print_exc()
        return jsonify({'status': 'error', 'msg': str(e)}), 500


@app.route('/download_db')
def download_db():
    """データベースファイルをダウンロードするエンドポイント"""
    print('[ACCESS] Database download request')
    try:
        if not os.path.exists(DB_PATH):
            return jsonify({'status': 'error', 'msg': 'Database file not found'}), 404
        
        # データベースファイルのサイズを確認
        db_size_mb = os.path.getsize(DB_PATH) / (1024 * 1024)
        print(f'[DOWNLOAD] Database size: {db_size_mb:.2f} MB')
        
        # データベースファイルを送信
        directory = os.path.dirname(DB_PATH)
        filename = os.path.basename(DB_PATH)
        
        response = send_from_directory(directory, filename, as_attachment=True)
        print(f'[DOWNLOAD] Sending database file: {filename}')
        
        return response
    except Exception as e:
        print(f'[ERROR] Database download failed: {e}')
        import traceback
        traceback.print_exc()
        return jsonify({'status': 'error', 'msg': str(e)}), 500


@app.route('/api/cleanup_old_tf_formats', methods=['POST'])
def cleanup_old_tf_formats():
    """古い時間足フォーマット（5m, 15m, 4H, 15M, 1H）をDBから削除するエンドポイント"""
    print('[CLEANUP] Database cleanup request')
    try:
        if not os.path.exists(DB_PATH):
            return jsonify({'status': 'error', 'msg': 'Database file not found'}), 404
        
        jst = pytz.timezone('Asia/Tokyo')
        
        # バックアップを作成
        backup_path = os.path.join(
            os.path.dirname(DB_PATH), 
            f'webhook_data_backup_cleanup_{datetime.now(jst).strftime("%Y%m%d_%H%M%S")}.db'
        )
        try:
            shutil.copy(DB_PATH, backup_path)
            print(f'[CLEANUP] Backup created: {backup_path}')
        except Exception as e:
            print(f'[CLEANUP ERROR] Backup creation failed: {e}')
            return jsonify({'status': 'error', 'msg': f'Backup creation failed: {str(e)}'}), 500
        
        # DB接続
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        # 削除対象の古い形式
        old_tf_formats = ['5m', '15m', '4H', '15M', '1H']
        
        # 削除対象のレコード数を確認
        tf_list = ','.join([f"'{tf}'" for tf in old_tf_formats])
        c.execute(f"SELECT symbol, tf, COUNT(*) as cnt FROM states WHERE tf IN ({tf_list}) GROUP BY symbol, tf ORDER BY symbol, tf")
        rows = c.fetchall()
        
        delete_details = {}
        total_delete = 0
        for row in rows:
            symbol, tf, count = row
            if tf not in delete_details:
                delete_details[tf] = []
            delete_details[tf].append({'symbol': symbol, 'count': count})
            total_delete += count
        
        if total_delete == 0:
            print('[CLEANUP] No old tf format records found')
            conn.close()
            return jsonify({
                'status': 'success',
                'deleted_count': 0,
                'message': 'No old tf format records found',
                'backup_path': backup_path
            }), 200
        
        # 削除実行
        print(f'[CLEANUP] Deleting {total_delete} old tf format records')
        for tf in old_tf_formats:
            c.execute(f"DELETE FROM states WHERE tf = ?", (tf,))
            affected = c.rowcount
            if affected > 0:
                print(f'[CLEANUP] tf={tf}: {affected} records deleted')
        
        conn.commit()
        conn.close()

        # dynamic_backup.json も同時クリーンアップ
        dynamic_backup_path = os.path.join(BASE_DIR, 'dynamic_backup.json')
        backup_json_cleaned = 0
        if os.path.exists(dynamic_backup_path):
            try:
                with open(dynamic_backup_path, 'r', encoding='utf-8') as f:
                    dyn_data = json.load(f)
                clean_dyn = {}
                for key, item in dyn_data.items():
                    tf_raw = item.get('tf', '')
                    tf_norm = _normalize_tf(tf_raw)
                    if tf_norm in old_tf_formats:
                        backup_json_cleaned += 1
                        print(f'[CLEANUP] dynamic_backup: removed key={key} (tf={tf_raw})')
                        continue
                    # キーも正規化形式に統一
                    sym = item.get('symbol', '')
                    item['tf'] = tf_norm
                    clean_dyn[f'{sym}_{tf_norm}'] = item
                with open(dynamic_backup_path, 'w', encoding='utf-8') as f:
                    json.dump(clean_dyn, f, ensure_ascii=False, indent=2)
                print(f'[CLEANUP] dynamic_backup.json: {backup_json_cleaned} old entries removed, {len(clean_dyn)} entries kept')
            except Exception as e:
                print(f'[CLEANUP] Warning: dynamic_backup.json cleanup failed: {e}')
        
        print(f'[CLEANUP] Cleanup completed successfully')
        return jsonify({
            'status': 'success',
            'deleted_count': total_delete,
            'details': delete_details,
            'message': f'Successfully deleted {total_delete} old tf format records (dynamic_backup: {backup_json_cleaned} removed)',
            'backup_path': backup_path
        }), 200
        
    except Exception as e:
        print(f'[CLEANUP ERROR] {e}')
        import traceback
        traceback.print_exc()
        return jsonify({'status': 'error', 'msg': str(e)}), 500


@app.route('/api/rules/export', methods=['GET'])
def api_rules_export():
    """全ルールをJSONとして返す（ダウンロード用）"""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('SELECT id, name, enabled, scope_json, rule_json, created_at, updated_at, sort_order FROM rules ORDER BY sort_order ASC, created_at ASC')
        rows = c.fetchall()
        conn.close()
        rules_list = []
        for r in rows:
            rule_data = json.loads(r[4]) if r[4] else {}
            obj = {
                'id': r[0], 'name': r[1], 'enabled': bool(r[2]),
                'scope': json.loads(r[3]) if r[3] else None,
                'created_at': r[5], 'updated_at': r[6], 'sort_order': r[7]
            }
            obj.update(rule_data)
            rules_list.append(obj)
        jst = pytz.timezone('Asia/Tokyo')
        export_data = {
            'exported_at': datetime.now(jst).isoformat(),
            'count': len(rules_list),
            'rules': rules_list
        }
        resp = make_response(json.dumps(export_data, ensure_ascii=False, indent=2))
        resp.headers['Content-Type'] = 'application/json; charset=utf-8'
        resp.headers['Content-Disposition'] = f'attachment; filename="rules_backup_{datetime.now(jst).strftime("%Y%m%d_%H%M%S")}.json"'
        return resp
    except Exception as e:
        return jsonify({'status': 'error', 'msg': str(e)}), 500


@app.route('/api/rules/import', methods=['POST'])
def api_rules_import():
    """ルールをJSONからインポート（既存ルールは merge or replace）"""
    try:
        payload = request.json or {}
        mode = payload.get('mode', 'merge')   # 'merge'=既存優先 / 'replace'=全置換
        rules_list = payload.get('rules', [])
        if not rules_list:
            return jsonify({'status': 'error', 'msg': 'rules が空です'}), 400

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        jst = pytz.timezone('Asia/Tokyo')
        now = datetime.now(jst).isoformat()

        if mode == 'replace':
            c.execute('DELETE FROM rules')

        imported = 0; skipped = 0
        for rule in rules_list:
            rid = rule.get('id')
            if not rid:
                continue
            if mode == 'merge':
                c.execute('SELECT id FROM rules WHERE id=?', (rid,))
                if c.fetchone():
                    skipped += 1
                    continue
            rule_data = {
                'voice': rule.get('voice', {}),
                'cloudAlign': rule.get('cloudAlign', {}),
                'conditions': rule.get('conditions', [])
            }
            c.execute('INSERT OR REPLACE INTO rules (id,name,enabled,scope_json,rule_json,created_at,updated_at,sort_order) VALUES (?,?,?,?,?,?,?,?)',
                (
                    rid, rule.get('name','unnamed'),
                    1 if rule.get('enabled', True) else 0,
                    json.dumps(rule.get('scope', {}), ensure_ascii=False),
                    json.dumps(rule_data, ensure_ascii=False),
                    rule.get('created_at', now), rule.get('updated_at', now),
                    rule.get('sort_order', 9999)
                ))
            imported += 1

        conn.commit()
        conn.close()
        return jsonify({'status': 'success', 'imported': imported, 'skipped': skipped}), 200
    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({'status': 'error', 'msg': str(e)}), 500


@app.route('/rules', methods=['GET', 'POST'])
def rules():
    try:
        if request.method == 'GET':
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            # sort_orderでソート（小さい順）
            c.execute('SELECT id, name, enabled, scope_json, rule_json, created_at, updated_at, sort_order FROM rules ORDER BY sort_order ASC, created_at ASC')
            rows = c.fetchall()
            conn.close()
            res = []
            for r in rows:
                # rule_jsonの中身をフラットに展開
                rule_data = json.loads(r[4]) if r[4] else {}
                rule_obj = {
                    'id': r[0], 'name': r[1], 'enabled': bool(r[2]),
                    'scope': json.loads(r[3]) if r[3] else None,
                    'created_at': r[5],
                    'updated_at': r[6] if len(r) > 6 else r[5],
                    'sort_order': r[7] if len(r) > 7 else 0
                }
                # rule_dataの中身をマージ（voice, cloudAlign, conditions等）
                rule_obj.update(rule_data)
                res.append(rule_obj)
            return jsonify({'status': 'success', 'rules': res}), 200

        # POST: 保存（新規/更新）
        payload = request.json
        if not payload:
            return jsonify({'status': 'error', 'msg': 'no json payload'}), 400
        
        # Debug: log the incoming payload for voice settings
        print(f'[DEBUG] Received payload: {json.dumps(payload, ensure_ascii=False, indent=2)}')
        
        # voice, cloudAlign, conditions等をrule_jsonにまとめる
        rule_data = {
            'voice': payload.get('voice', {}),
            'cloudAlign': payload.get('cloudAlign', {}),
            'conditions': payload.get('conditions', [])
        }
        
        # server-side validation: ensure alignment settings (if present) are sane
        rule_obj = payload.get('rule') or rule_data
        align = rule_obj.get('alignment')
        if align:
            try:
                tfs = align.get('tfs') or []
                if not isinstance(tfs, list) or any(not isinstance(x, str) for x in tfs):
                    return jsonify({'status':'error','msg':'alignment.tfs must be list of TF strings'}), 400
                if len(tfs) < 2:
                    return jsonify({'status':'error','msg':'alignment requires at least 2 TFs to be selected'}), 400
                
                # n may come as string or number; if missing, default to len(tfs)
                n_raw = align.get('n')
                if n_raw is None:
                    n_val = len(tfs)  # Default: require ALL TFs to match
                else:
                    try:
                        n_val = int(n_raw)
                    except Exception:
                        return jsonify({'status':'error','msg':'alignment.n must be an integer'}), 400
                
                if n_val < 2:
                    return jsonify({'status':'error','msg':'alignment.n must be >= 2'}), 400
                if n_val > len(tfs):
                    return jsonify({'status':'error','msg':'alignment.n cannot be greater than number of selected TFs'}), 400
                missing_mode = align.get('missing')
                if missing_mode not in ('ignore','fail'):
                    return jsonify({'status':'error','msg':'alignment.missing must be "ignore" or "fail"'}), 400
                
                # Ensure n is set in the alignment object for consistency
                if n_raw is None:
                    align['n'] = n_val
            except Exception as e:
                return jsonify({'status':'error','msg': 'alignment validation error: ' + str(e)}), 400

        rid = payload.get('id') or payload.get('name') or str(datetime.now().timestamp())
        name = payload.get('name', 'unnamed')
        enabled = 1 if payload.get('enabled', True) else 0
        scope_json = json.dumps(payload.get('scope', {}), ensure_ascii=False)
        # rule_dataを使用してvoice, cloudAlign, conditionsを保存
        rule_json = json.dumps(rule_data, ensure_ascii=False)
        updated_at = datetime.now().isoformat()

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        # Check if rule exists to preserve created_at and sort_order
        c.execute('SELECT created_at, sort_order FROM rules WHERE id = ?', (rid,))
        existing = c.fetchone()
        created_at = existing[0] if existing else updated_at
        sort_order = existing[1] if existing else 9999  # 新規ルールは最後に追加
        
        c.execute('INSERT OR REPLACE INTO rules (id, name, enabled, scope_json, rule_json, created_at, updated_at, sort_order) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                  (rid, name, enabled, scope_json, rule_json, created_at, updated_at, sort_order))
        conn.commit()
        conn.close()
        # ルール変更をJSONバックアップに保存（デプロイ後の自動復元に使用）
        threading.Thread(target=_save_rules_backup, daemon=True).start()
        return jsonify({'status': 'success', 'id': rid}), 200
    except Exception as e:
        print(f'[ERROR][rules] {e}')
        return jsonify({'status': 'error', 'msg': str(e)}), 500


@app.route('/rules/reorder', methods=['POST'])
def reorder_rules():
    """ルールの並び順を更新"""
    try:
        payload = request.json
        if not payload or 'order' not in payload:
            return jsonify({'status': 'error', 'msg': 'order array required'}), 400
        
        order = payload['order']  # [rule_id1, rule_id2, ...] の配列
        
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        for idx, rule_id in enumerate(order):
            c.execute('UPDATE rules SET sort_order = ? WHERE id = ?', (idx, rule_id))
        
        conn.commit()
        conn.close()
        threading.Thread(target=_save_rules_backup, daemon=True).start()
        return jsonify({'status': 'success'}), 200
    except Exception as e:
        print(f'[ERROR][reorder_rules] {e}')
        return jsonify({'status': 'error', 'msg': str(e)}), 500


@app.route('/rules/<rule_id>', methods=['DELETE'])
def delete_rule(rule_id):
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('DELETE FROM rules WHERE id = ?', (rule_id,))
        conn.commit()
        conn.close()
        threading.Thread(target=_save_rules_backup, daemon=True).start()
        return jsonify({'status': 'success', 'deleted': rule_id}), 200
    except Exception as e:
        print(f'[ERROR][delete_rule] {e}')
        return jsonify({'status': 'error', 'msg': str(e)}), 500


@app.route('/rules/<rule_id>/toggle', methods=['POST'])
def toggle_rule(rule_id):
    """ルールの有効/無効を切り替え"""
    try:
        data = request.get_json() or {}
        enabled = data.get('enabled', True)
        enabled_int = 1 if enabled else 0
        
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        # rule_json内のenabledフィールドも更新する
        c.execute('SELECT rule_json FROM rules WHERE id = ?', (rule_id,))
        row = c.fetchone()
        if row:
            rule_json = json.loads(row[0]) if row[0] else {}
            rule_json['enabled'] = enabled
            c.execute('UPDATE rules SET enabled = ?, rule_json = ? WHERE id = ?', 
                     (enabled_int, json.dumps(rule_json, ensure_ascii=False), rule_id))
        else:
            # rule_jsonがない場合はenabledカラムのみ更新
            c.execute('UPDATE rules SET enabled = ? WHERE id = ?', (enabled_int, rule_id))
        
        conn.commit()
        conn.close()
        
        print(f'[RULE] Toggled rule {rule_id} enabled={enabled}')
        return jsonify({'status': 'success', 'rule_id': rule_id, 'enabled': enabled}), 200
    except Exception as e:
        print(f'[ERROR][toggle_rule] {e}')
        return jsonify({'status': 'error', 'msg': str(e)}), 500


@app.route('/api/currency_order', methods=['GET'])
def get_currency_order():
    """通貨ペアの表示順序を取得"""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('SELECT symbol FROM currency_order ORDER BY sort_order ASC')
        symbols = [row[0] for row in c.fetchall()]
        conn.close()
        return jsonify({'status': 'success', 'order': symbols}), 200
    except Exception as e:
        print(f'[ERROR][get_currency_order] {e}')
        return jsonify({'status': 'error', 'msg': str(e)}), 500


@app.route('/api/currency_order', methods=['POST'])
def save_currency_order():
    """通貨ペアの表示順序を保存"""
    try:
        data = request.json
        symbols = data.get('symbols', [])
        
        if not symbols:
            return jsonify({'status': 'error', 'msg': 'No symbols provided'}), 400
        
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        # 既存データをクリア
        c.execute('DELETE FROM currency_order')
        
        # 新しい順序で保存
        for idx, symbol in enumerate(symbols):
            c.execute('''INSERT INTO currency_order (symbol, sort_order, updated_at)
                        VALUES (?, ?, ?)''',
                     (symbol, idx, datetime.now(jst).isoformat()))
        
        conn.commit()
        conn.close()
        
        print(f'[OK] Currency order saved: {symbols}')
        return jsonify({'status': 'success'}), 200
    except Exception as e:
        print(f'[ERROR][save_currency_order] {e}')
        return jsonify({'status': 'error', 'msg': str(e)}), 500


@app.route('/rules/<rule_id>/test', methods=['POST'])
def test_single_rule(rule_id):
    """単一ルールをテスト"""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        # ルールを取得
        c.execute('SELECT rule_json FROM rules WHERE id = ?', (rule_id,))
        row = c.fetchone()
        
        if not row:
            conn.close()
            return jsonify({'status': 'error', 'msg': 'Rule not found'}), 404
        
        rule = json.loads(row[0])
        
        # 現在の状態を取得（cloud_dataではなくclouds_jsonを使用）
        # tf='5'のレコードには全TFの雲データが含まれている
        c.execute('SELECT DISTINCT symbol FROM states')
        symbols = [r[0] for r in c.fetchall()]
        
        matches = []
        for sym in symbols:
            try:
                # 5mのレコードから全TFの雲データとcloud_orderを取得
                c.execute('SELECT clouds_json, cloud_order FROM states WHERE symbol = ? AND tf = ?', (sym, '5'))
                row_5m = c.fetchone()
                
                if not row_5m or not row_5m[0]:
                    continue
                
                clouds = json.loads(row_5m[0])
                cloud_order = row_5m[1] if len(row_5m) > 1 else None
                
                # clouds配列を {tf_label: cloud_data} の辞書に変換
                cloud_data = {}
                for cloud in clouds:
                    label = cloud.get('label')
                    if label:
                        cloud_data[label] = cloud
                
                # cloud_orderを特別なキーで追加（雲整列判定用）
                if cloud_order:
                    cloud_data['__cloud_order__'] = cloud_order
                
                # ルールがこの通貨に適用されるか
                scope_symbol = rule.get('scope', {}).get('symbol', '')
                if scope_symbol and scope_symbol != sym:
                    continue
                
                # 簡易マッチング（実際の評価ロジックを呼び出す）
                direction = _evaluate_rule_match(rule, cloud_data)
                if direction:
                    matches.append({'symbol': sym, 'direction': direction})
            except Exception as inner_e:
                print(f'[TEST RULE] Error evaluating {sym}: {inner_e}')
                import traceback
                traceback.print_exc()
        
        conn.close()
        return jsonify({'status': 'success', 'matches': matches}), 200
    except Exception as e:
        print(f'[ERROR][test_single_rule] {e}')
        return jsonify({'status': 'error', 'msg': str(e)}), 500


@app.route('/rules/test', methods=['GET', 'POST'])
def rules_test():
    try:
        payload = request.json
        if not payload:
            return jsonify({'status':'error','msg':'no json payload'}), 400

        rule = payload.get('rule') or payload.get('rule_obj') or {}
        scope = payload.get('scope') or {}
        state_override = payload.get('state_override')

        # determine state to use
        used_state = None
        states_for_symbol = []
        
        if state_override:
            # state_override を使用（5m JSON には全TFの雲データが含まれる）
            used_state = state_override
            
            # Ensure proper data structure
            if 'clouds' not in used_state:
                try:
                    if 'clouds_json' in used_state:
                        used_state['clouds'] = json.loads(used_state.get('clouds_json','[]')) if isinstance(used_state.get('clouds_json'), str) else used_state.get('clouds_json', [])
                    else:
                        used_state['clouds'] = []
                except Exception:
                    used_state['clouds'] = []
            
            # Ensure row_order is a list
            if 'row_order' in used_state and isinstance(used_state['row_order'], str):
                used_state['row_order'] = used_state['row_order'].split(',') if used_state['row_order'] else []
            elif 'row_order' not in used_state:
                used_state['row_order'] = []
            
            # Ensure nested objects exist
            if 'state' not in used_state:
                used_state['state'] = {'flag': used_state.get('state_flag', ''), 'word': used_state.get('state_word', '')}
            if 'daytrade' not in used_state:
                used_state['daytrade'] = {'status': used_state.get('daytrade_status', ''), 'bos': used_state.get('daytrade_bos', ''), 'time': used_state.get('daytrade_time', '')}
            if 'swing' not in used_state:
                used_state['swing'] = {'status': used_state.get('swing_status', ''), 'bos': used_state.get('swing_bos', ''), 'time': used_state.get('swing_time', '')}
        else:
            # query DB for latest state matching scope.symbol if provided
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            if scope and scope.get('symbol'):
                c.execute('SELECT * FROM states WHERE symbol = ? ORDER BY rowid DESC LIMIT 1', (scope.get('symbol'),))
            else:
                c.execute('SELECT * FROM states ORDER BY rowid DESC LIMIT 1')
            row = c.fetchone()
            cols = [d[0] for d in c.description] if c.description else []
            conn.close()
            if not row:
                return jsonify({'status':'error','msg':'no state available for test'}), 400
            d = dict(zip(cols, row))
            try:
                d['clouds'] = json.loads(d.get('clouds_json','[]'))
            except Exception:
                d['clouds'] = d.get('clouds_json')
            try:
                d['meta'] = json.loads(d.get('meta_json','{}'))
            except Exception:
                d['meta'] = d.get('meta_json')
            d['row_order'] = d.get('row_order','').split(',') if d.get('row_order') else []
            d['cloud_order'] = d.get('cloud_order','').split(',') if d.get('cloud_order') else []
            d['state'] = {'flag': d.get('state_flag',''), 'word': d.get('state_word','')}
            d['daytrade'] = {'status': d.get('daytrade_status',''), 'bos': d.get('daytrade_bos',''), 'time': d.get('daytrade_time','')}
            d['swing'] = {'status': d.get('swing_status',''), 'bos': d.get('swing_bos',''), 'time': d.get('swing_time','')}
            used_state = d

        # Load other states for the same symbol to allow fallback when a requested TF/cloud is missing
        # (This applies to both state_override and DB-queried cases)
        try:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            sym = used_state.get('symbol') if used_state else None
            if sym:
                c.execute('SELECT * FROM states WHERE symbol = ?', (sym,))
                rows = c.fetchall()
                cols = [d[0] for d in c.description] if c.description else []
                for r in rows:
                    dd = dict(zip(cols, r))
                    try:
                        dd['clouds'] = json.loads(dd.get('clouds_json','[]'))
                    except Exception:
                        dd['clouds'] = dd.get('clouds_json')
                    states_for_symbol.append(dd)
            conn.close()
        except Exception:
            states_for_symbol = []

        # helper to find a field, with debug info: search used_state first then other states
        def _find_field_with_fallback(label, field):
                searched = []
                # normalize helper (reuse same normalization logic as _find_cloud_field)
                def _tf_to_minutes_local(s):
                    try:
                        if s is None:
                            return None
                        ss = str(s).strip().lower()
                        if ss.isdigit():
                            return int(ss)
                        if ss.endswith('m'):
                            return int(ss[:-1])
                        if ss.endswith('h'):
                            return int(ss[:-1]) * 60
                        if 'min' in ss:
                            num = ''.join([c for c in ss if c.isdigit()])
                            return int(num) if num else None
                        digits = ''.join([c for c in ss if c.isdigit()])
                        if digits:
                            return int(digits)
                    except Exception:
                        return None
                    return None

                req_min = _tf_to_minutes_local(label)

                # search a given state object for a matching cloud
                def _search_state_for(state_obj):
                    clouds = state_obj.get('clouds', [])
                    for c in clouds:
                        c_label = c.get('label')
                        searched.append({'state_tf': state_obj.get('tf'), 'cloud_label': c_label})
                        if str(c_label) == str(label):
                            val = c.get(field)
                            # Apply gc default handling here too
                            if field == 'gc' and val is None and field not in c:
                                val = False
                            return {'value': val, 'found_in': {'state_tf': state_obj.get('tf'), 'cloud_label': c_label}}
                        try:
                            cmin = _tf_to_minutes_local(c_label)
                            if req_min is not None and cmin is not None and req_min == cmin:
                                val = c.get(field)
                                if field == 'gc' and val is None and field not in c:
                                    val = False
                                return {'value': val, 'found_in': {'state_tf': state_obj.get('tf'), 'cloud_label': c_label}}
                        except Exception:
                            pass
                    return None

                # Strategy: search states with most clouds first (most complete data)
                # Sort states_for_symbol by number of clouds (descending)
                all_states = [used_state] if used_state else []
                try:
                    all_states.extend([s for s in states_for_symbol if s.get('symbol') == (used_state.get('symbol') if used_state else None)])
                except Exception:
                    pass
                
                # Remove duplicates and sort by cloud count
                seen_tfs = set()
                unique_states = []
                for st in all_states:
                    tf_key = st.get('tf')
                    if tf_key not in seen_tfs:
                        seen_tfs.add(tf_key)
                        unique_states.append(st)
                
                # Strategy: different priorities for different field types
                # For bos_count, dauten, dauten_start_time_str: prefer individual TF states (more specific)
                # For gc, angle, thickness, etc.: prefer complete states (tf="5")
                
                priority_fields_for_individual = ['bos_count', 'dauten', 'dauten_start_time_str']
                
                if field in priority_fields_for_individual:
                    # For these fields, prioritize individual TF states over complete state
                    # Sort: smallest cloud count first (individual states), then by timestamp (newest)
                    unique_states.sort(key=lambda s: (len(s.get('clouds', [])), -(s.get('time', 0) or 0)))
                else:
                    # For other fields, prioritize states with most clouds (complete data)
                    unique_states.sort(key=lambda s: len(s.get('clouds', [])), reverse=True)

                # Search across all states in priority order
                for state_obj in unique_states:
                    res = _search_state_for(state_obj)
                    if res and res.get('value') is not None:
                        res['searched'] = searched
                        return res

                # Not found anywhere
                return {'value': None, 'found_in': None, 'searched': searched}

        # wrapper to ensure callers always get a dict with value/found_in/searched
        def _get_info(label, field):
            try:
                info = _find_field_with_fallback(label, field)
                if isinstance(info, dict):
                    # ensure keys exist
                    if 'searched' not in info:
                        info['searched'] = []
                    if 'found_in' not in info:
                        info['found_in'] = None
                    return info
                # non-dict (e.g., boolean False or raw value) -> wrap
                return {'value': info, 'found_in': None, 'searched': []}
            except Exception:
                return {'value': None, 'found_in': None, 'searched': []}

        # evaluate conditions
        conditions = (rule.get('conditions') or [])
        logic = rule.get('logic','AND').upper()
        details = []
        results = []

        # --- evaluate alignment if present ---
        align = rule.get('cloudAlign') or rule.get('alignment') or rule.get('rule',{}).get('alignment')
        # timeframes (new) または tfs (old) をサポート
        align_tfs = align.get('timeframes') or align.get('tfs', []) if align else []
        # allTimeframesがTrueの場合、全タイムフレームを使用
        if align and align.get('allTimeframes') and not align_tfs:
            align_tfs = ['5m', '15m', '1H', '4H']
        if align and align_tfs:
            try:
                tfs = align_tfs
                missing_mode = align.get('missingBehavior') or align.get('missing', 'fail')
                
                # Get row_order from used_state
                row_order = used_state.get('row_order', []) if used_state else []
                
                reason = None
                align_ok = False
                missingFound = False
                missing_tfs = []
                effective_tfs = []
                row_order_effective = []
                
                if not row_order:
                    align_ok = False; reason = 'no_row_order'
                elif len(tfs) == 0:
                    align_ok = False; reason = 'no_selection'
                elif len(tfs) == 1:
                    align_ok = False; reason = 'need_at_least_2'
                else:
                    # Check which tfs are missing in row_order
                    missing_tfs = [tf for tf in tfs if tf not in row_order]
                    missingFound = len(missing_tfs) > 0
                    
                    if missing_mode == 'fail' and missingFound:
                        align_ok = False; reason = 'missing_fail'
                    else:
                        # Exclude missing tfs and check if remaining tfs match the corresponding subsequence in row_order or its reverse
                        effective_tfs = [tf for tf in tfs if tf in row_order]
                        if len(effective_tfs) < 2:
                            align_ok = False; reason = 'too_few_effective_tfs'
                        else:
                            # Get the subsequence of row_order that matches effective_tfs
                            row_order_effective = [tf for tf in row_order if tf in effective_tfs]
                            align_ok = (effective_tfs == row_order_effective or effective_tfs == row_order_effective[::-1])
                            if not align_ok:
                                reason = 'order_mismatch'
                
                details.append({'cond':'alignment','tfs':tfs,'row_order':row_order,'missing_mode':missing_mode,'missing_found':missingFound,'missing_tfs':missing_tfs,'effective_tfs':effective_tfs,'row_order_effective':row_order_effective,'result':bool(align_ok),'reason':reason})
                results.append(bool(align_ok))
            except Exception as e:
                details.append({'cond':'alignment','error':str(e),'result':False})
                results.append(False)

        for cond in conditions:
            # support simple field conds: {label, field, op, value}
            if cond.get('field'):
                label = cond.get('timeframe') or cond.get('label')
                field = cond.get('field')
                op = cond.get('op', '==')
                val = cond.get('value')
                
                # Special handling for bos_count: use state-level daytrade_bos instead of cloud.bos_count
                # This matches the frontend display logic which uses state.daytrade.bos
                if field == 'bos_count':
                    # Find the state that matches the requested TF/label
                    bos_value = None
                    found_state = None
                    # Search all states for matching TF
                    all_states = [used_state] if used_state else []
                    all_states.extend(states_for_symbol)
                    for st in all_states:
                        # Match by label (normalize TF)
                        st_tf = str(st.get('tf', ''))
                        # Normalize: 5->5m, 15->15m, 60->1H, 240->4H
                        if st_tf == '5': st_tf = '5m'
                        elif st_tf == '15': st_tf = '15m'
                        elif st_tf == '60': st_tf = '1H'
                        elif st_tf == '240': st_tf = '4H'
                        
                        if st_tf.lower() == label.lower():
                            bos_value = st.get('daytrade_bos')
                            found_state = st
                            break
                    
                    if bos_value is not None:
                        info = {
                            'value': bos_value,
                            'found_in': {'state_tf': found_state.get('tf') if found_state else None, 'field': 'daytrade_bos'},
                            'searched': [{'state_tf': st.get('tf')} for st in all_states[:3]]  # limit for brevity
                        }
                    else:
                        # Fallback to cloud.bos_count if daytrade_bos not found
                        info = _get_info(label, field)
                else:
                    info = _get_info(label, field)
                
                actual = _normalize_actual(field, info.get('value'))
                # keep debug info available in details for missing cases
                info_searched = info.get('searched')
                info_found = info.get('found_in')

                # Special numeric-threshold semantics for selected fields:
                numeric_threshold_fields = ['distance_from_prev', 'distance_from_price', 'angle', 'thickness']
                if field in numeric_threshold_fields:
                    # Interpret user-entered threshold as absolute N (positive expected).
                    # Match if actual >= +N (up) or actual <= -N (down). Inclusive comparison.
                    try:
                        if val is None or val == '':
                            details.append({'cond': f"{label}.{field}", 'actual': actual, 'value': val, 'result': False, 'reason': 'no_threshold_provided'})
                            results.append(False)
                        else:
                            try:
                                N = float(val)
                            except Exception:
                                details.append({'cond': f"{label}.{field}", 'actual': actual, 'value': val, 'result': False, 'reason': 'invalid_threshold'})
                                results.append(False)
                                continue

                            if actual is None:
                                details.append({'cond': f"{label}.{field}", 'actual': None, 'threshold': N, 'result': False, 'reason': 'missing_field'})
                                results.append(False)
                            else:
                                try:
                                    a_val = float(actual)
                                except Exception:
                                    details.append({'cond': f"{label}.{field}", 'actual': actual, 'threshold': N, 'result': False, 'reason': 'non_numeric_actual'})
                                    results.append(False)
                                    continue

                                matched_dir = None
                                ok = False
                                if a_val >= N:
                                    ok = True; matched_dir = 'up'
                                elif a_val <= -N:
                                    ok = True; matched_dir = 'down'
                                details.append({'cond': f"{label}.{field}", 'actual': a_val, 'threshold': N, 'match_direction': matched_dir, 'result': bool(ok)})
                                results.append(bool(ok))
                    except Exception as e:
                        details.append({'cond': f"{label}.{field}", 'error': str(e), 'result': False})
                        results.append(False)
                    continue

                # Special handling for transfer_time_diff: time difference between dauten and cross in same direction
                if field == 'transfer_time_diff':
                    try:
                        # Get times
                        dauten_info_t = _get_info(label, 'dauten_start_time_str')
                        cross_info_t = _get_info(label, 'cross_start_time')
                        dauten_time_ms = _parse_time_to_ms(dauten_info_t.get('value'))
                        cross_time_ms = _parse_time_to_ms(cross_info_t.get('value'))
                        # Get directions
                        dauten_info = _get_info(label, 'dauten')
                        cross_info = _get_info(label, 'gc')
                        dauten_dir = _normalize_actual('dauten', dauten_info.get('value'))
                        cross_dir = _normalize_actual('gc', cross_info.get('value'))
                        
                        if dauten_time_ms is None or cross_time_ms is None or dauten_dir is None or cross_dir is None:
                            details.append({'cond': f"{label}.{field}", 'value': val, 'result': False, 'reason': 'missing_data', 'dauten_dir': dauten_dir, 'cross_dir': cross_dir})
                            results.append(False)
                        elif str(dauten_dir) not in ('上昇', '下降', 'up', 'down') or str(cross_dir) not in ('GC', 'DC'):
                            details.append({'cond': f"{label}.{field}", 'value': val, 'result': False, 'reason': 'invalid_direction', 'dauten_dir': str(dauten_dir), 'cross_dir': str(cross_dir)})
                            results.append(False)
                        else:
                            # Check if directions match: dauten '上昇'/'下降' matches gc 'GC'/'DC' (GC=上昇, DC=下降)
                            dauten_up = str(dauten_dir) in ('上昇', 'up')
                            cross_up = str(cross_dir) == 'GC'
                            if dauten_up != cross_up:
                                details.append({'cond': f"{label}.{field}", 'value': val, 'result': False, 'reason': 'directions_mismatch'})
                                results.append(False)
                            else:
                                # Calculate absolute time difference in minutes
                                delta_min = abs(dauten_time_ms - cross_time_ms) / 60000.0
                                try:
                                    threshold_min = float(val)
                                except Exception:
                                    details.append({'cond': f"{label}.{field}", 'value': val, 'result': False, 'reason': 'invalid_threshold'})
                                    results.append(False)
                                    continue
                                ok = delta_min <= threshold_min
                                details.append({'cond': f"{label}.{field}", 'delta_min': delta_min, 'actual': delta_min, 'threshold': threshold_min, 'result': bool(ok)})
                                results.append(bool(ok))
                    except Exception as e:
                        details.append({'cond': f"{label}.{field}", 'error': str(e), 'result': False})
                        results.append(False)
                    continue

                # Generic comparison handler for simple fields (e.g. dauten, gc, bos_count, etc.)
                try:
                    # If no value provided, check field behavior
                    if val is None or val == '':
                        if actual is None:
                            details.append({'cond': f"{label}.{field}", 'actual': None, 'value': val, 'result': False, 'reason': 'missing_field', 'found_in': info_found, 'searched': info_searched})
                            results.append(False)
                        else:
                            # For gc/dauten: value not specified means "exists and is truthy"
                            # But for gc, 'DC' should be treated as existing (not falsy in presence sense)
                            # For toggle fields like gc/dauten, if no value specified, just check existence (always true if field exists)
                            ok = True  # field exists
                            if field in ('gc', 'dauten'):
                                # These are always "present" if they have any value
                                ok = True
                            else:
                                # Other fields: interpret falsy strings as False ('false','0','')
                                try:
                                    if isinstance(actual, str):
                                        la = actual.strip().lower()
                                        if la in ('false','0',''):
                                            ok = False
                                    else:
                                        ok = bool(actual)
                                except Exception:
                                    ok = bool(actual)
                            details.append({'cond': f"{label}.{field}", 'actual': actual, 'value': val, 'result': bool(ok), 'reason': 'presence_check', 'found_in': info_found, 'searched': info_searched})
                            results.append(bool(ok))
                    else:
                        if actual is None:
                            details.append({'cond': f"{label}.{field}", 'actual': None, 'value': val, 'result': False, 'reason': 'missing_field', 'found_in': info_found, 'searched': info_searched})
                            results.append(False)
                        else:
                            ok = _compare_values(actual, op, val)
                            details.append({'cond': f"{label}.{field}", 'actual': actual, 'op': op, 'value': val, 'result': bool(ok), 'found_in': info_found, 'searched': info_searched})
                            results.append(bool(ok))
                except Exception as e:
                    details.append({'cond': f"{label}.{field}", 'error': str(e), 'result': False})
                    results.append(False)
                continue

            # timediff cond: either type=='timediff' or has left/right
            if cond.get('type') == 'timediff' or (cond.get('left') and cond.get('right')):
                left = cond.get('left')
                right = cond.get('right')
                op = cond.get('op','<=')
                # obtain ms
                def resolve_time(spec):
                    # spec can be dict {label, field} or string '1H.field'
                    if isinstance(spec, dict):
                        vinfo = _get_info(spec.get('label'), spec.get('field'))
                        return _parse_time_to_ms(vinfo.get('value'))
                    if isinstance(spec, str):
                        if '.' in spec:
                            lab, fld = spec.split('.',1)
                            vinfo = _get_info(lab, fld)
                            return _parse_time_to_ms(vinfo.get('value'))
                        else:
                            return _parse_time_to_ms(spec)
                    return _parse_time_to_ms(spec)

                left_ms = resolve_time(left)
                right_ms = resolve_time(right)
                if left_ms is None or right_ms is None:
                    details.append({'cond': 'timediff', 'left': left, 'right': right, 'result': False, 'reason':'missing time'})
                    results.append(False)
                else:
                    delta_min = abs(left_ms - right_ms) / 60000.0
                    compare_val = cond.get('value_minutes') or cond.get('value') or 0
                    try:
                        compare_val = float(compare_val)
                    except Exception:
                        compare_val = 0
                    if op == '<=':
                        ok = delta_min <= compare_val
                    elif op == '>=':
                        ok = delta_min >= compare_val
                    elif op == '<':
                        ok = delta_min < compare_val
                    elif op == '>':
                        ok = delta_min > compare_val
                    else:
                        ok = False
                    details.append({'cond':'timediff','left_ms':left_ms,'right_ms':right_ms,'delta_min':delta_min,'op':op,'value':compare_val,'result':bool(ok)})
                    results.append(bool(ok))
                continue

            # unknown cond
            details.append({'cond': cond, 'result': False, 'reason':'unsupported condition type'})
            results.append(False)

        # --- Direction consistency check ---
        # If conditions include directional fields (dauten, gc), check that all directions match
        # Extract directions from conditions that passed
        directions = []
        for i, cond in enumerate(conditions):
            if i >= len(results):
                continue
            if not results[i]:
                continue  # Skip failed conditions
            
            field = cond.get('field')
            if field in ('dauten', 'gc'):
                # Get actual value from details
                detail = next((d for d in details if d.get('cond') == f"{cond.get('timeframe') or cond.get('label')}.{field}"), None)
                if detail:
                    actual = detail.get('actual')
                    if actual:
                        # Map to direction: dauten -> '上昇'/'下降', gc -> 'GC'(上昇)/'DC'(下降)
                        if field == 'dauten':
                            direction = '上昇' if ('上昇' in str(actual) or 'up' in str(actual).lower()) else '下降'
                        elif field == 'gc':
                            direction = '上昇' if str(actual).upper() == 'GC' else '下降'
                        directions.append(direction)
        
        # Check if all directions are the same
        direction_consistent = True
        if len(directions) >= 2:
            first_direction = directions[0]
            if not all(d == first_direction for d in directions):
                direction_consistent = False
                details.append({
                    'cond': 'direction_consistency',
                    'directions': directions,
                    'result': False,
                    'reason': 'directions_mismatch'
                })

        matched = False
        if logic == 'AND':
            matched = all(results) if results else False
            # Apply direction consistency check
            if matched and not direction_consistent:
                matched = False
        else:
            matched = any(results) if results else False

        return jsonify({'status':'success','matched': matched, 'details': details, 'used_state': used_state}), 200
    except Exception as e:
        print('[ERROR][rules/test]', e)
        import traceback; traceback.print_exc()
        return jsonify({'status':'error','msg': str(e)}), 500

@app.route('/api/test_fire', methods=['POST'])
def api_test_fire():
    """テスト発火エンドポイント: 指定通貨の最新 5m 状態を取得してテスト通知を作成"""
    try:
        payload = request.json or {}
        symbol = payload.get('symbol', 'USDJPY')
        
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        # 指定通貨の最新 5m データを取得
        c.execute('SELECT * FROM states WHERE symbol = ? AND tf = ? ORDER BY rowid DESC LIMIT 1', (symbol, '5'))
        row = c.fetchone()
        cols = [d[0] for d in c.description] if c.description else []
        conn.close()
        
        if not row:
            return jsonify({'status': 'error', 'msg': f'No data available for {symbol}'}), 404
        
        # 行データを辞書に変換
        state_dict = dict(zip(cols, row))
        
        # JSON フィールドをパース
        try:
            state_dict['clouds'] = json.loads(state_dict.get('clouds_json', '[]'))
        except:
            state_dict['clouds'] = []
        
        try:
            state_dict['meta'] = json.loads(state_dict.get('meta_json', '{}'))
        except:
            state_dict['meta'] = {}
        
        # テスト通知を作成
        jst = pytz.timezone('Asia/Tokyo')
        test_notification = {
            'rule_id': 'test-fire',
            'rule_name': 'テスト発火',
            'symbol': state_dict.get('symbol', symbol),
            'tf': state_dict.get('tf', '5'),
            'direction': '上昇',  # デフォルト方向
            'message': 'テスト発火メッセージ',
            'timestamp': datetime.now(jst).isoformat(),
            'price': float(state_dict.get('price', 0))
        }
        
        # 通知をファイルに保存
        notifications_path = os.path.join(BASE_DIR, 'notifications.json')
        try:
            if os.path.exists(notifications_path):
                with open(notifications_path, 'r', encoding='utf-8') as f:
                    existing = json.load(f)
            else:
                existing = []
            
            existing.append(test_notification)
            
            # 最新100件のみ保持
            if len(existing) > 100:
                existing = existing[-100:]
            
            with open(notifications_path, 'w', encoding='utf-8') as f:
                json.dump(existing, f, ensure_ascii=False, indent=2)
            
            print(f'[TEST FIRE] Test notification created for {symbol}: {test_notification}')
        except Exception as e:
            print(f'[ERROR] Saving test notification: {e}')
        
        return jsonify({'status': 'success', 'notification': test_notification}), 200
    except Exception as e:
        print(f'[ERROR][api/test_fire] {e}')
        return jsonify({'status': 'error', 'msg': str(e)}), 500

@app.route('/api/settings', methods=['GET', 'POST'])
def api_settings():
    settings_path = os.path.join(BASE_DIR, 'settings.json')
    try:
        if request.method == 'GET':
            if os.path.exists(settings_path):
                with open(settings_path, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
            else:
                settings = {"update_delay_seconds": 10}
            return jsonify({'status': 'success', 'settings': settings}), 200
        else:  # POST
            data = request.json
            if not data or 'update_delay_seconds' not in data:
                return jsonify({'status': 'error', 'msg': 'Invalid data'}), 400
            try:
                delay = int(data['update_delay_seconds'])
                if delay < 0 or delay > 300:  # 0-5分
                    return jsonify({'status': 'error', 'msg': 'Delay must be 0-300 seconds'}), 400
            except ValueError:
                return jsonify({'status': 'error', 'msg': 'Delay must be integer'}), 400
            
            settings = {"update_delay_seconds": delay}
            with open(settings_path, 'w', encoding='utf-8') as f:
                json.dump(settings, f, ensure_ascii=False, indent=2)
            return jsonify({'status': 'success'}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'msg': str(e)}), 500

@app.route('/api/notifications', methods=['GET'])
def api_notifications():
    # Log client info for debugging
    client_ip = request.remote_addr
    user_agent = request.headers.get('User-Agent', 'Unknown')
    print(f'[API/NOTIFICATIONS] Client: {client_ip}, User-Agent: {user_agent[:50]}...')
    
    notifications_path = os.path.join(BASE_DIR, 'notifications.json')
    try:
        if os.path.exists(notifications_path):
            with open(notifications_path, 'r', encoding='utf-8') as f:
                notifications = json.load(f)
        else:
            notifications = []
        
        # Return latest 50 notifications
        return jsonify({'status': 'success', 'notifications': notifications[-50:]}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'msg': str(e)}), 500

@app.route('/api/backup/fetch', methods=['POST'])
def api_backup_fetch():
    """Gmail から手動でバックアップを取得（バックグラウンド実行 → 即座にジョブIDを返す）"""
    import uuid, threading

    # backup_recovery.py のパスを探す
    script_paths = [
        os.path.join(BASE_DIR, 'backup_recovery.py'),
        os.path.join(os.path.dirname(BASE_DIR), 'backup_recovery.py'),
        os.path.join(os.getcwd(), 'backup_recovery.py')
    ]
    script_path = None
    for path in script_paths:
        if os.path.exists(path):
            script_path = path
            break

    if not script_path:
        searched_paths = ', '.join(script_paths)
        return jsonify({'status': 'error', 'msg': f'backup_recovery.py not found (searched: {searched_paths})'}), 404

    import sys
    python_exe = sys.executable
    jst = pytz.timezone('Asia/Tokyo')

    job_id = str(uuid.uuid4())[:8]
    _backup_jobs[job_id] = {
        'status': 'running',
        'output': '',
        'started_at': datetime.now(jst).isoformat()
    }

    def _run_fetch(job_id, python_exe, script_path):
        """バックグラウンドスレッドで backup_recovery.py を実行"""
        try:
            result = subprocess.run(
                [python_exe, script_path, '--fetch', '--max', '500', '--after-days', '3'],
                capture_output=True,
                text=True,
                timeout=300
            )
            stderr_lower = (result.stderr or '').lower()
            if result.returncode == 0:
                _backup_jobs[job_id]['status'] = 'completed'
                _backup_jobs[job_id]['output'] = result.stdout
            elif 'invalid_grant' in stderr_lower or 'token has been expired' in stderr_lower or 'token has been revoked' in stderr_lower:
                _backup_jobs[job_id]['status'] = 'reauth_required'
                _backup_jobs[job_id]['output'] = result.stderr + '\n' + result.stdout
            else:
                _backup_jobs[job_id]['status'] = 'error'
                _backup_jobs[job_id]['output'] = result.stderr + '\n' + result.stdout
        except subprocess.TimeoutExpired:
            _backup_jobs[job_id]['status'] = 'error'
            _backup_jobs[job_id]['output'] = 'Timeout: Gmail fetch took too long (>300s)'
        except Exception as e:
            _backup_jobs[job_id]['status'] = 'error'
            _backup_jobs[job_id]['output'] = str(e)

    t = threading.Thread(target=_run_fetch, args=(job_id, python_exe, script_path), daemon=True)
    t.start()

    return jsonify({'status': 'started', 'job_id': job_id}), 202


@app.route('/api/backup/fetch/status', methods=['GET'])
def api_backup_fetch_status():
    """バックアップ取得ジョブのステータスを返す"""
    job_id = request.args.get('job_id', '')
    if not job_id or job_id not in _backup_jobs:
        return jsonify({'status': 'not_found'}), 404
    job = _backup_jobs[job_id]
    return jsonify({
        'status': job['status'],
        'output': job.get('output', ''),
        'started_at': job.get('started_at', '')
    }), 200

@app.route('/api/backup/token_status', methods=['GET'])
def api_backup_token_status():
    """token.json の状態を返す（canonical path のみを参照）"""
    try:
        token_path = os.path.join(BASE_DIR, 'token.json')
        if not os.path.exists(token_path):
            return jsonify({'status': 'not_found', 'msg': 'token.json not found', 'path': token_path}), 200

        info = {'path': token_path}
        info['mtime'] = os.path.getmtime(token_path)
        info['size'] = os.path.getsize(token_path)

        try:
            with open(token_path, 'r', encoding='utf-8') as f:
                token_json = json.load(f)
            info['has_refresh_token'] = 'refresh_token' in token_json and bool(token_json.get('refresh_token'))
            info['expiry'] = token_json.get('expiry') or token_json.get('_expiry') or token_json.get('expires_at')
        except Exception:
            info['has_refresh_token'] = False
            info['expiry'] = None

        return jsonify({'status': 'ok', 'token_info': info}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'msg': str(e)}), 500


@app.route('/api/backup/clear_token', methods=['POST'])
def api_backup_clear_token():
    """token.json を削除（再認証の準備用） — canonical path のみを削除"""
    try:
        token_path = os.path.join(BASE_DIR, 'token.json')
        removed = []
        if os.path.exists(token_path):
            os.remove(token_path)
            removed.append(token_path)
        return jsonify({'status': 'ok', 'removed': removed}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'msg': str(e)}), 500


@app.route('/api/backup/list', methods=['GET'])
def api_backup_list():
    """バックアップファイル一覧を取得"""
    try:
        backup_dir = r'C:\Users\kanda\Desktop\TradingViewBackup_JSON'
        
        if not os.path.exists(backup_dir):
            return jsonify({
                'status': 'success',
                'symbols': [],
                'summary': {}
            }), 200
        
        from pathlib import Path
        backup_path = Path(backup_dir)
        
        symbols = []
        summary = {}
        
        for symbol_folder in sorted(backup_path.iterdir()):
            if not symbol_folder.is_dir():
                continue
            
            symbol = symbol_folder.name
            symbols.append(symbol)
            summary[symbol] = {}
            
            for tf_folder in sorted(symbol_folder.iterdir()):
                if not tf_folder.is_dir():
                    continue
                
                tf = tf_folder.name
                json_files = list(tf_folder.glob('*.json'))
                
                # _no_time ファイルを除外（実際のタイムスタンプ付きファイルのみ）
                # パターン: 20260201_no_time_15m.json, 20260201_no_time_15m_1.json など
                timestamped_files = [f for f in json_files if '_no_time' not in f.name]
                
                count = len(json_files)
                
                if count > 0:
                    # タイムスタンプ付きファイルがあればそれを使用、なければ全ファイルから選択
                    files_for_range = timestamped_files if timestamped_files else json_files
                    
                    oldest = min(files_for_range, key=lambda f: f.name)
                    newest = max(files_for_range, key=lambda f: f.name)
                    
                    # ファイル名から YYYYMMDD_HHMMSS 部分を抽出
                    # 新形式: 20260130_223000_15m_1769779800000.json
                    # 旧形式: 20260131_064500_1769809500000.json
                    # どちらも最初の15文字で YYYYMMDD_HHMMSS を取得
                    def extract_datetime_str(filename):
                        # 最初の4+2+2+1+2+2 = 15 文字
                        return filename[:15]
                    
                    summary[symbol][tf] = {
                        'count': count,
                        'oldest': extract_datetime_str(oldest.name),
                        'newest': extract_datetime_str(newest.name)
                    }
        
        return jsonify({
            'status': 'success',
            'symbols': symbols,
            'summary': summary
        }), 200
        
    except Exception as e:
        print(f'[ERROR] Backup list failed: {e}')
        return jsonify({'status': 'error', 'msg': str(e)}), 500

@app.route('/api/backup/recovery', methods=['POST'])
def api_backup_recovery():
    """
    バックアップから DB にデータを復旧
    リクエスト: {
        "symbol": "EURJPY" or "all",
        "tf": "15m" or "all",
        "date": "20260131" or "all",
        "mode": "merge" or "replace"
    }
    """
    try:
        req = request.json
        symbol = req.get('symbol', 'all')
        tf = req.get('tf', 'all')
        date = req.get('date', 'all')
        mode = req.get('mode', 'merge')
        
        backup_dir = r'C:\Users\kanda\Desktop\TradingViewBackup_JSON'
        
        if not os.path.exists(backup_dir):
            return jsonify({'status': 'error', 'msg': 'Backup directory not found'}), 404
        
        from pathlib import Path
        backup_path = Path(backup_dir)
        
        # ファイルを検索
        files = []
        
        # 通貨フォルダを走査
        if symbol != 'all':
            symbol_folders = [backup_path / symbol]
        else:
            symbol_folders = [f for f in backup_path.iterdir() if f.is_dir()]
        
        for symbol_folder in symbol_folders:
            if not symbol_folder.exists():
                continue
            
            # 時間足フォルダを走査
            if tf != 'all':
                tf_folders = [symbol_folder / tf]
            else:
                tf_folders = [f for f in symbol_folder.iterdir() if f.is_dir()]
            
            for tf_folder in tf_folders:
                if not tf_folder.exists():
                    continue
                
                # JSON ファイルを取得
                for json_file in tf_folder.glob('*.json'):
                    # 日付フィルタ
                    if date != 'all':
                        if not json_file.name.startswith(date):
                            continue
                    
                    files.append(json_file)
        
        if not files:
            return jsonify({
                'status': 'warning',
                'msg': 'No backup files found matching criteria',
                'recovered': 0
            }), 200
        
        # DB に復旧
        jst = pytz.timezone('Asia/Tokyo')
        recovered_count = 0
        skipped_count = 0
        error_count = 0
        
        # ログ出力
        print(f'[BACKUP RECOVERY] Found {len(files)} files to process')
        print(f'[BACKUP RECOVERY] Mode: {mode}, Symbol: {symbol}, TF: {tf}, Date: {date}')
        
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        for file_path in files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                symbol_val = data.get('symbol', 'UNKNOWN')
                tf_val = data.get('tf', '5')
                
                # シグナルファイル（sgとcountのみ）をスキップ
                if 'sg' in data and 'time' not in data:
                    print(f'[BACKUP RECOVERY] Skipping signal file: {file_path.name}')
                    skipped_count += 1
                    continue
                
                # timeフィールドが無いファイルは、JSON内の sent_time → ファイル名 → ファイル名先頭 の順で補完して復旧を試みる
                if 'time' not in data or data.get('time', 0) == 0:
                    ms = None

                    # 1) JSON 内に sent_time (例: "26/02/17/07:00") があれば優先して使用
                    sent_time_str = data.get('sent_time') or data.get('sentTime') or ''
                    if sent_time_str:
                        try:
                            # 受け取りやすいフォーマットをいくつか試す
                            from datetime import datetime
                            s = sent_time_str.strip()
                            # 例: 26/02/17/07:00  または 2026/02/17 07:00
                            parsed = None
                            for fmt in ('%y/%m/%d/%H:%M', '%Y/%m/%d %H:%M', '%y/%m/%d %H:%M', '%Y/%m/%d/%H:%M', '%y-%m-%d %H:%M'):
                                try:
                                    parsed = datetime.strptime(s, fmt)
                                    break
                                except Exception:
                                    parsed = None
                            if parsed:
                                parsed = jst.localize(parsed)
                                ms = int(parsed.timestamp() * 1000)
                                data['time'] = ms
                                print(f"[BACKUP RECOVERY] No time in JSON -> using sent_time field: {ms} ({sent_time_str})")
                        except Exception:
                            ms = None

                    # 2) 末尾にミリ秒タイムスタンプがあれば使用（例: ..._1771279264000.json）
                    if not ms:
                        m = re.search(r'_(\d{13,})\.json$', file_path.name)
                        if m:
                            try:
                                ms = int(m.group(1))
                                data['time'] = ms
                                print(f"[BACKUP RECOVERY] No time in JSON -> using timestamp from filename suffix: {ms} ({file_path.name})")
                            except:
                                ms = None

                    # 3) 末尾のミリ秒がなければ、ファイル名先頭の YYYYMMDD_HHMMSS を使用
                    if not ms:
                        parts = file_path.stem.split('_')
                        if len(parts) >= 2 and len(parts[0]) == 8 and len(parts[1]) == 6:
                            try:
                                from datetime import datetime
                                dt = datetime.strptime(parts[0] + parts[1], '%Y%m%d%H%M%S')
                                dt = jst.localize(dt)
                                ms = int(dt.timestamp() * 1000)
                                data['time'] = ms
                                print(f"[BACKUP RECOVERY] No time in JSON -> using timestamp from filename head: {ms} ({file_path.name})")
                            except:
                                ms = None

                    if not ms:
                        print(f'[BACKUP RECOVERY] Skipping file without time: {file_path.name}')
                        skipped_count += 1
                        continue
                
                # mode が "merge" の場合、既存データがあればスキップ
                if mode == 'merge':
                    c.execute('SELECT COUNT(*) FROM states WHERE symbol = ? AND tf = ?', 
                             (symbol_val, tf_val))
                    count = c.fetchone()[0]
                    if count > 0:
                        # time を比較して新しい方を保持
                        c.execute('SELECT time FROM states WHERE symbol = ? AND tf = ?',
                                 (symbol_val, tf_val))
                        db_time = c.fetchone()[0]
                        backup_time = data.get('time', 0)
                        
                        if db_time >= backup_time:
                            print(f'[BACKUP RECOVERY] Skipping {symbol_val}/{tf_val}: DB has newer data (DB:{db_time} >= Backup:{backup_time})')
                            skipped_count += 1
                            continue
                        else:
                            print(f'[BACKUP RECOVERY] Updating {symbol_val}/{tf_val}: Backup has newer data (DB:{db_time} < Backup:{backup_time})')
                
                # received_at: JSON の sent_time を最優先、なければファイル名から抽出
                received_at_str = None

                # 1) JSON内の sent_time から取得（例: "26/02/19/00:30" = YY/MM/DD/HH:MM）
                sent_time_str = data.get('sent_time', '')
                if sent_time_str:
                    try:
                        st_parts = sent_time_str.split('/')
                        if len(st_parts) == 4:
                            syy, smm, sdd, shhmm = st_parts
                            shh, smn = shhmm.split(':')
                            sent_dt = jst.localize(datetime(2000 + int(syy), int(smm), int(sdd), int(shh), int(smn), 0))
                            received_at_str = sent_dt.isoformat()
                    except Exception:
                        pass

                # 2) フォールバック: ファイル名から受信時刻を抽出
                # 対応形式:
                # - 旧形式: 20260131_064500_1769809500000.json
                # - 新形式: 20260131_064500_15m_1769809500000.json
                if not received_at_str:
                    filename = os.path.basename(file_path)
                    if '_' in filename:
                        parts = filename.replace('.json', '').split('_')
                        if len(parts) >= 2:
                            try:
                                date_str = parts[0]  # 20260131
                                time_str = parts[1]  # 064500
                                if len(date_str) == 8 and len(time_str) == 6:
                                    dt = datetime.strptime(f"{date_str}{time_str}", "%Y%m%d%H%M%S")
                                    dt = jst.localize(dt)
                                    received_at_str = dt.isoformat()
                            except Exception:
                                pass

                if not received_at_str:
                    received_at_str = datetime.now(jst).isoformat()
                
                # DB に保存（sent_time を含む）
                c.execute('''INSERT OR REPLACE INTO states (
                            symbol, tf, timestamp, price, time,
                            state_flag, state_word,
                            daytrade_status, daytrade_bos, daytrade_time,
                            swing_status, swing_bos, swing_time,
                            row_order, cloud_order, clouds_json, meta_json, received_at, sent_time
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                        (symbol_val, tf_val,
                         datetime.now(jst).isoformat(), float(data.get('price', 0)),
                         data.get('time', 0),
                         data.get('state', {}).get('flag', ''),
                         data.get('state', {}).get('word', ''),
                         data.get('daytrade', {}).get('status', ''),
                         data.get('daytrade', {}).get('bos', ''),
                         data.get('daytrade', {}).get('time', ''),
                         data.get('swing', {}).get('status', ''),
                         data.get('swing', {}).get('bos', ''),
                         data.get('swing', {}).get('time', ''),
                         ','.join(data.get('row_order', [])),
                         ','.join(data.get('cloud_order', [])),
                         json.dumps(data.get('clouds', []), ensure_ascii=False),
                         json.dumps(data.get('meta', {}), ensure_ascii=False),
                         received_at_str,
                         data.get('sent_time', '')))
                
                recovered_count += 1
                print(f'[BACKUP RECOVERY] Recovered {symbol_val}/{tf_val} from {file_path.name} (time={data.get("time", 0)}, received_at={received_at_str})')
                
            except Exception as e:
                print(f'[ERROR] Failed to recover {file_path}: {e}')
                error_count += 1
                continue
        
        conn.commit()
        conn.close()
        
        print(f'[BACKUP RECOVERY] Summary: Recovered={recovered_count}, Skipped={skipped_count}, Errors={error_count}')
        
        # Socket.IO で通知
        socketio.emit('backup_recovery_complete', {
            'recovered': recovered_count,
            'skipped': skipped_count,
            'errors': error_count,
            'symbol': symbol,
            'tf': tf,
            'date': date
        })
        
        # テーブル更新通知
        socketio.emit('update_table', {'message': 'Backup recovery completed'})
        
        return jsonify({
            'status': 'success',
            'recovered': recovered_count,
            'skipped': skipped_count,
            'errors': error_count
        }), 200
        
    except Exception as e:
        print(f'[ERROR] Backup recovery failed: {e}')
        import traceback
        traceback.print_exc()
        return jsonify({'status': 'error', 'msg': str(e)}), 500

@app.route('/api/backup/send_to_target', methods=['POST', 'OPTIONS'])
def api_backup_send_to_target():
    """
    ローカルバックアップフォルダのJSONを指定Webhookへ送信。
    ローカルサーバー経由で呼び出すことで、Renderにアクセスできないローカルパスを参照できる。
    リクエスト: { "symbol":"all"/"USDJPY", "tf":"all"/"D",
                 "target":"local"/"production",
                 "local_url":"http://localhost:5000" (localの場合),
                 "mode":"merge"/"replace" }
    NOTE: 追加で OPTIONS/CORS をサポートし、受信ログを残す
    """
    # CORS preflight support
    if request.method == 'OPTIONS':
        resp = make_response('', 200)
        resp.headers['Access-Control-Allow-Origin'] = '*'
        resp.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
        resp.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        return resp

    try:
        # Diagnostic log for incoming calls from browser / UI
        try:
            origin = request.headers.get('Origin')
            with open(os.path.join(BASE_DIR, 'webhook_error.log'), 'a', encoding='utf-8') as _log:
                _log.write(f"[SEND_TO_TARGET] request from {request.remote_addr} Origin={origin} headers={dict(request.headers)}\n")
        except Exception:
            pass

        req = request.json or {}
        symbol_filter = req.get('symbol', 'all')
        tf_filter     = req.get('tf', 'all')
        target        = req.get('target', 'production')  # 'local' or 'production'
        local_url     = req.get('local_url', 'http://localhost:5000')
        mode          = req.get('mode', 'merge')

        PROD_URL  = 'https://tradingview-webhook-s5x1.onrender.com/webhook'
        LOCAL_URL = local_url.rstrip('/') + '/webhook'
        target_url = LOCAL_URL if target == 'local' else PROD_URL

        backup_dir = r'C:\Users\kanda\Desktop\TradingViewBackup_JSON'
        if not os.path.exists(backup_dir):
            return jsonify({'status': 'error', 'msg': f'バックアップフォルダが見つかりません: {backup_dir}'}), 404

        TF_MAP = {'5':'5','15':'15','60':'60','240':'240','D':'D','W':'W','M':'M'}

        symbols = (
            [symbol_filter] if symbol_filter != 'all'
            else sorted(d for d in os.listdir(backup_dir) if os.path.isdir(os.path.join(backup_dir, d)))
        )

        sent = 0; skipped = 0; errors = 0
        results = []

        for sym in symbols:
            sym_path = os.path.join(backup_dir, sym)
            if not os.path.isdir(sym_path):
                continue

            tf_folders = sorted(os.listdir(sym_path))
            for tf_folder in tf_folders:
                tf_path = os.path.join(sym_path, tf_folder)
                if not os.path.isdir(tf_path):
                    continue
                tf_norm = TF_MAP.get(tf_folder, tf_folder)
                if tf_filter != 'all' and tf_norm != tf_filter and tf_folder != tf_filter:
                    continue

                json_files = sorted([
                    f for f in os.listdir(tf_path)
                    if f.endswith('.json') and '_no_time' not in f
                ])
                if not json_files:
                    skipped += 1
                    continue

                latest = json_files[-1]
                file_path = os.path.join(tf_path, latest)
                try:
                    with open(file_path, 'r', encoding='utf-8') as fp:
                        data = json.load(fp)
                except Exception as e:
                    errors += 1
                    results.append({'symbol': sym, 'tf': tf_folder, 'status': 'error', 'msg': str(e)})
                    continue

                if 'sg' in data and 'clouds' not in data:
                    skipped += 1
                    continue

                # mergeモード: 送信先DBの時刻と比較（送信先がローカルの場合のみ比較可能）
                # replace/mergeどちらもwebhookに送る（サーバー側でDBに上書き保存される）
                try:
                    body = json.dumps(data).encode('utf-8')
                    req_obj = urllib.request.Request(
                        target_url, data=body,
                        headers={'Content-Type': 'application/json'},
                        method='POST'
                    )
                    with urllib.request.urlopen(req_obj, timeout=30) as r:
                        resp_text = r.read().decode()[:80]
                        results.append({'symbol': sym, 'tf': tf_folder, 'file': latest,
                                        'status': 'ok', 'resp': resp_text})
                        sent += 1
                        print(f'[SEND_TO_TARGET] {sym}/{tf_folder} -> {target_url} [{r.status}]')
                except Exception as e:
                    errors += 1
                    results.append({'symbol': sym, 'tf': tf_folder, 'status': 'error', 'msg': str(e)})
                    print(f'[SEND_TO_TARGET ERROR] {sym}/{tf_folder}: {e}')

                import time as _time
                _time.sleep(0.1)  # サーバー負荷軽減

        socketio.emit('update_table', {'message': 'send_to_target completed'})
        print(f'[SEND_TO_TARGET] Done: sent={sent}, skipped={skipped}, errors={errors}, target={target_url}')
        resp = jsonify({
            'status': 'success', 'target': target_url,
            'sent': sent, 'skipped': skipped, 'errors': errors,
            'results': results
        })
        resp.headers['Access-Control-Allow-Origin'] = '*'
        return resp, 200

    except Exception as e:
        import traceback; traceback.print_exc()
        resp = jsonify({'status': 'error', 'msg': str(e)})
        resp.headers['Access-Control-Allow-Origin'] = '*'
        return resp, 500


@app.route('/api/clear_notifications', methods=['POST'])
def api_clear_notifications():
    """Clear all notifications"""
    try:
        notifications_path = os.path.join(BASE_DIR, 'notifications.json')
        
        # Clear notifications file
        with open(notifications_path, 'w', encoding='utf-8') as f:
            json.dump([], f, ensure_ascii=False, indent=2)
        
        print('[API/CLEAR_NOTIFICATIONS] Notifications cleared')
        return jsonify({'status': 'success'}), 200
    except Exception as e:
        print(f'[ERROR][api/clear_notifications] {e}')
        return jsonify({'status': 'error', 'msg': str(e)}), 500

@app.route('/api/market_status', methods=['GET'])
def api_market_status():
    """Get current FX market status"""
    try:
        market_open = is_fx_market_open()
        utc_now = datetime.now(pytz.UTC)
        jst_now = datetime.now(pytz.timezone('Asia/Tokyo'))
        return jsonify({
            'status': 'success',
            'market_open': market_open,
            'utc_time': utc_now.isoformat(),
            'jst_time': jst_now.isoformat()
        }), 200
    except Exception as e:
        print(f'[ERROR][api/market_status] {e}')
        return jsonify({'status': 'error', 'msg': str(e)}), 500

@app.route('/api/clear_fire_history', methods=['POST'])
def api_clear_fire_history():
    """Clear fire history database"""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('DELETE FROM fire_history')
        conn.commit()
        conn.close()
        
        print('[API/CLEAR_FIRE_HISTORY] Fire history cleared')
        return jsonify({'status': 'success'}), 200
    except Exception as e:
        print(f'[ERROR][api/clear_fire_history] {e}')
        return jsonify({'status': 'error', 'msg': str(e)}), 500

@app.route('/api/fire_history')
def api_get_fire_history():
    """Get fire history from database"""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        # Check if direction column exists
        c.execute("PRAGMA table_info(fire_history)")
        columns = [row[1] for row in c.fetchall()]
        has_direction_column = 'direction' in columns
        
        # Get fire history ordered by most recent first
        if has_direction_column:
            c.execute('''SELECT rule_id, symbol, tf, fired_at, conditions_snapshot, last_state_snapshot, direction 
                         FROM fire_history 
                         ORDER BY fired_at DESC 
                         LIMIT 1000''')
        else:
            c.execute('''SELECT rule_id, symbol, tf, fired_at, conditions_snapshot, last_state_snapshot 
                         FROM fire_history 
                         ORDER BY fired_at DESC 
                         LIMIT 1000''')
        
        rows = c.fetchall()
        conn.close()
        
        histories = []
        for row in rows:
            if has_direction_column:
                rule_id, symbol, tf, fired_at, conditions_json, state_json, direction = row
            else:
                rule_id, symbol, tf, fired_at, conditions_json, state_json = row
                direction = None
            
            # Get rule name from rules table
            conn_rule = sqlite3.connect(DB_PATH)
            c_rule = conn_rule.cursor()
            c_rule.execute('SELECT name FROM rules WHERE id = ?', (rule_id,))
            rule_row = c_rule.fetchone()
            conn_rule.close()
            
            rule_name = rule_row[0] if rule_row else '不明'
            
            # directionがNoneの場合のフォールバック（旧データ用）
            if not direction:
                try:
                    conditions = json.loads(conditions_json) if conditions_json else []
                    state_snapshot = json.loads(state_json) if state_json else {}
                    
                    # Determine direction from state snapshot or conditions
                    if state_snapshot:
                        # 優先順位: dauten > gc > bos_count
                        # Check for dauten fields in snapshot
                        for key, value in state_snapshot.items():
                            if 'dauten' in key.lower() and value:
                                if value == 'up':
                                    direction = '上昇'
                                    print(f'[FIRE_HISTORY] Found direction from dauten in snapshot: {direction} (rule={rule_name}, symbol={symbol})')
                                    break
                                elif value == 'down':
                                    direction = '下降'
                                    print(f'[FIRE_HISTORY] Found direction from dauten in snapshot: {direction} (rule={rule_name}, symbol={symbol})')
                                    break
                        
                        # If not found, check gc fields
                        if not direction:
                            for key, value in state_snapshot.items():
                                if 'gc' in key.lower() and value is not None:
                                    if value is True or value == 'true' or value == True:
                                        direction = '上昇'
                                        print(f'[FIRE_HISTORY] Found direction from gc in snapshot: {direction} (rule={rule_name}, symbol={symbol})')
                                        break
                                    elif value is False or value == 'false' or value == False:
                                        direction = '下降'
                                        print(f'[FIRE_HISTORY] Found direction from gc in snapshot: {direction} (rule={rule_name}, symbol={symbol})')
                                        break
                    
                    # If still not found, check conditions
                    if not direction and conditions:
                        for cond in conditions:
                            # 文字列の場合はスキップ（旧データ形式）
                            if isinstance(cond, str):
                                continue
                            if not isinstance(cond, dict):
                                continue
                            
                            field = cond.get('field', '').lower()
                            if 'dauten' in field or 'gc' in field:
                                expected = cond.get('expected')
                                if expected == 'up' or expected == 'true' or expected is True:
                                    direction = '上昇'
                                    print(f'[FIRE_HISTORY] Found direction from conditions: {direction} (rule={rule_name}, symbol={symbol})')
                                    break
                                elif expected == 'down' or expected == 'false' or expected is False:
                                    direction = '下降'
                                    print(f'[FIRE_HISTORY] Found direction from conditions: {direction} (rule={rule_name}, symbol={symbol})')
                                    break
                    
                    if not direction:
                        print(f'[FIRE_HISTORY] No direction found for rule={rule_name}, symbol={symbol}, conditions={len(conditions) if conditions else 0}, snapshot_keys={list(state_snapshot.keys()) if state_snapshot else []}')
                        
                except Exception as e:
                    print(f'[ERROR] Error parsing fire history conditions: {e}')
                    import traceback
                    traceback.print_exc()
            
            histories.append({
                'rule_id': rule_id,
                'rule_name': rule_name,
                'symbol': symbol,
                'tf': tf,
                'timestamp': fired_at,
                'direction': direction
            })
        
        print(f'[API/FIRE_HISTORY] Retrieved {len(histories)} fire history records')
        return jsonify({'status': 'success', 'histories': histories}), 200
    except Exception as e:
        print(f'[ERROR][api/fire_history] {e}')
        import traceback
        traceback.print_exc()
        return jsonify({'status': 'error', 'msg': str(e)}), 500

@app.route('/api/webhook_logs')
def api_webhook_logs():
    try:
        log_path = os.path.join(BASE_DIR, 'webhook_log.txt')
        if not os.path.exists(log_path):
            return jsonify({'status': 'success', 'logs': []}), 200
        
        with open(log_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # 最新50件を返す
        return jsonify({'status': 'success', 'logs': lines[-50:]}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'msg': str(e)}), 500

def evaluate_and_fire_rules(data, symbol, tf_val):
    """Evaluate all enabled rules against the incoming data and fire notifications if matched.
    
    各タイムフレーム（5, 15, 60, 240）のJSONについて、独立してルール評価を実行。
    - tf=5 の場合：全雲情報を含むため、通常のルール評価
    - tf=15,60,240 の場合：当該時間足のダウ転・突破数・時間情報でルール評価
    """
    def wlog(msg):
        """Debug message to both console and file"""
        print(msg)
        try:
            with open(os.path.join(BASE_DIR, 'webhook_error.log'), 'a', encoding='utf-8') as f:
                f.write(f'{msg}\n')
        except:
            pass
    
    try:
        global FIRST_RECEIVE_FLAGS, SERVER_START_TIME
        jst = pytz.timezone('Asia/Tokyo')
        wlog(f'[EVALUATE] Starting rule evaluation for {symbol}/{tf_val}')
        
        # サーバー起動後のデータのみ評価（起動前のデータはスキップ）
        if SERVER_START_TIME is not None:
            webhook_time_ms = data.get('time', 0)
            if webhook_time_ms > 0:
                webhook_time = datetime.fromtimestamp(webhook_time_ms / 1000, tz=pytz.UTC)
                if webhook_time < SERVER_START_TIME:
                    wlog(f'[STARTUP_CHECK] Data from before server startup ({webhook_time.isoformat()} < {SERVER_START_TIME.isoformat()}), skipping evaluation')
                    return
        
        # 受信タイムフレームのラベルを取得
        tf_label_map = {'5': '5m', '15': '15m', '60': '1H', '240': '4H'}
        received_tf_label = tf_label_map.get(tf_val, tf_val)
        
        # 初回受信チェック（symbol + tf の組み合わせで管理）
        tf_key = f'{symbol}_{received_tf_label}'
        is_first_receive = tf_key not in FIRST_RECEIVE_FLAGS
        
        if is_first_receive:
            wlog(f'[FIRST_RECEIVE] First data reception for {symbol}/{received_tf_label}')
            FIRST_RECEIVE_FLAGS[tf_key] = True
        else:
            wlog(f'[RECEIVE] Subsequent data reception for {symbol}/{received_tf_label}')
        
        # 全タイムフレームの最新データをDBから取得
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        # 5m, 15m, 1H, 4H の全データを取得
        tf_states = {}
        base_cols = None
        for tf_key, tf_label in [('5', '5m'), ('15', '15m'), ('60', '1H'), ('240', '4H')]:
            c.execute('SELECT * FROM states WHERE symbol = ? AND tf = ? ORDER BY rowid DESC LIMIT 1', (symbol, tf_key))
            tf_row = c.fetchone()
            if tf_row:
                if base_cols is None:
                    base_cols = [d[0] for d in c.description] if c.description else []
                tf_state = dict(zip(base_cols, tf_row))
                tf_states[tf_label] = tf_state
        
        conn.close()
        
        if not tf_states:
            wlog(f'[FIRE] No state data found for {symbol} in database')
            return
        
        wlog(f'[FIRE] Retrieved states from DB for {symbol}: {list(tf_states.keys())}')
        wlog(f'[DEBUG] Calling _evaluate_rules_with_db_state for {symbol}')
        
        # webhook JSON の clouds 配列から受信したタイムフレームのデータを抽出
        current_cloud = None
        clouds = data.get('clouds', [])
        if clouds:
            # tf_val に対応する tf_label を作成
            tf_label = {'5': '5m', '15': '15m', '60': '1H', '240': '4H'}.get(tf_val, tf_val)
            # clouds 配列から該当するタイムフレームを検索
            for cloud in clouds:
                if cloud.get('label') == tf_label or cloud.get('tf') == tf_label:
                    current_cloud = cloud
                    wlog(f'[DEBUG] Found current cloud for {tf_label}: dauten={cloud.get("dauten")}, gc={cloud.get("gc")}')
                    break
        
        if not current_cloud:
            wlog(f'[WARNING] No cloud data found in webhook for tf={tf_val}')
        
        # 5mのJSONには全TFのデータが含まれているので、全て抽出
        all_clouds = {}
        if clouds:
            for cloud in clouds:
                label = cloud.get('label')
                if label in ['5m', '15m', '1H', '4H']:
                    all_clouds[label] = cloud
                    wlog(f'[DEBUG] Extracted cloud from webhook: {label} - dauten={cloud.get("dauten")}, gc={cloud.get("gc")}')
        
        # 統合データを使用してルール評価（初回受信フラグを渡す）
        _evaluate_rules_with_db_state(tf_states, symbol, all_clouds, tf_val, is_first_receive)
        wlog(f'[DEBUG] _evaluate_rules_with_db_state completed for {symbol}')
        
    except Exception as e:
        wlog(f'[ERROR] evaluate_and_fire_rules: {e}')
        import traceback
        traceback.print_exc()


def _evaluate_rules_with_db_state(tf_states, symbol, all_clouds=None, current_tf=None, is_first_receive=False):
    """DBから取得した全タイムフレームのデータを使用してルール評価
    
    表に表示されている現在値を基にルール判定
    - 5mのDBレコードには雲情報（gc, thickness等）
    - 各TF（15m, 1H, 4H）のDBレコードにはそのTFのダウ転換情報
    all_clouds: webhook から受け取った全TFのクラウドデータ {tf_label: cloud_data, ...}
    is_first_receive: このタイムフレーム・通貨ペアの組み合わせで初回受信かどうか
    """
    # Simple inline logging function - writes directly to file
    def wlog(msg):
        """Write log directly to file"""
        try:
            with open(os.path.join(BASE_DIR, 'webhook_error.log'), 'a', encoding='utf-8') as f:
                f.write(f'[RULE_V3] {msg}\n')
                f.flush()
        except:
            pass
    
    wlog('===== FUNCTION ENTRY =====')
    
    try:
        # tf_label -> {field: value, ...} のマッピングを作成
        # 表の視覚的内容を正確に反映するため、各TFのDBレコードから取得
        tf_cloud_data = {}
        
        wlog(f'[DEBUG] all_clouds={list(all_clouds.keys()) if all_clouds else None}, current_tf={current_tf}')
        
        # 1. まず5mのDBレコードから全TFの雲情報（gc, thickness等）を取得
        tf_state_5m = tf_states.get('5m')
        if tf_state_5m:
            clouds_json_str = tf_state_5m.get('clouds_json', '[]')
            try:
                clouds = json.loads(clouds_json_str)
                for cloud in clouds:
                    label = cloud.get('label')
                    if label in ['5m', '15m', '1H', '4H']:
                        tf_cloud_data[label] = cloud.copy()
                        wlog(f'[DB] Loaded cloud data for {label} from 5m DB: gc={cloud.get("gc")}, dauten={cloud.get("dauten")}')
            except Exception as e:
                wlog(f'[ERROR] Failed to parse 5m clouds_json: {e}')
        
        # 2. 各TF（15m, 1H, 4H）のDBレコードからダウ転換情報を上書き（これが表の視覚的内容）
        for tf_key, tf_label in [('15', '15m'), ('60', '1H'), ('240', '4H')]:
            tf_state = tf_states.get(tf_label)
            if tf_state:
                clouds_json_str = tf_state.get('clouds_json', '[]')
                try:
                    clouds = json.loads(clouds_json_str)
                    if clouds:
                        tf_cloud = clouds[0]  # 各TFのレコードには1つのクラウドのみ
                        if tf_label in tf_cloud_data:
                            # ダウ転換情報を上書き
                            tf_cloud_data[tf_label]['dauten'] = tf_cloud.get('dauten')
                            tf_cloud_data[tf_label]['bos_count'] = tf_cloud.get('bos_count')
                            tf_cloud_data[tf_label]['dauten_start_time'] = tf_cloud.get('dauten_start_time')
                            wlog(f'[DB] Overwrote dauten for {tf_label} from {tf_label} DB: dauten={tf_cloud.get("dauten")}, bos={tf_cloud.get("bos_count")}')
                        else:
                            tf_cloud_data[tf_label] = tf_cloud.copy()
                            wlog(f'[DB] Loaded {tf_label} data from {tf_label} DB: dauten={tf_cloud.get("dauten")}')
                except Exception as e:
                    wlog(f'[ERROR] Failed to parse {tf_label} clouds_json: {e}')
        
        # 3. webhook から受け取ったデータで上書き（最新データ優先）
        # 主体時間足（5m/15m/1H）のWebhookには全TFの最新雲情報が含まれている
        # そのため、Webhookデータを優先的に使用（表の実際の表示内容と一致）
        if all_clouds:
            for tf_label, cloud in all_clouds.items():
                if tf_label in tf_cloud_data:
                    # Webhookの最新データで全て上書き（dautenも含む）
                    tf_cloud_data[tf_label].update(cloud)
                    wlog(f'[WEBHOOK] Updated {tf_label} with webhook data: dauten={cloud.get("dauten")}, gc={cloud.get("gc")}, elapsed_str={cloud.get("elapsed_str")}')
                else:
                    tf_cloud_data[tf_label] = cloud.copy()
                    wlog(f'[WEBHOOK] Added {tf_label} from webhook: dauten={cloud.get("dauten")}, gc={cloud.get("gc")}, elapsed_str={cloud.get("elapsed_str")}')
        
        wlog(f'[DEBUG] tf_cloud_data final keys: {list(tf_cloud_data.keys())}')
        for tf_label, data in tf_cloud_data.items():
            wlog(f'[DEBUG] {tf_label}: dauten={data.get("dauten")}, gc={data.get("gc")}')
        
        # ルールを取得
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('SELECT id, name, enabled, scope_json, rule_json FROM rules WHERE enabled = 1')
        rows = c.fetchall()
        conn.close()
        
        if not rows:
            print('[FIRE] No enabled rules')
            return
        
        print(f'[FIRE] Evaluating {len(rows)} enabled rules for {symbol} using DB state')
        
        jst = pytz.timezone('Asia/Tokyo')
        fired_notifications = []
        for row in rows:
            rule_id, rule_name, enabled, scope_json, rule_json = row
            try:
                scope = json.loads(scope_json) if scope_json else {}
                rule = json.loads(rule_json) if rule_json else {}
                
                # ルールの音声設定を取得
                voice_settings = rule.get('voice', {})
                
                # フロントエンド互換のためキー名を統一（camelCase -> snake_case）
                # chime -> chime_file
                if voice_settings.get('chime') and not voice_settings.get('chime_file'):
                    voice_settings['chime_file'] = voice_settings['chime']
                # voiceFile -> voice_file
                if voice_settings.get('voiceFile') and not voice_settings.get('voice_file'):
                    voice_settings['voice_file'] = voice_settings['voiceFile']
                # insertSymbol -> insert_symbol
                if voice_settings.get('insertSymbol') and not voice_settings.get('insert_symbol'):
                    voice_settings['insert_symbol'] = voice_settings['insertSymbol']
                # symbolInsertPosition -> symbol_insert_position
                if voice_settings.get('symbolInsertPosition') and not voice_settings.get('symbol_insert_position'):
                    voice_settings['symbol_insert_position'] = voice_settings['symbolInsertPosition']
                # directionBased -> direction_based
                if voice_settings.get('directionBased') and not voice_settings.get('direction_based'):
                    voice_settings['direction_based'] = voice_settings['directionBased']
                # messagePosition -> message_position
                if voice_settings.get('messagePosition') and not voice_settings.get('message_position'):
                    voice_settings['message_position'] = voice_settings['messagePosition']
                # messageUp -> message_up
                if voice_settings.get('messageUp') and not voice_settings.get('message_up'):
                    voice_settings['message_up'] = voice_settings['messageUp']
                # messageDown -> message_down
                if voice_settings.get('messageDown') and not voice_settings.get('message_down'):
                    voice_settings['message_down'] = voice_settings['messageDown']
                # playChimeFirst -> play_chime_first
                if voice_settings.get('playChimeFirst') and not voice_settings.get('play_chime_first'):
                    voice_settings['play_chime_first'] = voice_settings['playChimeFirst']
                
                wlog(f'[RULE] Processing rule "{rule_name}" scope={scope}')
                wlog(f'[RULE] Voice settings: {voice_settings}')
                
                # Check scope: if scope has symbol, must match
                if scope.get('symbol') and scope['symbol'] != symbol:
                    wlog(f'[RULE] Rule "{rule_name}" skipped: scope symbol mismatch ({scope.get("symbol")} != {symbol})')
                    continue
                
                wlog(f'[RULE] Testing rule "{rule_name}" for {symbol}')
                
                # ルール条件を評価（AND条件：すべての条件が満たされる必要がある）
                conditions = rule.get('conditions', [])
                all_matched = True
                matched_conditions = []
                
                # 複数条件の場合、各条件から方向を収集
                condition_directions = []
                
                wlog(f'[RULE][V4_FIXED] Evaluating {len(conditions)} conditions')
                
                for cond in conditions:
                    tf_label = cond.get('timeframe') or cond.get('label')  # '5m', '15m', '1H', '4H'
                    field = cond.get('field')      # 'dauten', 'bos_count', 'gc' など
                    value = cond.get('value')      # 期待値
                    
                    # クラウドデータから値を取得
                    cloud_data = tf_cloud_data.get(tf_label)
                    if cloud_data is None:
                        wlog(f'[RULE] Cloud data not available for {tf_label}')
                        all_matched = False
                        break
                    
                    found_value = cloud_data.get(field)
                    
                    # 条件をチェック
                    condition_met = False
                    # 空文字列('')も「存在チェック」として扱う
                    is_presence_check = (value is None) or (value == '') or (str(value).strip() == '')
                    if is_presence_check:
                        # Presence check: フィールドが存在し、有効な値を持つかチェック
                        if field == 'gc':
                            # gcはTrue/Falseが有効値
                            condition_met = found_value is not None
                        elif field == 'dauten':
                            # dautenは'up'または'down'が有効値
                            condition_met = found_value in ['up', 'down']
                        elif field == 'bos_count':
                            # bos_countは0以外の値が有効
                            condition_met = found_value is not None and found_value != 0 and found_value != '0'
                        else:
                            condition_met = found_value is not None and found_value != ''
                    else:
                        # Value check: 値が一致するかチェック
                        condition_met = found_value == value
                    
                    if condition_met:
                        matched_conditions.append(cond)
                        wlog(f'[RULE] Condition met: {tf_label}.{field} = {found_value}')
                        
                        # 各フィールドから方向を判定
                        direction = None
                        if field == 'dauten':
                            if found_value == 'up':
                                direction = 'up'
                            elif found_value == 'down':
                                direction = 'down'
                        elif field == 'gc':
                            # gc=True は上昇（青）、gc=False は下降（赤）
                            if found_value is True:
                                direction = 'up'
                            elif found_value is False:
                                direction = 'down'
                        elif field == 'bos_count':
                            # bos_count自体には方向情報がないので、同じTFのdautenから方向を取得
                            # bos_countは常に0以上の整数なので、方向はdautenに依存
                            cloud_for_bos = tf_cloud_data.get(tf_label, {})
                            dauten_for_bos = cloud_for_bos.get('dauten')
                            if dauten_for_bos == 'up':
                                direction = 'up'
                            elif dauten_for_bos == 'down':
                                direction = 'down'
                            wlog(f'[RULE] bos_count direction from dauten: {dauten_for_bos} -> {direction}')
                        
                        condition_directions.append(direction)
                        wlog(f'[RULE] Added direction: {direction}')
                    else:
                        all_matched = False
                        wlog(f'[RULE] Condition not met: {tf_label}.{field} (found={found_value}, expected={value})')
                        break
                
                # 複数条件の場合、方向の整合性をチェック
                wlog(f'[RULE] === Direction check START === all_matched={all_matched}, num_conditions={len(conditions)}, directions={condition_directions}')
                if all_matched and len(conditions) > 1:
                    # None以外の方向を収集
                    valid_directions = [d for d in condition_directions if d is not None]
                    wlog(f'[RULE] Valid directions: {valid_directions}')
                    
                    if len(valid_directions) > 1:
                        # 方向が複数ある場合、すべて同じ方向かチェック
                        if len(set(valid_directions)) > 1:
                            # 方向が一致していない
                            all_matched = False
                            wlog(f'[RULE] Direction mismatch: {valid_directions} - not firing')
                        else:
                            wlog(f'[RULE] Direction aligned: {valid_directions[0]}')
                    elif len(valid_directions) == 1:
                        wlog(f'[RULE] Single direction: {valid_directions[0]}')
                    else:
                        wlog(f'[RULE] No direction info available')
                
                # ===== Alignment チェック =====
                # ルールに alignment 設定がある場合、cloud_order の並び順をチェック
                # cloudAlign (新形式) または alignment (旧形式) をサポート
                alignment_config = rule.get('cloudAlign') or rule.get('alignment')
                alignment_direction = None  # 整列の方向（'上昇' or '下降'）
                current_tf_order = None  # 現在のTF順序（価格を除外）
                
                # alignment_configが有効かどうかを判定（allTimeframes=True または timeframes/tfsが指定されている場合）
                alignment_is_active = False
                if alignment_config:
                    tfs_check = alignment_config.get('timeframes') or alignment_config.get('tfs', [])
                    if alignment_config.get('allTimeframes') or (tfs_check and len(tfs_check) > 0):
                        alignment_is_active = True
                
                if alignment_is_active and all_matched:
                    wlog(f'[RULE] Checking alignment: {alignment_config}')
                    
                    # timeframes (new) または tfs (old) をサポート
                    tfs = alignment_config.get('timeframes') or alignment_config.get('tfs', [])  # ['5m', '15m', '1H', '4H']
                    
                    # allTimeframesがTrueの場合、全タイムフレームを使用
                    if alignment_config.get('allTimeframes') and not tfs:
                        tfs = ['5m', '15m', '1H', '4H']
                    
                    # DBから現在の cloud_order を取得
                    conn_order = sqlite3.connect(DB_PATH)
                    c_order = conn_order.cursor()
                    c_order.execute('SELECT cloud_order FROM states WHERE symbol = ? AND tf = ? LIMIT 1', (symbol, '5'))
                    row_order = c_order.fetchone()
                    conn_order.close()
                    
                    if row_order and row_order[0]:
                        cloud_order_str = row_order[0]  # '5m,15m,1H,4H,価格' のような文字列
                        cloud_order = [x.strip() for x in cloud_order_str.split(',')]
                        
                        # 「価格」を除外してTFのみ抽出
                        cloud_order_tfs = [x for x in cloud_order if x in ['5m', '15m', '1H', '4H']]
                        
                        # 選択されたTFのみを抽出（順序を保持）
                        selected_order = [x for x in cloud_order_tfs if x in tfs]
                        
                        # 現在のTF順序を保存（価格除外）
                        current_tf_order = ','.join(selected_order)
                        
                        # 期待する昇順と降順
                        expected_asc = tfs  # ['5m', '15m', '1H', '4H']
                        expected_desc = list(reversed(tfs))  # ['4H', '1H', '15m', '5m']
                        
                        # 整列判定
                        is_aligned = (selected_order == expected_asc or selected_order == expected_desc)
                        
                        if is_aligned:
                            # 整列方向を判定
                            if selected_order == expected_asc:
                                alignment_direction = '上昇'
                            else:
                                alignment_direction = '下降'
                            wlog(f'[RULE] Alignment OK: {selected_order} matches expected order (direction={alignment_direction})')
                        else:
                            all_matched = False
                            wlog(f'[RULE] Alignment failed: {selected_order} does not match expected order (asc={expected_asc}, desc={expected_desc})')
                    else:
                        all_matched = False
                        wlog(f'[RULE] Alignment failed: cloud_order not found in DB')
                
                wlog(f'[RULE] Rule "{rule_name}" result: all_matched={all_matched}')

                
                # ===== 値を正規化する関数（比較と保存で共通使用）=====
                def normalize_value_for_comparison(val, field_name):
                    """値を比較用に正規化する"""
                    if val is None:
                        return None
                    
                    # bos_count の場合: 数値に統一
                    # インジケーター形式: 0, 1, 2, 3 など（数値）
                    # 表示形式: "-", "BOS-1", "BOS-2" など
                    if field_name == 'bos_count':
                        if isinstance(val, (int, float)):
                            return int(val)  # 0も含めて数値として保持
                        if isinstance(val, str):
                            val_str = str(val).strip()
                            if val_str == '-' or val_str == '' or val_str.lower() == 'none':
                                return 0  # "-" は 0 として扱う
                            # "BOS-1" → 1, "BOS-2" → 2
                            if 'BOS-' in val_str.upper():
                                try:
                                    return int(val_str.upper().replace('BOS-', ''))
                                except:
                                    return 0
                            try:
                                return int(float(val_str))
                            except:
                                return 0
                        return 0
                    
                    # gc の場合: boolean に統一
                    if field_name == 'gc':
                        if isinstance(val, bool):
                            return val
                        if isinstance(val, str):
                            return val.lower() in ('true', '1', 'yes', 'gc')
                        return bool(val)
                    
                    # dauten の場合: 'up'/'down' に統一
                    if field_name == 'dauten':
                        if isinstance(val, str):
                            val_lower = val.lower()
                            if 'up' in val_lower or '上' in val_lower:
                                return 'up'
                            if 'down' in val_lower or '下' in val_lower:
                                return 'down'
                        return val
                    
                    return val

                # ===== 発火判定ロジック（条件揃い状態に関わらず実行）=====
                num_conditions = len(conditions)
                should_fire = False
                
                # ===== 前回の発火状態を取得 =====
                # 発火した記録のみがfire_historyに保存されているため、最新の発火時の状態と比較
                conn_check = sqlite3.connect(DB_PATH)
                c_check = conn_check.cursor()
                c_check.execute('''SELECT last_state_snapshot FROM fire_history 
                                   WHERE rule_id = ? AND symbol = ? AND tf = ?
                                   ORDER BY fired_at DESC LIMIT 1''', 
                               (rule_id, symbol, ''))
                last_fire = c_check.fetchone()
                conn_check.close()
                
                last_state = None
                
                if last_fire and last_fire[0]:
                    try:
                        last_state = json.loads(last_fire[0])
                    except:
                        last_state = None
                
                # ===== 今回の条件揃い状態 =====
                current_conditions_matched = all_matched
                
                # ===== 発火判定ロジック =====
                # 「条件が崩れてから再度揃った」場合に発火
                # 1. 条件を満たしている (all_matched=True)
                # 2. かつ、前回発火時に条件が揃っていなかった、または明確な変化がある
                
                should_fire = False
                
                # ===== ウォームアップ期間チェック =====
                # サーバー起動後60秒以内は発火をスキップ（再起動時の誤発火防止）
                utc_now = datetime.now(pytz.UTC)
                wlog(f'[RULE] Checking warmup: SERVER_START_TIME={SERVER_START_TIME}, utc_now={utc_now}')
                
                if SERVER_START_TIME is None:
                    # SERVER_START_TIMEが未設定の場合は安全のため発火をスキップ
                    wlog(f'[RULE] SERVER_START_TIME is None, skipping fire for safety')
                    continue
                
                seconds_since_startup = (utc_now - SERVER_START_TIME).total_seconds()
                in_warmup_period = seconds_since_startup < 60
                wlog(f'[RULE] Warmup check: seconds_since_startup={seconds_since_startup:.1f}, in_warmup={in_warmup_period}')
                
                if in_warmup_period:
                    wlog(f'[RULE] In warmup period ({seconds_since_startup:.1f}s since startup), skipping fire')
                    # ウォームアップ期間中は発火せず、状態のみ記録
                    if all_matched:
                        # 現在の状態をスナップショットとして保存（次回の比較用）
                        state_snapshot = {
                            'symbol': symbol,
                            'conditions': str(conditions),
                            '__conditions_matched__': True,
                            '__warmup_record__': True
                        }
                        
                        # Alignment ルールの場合は tf_order を保存
                        if alignment_is_active and current_tf_order:
                            state_snapshot['tf_order'] = current_tf_order
                        
                        # 各条件のフィールド値を保存
                        for cond in conditions:
                            tf_label = cond.get('timeframe') or cond.get('label')
                            field = cond.get('field')
                            cond_cloud_data = tf_cloud_data.get(tf_label, {})
                            raw_value = cond_cloud_data.get(field)
                            normalized_value = normalize_value_for_comparison(raw_value, field)
                            state_snapshot[f'{tf_label}.{field}'] = normalized_value
                        
                        # fire_historyに記録（発火ではなく状態記録として）
                        try:
                            conn_warmup = sqlite3.connect(DB_PATH)
                            c_warmup = conn_warmup.cursor()
                            c_warmup.execute('''INSERT INTO fire_history 
                                             (rule_id, symbol, tf, fired_at, conditions_snapshot, last_state_snapshot)
                                             VALUES (?, ?, ?, ?, ?, ?)''',
                                          (rule_id, symbol, '', datetime.now(jst).isoformat(),
                                           json.dumps({'warmup': True}, ensure_ascii=False),
                                           json.dumps(state_snapshot, ensure_ascii=False)))
                            conn_warmup.commit()
                            conn_warmup.close()
                            wlog(f'[RULE] Warmup state recorded for rule {rule_name}')
                        except Exception as e:
                            wlog(f'[RULE] Error recording warmup state: {e}')
                    wlog(f'[RULE] Skipping rule evaluation during warmup period')
                    continue  # 次のルールへ
                
                # ===== 初回受信チェック =====
                # サーバー起動後、各タイムフレームで初めてデータを受信した時の処理
                # ただし、過去の履歴（last_state）がある場合は通常評価を行う
                # （新しい変化があれば発火する必要があるため - 特に4H足で重要）
                if is_first_receive and last_state is None:
                    wlog(f'[RULE] First receive with no history, recording state without firing')
                    # 完全な初回（履歴なし）の場合のみ発火をスキップ
                    if all_matched:
                        state_snapshot = {
                            'symbol': symbol,
                            'conditions': str(conditions),
                            '__conditions_matched__': True,
                            '__first_receive_record__': True
                        }
                        
                        # Alignment ルールの場合は tf_order を保存
                        if alignment_is_active and current_tf_order:
                            state_snapshot['tf_order'] = current_tf_order
                        
                        # 各条件のフィールド値を保存
                        for cond in conditions:
                            tf_label = cond.get('timeframe') or cond.get('label')
                            field = cond.get('field')
                            cond_cloud_data = tf_cloud_data.get(tf_label, {})
                            raw_value = cond_cloud_data.get(field)
                            normalized_value = normalize_value_for_comparison(raw_value, field)
                            state_snapshot[f'{tf_label}.{field}'] = normalized_value
                        
                        # fire_historyに記録
                        try:
                            conn_first = sqlite3.connect(DB_PATH)
                            c_first = conn_first.cursor()
                            c_first.execute('''INSERT INTO fire_history 
                                             (rule_id, symbol, tf, fired_at, conditions_snapshot, last_state_snapshot)
                                             VALUES (?, ?, ?, ?, ?, ?)''',
                                          (rule_id, symbol, '', datetime.now(jst).isoformat(),
                                           json.dumps({'first_receive': True}, ensure_ascii=False),
                                           json.dumps(state_snapshot, ensure_ascii=False)))
                            conn_first.commit()
                            conn_first.close()
                            wlog(f'[RULE] First receive state recorded for rule {rule_name}')
                        except Exception as e:
                            wlog(f'[RULE] Error recording first receive state: {e}')
                    wlog(f'[RULE] Skipping rule evaluation for first receive (no history)')
                    continue  # 次のルールへ
                elif is_first_receive and last_state is not None:
                    # 初回受信だが過去の履歴がある場合
                    # サーバー再起動直後のケース：履歴が最近（例：1時間以内）の場合は発火をスキップ
                    # 古い履歴（例：4H足で8時間以上前）の場合のみ通常評価
                    last_fired_at_str = last_state.get('__fired_at__')
                    skip_fire = False
                    if last_fired_at_str:
                        try:
                            last_fired_at = datetime.fromisoformat(last_fired_at_str.replace('Z', '+00:00'))
                            jst = pytz.timezone('Asia/Tokyo')
                            now = datetime.now(jst)
                            if last_fired_at.tzinfo is None:
                                last_fired_at = jst.localize(last_fired_at)
                            time_since_last_fire = now - last_fired_at
                            
                            # 時間足に応じて猶予期間を設定
                            grace_period_hours = 2  # デフォルト2時間
                            if '4H' in str(conditions):
                                grace_period_hours = 6  # 4H足は6時間
                            elif '1H' in str(conditions):
                                grace_period_hours = 3  # 1H足は3時間
                            
                            if time_since_last_fire.total_seconds() < grace_period_hours * 3600:
                                skip_fire = True
                                wlog(f'[RULE] First receive but last fire was recent ({time_since_last_fire.total_seconds() / 3600:.1f}h ago), skipping to avoid duplicate')
                        except Exception as e:
                            wlog(f'[RULE] Error checking last fire time: {e}')
                    
                    if skip_fire:
                        # 最近発火済みの場合はスキップ
                        wlog(f'[RULE] Skipping evaluation for first receive (recent history)')
                        continue  # 次のルールへ
                    else:
                        # 古い履歴の場合は通常評価を継続
                        wlog(f'[RULE] First receive but history is old, evaluating normally (may fire if changed)')
                
                if all_matched:
                    # 条件を満たしている場合、前回の状態をチェック
                    has_field_change = False
                    
                    if last_state is None:
                        # 初回評価の場合は発火せず、状態を記録するのみ
                        # （次回以降の変化検出のため）
                        wlog(f'[RULE] First evaluation with matched conditions, recording state without firing')
                        has_field_change = False  # 発火しない
                    elif last_state.get('__conditions_matched__') == False:
                        # 前回発火時は条件が崩れていた → 今回揃ったので発火
                        has_field_change = True
                        wlog(f'[RULE] Conditions were not matched last time, now matched, should_fire=True')
                    else:
                        # Alignment ルールの場合は TF順序（価格除外）の変化をチェック
                        if alignment_is_active:
                            # 現在のTF順序を取得（価格除外）
                            conn_order_check = sqlite3.connect(DB_PATH)
                            c_order_check = conn_order_check.cursor()
                            c_order_check.execute('SELECT cloud_order FROM states WHERE symbol = ? AND tf = ? LIMIT 1', (symbol, '5'))
                            row_order_check = c_order_check.fetchone()
                            conn_order_check.close()
                            
                            if row_order_check and row_order_check[0]:
                                cloud_order_str = row_order_check[0]
                                cloud_order = [x.strip() for x in cloud_order_str.split(',')]
                                # 価格を除外してTFのみ抽出
                                cloud_order_tfs = [x for x in cloud_order if x in ['5m', '15m', '1H', '4H']]
                                tfs = alignment_config.get('timeframes') or alignment_config.get('tfs', [])
                                if alignment_config.get('allTimeframes') and not tfs:
                                    tfs = ['5m', '15m', '1H', '4H']
                                selected_order = [x for x in cloud_order_tfs if x in tfs]
                                current_tf_order = ','.join(selected_order)
                            else:
                                current_tf_order = ''
                            
                            last_tf_order = last_state.get('tf_order', '')
                            
                            # TF順序が変化し、かつ現在整列している場合に発火
                            if current_tf_order != last_tf_order:
                                has_field_change = True
                                wlog(f'[RULE] TF order change detected: {last_tf_order} → {current_tf_order}')
                            else:
                                wlog(f'[RULE] TF order unchanged: {current_tf_order}')
                        else:
                            # 通常のルール: 各条件のフィールド値が変化したかチェック
                            for cond in conditions:
                                tf_label = cond.get('timeframe') or cond.get('label')
                                field = cond.get('field')
                                field_key = f'{tf_label}.{field}'
                                
                                current_value = tf_cloud_data.get(tf_label, {}).get(field)
                                last_value = last_state.get(field_key)
                                
                                # 値を正規化して比較（外側で定義したnormalize_value_for_comparisonを使用）
                                normalized_current = normalize_value_for_comparison(current_value, field)
                                normalized_last = normalize_value_for_comparison(last_value, field)
                                
                                if normalized_current != normalized_last:
                                    has_field_change = True
                                    wlog(f'[RULE] Field change detected: {field_key} = {last_value}({normalized_last}) → {current_value}({normalized_current})')
                                    break
                                else:
                                    wlog(f'[RULE] Field unchanged: {field_key} = {normalized_current}')
                        
                        if not has_field_change:
                            wlog(f'[RULE] Conditions matched but no field change, should_fire=False')
                    
                    should_fire = has_field_change
                    
                    # 初回評価の場合は状態を記録（発火はしない）
                    if last_state is None and all_matched:
                        wlog(f'[RULE] Recording initial state for rule {rule_name}')
                        state_snapshot = {
                            'symbol': symbol,
                            'conditions': str(conditions),
                            '__conditions_matched__': True,
                            '__initial_record__': True
                        }
                        
                        # Alignment ルールの場合は tf_order を保存
                        if alignment_is_active and current_tf_order:
                            state_snapshot['tf_order'] = current_tf_order
                        
                        # 各条件のフィールド値を保存
                        for cond in conditions:
                            tf_label = cond.get('timeframe') or cond.get('label')
                            field = cond.get('field')
                            cond_cloud_data = tf_cloud_data.get(tf_label, {})
                            raw_value = cond_cloud_data.get(field)
                            normalized_value = normalize_value_for_comparison(raw_value, field)
                            state_snapshot[f'{tf_label}.{field}'] = normalized_value
                        
                        try:
                            conn_init = sqlite3.connect(DB_PATH)
                            c_init = conn_init.cursor()
                            c_init.execute('''INSERT INTO fire_history 
                                             (rule_id, symbol, tf, fired_at, conditions_snapshot, last_state_snapshot)
                                             VALUES (?, ?, ?, ?, ?, ?)''',
                                          (rule_id, symbol, '', datetime.now(jst).isoformat(),
                                           json.dumps({'initial_record': True}, ensure_ascii=False),
                                           json.dumps(state_snapshot, ensure_ascii=False)))
                            conn_init.commit()
                            conn_init.close()
                            wlog(f'[RULE] Initial state recorded for rule {rule_name}')
                        except Exception as e:
                            wlog(f'[RULE] Error recording initial state: {e}')
                else:
                    wlog(f'[RULE] Conditions not matched, should_fire=False')
                    
                    # ===== 条件が崩れた時の処理 =====
                    # 前回発火時に条件が揃っていた場合、「崩れた」ことを記録
                    # これにより、次回揃った時に再発火できる
                    if last_state and last_state.get('__conditions_matched__') == True:
                        wlog(f'[RULE] Conditions were matched last time, now not matched, recording state reset')
                        try:
                            conn_reset = sqlite3.connect(DB_PATH)
                            c_reset = conn_reset.cursor()
                            jst = pytz.timezone('Asia/Tokyo')
                            reset_snapshot = {
                                'symbol': symbol,
                                '__conditions_matched__': False,
                                '__reset_reason__': 'conditions_no_longer_matched'
                            }
                            c_reset.execute('''INSERT INTO fire_history 
                                             (rule_id, symbol, tf, fired_at, conditions_snapshot, last_state_snapshot)
                                             VALUES (?, ?, ?, ?, ?, ?)''',
                                          (rule_id, symbol, '', datetime.now(jst).isoformat(),
                                           json.dumps({'reset': True}, ensure_ascii=False),
                                           json.dumps(reset_snapshot, ensure_ascii=False)))
                            conn_reset.commit()
                            conn_reset.close()
                            wlog(f'[RULE] State reset recorded for rule {rule_name}')
                        except Exception as e:
                            wlog(f'[RULE] Error recording state reset: {e}')
                
                # ===== 発火処理 =====
                if should_fire:
                    wlog(f'[RULE] [OK] FIRING Rule: {rule_name}')
                    
                    # 状態スナップショットに__conditions_matched__フラグを追加
                    state_snapshot = {
                        'symbol': symbol,
                        'conditions': str(conditions),
                        '__conditions_matched__': current_conditions_matched,
                        '__fired_at__': datetime.now(jst).isoformat()
                    }
                    
                    # Alignment ルールの場合は tf_order（価格除外のTF順序）を保存
                    if alignment_is_active:
                        conn_order_snap = sqlite3.connect(DB_PATH)
                        c_order_snap = conn_order_snap.cursor()
                        c_order_snap.execute('SELECT cloud_order FROM states WHERE symbol = ? AND tf = ? LIMIT 1', (symbol, '5'))
                        row_order_snap = c_order_snap.fetchone()
                        conn_order_snap.close()
                        
                        if row_order_snap and row_order_snap[0]:
                            cloud_order_str = row_order_snap[0]
                            cloud_order = [x.strip() for x in cloud_order_str.split(',')]
                            # 価格を除外してTFのみ抽出
                            cloud_order_tfs = [x for x in cloud_order if x in ['5m', '15m', '1H', '4H']]
                            tfs = alignment_config.get('timeframes') or alignment_config.get('tfs', [])
                            if alignment_config.get('allTimeframes') and not tfs:
                                tfs = ['5m', '15m', '1H', '4H']
                            selected_order = [x for x in cloud_order_tfs if x in tfs]
                            state_snapshot['tf_order'] = ','.join(selected_order)
                            # cloud_order も参考として保存（ログ用）
                            state_snapshot['cloud_order'] = row_order_snap[0]
                    
                    # 各条件のタイムフレームごとにcloud_dataを追加（正規化した値を保存）
                    for cond in conditions:
                        tf_label = cond.get('timeframe') or cond.get('label')
                        field = cond.get('field')
                        cond_cloud_data = tf_cloud_data.get(tf_label, {})
                        raw_value = cond_cloud_data.get(field)
                        # 正規化した値を保存（比較時と同じ形式）
                        normalized_value = normalize_value_for_comparison(raw_value, field)
                        state_snapshot[f'{tf_label}.{field}'] = normalized_value
                        wlog(f'[RULE] Saving to snapshot: {tf_label}.{field} = {raw_value} → {normalized_value}')
                    
                    # 方向を判定（発火履歴保存前に判定）
                    direction = None
                    
                    # Alignment ルールの場合は alignment_direction を優先
                    if alignment_direction:
                        direction = alignment_direction
                        wlog(f'[RULE] Direction from alignment: {direction}')
                    elif conditions:
                        primary_field = conditions[0].get('field')
                        primary_tf_label = conditions[0].get('timeframe') or conditions[0].get('label')
                        cloud_data = tf_cloud_data.get(primary_tf_label, {})
                        
                        wlog(f'[RULE] Direction check: primary_field={primary_field}, tf={primary_tf_label}, cloud_data keys={list(cloud_data.keys()) if cloud_data else None}')
                        
                        if primary_field == 'dauten':
                            dauten_value = cloud_data.get('dauten')
                            wlog(f'[RULE] Direction from dauten: {dauten_value}')
                            if dauten_value == 'up':
                                direction = '上昇'
                            elif dauten_value == 'down':
                                direction = '下降'
                        
                        elif primary_field == 'gc':
                            # gc=True は上昇（青）、gc=False は下降（赤）
                            gc_value = cloud_data.get('gc')
                            wlog(f'[RULE] Direction from gc: {gc_value}')
                            if gc_value is True:
                                direction = '上昇'
                            elif gc_value is False:
                                direction = '下降'
                        
                        elif primary_field == 'bos_count':
                            # BOSの方向は同じTFのdautenから判定
                            # bos_count自体は常に正の数なので、dautenを参照
                            dauten_value = cloud_data.get('dauten')
                            bos_value = cloud_data.get('bos_count')
                            wlog(f'[RULE] Direction from bos_count: bos={bos_value}, dauten={dauten_value}')
                            if dauten_value == 'up':
                                direction = '上昇'
                            elif dauten_value == 'down':
                                direction = '下降'
                    
                    wlog(f'[RULE] Final direction for "{rule_name}": {direction}')
                    
                    # 発火履歴を保存（directionを含む）
                    fired_at = datetime.now(jst).isoformat()
                    try:
                        conn_fire = sqlite3.connect(DB_PATH)
                        c_fire = conn_fire.cursor()
                        
                        c_fire.execute('''INSERT INTO fire_history 
                                         (rule_id, symbol, tf, fired_at, conditions_snapshot, last_state_snapshot, direction)
                                         VALUES (?, ?, ?, ?, ?, ?, ?)''',
                                      (rule_id, symbol, '', fired_at, 
                                       json.dumps(conditions, ensure_ascii=False), 
                                       json.dumps(state_snapshot, ensure_ascii=False),
                                       direction))
                        
                        conn_fire.commit()
                        conn_fire.close()
                    except Exception as e:
                        wlog(f'[RULE] Error saving fire history: {e}')
                    
                    # メッセージを構築（方向別メッセージを含む）
                    common_message = voice_settings.get('message', '')
                    message_up = voice_settings.get('message_up', '')
                    message_down = voice_settings.get('message_down', '')
                    message_position = voice_settings.get('message_position', 'suffix')
                    
                    # 方向別メッセージを選択
                    if direction == '上昇' and message_up:
                        direction_message = message_up
                    elif direction == '下降' and message_down:
                        direction_message = message_down
                    else:
                        direction_message = ''
                    
                    # メッセージ結合
                    if message_position == 'prefix':
                        final_message = (direction_message + ' ' + common_message).strip() if direction_message else common_message
                    elif message_position == 'suffix':
                        final_message = (common_message + ' ' + direction_message).strip() if direction_message else common_message
                    elif message_position == 'both':
                        final_message = (direction_message + ' ' + common_message + ' ' + direction_message).strip() if direction_message else common_message
                    else:
                        final_message = common_message
                    
                    # メッセージが空の場合はルール名を使用
                    if not final_message:
                        final_message = rule_name
                    
                    fired_notifications.append({
                        'rule_id': rule_id,
                        'rule_name': rule_name,
                        'symbol': symbol,
                        'tf': 'multi',
                        'timestamp': fired_at,
                        'message': final_message,
                        'direction': direction,
                        'voice_settings': voice_settings
                    })
                    wlog(f'[FIRE] [OK] Notification fired for rule "{rule_name}" direction={direction}')
                    wlog(f'[FIRE] [OK] Added to fired_notifications list (count={len(fired_notifications)})')
                else:
                    # 発火しない場合もログ出力
                    wlog(f'[RULE] Rule "{rule_name}" not firing')
                
            except Exception as e:
                error_msg = f'[FIRE] Error evaluating rule "{rule_name}": {e}'
                print(error_msg)
                wlog(error_msg)
                import traceback
                tb_str = traceback.format_exc()
                print(tb_str)
                wlog(tb_str)
        
        # 発火した通知をSocket.IOで配信
        wlog(f'[FIRE] Checking fired_notifications: count={len(fired_notifications)}')
        if fired_notifications:
            # 各通知を個別に送信
            for notification in fired_notifications:
                try:
                    socketio.emit('new_notification', notification)
                    wlog(f'[FIRE] Emitted new_notification event for rule "{notification["rule_name"]}"')
                    print(f'[FIRE] Emitted new_notification event for rule "{notification["rule_name"]}"')
                except Exception as emit_error:
                    wlog(f'[FIRE] ERROR emitting notification: {emit_error}')
                    print(f'[FIRE] ERROR emitting notification: {emit_error}')
            wlog(f'[FIRE] Total {len(fired_notifications)} notifications sent')
            print(f'[FIRE] Total {len(fired_notifications)} notifications sent')
        
    except Exception as e:
        print(f'[ERROR] _evaluate_rules_with_db_state: {e}')
        import traceback
        traceback.print_exc()


def _evaluate_rules_with_timeframe_data(data, symbol, tf_val):
    """tf=15, 60, 240 用のルール評価
    
    当該タイムフレームのダウ転・突破数でルール評価を実行
    """
    try:
        # tf値を時間足ラベルにマッピング
        tf_map = {
            '15': '15m',
            '60': '1H',
            '240': '4H'
        }
        tf_label = tf_map.get(tf_val, f'tf{tf_val}')
        
        # JSONから当該タイムフレームのデータを抽出
        clouds = data.get('clouds', [])
        tf_cloud = None
        
        for cloud in clouds:
            if cloud.get('label') == tf_label or cloud.get('tf') == tf_label:
                tf_cloud = cloud
                break
        
        if not tf_cloud:
            print(f'[FIRE] No cloud data found for {tf_label} in received JSON')
            return
        
        print(f'[FIRE] Evaluating rules for {symbol}/{tf_val} ({tf_label}) with cloud data: dauten={tf_cloud.get("dauten")}, bos={tf_cloud.get("bos_count")}')
        
        # ルールを取得して評価
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('SELECT id, name, enabled, scope_json, rule_json FROM rules WHERE enabled = 1')
        rows = c.fetchall()
        conn.close()
        
        if not rows:
            print('[FIRE] No enabled rules')
            return
        
        print(f'[FIRE] Evaluating {len(rows)} enabled rules for {symbol}/{tf_val}')
        
        jst = pytz.timezone('Asia/Tokyo')
        fired_notifications = []
        
        for row in rows:
            rule_id, rule_name, enabled, scope_json, rule_json = row
            try:
                scope = json.loads(scope_json) if scope_json else {}
                rule = json.loads(rule_json) if rule_json else {}
                
                # Check scope: if scope has symbol, must match
                if scope.get('symbol') and scope['symbol'] != symbol:
                    print(f'[FIRE] Rule "{rule_name}" scope mismatch: {scope.get("symbol")} != {symbol}')
                    continue
                
                # Check scope: if scope has tf, must match
                if scope.get('tf') and scope['tf'] != tf_val:
                    print(f'[FIRE] Rule "{rule_name}" tf mismatch: {scope.get("tf")} != {tf_val}')
                    continue
                
                print(f'[FIRE] Testing rule "{rule_name}" for {symbol}/{tf_val}')
                
                # ルール条件を評価
                conditions = rule.get('conditions', [])
                all_matched = True
                
                for cond in conditions:
                    label = cond.get('timeframe') or cond.get('label')
                    field = cond.get('field')
                    value = cond.get('value')
                    
                    # 条件のラベルが当該タイムフレームと一致するかチェック
                    if label != tf_label:
                        print(f'[FIRE] Condition label mismatch: {label} != {tf_label}, skipping condition')
                        all_matched = False
                        break
                    
                    # tf_cloudからフィールド値を取得
                    found_value = tf_cloud.get(field)
                    
                    # 条件をチェック
                    condition_met = False
                    if value is None:
                        # Presence check
                        condition_met = found_value is not None
                    else:
                        # Value check
                        condition_met = found_value == value
                    
                    if not condition_met:
                        all_matched = False
                        print(f'[FIRE] Condition not met: {label}.{field} (found={found_value}, expected={value})')
                        break
                
                print(f'[FIRE] Rule "{rule_name}" result: matched={all_matched}')
                
                # ルールが一致した場合は通知を発火
                if all_matched:
                    print(f'[FIRE] [OK] Rule MATCHED: {rule_name}')
                    
                    # Get last fired state for this rule/tf
                    conn_check = sqlite3.connect(DB_PATH)
                    c_check = conn_check.cursor()
                    c_check.execute('''SELECT last_state_snapshot FROM fire_history 
                                       WHERE rule_id = ? AND symbol = ? AND tf = ? 
                                       ORDER BY fired_at DESC LIMIT 1''', (rule_id, symbol, tf_val))
                    last_fire = c_check.fetchone()
                    conn_check.close()
                    
                    last_state = None
                    if last_fire and last_fire[0]:
                        try:
                            last_state = json.loads(last_fire[0])
                        except:
                            last_state = None
                    
                    # 状態変化をチェック（dauten, bos_countの変化を検出）
                    should_fire = False
                    
                    if last_state is None:
                        # 初回発火
                        should_fire = True
                        print(f'[FIRE] First time firing for this rule/symbol/tf')
                    else:
                        # 前回の状態と比較
                        prev_dauten = last_state.get('dauten')
                        prev_bos = last_state.get('bos_count')
                        curr_dauten = tf_cloud.get('dauten')
                        curr_bos = tf_cloud.get('bos_count')
                        
                        if prev_dauten != curr_dauten or prev_bos != curr_bos:
                            should_fire = True
                            print(f'[FIRE] State change detected: dauten {prev_dauten}->{curr_dauten}, bos {prev_bos}->{curr_bos}')
                        else:
                            print(f'[FIRE] No state change, skipping fire')
                    
                    if should_fire:
                        # 通知を記録してメッセージをキューに追加
                        try:
                            conn_fire = sqlite3.connect(DB_PATH)
                            c_fire = conn_fire.cursor()
                            
                            # 現在の状態をスナップショットとして保存
                            current_state_snapshot = json.dumps({
                                'dauten': tf_cloud.get('dauten'),
                                'bos_count': tf_cloud.get('bos_count'),
                                'gc': tf_cloud.get('gc')
                            }, ensure_ascii=False)
                            
                            # 方向を判定
                            direction = None
                            dauten_value = tf_cloud.get('dauten')
                            if dauten_value == 'up':
                                direction = '上昇'
                            elif dauten_value == 'down':
                                direction = '下降'
                            
                            c_fire.execute('''INSERT INTO fire_history 
                                             (rule_id, symbol, tf, fired_at, last_state_snapshot, direction)
                                             VALUES (?, ?, ?, ?, ?, ?)''',
                                          (rule_id, symbol, tf_val, datetime.now(jst).isoformat(), current_state_snapshot, direction))
                            conn_fire.commit()
                            conn_fire.close()
                            
                            fired_notifications.append({
                                'rule_id': rule_id,
                                'rule_name': rule_name,
                                'symbol': symbol,
                                'tf': tf_val
                            })
                            print(f'[FIRE] [OK] Notification fired for rule "{rule_name}"')
                        except Exception as e:
                            print(f'[FIRE] Error recording fire history: {e}')
                    
            except Exception as e:
                print(f'[FIRE] Error evaluating rule "{rule_name}": {e}')
                import traceback
                traceback.print_exc()
        
        # 発火した通知をSocket.IOで配信
        if fired_notifications:
            socketio.emit('rule_fired', {
                'notifications': fired_notifications,
                'timestamp': datetime.now(jst).isoformat()
            })
            print(f'[FIRE] Emitted {len(fired_notifications)} rule_fired events')
        
    except Exception as e:
        print(f'[ERROR] _evaluate_rules_with_timeframe_data: {e}')
        import traceback
        traceback.print_exc()


def _evaluate_rules_with_state(base_state):
    """統合されたstateデータを使用してルール評価を実行
    
    Note: この関数に到達するデータは evaluate_and_fire_rules() 内の時刻フィルターを
    通過済みのため、遅延アラート（過去データ再計算）は既に除外されている
    """
    try:
        currency_names = {
            'USDJPY': 'ドル円',
            'EURUSD': 'ユーロドル',
            'GBPUSD': 'ポンドドル',
            'GBPJPY': 'ポンド円',
            'AUDUSD': 'オージードル',
            'AUDJPY': 'オージー円',
            'NZDUSD': 'ニュージードル',
            'NZDJPY': 'ニュージー円',
            'CADJPY': 'カナダ円',
            'CHFJPY': 'スイス円',
            'EURJPY': 'ユーロ円',
            'GBPAUD': 'ポンドオージー',
            'EURGBP': 'ユーロポンド',
            'USDCAD': 'ドルカナダ',
            'USDCHF': 'ドルスイス'
        }
        
        # 統合データから symbol と tf を取得
        symbol = base_state.get('symbol', 'UNKNOWN')
        tf = '5'  # 統合データは常に tf=5 ベース
        
        # Get all enabled rules
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('SELECT id, name, enabled, scope_json, rule_json FROM rules WHERE enabled = 1')
        rows = c.fetchall()
        conn.close()
        
        if not rows:
            print('[FIRE] No enabled rules')
            return  # No enabled rules
        
        print(f'[FIRE] Evaluating {len(rows)} enabled rules for {symbol}/{tf}')
        
        jst = pytz.timezone('Asia/Tokyo')
        fired_notifications = []
        
        for row in rows:
            rule_id, rule_name, enabled, scope_json, rule_json = row
            try:
                scope = json.loads(scope_json) if scope_json else {}
                rule = json.loads(rule_json) if rule_json else {}
                
                # Check scope: if scope has symbol, must match
                if scope.get('symbol') and scope['symbol'] != base_state.get('symbol'):
                    print(f'[FIRE] Rule "{rule_name}" scope mismatch: {scope.get("symbol")} != {base_state.get("symbol")}')
                    continue
                
                print(f'[FIRE] Testing rule "{rule_name}" for {symbol}/{tf}')
                
                # Directly evaluate rule conditions against base_state (simplified version)
                # Check if all conditions are met
                conditions = rule.get('conditions', [])
                all_matched = True
                
                for cond in conditions:
                    label = cond.get('label')
                    field = cond.get('field')
                    value = cond.get('value')
                    
                    # Find the cloud field in base_state
                    found_value = None
                    for cloud in base_state.get('clouds', []):
                        if cloud.get('label') == label:
                            found_value = cloud.get(field)
                            break
                    
                    # Check if condition matches
                    condition_met = False
                    if value is None:
                        # Presence check: field should exist and have a value
                        condition_met = found_value is not None
                    else:
                        # Value check
                        condition_met = found_value == value
                    
                    if not condition_met:
                        all_matched = False
                        print(f'[FIRE] Condition not met: {label}.{field} (found={found_value}, expected={value})')
                        break
                
                # Build result object
                result = {
                    'status': 'success',
                    'matched': all_matched,
                    'details': [{'result': all_matched}] if all_matched else []
                }
                
                print(f'[FIRE] Rule "{rule_name}" result: matched={result.get("matched")}')
                
                if result.get('status') == 'success' and result.get('matched'):
                    # Categorize condition types:
                    # 1. State change fields (gc, dauten, bos_count) - fire when value changes
                    # 2. Threshold fields (angle, thickness, distance_*, transfer_time_diff) - fire when crossing threshold
                    # 3. Alignment - fire when alignment state changes (aligned -> not aligned -> aligned)
                    
                    # BOS count is now treated as state change (fires on every count change)
                    state_change_fields = ('gc', 'dauten', 'bos_count')
                    threshold_fields = ('angle', 'thickness', 'distance_from_prev', 'distance_from_price', 'transfer_time_diff')
                    
                    should_fire = False
                    changed_fields = []
                    rule_conditions = rule.get('conditions', [])
                    has_alignment = rule.get('cloudAlign') is not None or rule.get('alignment') is not None
                    
                    # Get last fired state for this rule
                    conn_check = sqlite3.connect(DB_PATH)
                    c_check = conn_check.cursor()
                    c_check.execute('''SELECT last_state_snapshot FROM fire_history 
                                       WHERE rule_id = ? AND symbol = ? AND tf = ? 
                                       ORDER BY fired_at DESC LIMIT 1''', (rule_id, symbol, tf))
                    last_fire = c_check.fetchone()
                    conn_check.close()
                    
                    last_state = None
                    if last_fire and last_fire[0]:
                        try:
                            last_state = json.loads(last_fire[0])
                        except:
                            last_state = None
                    
                    # Build current state snapshot
                    current_state = {}
                    curr_clouds = base_state.get('clouds', [])
                    
                    # Check state change fields (gc, dauten, bos_count)
                    for cond in rule_conditions:
                        field = cond.get('field')
                        label = cond.get('timeframe') or cond.get('label')
                        
                        if field in state_change_fields:
                            # Find current value
                            curr_val = None
                            for c in curr_clouds:
                                if c.get('label') == label:
                                    curr_val = c.get(field)
                                    break
                            
                            state_key = f'{label}.{field}'
                            current_state[state_key] = curr_val
                            
                            # Compare with last state
                            if last_state is None or last_state.get(state_key) != curr_val:
                                should_fire = True
                                changed_fields.append(state_key)
                                prev_val = last_state.get(state_key) if last_state else None
                                print(f'[FIRE] State change: {state_key} changed from {prev_val} to {curr_val}')
                    
                    # Check threshold fields (angle, thickness, distance_*, transfer_time_diff)
                    for cond in rule_conditions:
                        field = cond.get('field')
                        label = cond.get('timeframe') or cond.get('label')
                        threshold_value = cond.get('value')
                        
                        if field in threshold_fields:
                            # Find current value
                            curr_val = None
                            for c in curr_clouds:
                                if c.get('label') == label:
                                    curr_val = c.get(field)
                                    break
                            
                            # For transfer_time_diff, calculate based on detail results
                            if field == 'transfer_time_diff':
                                # Find the detail for this condition
                                details = result.get('details', [])
                                for detail in details:
                                    if detail.get('cond') == f'{label}.{field}':
                                        curr_val = detail.get('delta_min') or detail.get('actual')
                                        break
                            
                            state_key = f'{label}.{field}'
                            
                            # Determine if threshold is met
                            threshold_met = False
                            if curr_val is not None and threshold_value is not None:
                                try:
                                    curr_float = float(curr_val)
                                    threshold_float = float(threshold_value)
                                    
                                    # For distance/angle/thickness: value >= threshold
                                    # For transfer_time_diff: value <= threshold
                                    if field == 'transfer_time_diff':
                                        threshold_met = curr_float <= threshold_float
                                    else:
                                        # For angle, thickness, distance: check if >= +N or <= -N
                                        threshold_met = (curr_float >= threshold_float) or (curr_float <= -threshold_float)
                                except:
                                    threshold_met = False
                            
                            current_state[state_key] = threshold_met
                            
                            # Fire if: threshold is met AND (no last state OR last state was NOT met)
                            last_threshold_met = last_state.get(state_key) if last_state else None
                            
                            if threshold_met and (last_threshold_met is None or not last_threshold_met):
                                should_fire = True
                                changed_fields.append(state_key)
                                print(f'[FIRE] Threshold crossed: {state_key} = {curr_val} (threshold: {threshold_value}, was_met: {last_threshold_met} -> now_met: {threshold_met})')
                    
                    # Check alignment condition
                    if has_alignment:
                        alignment = rule.get('cloudAlign') or rule.get('alignment')
                        
                        # Determine if alignment is met from details
                        alignment_met = False
                        details = result.get('details', [])
                        for detail in details:
                            if detail.get('cond') == 'alignment':
                                alignment_met = detail.get('result', False)
                                break
                        
                        state_key = 'alignment'
                        current_state[state_key] = alignment_met
                        
                        # Fire if: aligned AND (no last state OR last state was NOT aligned)
                        last_alignment_met = last_state.get(state_key) if last_state else None
                        
                        if alignment_met and (last_alignment_met is None or not last_alignment_met):
                            should_fire = True
                            changed_fields.append(state_key)
                            print(f'[FIRE] Alignment achieved: was_aligned: {last_alignment_met} -> now_aligned: {alignment_met}')
                    
                    if not should_fire:
                        print(f'[FIRE] Rule "{rule_name}" matched but no state change detected, skipping notification')
                        continue
                    
                    print(f'[FIRE] Rule "{rule_name}" FIRED! Changed fields: {changed_fields}')
                    
                    # Rule fired! Determine direction from dauten, bos_count, and gc fields
                    direction = None
                    
                    # Collect directions from cloud data directly (not from details)
                    directions_found = []
                    
                    # Extract direction from cloud conditions
                    rule_conditions = rule.get('conditions', [])
                    for cond in rule_conditions:
                        label = cond.get('timeframe') or cond.get('label')
                        field = cond.get('field')
                        
                        # Find cloud value
                        for cloud in base_state.get('clouds', []):
                            if cloud.get('label') == label:
                                actual = cloud.get(field)
                                # gc の場合は dauten から方向を取得
                                dauten_value = cloud.get('dauten')
                                
                                if actual is not None:
                                    if field == 'dauten':
                                        if '上昇' in str(actual) or 'up' in str(actual).lower():
                                            directions_found.append('上昇')
                                        elif '下降' in str(actual) or 'down' in str(actual).lower():
                                            directions_found.append('下降')
                                    elif field == 'gc':
                                        # gc=True は上昇（青）、gc=False は下降（赤）
                                        if actual is True or str(actual).upper() == 'TRUE':
                                            directions_found.append('上昇')
                                        elif actual is False or str(actual).upper() == 'FALSE':
                                            directions_found.append('下降')
                                    elif field == 'bos_count':
                                        try:
                                            bos_val = float(actual)
                                            if bos_val > 0:
                                                directions_found.append('上昇')
                                            elif bos_val < 0:
                                                directions_found.append('下降')
                                        except:
                                            pass
                                break
                    
                    # Determine overall direction: majority vote, or first if tie
                    if directions_found:
                        up_count = directions_found.count('上昇')
                        down_count = directions_found.count('下降')
                        if up_count > down_count:
                            direction = '上昇'
                        elif down_count > up_count:
                            direction = '下降'
                        else:
                            direction = directions_found[0]  # Tie, use first
                    
                    # If no direction found, default to '上昇'
                    if direction is None:
                        direction = '上昇'
                    
                    # Get custom messages from rule
                    voice_settings = rule.get('voice', {})
                    message_up = voice_settings.get('message_up', f'{rule_name} が上昇方向で発火しました')
                    message_down = voice_settings.get('message_down', f'{rule_name} が下降方向で発火しました')
                    common_message = voice_settings.get('message', '')
                    message_position = voice_settings.get('message_position', 'suffix')
                    
                    # Select direction-specific message
                    direction_message = message_up if direction == '上昇' else message_down
                    
                    # Combine messages based on position
                    if message_position == 'prefix':
                        combined_message = direction_message + ' ' + common_message if common_message else direction_message
                    elif message_position == 'suffix':
                        combined_message = common_message + ' ' + direction_message if common_message else direction_message
                    elif message_position == 'both':
                        combined_message = direction_message + ' ' + common_message + ' ' + direction_message if common_message else direction_message + ' ' + direction_message
                    else:
                        combined_message = direction_message
                    
                    # Ensure message is not empty
                    if not combined_message.strip():
                        combined_message = f'{rule_name} が発火しました'
                    
                    # Replace {symbol} placeholder with Japanese currency name or insert based on position
                    symbol = base_state.get('symbol', 'UNKNOWN')
                    japanese_name = currency_names.get(symbol, symbol)
                    
                    if voice_settings.get('insert_symbol'):
                        position = voice_settings.get('symbol_insert_position', 'prefix')
                        if position == 'prefix':
                            combined_message = japanese_name + ' ' + combined_message
                        elif position == 'suffix':
                            combined_message = combined_message + ' ' + japanese_name
                        elif position == 'both':
                            combined_message = japanese_name + ' ' + combined_message + ' ' + japanese_name
                    else:
                        # Legacy behavior: replace {symbol} placeholder
                        combined_message = combined_message.replace('{symbol}', japanese_name)
                    
                    # Create notification
                    notification = {
                        'rule_id': rule_id,
                        'rule_name': rule_name,
                        'symbol': base_state.get('symbol', 'UNKNOWN'),
                        'tf': base_state.get('tf', '5'),
                        'direction': direction,
                        'message': combined_message,
                        'timestamp': datetime.now(jst).isoformat(),
                        'price': float(base_state.get('price', 0)),
                        'voice_settings': voice_settings  # 音声設定を含める
                    }
                    
                    fired_notifications.append(notification)
                    
                    # Record fire event in history with current state snapshot
                    try:
                        conn_hist = sqlite3.connect(DB_PATH)
                        c_hist = conn_hist.cursor()
                        c_hist.execute('''INSERT INTO fire_history (rule_id, symbol, tf, fired_at, conditions_snapshot, last_state_snapshot, direction)
                                         VALUES (?, ?, ?, ?, ?, ?, ?)''',
                                      (rule_id, symbol, tf, datetime.now(jst).isoformat(), 
                                       json.dumps(rule.get('conditions', []), ensure_ascii=False),
                                       json.dumps(current_state, ensure_ascii=False),
                                       direction))
                        conn_hist.commit()
                        conn_hist.close()
                    except Exception as e:
                        print(f'[ERROR] Saving fire history: {e}')
                    
                    print(f'[RULE FIRED] {rule_name} - {direction} - {combined_message}')
            
            except Exception as e:
                print(f'[ERROR] Evaluating rule {rule_id}: {e}')
                continue
        
        # Save notifications to file
        if fired_notifications:
            notifications_path = os.path.join(BASE_DIR, 'notifications.json')
            try:
                if os.path.exists(notifications_path):
                    with open(notifications_path, 'r', encoding='utf-8') as f:
                        existing = json.load(f)
                else:
                    existing = []
                
                existing.extend(fired_notifications)
                
                # Keep only last 100 notifications
                if len(existing) > 100:
                    existing = existing[-100:]
                
                with open(notifications_path, 'w', encoding='utf-8') as f:
                    json.dump(existing, f, ensure_ascii=False, indent=2)
                
                print(f'[NOTIFICATIONS] Saved {len(fired_notifications)} notifications')
                
                # Socket.IOで新しい通知を送信
                for notification in fired_notifications:
                    socketio.emit('new_notification', notification)
                    print(f'[SOCKET.IO] Notification sent: {notification.get("rule_name")}')
            
            except Exception as e:
                print(f'[ERROR] Saving notifications: {e}')
    
    except Exception as e:
        print(f'[ERROR] evaluate_and_fire_rules: {e}')

# トラブルシューティング用エンドポイント
@app.route('/api/webhook-diagnostics', methods=['GET'])
def webhook_diagnostics():
    """Webhook受信と処理の状態を確認するエンドポイント"""
    try:
        jst = pytz.timezone('Asia/Tokyo')
        diagnostics = {
            'server_time': datetime.now(jst).isoformat(),
            'webhook_log_exists': os.path.exists(os.path.join(BASE_DIR, 'webhook_log.txt')),
            'webhook_error_log_exists': os.path.exists(os.path.join(BASE_DIR, 'webhook_error.log')),
            'database_exists': os.path.exists(DB_PATH),
        }
        
        # webhook_log.txt の最後の行を取得
        webhook_log_path = os.path.join(BASE_DIR, 'webhook_log.txt')
        if os.path.exists(webhook_log_path):
            try:
                with open(webhook_log_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    diagnostics['webhook_log_last_entries'] = lines[-10:] if lines else []
                    diagnostics['webhook_log_total_lines'] = len(lines)
            except:
                pass
        
        # webhook_error.log の最後の行を取得
        webhook_error_path = os.path.join(BASE_DIR, 'webhook_error.log')
        if os.path.exists(webhook_error_path):
            try:
                with open(webhook_error_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    diagnostics['error_log_last_entries'] = lines[-20:] if lines else []
                    diagnostics['error_log_total_lines'] = len(lines)
            except:
                pass
        
        # データベースの最後の記録
        try:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("SELECT symbol, tf, time, timestamp FROM states WHERE symbol='USDJPY' AND tf='5' ORDER BY timestamp DESC LIMIT 1")
            last_record = c.fetchone()
            if last_record:
                diagnostics['last_usdjpy5_record'] = {
                    'symbol': last_record[0],
                    'tf': last_record[1],
                    'json_time': last_record[2],
                    'db_timestamp': last_record[3]
                }
            
            # fire_history の最後の記録
            c.execute("SELECT rule_id, symbol, tf, fired_at FROM fire_history WHERE symbol='USDJPY' AND tf='5' ORDER BY fired_at DESC LIMIT 1")
            last_fire = c.fetchone()
            if last_fire:
                diagnostics['last_rule_fire'] = {
                    'rule_id': last_fire[0],
                    'symbol': last_fire[1],
                    'tf': last_fire[2],
                    'fired_at': last_fire[3]
                }
            
            conn.close()
        except Exception as e:
            diagnostics['database_error'] = str(e)
        
        return jsonify(diagnostics), 200
    except Exception as e:
        return jsonify({'status': 'error', 'msg': str(e)}), 500

@app.route('/api/save_notes', methods=['POST'])
def save_notes():
    try:
        payload = request.get_json()
        if not payload:
            return jsonify({'status': 'error', 'msg': 'No data provided'}), 400
        
        # フロントエンドから送信される形式: {pages: [...], currentPage: ...}
        # またはそのままnotePages配列として送信される場合もある
        notes_data = payload
        
        notes_path = os.path.join(BASE_DIR, 'notes_data.json')
        print(f'[NOTE API] Saving notes to {notes_path}')
        print(f'[NOTE API] Data type: {type(notes_data)}, Content: {json.dumps(notes_data, ensure_ascii=False)[:200]}...')
        
        # ファイルに保存
        with open(notes_path, 'w', encoding='utf-8') as f:
            json.dump(notes_data, f, ensure_ascii=False, indent=2)
        
        print(f'[NOTE API] Notes saved successfully')
        return jsonify({'status': 'success', 'msg': 'Notes saved'})
    except Exception as e:
        error_msg = f'[ERROR] save_notes failed: {str(e)}'
        print(error_msg)
        return jsonify({'status': 'error', 'msg': str(e)}), 500

@app.route('/api/load_notes', methods=['GET'])
def load_notes():
    try:
        notes_path = os.path.join(BASE_DIR, 'notes_data.json')
        print(f'[NOTE API] Loading notes from {notes_path}')
        
        if os.path.exists(notes_path):
            with open(notes_path, 'r', encoding='utf-8') as f:
                notes_data = json.load(f)
            print(f'[NOTE API] Loaded notes: {len(notes_data) if isinstance(notes_data, list) else "dict"} items')
            # フロントエンドは notes フィールドを期待している
            return jsonify({'status': 'success', 'notes': notes_data})
        else:
            print(f'[NOTE API] Notes file not found, returning empty array')
            return jsonify({'status': 'success', 'notes': []})
    except Exception as e:
        error_msg = f'[ERROR] load_notes failed: {str(e)}'
        print(error_msg)
        return jsonify({'status': 'error', 'msg': str(e)}), 500

if __name__ == '__main__':
    print('[DEBUG] Starting init_db...')
    init_db()
    print('[DEBUG] init_db completed')
    port = int(os.environ.get('PORT', 5000))
    
    # ログファイルの初期化
    jst = pytz.timezone('Asia/Tokyo')
    startup_log = os.path.join(BASE_DIR, 'webhook_error.log')
    try:
        with open(startup_log, 'a', encoding='utf-8') as f:
            f.write(f'\n{"="*80}\n')
            f.write(f'{datetime.now(jst).isoformat()} - [STARTUP] Starting Flask server on port {port}\n')
            f.write(f'{"="*80}\n')
    except:
        pass
    
    # バックアップ自動取得スレッドを起動
    def auto_backup_fetch_loop():
        """30分ごとにGmailからバックアップを自動取得"""
        jst = pytz.timezone('Asia/Tokyo')
        while True:
            try:
                time.sleep(1800)  # 30分待機
                
                print(f'[AUTO BACKUP] Starting automatic backup fetch at {datetime.now(jst).strftime("%Y-%m-%d %H:%M:%S")}')
                
                # backup_recovery.pyのパスを探す
                script_paths = [
                    os.path.join(BASE_DIR, 'backup_recovery.py'),
                    os.path.join(os.path.dirname(BASE_DIR), 'backup_recovery.py'),
                    os.path.join(os.getcwd(), 'backup_recovery.py')
                ]
                
                script_path = None
                for path in script_paths:
                    if os.path.exists(path):
                        script_path = path
                        break
                
                if not script_path:
                    print(f'[AUTO BACKUP ERROR] backup_recovery.py not found')
                    continue
                
                # 現在実行中のPythonを使用（仮想環境を維持）
                import sys
                python_exe = sys.executable
                
                # 実行（--after-days 3 で直近3日分のみ取得: D/4H も含め効率よく処理）
                result = subprocess.run(
                    [python_exe, script_path, '--fetch', '--max', '500', '--after-days', '3'],
                    capture_output=True,
                    text=True,
                    timeout=300  # 5分に拡大（Gmail API遅延対応）
                )
                
                if result.returncode == 0:
                    # 成功数を抽出
                    output = result.stdout
                    if '[SUMMARY]' in output:
                        summary_line = [line for line in output.split('\n') if '[SUMMARY]' in line]
                        if summary_line:
                            print(f'[AUTO BACKUP] {summary_line[0]}')
                    else:
                        print(f'[AUTO BACKUP] Completed successfully')
                else:
                    print(f'[AUTO BACKUP ERROR] {result.stderr}')
                    
            except subprocess.TimeoutExpired:
                print(f'[AUTO BACKUP ERROR] Timeout after 300 seconds')
            except Exception as e:
                print(f'[AUTO BACKUP ERROR] {str(e)}')
                traceback.print_exc()
    
    # バックグラウンドスレッドを起動
    backup_thread = threading.Thread(target=auto_backup_fetch_loop, daemon=True)
    backup_thread.start()
    print(f'[AUTO BACKUP] Background thread started (30min interval)')
    
    print(f'[START] Starting server on port {port} at {datetime.now(jst).isoformat()}')
    print('[DEBUG] About to call socketio.run...')
    
    try:
        print('[DEBUG] Calling socketio.run...')
        socketio.run(app, host='0.0.0.0', port=port, debug=False, allow_unsafe_werkzeug=True, use_reloader=False)
        print('[DEBUG] socketio.run completed')
    except Exception as e:
        error_msg = f'[CRITICAL ERROR] Server crashed: {str(e)}'
        print(error_msg)
        import traceback
        print('[DEBUG] Full traceback:')
        traceback.print_exc()
        try:
            with open(startup_log, 'a', encoding='utf-8') as f:
                f.write(f'{datetime.now(jst).isoformat()} - {error_msg}\n')
                f.write(f'Full traceback:\n{traceback.format_exc()}\n')
        except:
            pass
        raise

