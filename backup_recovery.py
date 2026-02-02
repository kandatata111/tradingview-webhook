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
    括弧のマッチングで正確に抽出
    """
    import html
    
    # HTML エンティティをデコード（&#34; → " など）
    body_decoded = html.unescape(body)
    
    # デバッグ: 本文の一部を表示
    print(f'[DEBUG] Body length: {len(body_decoded)} chars')
    if len(body_decoded) > 0:
        # 最初の500文字を表示
        preview = body_decoded[:500].replace('\n', '\\n').replace('\r', '\\r')
        print(f'[DEBUG] Body preview: {preview}')
    
    # {"symbol" から始まる JSON を探す
    pos = body_decoded.find('{"symbol"')
    if pos < 0:
        print('[DEBUG] JSON pattern not found in body')
        return None
    
    print(f'[DEBUG] Found JSON at position {pos}')
    
    # 括弧のマッチングで JSON 全体を抽出
    depth = 0
    in_string = False
    escape = False
    
    for i in range(pos, len(body_decoded)):
        char = body_decoded[i]
        
        if escape:
            escape = False
            continue
        
        if char == '\\':
            escape = True
            continue
        
        if char == '"':
            in_string = not in_string
            continue
        
        if not in_string:
            if char == '{':
                depth += 1
            elif char == '}':
                depth -= 1
                if depth == 0:
                    json_str = body_decoded[pos:i+1]
                    print(f'[DEBUG] Extracted JSON string (length={len(json_str)}): {json_str[:200]}...')
                    try:
                        data = json.loads(json_str)
                        if 'symbol' in data and 'tf' in data:
                            print(f'[DEBUG] Successfully parsed JSON: symbol={data.get("symbol")}, tf={data.get("tf")}')
                            return data
                        else:
                            print(f'[DEBUG] JSON missing required fields: {data.keys()}')
                    except json.JSONDecodeError as e:
                        print(f'[DEBUG] JSON decode error: {e}')
                        pass
                    break
    
    print('[DEBUG] Failed to extract valid JSON')
    return None

def save_json_to_file(json_data):
    """
    JSON データをローカルファイルに保存
    フォルダ構造: TradingViewBackup_JSON/SYMBOL/TF/YYYYMMDD_HHMMSS_time.json
    """
    try:
        symbol = json_data.get('symbol', 'UNKNOWN')
        tf = json_data.get('tf', '5')
        time_ms = json_data.get('time', 0)
        
        # デバッグ: D, W, M, Yの場合はログ出力
        if tf in ('D', 'W', 'M', 'Y'):
            print(f'[DEBUG] Processing {symbol} {tf}: has clouds={("clouds" in json_data)}, time={time_ms}')
        
        # 時間足を正規化（15m, 1H, 4H, D, W, M, Y）
        tf_normalized = tf
        if tf == '5':
            tf_normalized = '5m'
        elif tf == '15':
            tf_normalized = '15m'
        elif tf in ('1', '60'):
            tf_normalized = '1H'
        elif tf in ('4', '240'):
            tf_normalized = '4H'
        elif tf in ('D', 'W', 'M', 'Y'):
            tf_normalized = tf  # D, W, M, Y はそのまま
        
        # タイムスタンプからファイル名を生成（YYYYMMDD_HHMMSS_TF_timestamp形式）
        if time_ms:
            dt = datetime.fromtimestamp(time_ms / 1000, tz=JST)
            filename = dt.strftime('%Y%m%d_%H%M%S') + f'_{tf_normalized}_{time_ms}.json'
        else:
            # time がない場合は現在時刻
            filename = datetime.now(JST).strftime('%Y%m%d_%H%M%S') + f'_{tf_normalized}_no_time.json'
        
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
        print(f'[ERROR] Failed to save JSON: {e}')
        return False

def fetch_from_gmail(max_results=100, mark_as_read=False):
    """
    Gmail から TradingView メールを取得して保存
    
    Args:
        max_results: 取得する最大メール数
        mark_as_read: 処理後に既読にするか
    
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
        
        # Gmail API サービス構築
        service = build('gmail', 'v1', credentials=creds)
        
        # TradingView からのメールを検索（既読・未読問わず）
        query = 'from:noreply@tradingview.com'
        results = service.users().messages().list(
            userId='me',
            q=query,
            maxResults=max_results
        ).execute()
        
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
                ).execute()
                
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
                                    attachment = service.users().messages().attachments().get(
                                        userId='me',
                                        messageId=msg_id,
                                        id=attachment_id
                                    ).execute()
                                    data = attachment.get('data', '')
                                    if data:
                                        return base64.urlsafe_b64decode(data).decode('utf-8')
                        
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
                                    attachment = service.users().messages().attachments().get(
                                        userId='me',
                                        messageId=msg_id,
                                        id=attachment_id
                                    ).execute()
                                    data = attachment.get('data', '')
                                    if data:
                                        return base64.urlsafe_b64decode(data).decode('utf-8')
                        
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
                            attachment = service.users().messages().attachments().get(
                                userId='me',
                                messageId=msg_id,
                                id=attachment_id
                            ).execute()
                            data = attachment.get('data', '')
                            if data:
                                return base64.urlsafe_b64decode(data).decode('utf-8')
                    return None
                
                body = get_body_from_payload(payload, msg['id']) or ''
                
                if not body:
                    print(f'[SKIP] No body found in message {msg["id"]}')
                    skip_count += 1
                    continue
                
                # JSON を抽出
                json_data = extract_json_from_email_body(body)
                
                if json_data:
                    # ファイルに保存
                    saved = save_json_to_file(json_data)
                    if saved:
                        success_count += 1
                    else:
                        skip_count += 1
                    
                    # 既読マークを付ける
                    if mark_as_read:
                        service.users().messages().modify(
                            userId='me',
                            id=msg['id'],
                            body={'removeLabelIds': ['UNREAD']}
                        ).execute()
                else:
                    print(f'[SKIP] No JSON found in message {msg["id"]}')
                    skip_count += 1
                    
            except Exception as e:
                print(f'[ERROR] Failed to process message {msg["id"]}: {e}')
                error_count += 1
                continue
        
        print(f'\n[SUMMARY] Success: {success_count}, Skipped: {skip_count}, Errors: {error_count}')
        return (success_count, skip_count, error_count)
        
    except Exception as e:
        print(f'[CRITICAL ERROR] Gmail API failed: {e}')
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
    parser.add_argument('--max', type=int, default=100, help='Maximum emails to fetch')
    parser.add_argument('--mark-read', action='store_true', help='Mark emails as read after processing')
    parser.add_argument('--summary', action='store_true', help='Show backup summary')
    parser.add_argument('--list', nargs='*', help='List backup files (optional: symbol tf date)')
    
    args = parser.parse_args()
    
    # フォルダ構造を確保
    ensure_backup_structure()
    
    if args.fetch:
        # Gmail から取得
        print('[START] Fetching emails from Gmail...')
        fetch_from_gmail(max_results=args.max, mark_as_read=args.mark_read)
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
