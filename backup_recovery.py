"""
TradingView メールバックアップ取得・復旧スクリプト
Gmail から JSON を抽出してローカルに保存する
"""
import os
import json
import re
from datetime import datetime
import pytz
import base64
from pathlib import Path

# Gmail API imports（後で設定）
try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    GMAIL_API_AVAILABLE = True
except ImportError:
    GMAIL_API_AVAILABLE = False
    print('[WARNING] Gmail API libraries not installed. Install with: pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client')

# バックアップディレクトリ
BACKUP_DIR = r'C:\Users\kanda\Desktop\TradingViewBackup_JSON'
JST = pytz.timezone('Asia/Tokyo')

# Gmail API スコープ
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

def ensure_backup_structure():
    """バックアップフォルダ構造を確認・作成"""
    Path(BACKUP_DIR).mkdir(parents=True, exist_ok=True)
    print(f'[OK] Backup directory ensured: {BACKUP_DIR}')

def extract_json_from_email_body(body):
    """
    メール本文（HTML形式）から JSON を抽出
    HTML エンティティエンコードされた JSON に対応
    複数の JSON が本文にある場合: sent_time + clouds を持つ最大のデータ JSON を優先して返す
    """
    import html

    # HTML エンティティをデコード（&#34; → " など）
    body_decoded = html.unescape(body)

    print(f'[DEBUG] Body length: {len(body_decoded)} chars')
    if body_decoded:
        preview = body_decoded[:500].replace('\n', '\\n').replace('\r', '\\r')
        safe_preview = preview.encode('ascii', 'backslashreplace').decode('ascii')
        print(f'[DEBUG] Body preview: {safe_preview}')

    def _extract_all_json_candidates(text):
        """{"symbol" から始まる JSON を本文内で全て抽出して返す"""
        results = []
        search_start = 0
        while True:
            pos = text.find('{"symbol"', search_start)
            if pos < 0:
                break
            depth = 0
            in_str = False
            esc = False
            end_pos = pos
            for i in range(pos, len(text)):
                ch = text[i]
                if esc:
                    esc = False
                    continue
                if ch == '\\':
                    esc = True
                    continue
                if ch == '"':
                    in_str = not in_str
                    continue
                if not in_str:
                    if ch == '{':
                        depth += 1
                    elif ch == '}':
                        depth -= 1
                        if depth == 0:
                            end_pos = i
                            break
            json_str = text[pos:end_pos + 1]
            try:
                d = json.loads(json_str)
                if 'symbol' in d and 'tf' in d:
                    results.append(d)
                    safe = json_str[:150].encode('ascii', 'backslashreplace').decode('ascii')
                    print(f'[DEBUG] Candidate JSON (len={len(json_str)}): symbol={d.get("symbol")}, tf={d.get("tf")}, has_sent_time={"sent_time" in d}, has_clouds={"clouds" in d}, has_sg={"sg" in d}')
            except json.JSONDecodeError:
                pass
            search_start = end_pos + 1
        return results

    candidates = _extract_all_json_candidates(body_decoded)

    if not candidates:
        print('[DEBUG] No JSON candidates found in body')
        return None

    # 優先スコア: sent_time あり(+4) + clouds あり(+2) + sg なし(+1)
    def _score(d):
        return (int(bool(d.get('sent_time'))) * 4 +
                int(bool(d.get('clouds'))) * 2 +
                int('sg' not in d))

    best = max(candidates, key=lambda d: (_score(d), len(json.dumps(d))))
    print(f'[DEBUG] Selected JSON: symbol={best.get("symbol")}, tf={best.get("tf")}, score={_score(best)}')
    return best

def save_json_to_file(json_data, email_received_time=None):
    """
    JSON データをローカルファイルに保存
    フォルダ構造: TradingViewBackup_JSON/SYMBOL/TF/YYYYMMDD_HHMM_senttime_TF_ts.json

    ファイル名は sent_time（バー時刻）を最優先で使う。
    同じバーのシグナルアラートと正規データが同じメール受信時刻で届いても
    sent_time が違えば衝突しないため、正規データが保存されなくなる問題を防ぐ。

    Args:
        json_data: JSONデータ
        email_received_time: メール受信日時（ミリ秒単位タイムスタンプ）
    """
    try:
        symbol = json_data.get('symbol', 'UNKNOWN')
        tf = json_data.get('tf', '5')
        sent_time_val = json_data.get('sent_time', '')

        # ---- シグナルペイロード拒否 ----
        # TradingView のシグナルアラートは sg キーがあり clouds がない
        if 'sg' in json_data and not json_data.get('clouds'):
            print(f'[SKIP] Signal payload (sg={json_data["sg"]}, no clouds): {symbol}/{tf}')
            return False
        # sent_time も clouds も ない完全な空ペイロード
        if not sent_time_val and not json_data.get('clouds'):
            print(f'[SKIP] Empty payload (no sent_time, no clouds): {symbol}/{tf}')
            return False
        # ---- 拒否ここまで ----

        # Pine Script から送信された send_time を優先、なければ time フィールドを使用
        time_ms = json_data.get('send_time', json_data.get('time', 0))

        # デバッグ: D, W, M, Y の場合はログ出力
        if tf in ('D', 'W', 'M', 'Y'):
            print(f'[DEBUG] Processing {symbol} {tf}: has clouds={"clouds" in json_data}, sent_time={sent_time_val}, time_ms={time_ms}')

        # 時間足を正規化（JSON表現は数値コードに統一）
        tf_normalized = tf
        if tf in ('5', '5m', '5M'):
            tf_normalized = '5'
        elif tf in ('15', '15m', '15M'):
            tf_normalized = '15'
        elif tf in ('1', '60', '1H', '1h'):
            tf_normalized = '60'
        elif tf in ('4', '240', '4H', '4h'):
            tf_normalized = '240'
        elif tf in ('D', 'W', 'M', 'Y'):
            tf_normalized = tf  # D, W, M, Y はそのまま

        # ---- ファイル名生成 ----
        # 優先順位:
        #   1. sent_time (バー確定時刻) → 同一バーの別メールが衝突しない
        #   2. email_received_time (メール受信時刻)
        #   3. time_ms (PineScript の time フィールド)
        #   4. 現在時刻
        if sent_time_val:
            try:
                parts = sent_time_val.split('/')
                if len(parts) == 4:
                    yy, mm, dd, hhmm = parts
                    hh, mn = hhmm.split(':')
                    dt = JST.localize(datetime(2000 + int(yy), int(mm), int(dd), int(hh), int(mn)))
                    ts_ms = int(dt.timestamp() * 1000)
                    filename = dt.strftime('%Y%m%d_%H%M') + f'_senttime_{tf_normalized}_{ts_ms}.json'
                    print(f'[INFO] Using sent_time: {sent_time_val} -> {filename}')
                else:
                    raise ValueError('unexpected sent_time format')
            except Exception as _e:
                print(f'[WARNING] Cannot parse sent_time "{sent_time_val}": {_e}')
                if email_received_time and email_received_time > 0:
                    dt = datetime.fromtimestamp(email_received_time / 1000, tz=JST)
                    filename = dt.strftime('%Y%m%d_%H%M%S') + f'_{tf_normalized}_{email_received_time}.json'
                else:
                    now_ms = int(datetime.now(JST).timestamp() * 1000)
                    filename = datetime.now(JST).strftime('%Y%m%d_%H%M%S') + f'_{tf_normalized}_{now_ms}.json'
        elif email_received_time and email_received_time > 0:
            dt = datetime.fromtimestamp(email_received_time / 1000, tz=JST)
            filename = dt.strftime('%Y%m%d_%H%M%S') + f'_{tf_normalized}_{email_received_time}.json'
            print(f'[INFO] Using email_received_time: {email_received_time} -> {filename}')
        elif time_ms and time_ms > 0:
            dt = datetime.fromtimestamp(time_ms / 1000, tz=JST)
            filename = dt.strftime('%Y%m%d_%H%M%S') + f'_{tf_normalized}_{time_ms}.json'
            print(f'[INFO] Using time_ms: {time_ms} -> {filename}')
        else:
            now_ms = int(datetime.now(JST).timestamp() * 1000)
            filename = datetime.now(JST).strftime('%Y%m%d_%H%M%S') + f'_{tf_normalized}_{now_ms}.json'
            print(f'[WARNING] No valid timestamp. email_received_time={email_received_time}, time_ms={time_ms}, using now: {now_ms}')
        # ---- ファイル名生成ここまで ----

        # フォルダ作成
        folder_path = Path(BACKUP_DIR) / symbol / tf_normalized
        folder_path.mkdir(parents=True, exist_ok=True)

        # ファイル保存
        file_path = folder_path / filename

        # 既存ファイルがある場合はスキップ
        if file_path.exists():
            print(f'[SKIP] File already exists: {file_path.name}')
            return False

        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, ensure_ascii=False, indent=2)

        print(f'[SAVED] {symbol}/{tf_normalized}: {filename}')
        return True

    except Exception as e:
        error_msg = str(e).encode('ascii', 'backslashreplace').decode('ascii')
        print(f'[ERROR] Failed to save JSON: {error_msg}')
        return False

def fetch_from_gmail(max_results=500, mark_as_read=False, after_days=0):
    """
    Gmail から TradingView メールを取得して保存
    
    Args:
        max_results: 取得する最大メール数
        mark_as_read: 処理後に既読にするか
        after_days: 0より大きい場合、Google の newer_than:Nd フィルタを付加
    
    Returns:
        (成功数, スキップ数, エラー数)
    """
    if not GMAIL_API_AVAILABLE:
        print('[ERROR] Gmail API libraries not installed.')
        return (0, 0, 1)
    
    try:
        # 認証情報を読み込み
        creds = None
        token_path = os.path.join(os.path.dirname(__file__), 'token.json')
        credentials_path = os.path.join(os.path.dirname(__file__), 'credentials.json')
        
        # トークンファイルがあれば読み込み
        if os.path.exists(token_path):
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)
        
        # 認証情報がないか無効な場合は再認証
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists(credentials_path):
                    print('[ERROR] credentials.json not found. Please follow Gmail API setup instructions.')
                    return (0, 0, 1)
                
                flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
                creds = flow.run_local_server(port=0)
            
            # トークンを保存
            with open(token_path, 'w') as token:
                token.write(creds.to_json())
        
        # Gmail API サービス構築(タイムアウト付き)
        service = build('gmail', 'v1', credentials=creds, static_discovery=False)
        
        # TradingView からのメールを検索（既読・未読問わず）
        query = 'from:noreply@tradingview.com'
        if after_days and after_days > 0:
            query += f' newer_than:{after_days}d'
            print(f'[INFO] Gmail query with date filter: {query}')
        try:
            results = service.users().messages().list(
                userId='me',
                q=query,
                maxResults=max_results
            ).execute(num_retries=2)  # リトライを追加
        except Exception as e:
            print(f'[ERROR] Failed to list messages: {str(e)}')
            return (0, 0, 1)
        
        messages = results.get('messages', [])
        
        if not messages:
            print('[INFO] No emails found.')
            return (0, 0, 0)
        
        print(f'[INFO] Found {len(messages)} emails from TradingView')
        
        success_count = 0
        skip_count = 0
        error_count = 0
        
        for msg in messages:
            try:
                # メッセージの詳細を取得
                print(f'\n[PROCESSING] Message ID: {msg["id"]}')
                message = service.users().messages().get(
                    userId='me',
                    id=msg['id'],
                    format='full'
                ).execute(num_retries=2)  # リトライを追加
                
                # メール本文を取得
                payload = message['payload']
                body = ''
                
                # multipart メールまたは通常のメール
                def get_body_from_payload(p, msg_id):
                    """再帰的に本体を取得（attachmentId 対応）"""
                    if 'parts' in p:
                        # multipart
                        for part in p['parts']:
                            mime_type = part.get('mimeType', '')
                            part_body = part.get('body', {})
                            
                            # body data がある場合
                            if part_body.get('data'):
                                if mime_type == 'text/plain':
                                    return base64.urlsafe_b64decode(part_body['data']).decode('utf-8')
                            
                            # body data がなく attachmentId がある場合（大きいメール本文）
                            elif part_body.get('attachmentId'):
                                if mime_type == 'text/plain':
                                    attachment_id = part_body['attachmentId']
                                    try:
                                        attachment = service.users().messages().attachments().get(
                                            userId='me',
                                            messageId=msg_id,
                                            id=attachment_id
                                        ).execute(num_retries=2)
                                        data = attachment.get('data', '')
                                        if data:
                                            return base64.urlsafe_b64decode(data).decode('utf-8')
                                    except Exception as e:
                                        print(f'[WARNING] Failed to get attachment: {str(e)}')
                                        pass
                        
                        # plain text がない場合は HTML を取得
                        for part in p['parts']:
                            mime_type = part.get('mimeType', '')
                            part_body = part.get('body', {})
                            
                            if part_body.get('data'):
                                if mime_type == 'text/html':
                                    return base64.urlsafe_b64decode(part_body['data']).decode('utf-8')
                            elif part_body.get('attachmentId'):
                                if mime_type == 'text/html':
                                    attachment_id = part_body['attachmentId']
                                    try:
                                        attachment = service.users().messages().attachments().get(
                                            userId='me',
                                            messageId=msg_id,
                                            id=attachment_id
                                        ).execute(num_retries=2)
                                        data = attachment.get('data', '')
                                        if data:
                                            return base64.urlsafe_b64decode(data).decode('utf-8')
                                    except Exception as e:
                                        print(f'[WARNING] Failed to get HTML attachment: {str(e)}')
                                        pass
                        
                        # さらに nested parts をチェック
                        for part in p['parts']:
                            if 'parts' in part:
                                result = get_body_from_payload(part, msg_id)
                                if result:
                                    return result
                    else:
                        # single part
                        part_body = p.get('body', {})
                        if part_body.get('data'):
                            return base64.urlsafe_b64decode(part_body['data']).decode('utf-8')
                        elif part_body.get('attachmentId'):
                            attachment_id = part_body['attachmentId']
                            try:
                                attachment = service.users().messages().attachments().get(
                                    userId='me',
                                    messageId=msg_id,
                                    id=attachment_id
                                ).execute(num_retries=2)
                                data = attachment.get('data', '')
                                if data:
                                    return base64.urlsafe_b64decode(data).decode('utf-8')
                            except Exception as e:
                                print(f'[WARNING] Failed to get single attachment: {str(e)}')
                                pass
                    return None
                
                body = get_body_from_payload(payload, msg['id']) or ''
                
                if not body:
                    print(f'[SKIP] No body found in message {msg["id"]}')
                    skip_count += 1
                    continue
                
                print(f'[DEBUG] Body extracted, length={len(body)} chars')
                
                # JSON を抽出
                json_data = extract_json_from_email_body(body)
                
                if json_data:
                    # メールの受信日時を取得（internalDateはミリ秒単位のタイムスタンプ）
                    email_time_ms = int(message.get('internalDate', 0))
                    print(f'[DEBUG] Email ID={msg["id"]}, internalDate={message.get("internalDate")}, email_time_ms={email_time_ms}')
                    
                    # ファイルに保存（メール受信日時を渡す）
                    saved = save_json_to_file(json_data, email_received_time=email_time_ms)
                    if saved:
                        success_count += 1
                    else:
                        skip_count += 1
                    
                    # 既読マークを付ける
                    if mark_as_read:
                        try:
                            service.users().messages().modify(
                                userId='me',
                                id=msg['id'],
                                body={'removeLabelIds': ['UNREAD']}
                            ).execute(num_retries=2)
                        except Exception as e:
                            print(f'[WARNING] Failed to mark message as read: {str(e)}')
                            pass
                else:
                    print(f'[SKIP] No JSON found in message {msg["id"]}')
                    skip_count += 1
                    
            except Exception as e:
                # Unicode文字を含むエラーメッセージを安全に出力
                error_msg = str(e).encode('ascii', 'backslashreplace').decode('ascii')
                print(f'[ERROR] Failed to process message {msg["id"]}: {error_msg}')
                error_count += 1
                continue
        
        print(f'\n[SUMMARY] Success: {success_count}, Skipped: {skip_count}, Errors: {error_count}')
        return (success_count, skip_count, error_count)
        
    except Exception as e:
        error_msg = str(e).encode('ascii', 'backslashreplace').decode('ascii')
        print(f'[CRITICAL ERROR] Gmail API failed: {error_msg}')
        import traceback
        traceback.print_exc()
        return (0, 0, 1)

def list_backup_files(symbol=None, tf=None, date=None):
    """
    バックアップファイル一覧を取得
    
    Args:
        symbol: 通貨ペア（None=全て）
        tf: 時間足（None=全て）
        date: 日付（YYYYMMdd形式、None=全て）
    
    Returns:
        List[Path]: ファイルパスのリスト
    """
    backup_path = Path(BACKUP_DIR)
    
    if not backup_path.exists():
        return []
    
    files = []
    
    # 通貨フォルダを走査
    if symbol:
        symbol_folders = [backup_path / symbol]
    else:
        symbol_folders = [f for f in backup_path.iterdir() if f.is_dir()]
    
    for symbol_folder in symbol_folders:
        if not symbol_folder.exists():
            continue
        
        # 時間足フォルダを走査
        if tf:
            tf_folders = [symbol_folder / tf]
        else:
            tf_folders = [f for f in symbol_folder.iterdir() if f.is_dir()]
        
        for tf_folder in tf_folders:
            if not tf_folder.exists():
                continue
            
            # JSON ファイルを取得
            for json_file in tf_folder.glob('*.json'):
                # 日付フィルタ
                if date:
                    if not json_file.name.startswith(date):
                        continue
                
                files.append(json_file)
    
    # タイムスタンプでソート
    files.sort()
    return files

def print_backup_summary():
    """バックアップの概要を表示"""
    backup_path = Path(BACKUP_DIR)
    
    if not backup_path.exists():
        print('[INFO] Backup directory not found.')
        return
    
    print('\n===== Backup Summary =====')
    
    for symbol_folder in sorted(backup_path.iterdir()):
        if not symbol_folder.is_dir():
            continue
        
        symbol = symbol_folder.name
        print(f'\n{symbol}:')
        
        for tf_folder in sorted(symbol_folder.iterdir()):
            if not tf_folder.is_dir():
                continue
            
            tf = tf_folder.name
            json_files = list(tf_folder.glob('*.json'))
            count = len(json_files)
            
            if count > 0:
                oldest = min(json_files, key=lambda f: f.name)
                newest = max(json_files, key=lambda f: f.name)
                print(f'  {tf}: {count} files ({oldest.name[:15]}...{newest.name[:15]})')
    
    print('\n==========================\n')

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='TradingView Email Backup Tool')
    parser.add_argument('--fetch', action='store_true', help='Fetch emails from Gmail')
    parser.add_argument('--max', type=int, default=500, help='Maximum emails to fetch (default: 500)')
    parser.add_argument('--after-days', type=int, default=0, dest='after_days', help='Only fetch emails newer than N days (e.g. --after-days 3). 0=no filter')
    parser.add_argument('--mark-read', action='store_true', help='Mark emails as read after processing')
    parser.add_argument('--summary', action='store_true', help='Show backup summary')
    parser.add_argument('--list', nargs='*', help='List backup files (optional: symbol tf date)')
    
    args = parser.parse_args()
    
    # フォルダ構造を確保
    ensure_backup_structure()
    
    if args.fetch:
        # Gmail から取得
        after_days_val = args.after_days if hasattr(args, 'after_days') else 0
        print(f'[START] Fetching emails from Gmail (max={args.max}, after_days={after_days_val})...')
        fetch_from_gmail(max_results=args.max, mark_as_read=args.mark_read, after_days=after_days_val)
        print('[DONE]')
    
    elif args.summary:
        # サマリー表示
        print_backup_summary()
    
    elif args.list is not None:
        # ファイル一覧
        symbol = args.list[0] if len(args.list) > 0 else None
        tf = args.list[1] if len(args.list) > 1 else None
        date = args.list[2] if len(args.list) > 2 else None
        
        files = list_backup_files(symbol, tf, date)
        print(f'\nFound {len(files)} files:')
        for f in files:
            print(f'  {f.relative_to(BACKUP_DIR)}')
    
    else:
        # デフォルト: サマリー表示
        print_backup_summary()
