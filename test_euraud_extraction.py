from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
import json
import base64
import html

# 認証
import os
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

def get_html_body(payload):
    """HTMLボディを取得"""
    mime_type = payload.get('mimeType', '')
    
    if 'parts' in payload:
        for part in payload['parts']:
            part_mime = part.get('mimeType', '')
            if part_mime == 'text/html':
                part_body = part.get('body', {})
                data = part_body.get('data', '')
                if data:
                    return base64.urlsafe_b64decode(data).decode('utf-8')
            elif 'parts' in part:
                result = get_html_body(part)
                if result:
                    return result
    else:
        if mime_type == 'text/html':
            body_data = payload.get('body', {}).get('data', '')
            if body_data:
                return base64.urlsafe_b64decode(body_data).decode('utf-8')
    
    return None

body = get_html_body(payload)

if body:
    print(f'\nOriginal body length: {len(body)}')
    
    # HTML unescapeを実行
    body_decoded = html.unescape(body)
    print(f'Decoded body length: {len(body_decoded)}')
    
    # {"symbol" を探す
    pos = body_decoded.find('{"symbol"')
    print(f'\nSearching for JSON pattern...')
    print(f'Found at position: {pos}')
    
    if pos >= 0:
        # 周辺のコンテキストを表示
        context_start = max(0, pos - 100)
        context_end = min(len(body_decoded), pos + 500)
        print(f'\nContext around JSON:')
        print(body_decoded[context_start:context_end])
        
        # JSONを抽出してパース
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
                        print(f'\n✅ Extracted JSON (length={len(json_str)})')
                        print(f'First 300 chars: {json_str[:300]}')
                        
                        try:
                            data = json.loads(json_str)
                            print(f'\n✅ JSON parsed successfully!')
                            print(f'Symbol: {data.get("symbol")}')
                            print(f'TF: {data.get("tf")}')
                            print(f'Clouds: {len(data.get("clouds", []))} items')
                        except Exception as e:
                            print(f'\n❌ Failed to parse: {e}')
                        break
    else:
        print('\n❌ JSON pattern not found in decoded body')
        
        # HTMLソースで確認
        print('\nSearching in original (escaped) body...')
        escaped_pos = body.find('{&')
        if escaped_pos >= 0:
            print(f'Found escaped JSON at position: {escaped_pos}')
            print(f'Context: {body[escaped_pos:escaped_pos+200]}')
else:
    print('\n❌ Failed to extract HTML body')
