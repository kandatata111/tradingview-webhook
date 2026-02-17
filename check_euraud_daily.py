from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
import json
import base64
import os

# 認証
token_path = os.path.join(os.path.dirname(__file__), 'token.json')
creds = Credentials.from_authorized_user_file(token_path)
service = build('gmail', 'v1', credentials=creds)

# EURAUD日足メールを直接取得
msg_id = '19c2aac6124003e4'
message = service.users().messages().get(userId='me', id=msg_id, format='full').execute()

print(f'Message ID: {msg_id}')
print(f'Internal Date: {message.get("internalDate")}')

# Payloadを解析
payload = message.get('payload', {})
print(f'\nPayload mimeType: {payload.get("mimeType")}')
print(f'Payload has parts: {("parts" in payload)}')

def get_html_body(payload, msg_id):
    """HTMLボディを取得"""
    mime_type = payload.get('mimeType', '')
    
    if 'parts' in payload:
        # マルチパート
        for part in payload['parts']:
            part_mime = part.get('mimeType', '')
            print(f'  Part mimeType: {part_mime}')
            
            if part_mime == 'text/html':
                part_body = part.get('body', {})
                data = part_body.get('data', '')
                if data:
                    return base64.urlsafe_b64decode(data).decode('utf-8')
            elif 'parts' in part:
                # ネストされたパーツ
                result = get_html_body(part, msg_id)
                if result:
                    return result
    else:
        # シングルパート
        if mime_type == 'text/html':
            body_data = payload.get('body', {}).get('data', '')
            if body_data:
                return base64.urlsafe_b64decode(body_data).decode('utf-8')
    
    return None

body = get_html_body(payload, msg_id)

if body:
    print(f'\nBody length: {len(body)}')
    
    # JSONを探す（いろいろなパターンで）
    patterns = [
        '{"symbol":',
        '{"symbol"',
        '"symbol":"EURAUD"',
        'EURAUD',
        '"tf":"D"'
    ]
    
    for pattern in patterns:
        if pattern in body:
            idx = body.find(pattern)
            print(f'\n✅ Found pattern "{pattern}" at position {idx}')
            # context = body[max(0,idx-50):idx+200]
            # print(f'Context: ...{context}...')
        else:
            print(f'\n❌ Pattern "{pattern}" not found')
    
    # ファイルに保存（UTF-8）
    with open('euraud_body.html', 'w', encoding='utf-8') as f:
        f.write(body)
    print(f'\n✅ Body saved to euraud_body.html')
else:
    print('\n❌ Failed to extract HTML body')
