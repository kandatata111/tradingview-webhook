import sqlite3
import json

conn = sqlite3.connect('webhook_data.db')
c = conn.cursor()
c.execute('SELECT id, name, enabled, rule_json FROM rules')
rows = c.fetchall()

print('=== 全ルールの音声設定 ===\n')
for r in rows:
    rule_id, name, enabled, rule_json = r
    rule_data = json.loads(rule_json)
    voice_settings = rule_data.get('voice', {})
    
    print(f'【ルールID】 {rule_id}')
    print(f'【名前】 {name}')
    print(f'【有効】 {"✓有効" if enabled else "×無効"}')
    print(f'【音声名】 {voice_settings.get("voice_name", "未設定")}')
    print(f'【メッセージ】 {voice_settings.get("message", "未設定")}')
    print(f'【上昇メッセージ】 {voice_settings.get("message_up", "未設定")}')
    print(f'【下降メッセージ】 {voice_settings.get("message_down", "未設定")}')
    print(f'【チャイム】 {voice_settings.get("chime_file", "なし")}')
    print('-' * 60)

conn.close()
