from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

# 認証
creds = Credentials.from_authorized_user_file('token.json')
service = build('gmail', 'v1', credentials=creds)

target_msg_id = '19c2aac6124003e4'  # EURAUD 日足

# backup_recovery.pyと同じクエリで500件取得
print('Fetching emails with query: from:noreply@tradingview.com (max 500)...')
results = service.users().messages().list(
    userId='me',
    q='from:noreply@tradingview.com',
    maxResults=500
).execute()

messages = results.get('messages', [])
print(f'Total emails fetched: {len(messages)}')

# ターゲットメールがリストに含まれているか確認
found = False
for idx, msg in enumerate(messages):
    if msg['id'] == target_msg_id:
        print(f'\n✅ EURAUD daily email FOUND at index {idx}!')
        print(f'Message ID: {msg["id"]}')
        found = True
        break

if not found:
    print(f'\n❌ EURAUD daily email (ID={target_msg_id}) NOT FOUND in the 500 emails')
    print('\nSearching with different query: subject:日毎...')
    
    # 日足専用の検索
    results2 = service.users().messages().list(
        userId='me',
        q='subject:日毎 from:noreply@tradingview.com',
        maxResults=50
    ).execute()
    
    messages2 = results2.get('messages', [])
    print(f'Daily emails found: {len(messages2)}')
    
    # この中にあるか確認
    for idx, msg in enumerate(messages2):
        if msg['id'] == target_msg_id:
            print(f'\n✅ EURAUD daily email FOUND in daily-specific search at index {idx}!')
            break
