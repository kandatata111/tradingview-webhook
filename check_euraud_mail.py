from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
import json

# 認証
creds = Credentials.from_authorized_user_file('token.json')
service = build('gmail', 'v1', credentials=creds)

# EURAUD日足メールを検索
results = service.users().messages().list(
    userId='me',
    q='EURAUD from:noreply@tradingview.com',
    maxResults=10
).execute()

messages = results.get('messages', [])
print(f'Found {len(messages)} EURAUD messages from TradingView\n')

for msg in messages:
    # メッセージの詳細を取得
    message = service.users().messages().get(userId='me', id=msg['id'], format='full').execute()
    
    # 件名を取得
    headers = message.get('payload', {}).get('headers', [])
    subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No subject')
    
    # 受信日時
    internal_date = message.get('internalDate', 0)
    
    print(f'Message ID: {msg["id"]}')
    print(f'Subject: {subject}')
    print(f'Internal Date: {internal_date}')
    
    # 本文からJSONを探す
    def get_body(payload):
        if 'parts' in payload:
            for part in payload['parts']:
                if part.get('mimeType') == 'text/html':
                    import base64
                    data = part.get('body', {}).get('data', '')
                    if data:
                        return base64.urlsafe_b64decode(data).decode('utf-8')
        return payload.get('body', {}).get('data', '')
    
    import base64
    body = get_body(message.get('payload', {}))
    if body:
        body = base64.urlsafe_b64decode(body).decode('utf-8') if body else ''
    
    # JSONを抽出
    start = body.find('{"symbol":')
    if start != -1:
        end = body.find('}', start)
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
            print(f'Symbol: {data.get("symbol")}, TF: {data.get("tf")}')
        except:
            print('Failed to parse JSON')
    
    print('-' * 80)
