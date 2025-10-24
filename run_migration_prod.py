"""
本番サーバーでマイグレーションを実行
Renderのコンソールまたはワンタイムジョブで実行
"""
import os
import sys

# このスクリプトを実行する前に、render_server.pyが起動している必要があります
# または、Renderのダッシュボードから「Shell」を開いて実行します

print("=" * 60)
print("本番環境マイグレーション実行")
print("=" * 60)

# 環境変数を確認
if 'DATABASE_URL' not in os.environ:
    print("\n❌ DATABASE_URL環境変数が設定されていません")
    print("このスクリプトは本番環境（Render）で実行する必要があります")
    print("\n実行方法:")
    print("1. Renderダッシュボードを開く")
    print("2. サービス 'tradingview-webhook' を選択")
    print("3. 'Shell' タブをクリック")
    print("4. 以下のコマンドを実行:")
    print("   python migrate_database.py")
    sys.exit(1)

# マイグレーションを実行
from migrate_database import migrate_postgresql

success = migrate_postgresql()

if success:
    print("\n✅ 本番環境のデータベース更新完了")
    print("次のステップ:")
    print("1. python send_to_production.py を実行してテストデータを送信")
    print("2. https://tradingview-webhook-s5x1.onrender.com/ で確認")
else:
    print("\n❌ マイグレーション失敗")
    sys.exit(1)
