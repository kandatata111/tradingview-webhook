import re

# webhook_log.txt の最新エントリを解析
with open('webhook_log.txt', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# 最新の送信時刻（18:21:22以降）を抽出
recent_lines = [line for line in lines if '2025-11-20T18:21:' in line or '2025-11-20T18:32:' in line or '2025-11-20T18:33:' in line]

print(f"=== 最近の送信（18:21以降）: {len(recent_lines)} 件 ===\n")

for line in recent_lines[-10:]:
    # タイムスタンプとシンボル/tfを抽出
    match = re.match(r'([\d\-T:+]+) - ([A-Z]+)/(\d+)', line)
    if match:
        timestamp, symbol, tf = match.groups()
        print(f"{timestamp} - {symbol}/tf={tf}")

# 実際にサーバーが動作しているか確認
print("\n=== サーバー動作確認 ===")
print("webhook_log.txt に最新のエントリがあります")
print("しかし [FIRE] ログが見当たりません")
print("\n問題の可能性:")
print("1. evaluate_and_fire_rules() が呼ばれていない")
print("2. 例外が発生してキャッチされている")
print("3. ログが別の場所に出力されている")
