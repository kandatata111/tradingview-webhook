from flask import Flask, request, jsonify, render_template
import os
import requests
from datetime import datetime
import json
import webbrowser
import threading

app = Flask(__name__)

# スクリプトのディレクトリを取得
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'webhook_data.db')

# データベース接続関数（PostgreSQL優先、フォールバックでSQLite）
def get_db_connection():
    """データベース接続を取得（PostgreSQL優先、SQLiteフォールバック）"""
    try:
        import psycopg2
        return psycopg2.connect(os.environ['DATABASE_URL'])
    except (ImportError, KeyError):
        # PostgreSQLが利用できない場合はSQLiteを使用
        import sqlite3
        return sqlite3.connect(DB_PATH)

def is_postgresql():
    """PostgreSQLを使用しているかどうか"""
    try:
        import psycopg2
        return 'DATABASE_URL' in os.environ
    except ImportError:
        return False

# 雲状態分析関数
def analyze_clouds(symbol, price, clouds):
    """
    雲の状態を分析して通知を生成
    """
    notifications = []
    
    for cloud in clouds:
        label = cloud.get('label', '')
        tf = cloud.get('tf', '')
        gc = cloud.get('gc', False)
        fire_count = cloud.get('fire_count', 0)
        max_reached = cloud.get('max_reached', False)
        thickness = cloud.get('thickness', 0)
        angle = cloud.get('angle', 0)
        elapsed = cloud.get('elapsed', 0)
        
        # 発火があった場合のみ通知
        if fire_count > 0:
            # 雲の種類を判定
            if label == '5m':
                cloud_type = 'short'
                cloud_name = '短期雲'
            elif label == '15m':
                cloud_type = 'mid'
                cloud_name = '中期雲'
            elif label == '1H':
                cloud_type = 'long'
                cloud_name = '長期雲'
            elif label == '4H':
                cloud_type = 'ultra'
                cloud_name = '超長期雲'
            else:
                continue
            
            # GC/DCを判定
            direction = 'up' if gc else 'dn'
            direction_ja = 'ゴールデンクロス' if gc else 'デッドクロス'
            
            # アラートタイプを決定
            alert_type = f'{cloud_type}_{direction}'
            
            # 最大発火数到達の場合
            if max_reached:
                alert_type = 'max_reached'
                direction_ja = '最大発火数到達'
            
            # メッセージ生成
            message = f"{cloud_name} {direction_ja} (発火{fire_count}回)"
            
            # Discord用メッセージ
            line_message = f"""🔔 ダウ雲アラート
銘柄: {symbol}
時間足: {tf}
価格: {price}

{cloud_name} ({label})
状態: {direction_ja}
発火回数: {fire_count}回
雲厚み: {thickness:.2f} Pips
雲角度: {angle:.2f}°
経過時間: {elapsed}バー

時刻: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""
            
            notifications.append({
                'alert_type': alert_type,
                'message': message,
                'line_message': line_message,
                'cloud_label': label
            })
    
    return notifications

# Database setup
def init_db():
    """データベース初期化"""
    if is_postgresql():
        # PostgreSQLの場合
        conn = get_db_connection()
        c = conn.cursor()
        
        # 現在状態テーブル(通貨ペアごとに最新状態のみ保持)
        c.execute('''CREATE TABLE IF NOT EXISTS current_states
                     (symbol TEXT PRIMARY KEY,
                      timestamp TEXT,
                      tf TEXT,
                      price REAL,
                      daily_dow_status TEXT,
                      daily_dow_bos TEXT,
                      daily_dow_time TEXT,
                      swing_dow_status TEXT,
                      swing_dow_bos TEXT,
                      swing_dow_time TEXT,
                      row_order TEXT,
                      cloud_order TEXT,
                      cloud_5m_gc INTEGER,
                      cloud_5m_thickness REAL,
                      cloud_5m_angle REAL,
                      cloud_5m_fire_count INTEGER,
                      cloud_5m_elapsed TEXT,
                      cloud_5m_distance_from_price REAL,
                      cloud_5m_distance_from_prev REAL,
                      cloud_15m_gc INTEGER,
                      cloud_15m_thickness REAL,
                      cloud_15m_angle REAL,
                      cloud_15m_fire_count INTEGER,
                      cloud_15m_elapsed TEXT,
                      cloud_15m_distance_from_price REAL,
                      cloud_15m_distance_from_prev REAL,
                      cloud_1h_gc INTEGER,
                      cloud_1h_thickness REAL,
                      cloud_1h_angle REAL,
                      cloud_1h_fire_count INTEGER,
                      cloud_1h_elapsed TEXT,
                      cloud_1h_distance_from_price REAL,
                      cloud_1h_distance_from_prev REAL,
                      cloud_4h_gc INTEGER,
                      cloud_4h_thickness REAL,
                      cloud_4h_angle REAL,
                      cloud_4h_fire_count INTEGER,
                      cloud_4h_elapsed TEXT,
                      cloud_4h_distance_from_price REAL,
                      cloud_4h_distance_from_prev REAL)''')
        
        # 発火履歴テーブル（通知用）
        c.execute('''CREATE TABLE IF NOT EXISTS fire_history
                     (id SERIAL PRIMARY KEY,
                      timestamp TEXT,
                      symbol TEXT,
                      cloud_label TEXT,
                      fire_count INTEGER,
                      gc INTEGER,
                      message TEXT)''')
        
        conn.commit()
        conn.close()
    else:
        # SQLiteの場合
        import sqlite3
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        # 現在状態テーブル(通貨ペアごとに最新状態のみ保持)
        c.execute('''CREATE TABLE IF NOT EXISTS current_states
                     (symbol TEXT PRIMARY KEY,
                      timestamp TEXT,
                      tf TEXT,
                      price REAL,
                      daily_dow_status TEXT,
                      daily_dow_bos TEXT,
                      daily_dow_time TEXT,
                      swing_dow_status TEXT,
                      swing_dow_bos TEXT,
                      swing_dow_time TEXT,
                      row_order TEXT,
                      cloud_order TEXT,
                      cloud_5m_gc INTEGER,
                      cloud_5m_thickness REAL,
                      cloud_5m_angle REAL,
                      cloud_5m_fire_count INTEGER,
                      cloud_5m_elapsed TEXT,
                      cloud_5m_distance_from_price REAL,
                      cloud_5m_distance_from_prev REAL,
                      cloud_15m_gc INTEGER,
                      cloud_15m_thickness REAL,
                      cloud_15m_angle REAL,
                      cloud_15m_fire_count INTEGER,
                      cloud_15m_elapsed TEXT,
                      cloud_15m_distance_from_price REAL,
                      cloud_15m_distance_from_prev REAL,
                      cloud_1H_gc INTEGER,
                      cloud_1H_thickness REAL,
                      cloud_1H_angle REAL,
                      cloud_1H_fire_count INTEGER,
                      cloud_1H_elapsed TEXT,
                      cloud_1H_distance_from_price REAL,
                      cloud_1H_distance_from_prev REAL,
                      cloud_4H_gc INTEGER,
                      cloud_4H_thickness REAL,
                      cloud_4H_angle REAL,
                      cloud_4H_fire_count INTEGER,
                      cloud_4H_elapsed TEXT,
                      cloud_4H_distance_from_price REAL,
                      cloud_4H_distance_from_prev REAL)''')
        
        # 発火履歴テーブル（通知用）
        c.execute('''CREATE TABLE IF NOT EXISTS fire_history
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      timestamp TEXT,
                      symbol TEXT,
                      cloud_label TEXT,
                      fire_count INTEGER,
                      gc INTEGER,
                      message TEXT)''')
        
        conn.commit()
        conn.close()

# Send Discord notification
def send_discord_notification(message):
    webhook_url = os.getenv('DISCORD_WEBHOOK_URL')
    if not webhook_url:
        print("DISCORD_WEBHOOK_URL not set")
        return
    
    payload = {
        'content': message
    }
    try:
        response = requests.post(webhook_url, json=payload)
        print(f"Discord notification sent: {response.status_code}")
    except Exception as e:
        print(f"Discord notification error: {e}")

# Forward to local client
def forward_to_local_client(data):
    local_url = os.getenv('LOCAL_CLIENT_URL')
    if not local_url:
        print("LOCAL_CLIENT_URL not set - skipping forward")
        return
    
    try:
        requests.post(local_url, json=data, timeout=5)
        print("Forwarded to local client")
    except Exception as e:
        print(f"Forward error: {e}")

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        data = request.json
        if data is None:
            print(f"Error: request.json is None. Content-Type: {request.content_type}")
            print(f"Raw data: {request.get_data()}")
            return jsonify({'status': 'error', 'message': 'Invalid JSON data'}), 400
        
        print(f"Received webhook: {data}")
        
        # Extract data from complex JSON structure
        symbol = data.get('symbol', 'UNKNOWN')
        tf = data.get('tf', '5')
        price = data.get('price', 0)
        clouds = data.get('clouds', [])
        
        # デイトレード/スイングダウ情報の取得
        # 'daytrade'/'swing' または 'daily_dow'/'swing_dow' の両方をサポート
        # 受け取ったデータをそのまま使用
        daytrade_raw = data.get('daytrade', data.get('daily_dow', {}))
        swing_raw = data.get('swing', data.get('swing_dow', {}))
        
        daily_dow = {
            'status': daytrade_raw.get('status', ''),
            'bos': daytrade_raw.get('bos', ''),
            'time': daytrade_raw.get('time', '')
        }
        
        swing_dow = {
            'status': swing_raw.get('status', ''),
            'bos': swing_raw.get('bos', ''),
            'time': swing_raw.get('time', '')
        }
        
        row_order = data.get('row_order', ['price', '5m', '15m', '1H', '4H'])
        cloud_order = data.get('cloud_order', ['5m', '15m', '1H', '4H'])
        
        # 雲データをパース
        cloud_data = {}
        for cloud in clouds:
            label = cloud.get('label', '')
            cloud_data[label] = {
                'gc': 1 if cloud.get('gc', False) else 0,
                'thickness': cloud.get('thickness', 0),
                'angle': cloud.get('angle', 0),
                'fire_count': cloud.get('fire_count', 0),
                'elapsed': str(cloud.get('elapsed', '')),
                'distance_from_price': cloud.get('distance_from_price', 0),
                'distance_from_prev': cloud.get('distance_from_prev', 0)
            }
        
        # Save to database
        conn = get_db_connection()
        c = conn.cursor()
        
        # values変数を定義
        values = (
            symbol, datetime.now().isoformat(), tf, price,
            daily_dow['status'], daily_dow['bos'], daily_dow['time'],
            swing_dow['status'], swing_dow['bos'], swing_dow['time'],
            ','.join(row_order), ','.join(cloud_order),
            cloud_data.get('5m', {}).get('gc', 0),
            cloud_data.get('5m', {}).get('thickness', 0),
            cloud_data.get('5m', {}).get('angle', 0),
            cloud_data.get('5m', {}).get('fire_count', 0),
            cloud_data.get('5m', {}).get('elapsed', ''),
            cloud_data.get('5m', {}).get('distance_from_price', 0),
            cloud_data.get('5m', {}).get('distance_from_prev', 0),
            cloud_data.get('15m', {}).get('gc', 0),
            cloud_data.get('15m', {}).get('thickness', 0),
            cloud_data.get('15m', {}).get('angle', 0),
            cloud_data.get('15m', {}).get('fire_count', 0),
            cloud_data.get('15m', {}).get('elapsed', ''),
            cloud_data.get('15m', {}).get('distance_from_price', 0),
            cloud_data.get('15m', {}).get('distance_from_prev', 0),
            cloud_data.get('1H', {}).get('gc', 0),
            cloud_data.get('1H', {}).get('thickness', 0),
            cloud_data.get('1H', {}).get('angle', 0),
            cloud_data.get('1H', {}).get('fire_count', 0),
            cloud_data.get('1H', {}).get('elapsed', ''),
            cloud_data.get('1H', {}).get('distance_from_price', 0),
            cloud_data.get('1H', {}).get('distance_from_prev', 0),
            cloud_data.get('4H', {}).get('gc', 0),
            cloud_data.get('4H', {}).get('thickness', 0),
            cloud_data.get('4H', {}).get('angle', 0),
            cloud_data.get('4H', {}).get('fire_count', 0),
            cloud_data.get('4H', {}).get('elapsed', ''),
            cloud_data.get('4H', {}).get('distance_from_price', 0),
            cloud_data.get('4H', {}).get('distance_from_prev', 0)
        )
        
        if is_postgresql():
            # PostgreSQLの場合
            c.execute("""INSERT INTO current_states 
                         (symbol, timestamp, tf, price,
                          daily_dow_status, daily_dow_bos, daily_dow_time,
                          swing_dow_status, swing_dow_bos, swing_dow_time,
                          row_order,
                          cloud_order,
                          cloud_5m_gc, cloud_5m_thickness, cloud_5m_angle, cloud_5m_fire_count, cloud_5m_elapsed,
                          cloud_5m_distance_from_price, cloud_5m_distance_from_prev,
                          cloud_15m_gc, cloud_15m_thickness, cloud_15m_angle, cloud_15m_fire_count, cloud_15m_elapsed,
                          cloud_15m_distance_from_price, cloud_15m_distance_from_prev,
                          cloud_1h_gc, cloud_1h_thickness, cloud_1h_angle, cloud_1h_fire_count, cloud_1h_elapsed,
                          cloud_1h_distance_from_price, cloud_1h_distance_from_prev,
                          cloud_4h_gc, cloud_4h_thickness, cloud_4h_angle, cloud_4h_fire_count, cloud_4h_elapsed,
                          cloud_4h_distance_from_price, cloud_4h_distance_from_prev)
                         VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                         ON CONFLICT (symbol) DO UPDATE SET
                             timestamp = EXCLUDED.timestamp,
                             tf = EXCLUDED.tf,
                             price = EXCLUDED.price,
                             daily_dow_status = EXCLUDED.daily_dow_status,
                             daily_dow_bos = EXCLUDED.daily_dow_bos,
                             daily_dow_time = EXCLUDED.daily_dow_time,
                             swing_dow_status = EXCLUDED.swing_dow_status,
                             swing_dow_bos = EXCLUDED.swing_dow_bos,
                             swing_dow_time = EXCLUDED.swing_dow_time,
                             row_order = EXCLUDED.row_order,
                             cloud_order = EXCLUDED.cloud_order,
                             cloud_5m_gc = EXCLUDED.cloud_5m_gc,
                             cloud_5m_thickness = EXCLUDED.cloud_5m_thickness,
                             cloud_5m_angle = EXCLUDED.cloud_5m_angle,
                             cloud_5m_fire_count = EXCLUDED.cloud_5m_fire_count,
                             cloud_5m_elapsed = EXCLUDED.cloud_5m_elapsed,
                             cloud_5m_distance_from_price = EXCLUDED.cloud_5m_distance_from_price,
                             cloud_5m_distance_from_prev = EXCLUDED.cloud_5m_distance_from_prev,
                             cloud_15m_gc = EXCLUDED.cloud_15m_gc,
                             cloud_15m_thickness = EXCLUDED.cloud_15m_thickness,
                             cloud_15m_angle = EXCLUDED.cloud_15m_angle,
                             cloud_15m_fire_count = EXCLUDED.cloud_15m_fire_count,
                             cloud_15m_elapsed = EXCLUDED.cloud_15m_elapsed,
                             cloud_15m_distance_from_price = EXCLUDED.cloud_15m_distance_from_price,
                             cloud_15m_distance_from_prev = EXCLUDED.cloud_15m_distance_from_prev,
                             cloud_1h_gc = EXCLUDED.cloud_1h_gc,
                             cloud_1h_thickness = EXCLUDED.cloud_1h_thickness,
                             cloud_1h_angle = EXCLUDED.cloud_1h_angle,
                             cloud_1h_fire_count = EXCLUDED.cloud_1h_fire_count,
                             cloud_1h_elapsed = EXCLUDED.cloud_1h_elapsed,
                             cloud_1h_distance_from_price = EXCLUDED.cloud_1h_distance_from_price,
                             cloud_1h_distance_from_prev = EXCLUDED.cloud_1h_distance_from_prev,
                             cloud_4h_gc = EXCLUDED.cloud_4h_gc,
                             cloud_4h_thickness = EXCLUDED.cloud_4h_thickness,
                             cloud_4h_angle = EXCLUDED.cloud_4h_angle,
                             cloud_4h_fire_count = EXCLUDED.cloud_4h_fire_count,
                             cloud_4h_elapsed = EXCLUDED.cloud_4h_elapsed,
                             cloud_4h_distance_from_price = EXCLUDED.cloud_4h_distance_from_price,
                             cloud_4h_distance_from_prev = EXCLUDED.cloud_4h_distance_from_prev""",
                      values)
        else:
            # SQLiteの場合
            placeholders = ', '.join(['?'] * 40)
            c.execute(f"""INSERT OR REPLACE INTO current_states 
                         (symbol, timestamp, tf, price,
                          daily_dow_status, daily_dow_bos, daily_dow_time,
                          swing_dow_status, swing_dow_bos, swing_dow_time,
                          row_order,
                          cloud_order,
                          cloud_5m_gc, cloud_5m_thickness, cloud_5m_angle, cloud_5m_fire_count, cloud_5m_elapsed,
                          cloud_5m_distance_from_price, cloud_5m_distance_from_prev,
                          cloud_15m_gc, cloud_15m_thickness, cloud_15m_angle, cloud_15m_fire_count, cloud_15m_elapsed,
                          cloud_15m_distance_from_price, cloud_15m_distance_from_prev,
                          cloud_1H_gc, cloud_1H_thickness, cloud_1H_angle, cloud_1H_fire_count, cloud_1H_elapsed,
                          cloud_1H_distance_from_price, cloud_1H_distance_from_prev,
                          cloud_4H_gc, cloud_4H_thickness, cloud_4H_angle, cloud_4H_fire_count, cloud_4H_elapsed,
                          cloud_4H_distance_from_price, cloud_4H_distance_from_prev)
                         VALUES ({placeholders})""",
                      values)
        
        conn.commit()
        conn.close()
        
        # Analyze clouds and generate notifications (発火時のみ通知)
        notifications = analyze_clouds(symbol, price, clouds)
        
        # 発火履歴を保存（通知が発生した時のみ）
        if len(notifications) > 0:
            conn = get_db_connection()
            c = conn.cursor()
            for notif in notifications:
                if is_postgresql():
                    c.execute("""INSERT INTO fire_history (timestamp, symbol, cloud_label, fire_count, gc, message)
                                 VALUES (%s, %s, %s, %s, %s, %s)""",
                              (datetime.now().isoformat(), symbol, notif['cloud_label'], 
                               cloud_data.get(notif['cloud_label'], {}).get('fire_count', 0),
                               cloud_data.get(notif['cloud_label'], {}).get('gc', 0),
                               notif['message']))
                else:
                    c.execute("""INSERT INTO fire_history (timestamp, symbol, cloud_label, fire_count, gc, message)
                                 VALUES (?, ?, ?, ?, ?, ?)""",
                              (datetime.now().isoformat(), symbol, notif['cloud_label'], 
                               cloud_data.get(notif['cloud_label'], {}).get('fire_count', 0),
                               cloud_data.get(notif['cloud_label'], {}).get('gc', 0),
                               notif['message']))
            conn.commit()
            conn.close()
        
        # Send Discord notifications (発火時のみ)
        for notif in notifications:
            send_discord_notification(notif['line_message'])
            
            # Forward to local client
            forward_to_local_client({
                'alert_type': notif['alert_type'],
                'message': notif['message'],
                'symbol': symbol,
                'price': price,
                'cloud_label': notif['cloud_label']
            })
        
        return jsonify({'status': 'success', 'message': 'State updated', 'notifications': len(notifications)}), 200
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'healthy'}), 200

@app.route('/', methods=['GET'])
def dashboard():
    """Webダッシュボード"""
    return render_template('dashboard.html')

@app.route('/current_states', methods=['GET'])
def get_current_states():
    """全通貨ペアの現在状態を取得"""
    try:
        conn = get_db_connection()
        if is_postgresql():
            try:
                import psycopg2.extras
                cursor_factory = psycopg2.extras.RealDictCursor
            except ImportError:
                cursor_factory = None
            
            if cursor_factory:
                c = conn.cursor(cursor_factory=cursor_factory)
                c.execute("""SELECT * FROM current_states ORDER BY symbol""")
                states = c.fetchall()
                conn.close()
                
                result = []
                for s in states:
                    result.append({
                        'symbol': s['symbol'],
                        'timestamp': s['timestamp'],
                        'tf': s['tf'],
                        'price': s['price'],
                        'daily_dow': {
                            'status': s['daily_dow_status'] or '',
                            'bos': s['daily_dow_bos'] or '',
                            'time': s['daily_dow_time'] or ''
                        },
                        'swing_dow': {
                            'status': s['swing_dow_status'] or '',
                            'bos': s['swing_dow_bos'] or '',
                            'time': s['swing_dow_time'] or ''
                        },
                        'row_order': s['row_order'].split(',') if s['row_order'] else ['price', '5m', '15m', '1H', '4H'],
                        'cloud_order': s['cloud_order'].split(',') if s['cloud_order'] else ['5m', '15m', '1H', '4H'],
                        'clouds': {
                            '5m': {
                                'gc': bool(s['cloud_5m_gc']),
                                'thickness': s['cloud_5m_thickness'],
                                'angle': s['cloud_5m_angle'],
                                'fire_count': s['cloud_5m_fire_count'],
                                'elapsed': s['cloud_5m_elapsed'],
                                'distance_from_price': s['cloud_5m_distance_from_price'],
                                'distance_from_prev': s['cloud_5m_distance_from_prev']
                            },
                            '15m': {
                                'gc': bool(s['cloud_15m_gc']),
                                'thickness': s['cloud_15m_thickness'],
                                'angle': s['cloud_15m_angle'],
                                'fire_count': s['cloud_15m_fire_count'],
                                'elapsed': s['cloud_15m_elapsed'],
                                'distance_from_price': s['cloud_15m_distance_from_price'],
                                'distance_from_prev': s['cloud_15m_distance_from_prev']
                            },
                            '1H': {
                                'gc': bool(s['cloud_1h_gc']),
                                'thickness': s['cloud_1h_thickness'],
                                'angle': s['cloud_1h_angle'],
                                'fire_count': s['cloud_1h_fire_count'],
                                'elapsed': s['cloud_1h_elapsed'],
                                'distance_from_price': s['cloud_1h_distance_from_price'],
                                'distance_from_prev': s['cloud_1h_distance_from_prev']
                            },
                            '4H': {
                                'gc': bool(s['cloud_4h_gc']),
                                'thickness': s['cloud_4h_thickness'],
                                'angle': s['cloud_4h_angle'],
                                'fire_count': s['cloud_4h_fire_count'],
                                'elapsed': s['cloud_4h_elapsed'],
                                'distance_from_price': s['cloud_4h_distance_from_price'],
                                'distance_from_prev': s['cloud_4h_distance_from_prev']
                            }
                        }
                    })
                
                return jsonify({
                    'status': 'success',
                    'states': result
                }), 200
            else:
                # psycopg2が利用できない場合はSQLiteとして扱う
                c = conn.cursor()
                c.execute("""SELECT * FROM current_states ORDER BY symbol""")
                states = c.fetchall()
                conn.close()
                
                result = []
                for s in states:
                    result.append({
                        'symbol': s[0],
                        'timestamp': s[1],
                        'tf': s[2],
                        'price': s[3],
                        'daily_dow': {
                            'status': s[4] or '',
                            'bos': s[5] or '',
                            'time': s[6] or ''
                        },
                        'swing_dow': {
                            'status': s[7] or '',
                            'bos': s[8] or '',
                            'time': s[9] or ''
                        },
                        'row_order': s[10].split(',') if s[10] else ['price', '5m', '15m', '1H', '4H'],
                        'cloud_order': s[11].split(',') if s[11] else ['5m', '15m', '1H', '4H'],
                        'clouds': {
                            '5m': {
                                'gc': bool(s[12]),
                                'thickness': s[13],
                                'angle': s[14],
                                'fire_count': s[15],
                                'elapsed': s[16],
                                'distance_from_price': s[17],
                                'distance_from_prev': s[18]
                            },
                            '15m': {
                                'gc': bool(s[19]),
                                'thickness': s[20],
                                'angle': s[21],
                                'fire_count': s[22],
                                'elapsed': s[23],
                                'distance_from_price': s[24],
                                'distance_from_prev': s[25]
                            },
                            '1H': {
                                'gc': bool(s[26]),
                                'thickness': s[27],
                                'angle': s[28],
                                'fire_count': s[29],
                                'elapsed': s[30],
                                'distance_from_price': s[31],
                                'distance_from_prev': s[32]
                            },
                            '4H': {
                                'gc': bool(s[33]),
                                'thickness': s[34],
                                'angle': s[35],
                                'fire_count': s[36],
                                'elapsed': s[37],
                                'distance_from_price': s[38],
                                'distance_from_prev': s[39]
                            }
                        }
                    })
                
                return jsonify({
                    'status': 'success',
                    'states': result
                }), 200
        else:
            # SQLiteの場合
            c = conn.cursor()
            c.execute("""SELECT * FROM current_states ORDER BY symbol""")
            states = c.fetchall()
            conn.close()
            
            result = []
            for s in states:
                result.append({
                    'symbol': s[0],
                    'timestamp': s[1],
                    'tf': s[2],
                    'price': s[3],
                    'daily_dow': {
                        'status': s[4] or '',
                        'bos': s[5] or '',
                        'time': s[6] or ''
                    },
                    'swing_dow': {
                        'status': s[7] or '',
                        'bos': s[8] or '',
                        'time': s[9] or ''
                    },
                    'row_order': s[10].split(',') if s[10] else ['price', '5m', '15m', '1H', '4H'],
                    'cloud_order': s[11].split(',') if s[11] else ['5m', '15m', '1H', '4H'],
                    'clouds': {
                        '5m': {
                            'gc': bool(s[12]),
                            'thickness': s[13],
                            'angle': s[14],
                            'fire_count': s[15],
                            'elapsed': s[16],
                            'distance_from_price': s[17],
                            'distance_from_prev': s[18]
                        },
                        '15m': {
                            'gc': bool(s[19]),
                            'thickness': s[20],
                            'angle': s[21],
                            'fire_count': s[22],
                            'elapsed': s[23],
                            'distance_from_price': s[24],
                            'distance_from_prev': s[25]
                        },
                        '1H': {
                            'gc': bool(s[26]),
                            'thickness': s[27],
                            'angle': s[28],
                            'fire_count': s[29],
                            'elapsed': s[30],
                            'distance_from_price': s[31],
                            'distance_from_prev': s[32]
                        },
                        '4H': {
                            'gc': bool(s[33]),
                            'thickness': s[34],
                            'angle': s[35],
                            'fire_count': s[36],
                            'elapsed': s[37],
                            'distance_from_price': s[38],
                            'distance_from_prev': s[39]
                        }
                    }
                })
        
        return jsonify({
            'status': 'success',
            'states': result
        }), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/fire_history', methods=['GET'])
def get_fire_history():
    """発火履歴を取得"""
    try:
        conn = get_db_connection()
        if is_postgresql():
            try:
                import psycopg2.extras
                cursor_factory = psycopg2.extras.RealDictCursor
            except ImportError:
                cursor_factory = None
            
            if cursor_factory:
                c = conn.cursor(cursor_factory=cursor_factory)
                c.execute("""SELECT * FROM fire_history ORDER BY timestamp DESC LIMIT 50""")
                history = c.fetchall()
                conn.close()
                
                result = []
                for h in history:
                    result.append({
                        'id': h['id'],
                        'timestamp': h['timestamp'],
                        'symbol': h['symbol'],
                        'cloud_label': h['cloud_label'],
                        'fire_count': h['fire_count'],
                        'gc': bool(h['gc']),
                        'message': h['message']
                    })
                
                return jsonify({
                    'status': 'success',
                    'history': result
                }), 200
            else:
                # psycopg2が利用できない場合はSQLiteとして扱う
                c = conn.cursor()
                c.execute("""SELECT * FROM fire_history ORDER BY timestamp DESC LIMIT 50""")
                history = c.fetchall()
                conn.close()
                
                result = []
                for h in history:
                    result.append({
                        'id': h[0],
                        'timestamp': h[1],
                        'symbol': h[2],
                        'cloud_label': h[3],
                        'fire_count': h[4],
                        'gc': bool(h[5]),
                        'message': h[6]
                    })
                
                return jsonify({
                    'status': 'success',
                    'history': result
                }), 200
        else:
            # SQLiteの場合
            c = conn.cursor()
            c.execute("""SELECT * FROM fire_history ORDER BY timestamp DESC LIMIT 50""")
            history = c.fetchall()
            conn.close()
            
            result = []
            for h in history:
                result.append({
                    'id': h[0],
                    'timestamp': h[1],
                    'symbol': h[2],
                    'cloud_label': h[3],
                    'fire_count': h[4],
                    'gc': bool(h[5]),
                    'message': h[6]
                })
        
        return jsonify({
            'status': 'success',
            'history': result
        }), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

def open_browser():
    """サーバー起動後にブラウザを自動で開く"""
    webbrowser.open('http://localhost:5000')

if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 5000))
    
    # Render環境ではブラウザ自動起動を無効化
    if os.environ.get('RENDER') != 'true':
        # ローカル開発時のみブラウザを開く
        if os.environ.get('WERKZEUG_RUN_MAIN') != 'true':
            threading.Timer(1.5, open_browser).start()
    
    app.run(host='0.0.0.0', port=port, debug=(os.environ.get('FLASK_ENV') == 'development'))
