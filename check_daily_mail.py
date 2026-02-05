from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
import json

# 認証
creds = Credentials.from_authorized_user_file('token.json')
service = build('gmail', 'v1', credentials=creds)

# 日足メールを検索（「日毎」を含む件名）
results = service.users().messages().list(
    userId='me',
    q='subject:日毎 from:noreply@tradingview.com',
    maxResults=20
).execute()

messages = results.get('messages', [])
print(f'Found {len(messages)} daily messages from TradingView\n')

for msg in messages:
    # メッセージの詳細を取得
    message = service.users().messages().get(userId='me', id=msg['id'], format='full').execute()
    
    # 件名を取得
    headers = message.get('payload', {}).get('headers', [])
    subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No subject')
    
    # 受信日時
    internal_date = message.get('internalDate', 0)
    from datetime import datetime
    import pytz
    dt = datetime.fromtimestamp(int(internal_date)/1000, tz=pytz.timezone('Asia/Tokyo'))
    
    print(f'Message ID: {msg["id"]}')
    print(f'Subject: {subject}')
    print(f'Internal Date: {internal_date} ({dt.strftime("%Y-%m-%d %H:%M:%S JST")})')
    
    # 本文からJSONを探す
    def get_body(payload):
        if 'parts' in payload:
            for part in payload['parts']:
                if part.get('mimeType') == 'text/html':
                    import base64
                    data = part.get('body', {}).get('data', '')
                    if data:
                        return base64.urlsafe_b64decode(data).decode('utf-8')
        body_data = payload.get('body', {}).get('data', '')
        if body_data:
            import base64
            return base64.urlsafe_b64decode(body_data).decode('utf-8')
        return ''
    
    body = get_body(message.get('payload', {}))
    
    # JSONを抽出
    start = body.find('{"symbol":')
    if start != -1:
        # 最後の}を見つける
        brace_count = 1
        i = start + 1
        while i < len(body) and brace_count > 0:
            if body[i] == '{':
                brace_count += 1
            elif body[i] == '}':
                brace_count -= 1
            i += 1
        
        json_str = body[start:i]
        try:
            data = json.loads(json_str)
            symbol = data.get("symbol", "?")
            tf = data.get("tf", "?")
            print(f'Symbol: {symbol}, TF: {tf}')
            
            # EURAUDの場合は詳細表示
            if symbol == 'EURAUD' and tf == 'D':
                print(f'✅ FOUND EURAUD DAILY!')
                print(f'JSON: {json_str[:200]}...')
        except Exception as e:
            print(f'Failed to parse JSON: {e}')
    
    print('-' * 100)
