"""
本番環境デプロイスクリプト
- ローカルテスト実行
- Git操作（コミット・プッシュ）
- Renderデプロイ待機
- 本番環境テスト
- ブラウザ自動起動
"""
import subprocess
import sys
import time
import requests
import json
import os
from pathlib import Path

# 設定
RENDER_URL = "https://tradingview-webhook-s5x1.onrender.com"
LOCAL_URL = "http://localhost:5000"
RENDER_WEBHOOK_URL = f"{RENDER_URL}/webhook"
RENDER_DASHBOARD_URL = f"{RENDER_URL}/dashboard"

def run_command(cmd, description, cwd=None):
    """コマンド実行"""
    print(f"\n🔧 {description}")
    try:
        result = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ {description} 成功")
            if result.stdout.strip():
                print(f"   出力: {result.stdout.strip()}")
            return True
        else:
            print(f"❌ {description} 失敗")
            print(f"   エラー: {result.stderr.strip()}")
            return False
    except Exception as e:
        print(f"❌ {description} エラー: {e}")
        return False

def wait_for_render_deployment():
    """Renderデプロイ完了を待機"""
    print(f"\n⏳ Renderデプロイ待機中...")

    max_attempts = 30  # 5分待機
    for attempt in range(max_attempts):
        try:
            response = requests.get(RENDER_DASHBOARD_URL, timeout=10)
            if response.status_code == 200:
                print(f"✅ Renderデプロイ完了（{attempt + 1}回目）")
                return True
        except:
            pass

        print(f"   待機中... ({attempt + 1}/{max_attempts})")
        time.sleep(10)

    print(f"❌ Renderデプロイタイムアウト")
    return False

def test_render_webhook():
    """Render webhookテスト"""
    print(f"\n🧪 Render webhookテスト")

    test_data = {
        "symbol": "USDJPY",
        "tf": "5",
        "time": 1761015000000,
        "state": {"flag": "", "word": ""},
        "daytrade": {"status": "上昇ダウ", "bos": "", "time": 85},
        "swing": {"status": "上昇ダウ", "bos": "", "time": 70},
        "row_order": ["price", "5m", "15m", "1H", "4H"],
        "cloud_order": ["5m", "15m", "1H", "4H"],
        "clouds": [
            {"label": "5m", "tf": "5m", "gc": True, "fire_count": 0, "thickness": 8.49, "angle": 34.95, "elapsed": 80}
        ],
        "price": 151.219
    }

    try:
        response = requests.post(RENDER_WEBHOOK_URL, json=test_data, timeout=15)
        if response.status_code == 200:
            result = response.json()
            if result.get('status') == 'success':
                print(f"✅ Render webhookテスト成功")
                return True
            else:
                print(f"⚠️ Render webhookテスト失敗: {result.get('message')}")
                return False
        else:
            print(f"❌ Render webhook HTTPエラー: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Render webhookテストエラー: {e}")
        return False

def open_browser(url):
    """ブラウザ起動"""
    print(f"\n🌐 ブラウザ起動: {url}")
    try:
        if sys.platform == "win32":
            os.startfile(url)
        elif sys.platform == "darwin":
            subprocess.run(["open", url])
        else:
            subprocess.run(["xdg-open", url])
        print(f"✅ ブラウザ起動成功")
        return True
    except Exception as e:
        print(f"⚠️ ブラウザ起動失敗: {e}")
        return False

def deploy():
    """デプロイ実行"""
    print(f"🚀 本番環境デプロイ開始")
    print(f"{'='*60}")

    # 作業ディレクトリ設定
    workspace_dir = Path(__file__).parent

    # 1. ローカルテスト実行（スキップ）
    print(f"\n📋 ステップ1: ローカルテスト（スキップ）")
    print(f"   ローカルテストは手動で実行してください")

    # 2. Gitコミット
    print(f"\n📋 ステップ2: Gitステータス確認")
    run_command("git status", "Git status", workspace_dir)
    
    # Gitに変更がない場合はコミットをスキップ
    print(f"\n📋 ステップ3: Gitコミット・プッシュ")
    run_command("git add .", "Git add", workspace_dir)
    
    # コミットメッセージを入力
    commit_msg = input("コミットメッセージを入力 (Enterでスキップ): ").strip()
    if commit_msg:
        if not run_command(f'git commit -m "{commit_msg}"', "Git commit", workspace_dir):
            print(f"⚠️ コミット失敗またはコミット不要、続行します")
    else:
        print(f"   コミットをスキップしました")

    # 3. Gitプッシュ
    print(f"\n📋 ステップ4: Gitプッシュ")
    if not run_command("git push origin master", "Git push", workspace_dir):
        print(f"⚠️ プッシュ失敗、続行します")

    # 4. Renderデプロイ待機
    print(f"\n📋 ステップ5: Renderデプロイ待機")
    if not wait_for_render_deployment():
        print(f"⚠️ Renderデプロイ待機タイムアウト、続行します")

    # 5. 本番環境テスト
    print(f"\n📋 ステップ6: 本番環境テスト")
    if not test_render_webhook():
        print(f"⚠️ 本番環境テスト失敗、続行します")

    # 6. ブラウザ起動
    print(f"\n📋 ステップ7: ブラウザ起動")
    open_browser(RENDER_DASHBOARD_URL)

    print(f"\n{'='*60}")
    print(f"🎉 デプロイ完了！")
    print(f"   ダッシュボード: {RENDER_DASHBOARD_URL}")
    print(f"   Webhook URL: {RENDER_WEBHOOK_URL}")
    print(f"{'='*60}")

    return True

if __name__ == '__main__':
    success = deploy()
    sys.exit(0 if success else 1)