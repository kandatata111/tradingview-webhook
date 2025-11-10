"""
Webhook機能の統合テストスクリプト
- ローカルまたはRenderへのテスト送信
- 複数パターンのテストデータ
- レスポンスの自動検証
"""
import requests
import json
import sys

# テスト環境を選択
TEST_ENVIRONMENTS = {
    'local': 'http://localhost:5000/webhook',
    'render': 'https://tradingview-webhook-s5x1.onrender.com/webhook'
}

# テストデータパターン
TEST_CASES = {
    'normal': {
        "symbol": "USDJPY",
        "tf": "5",
        "time": 1761015000000,
        "state": {"flag": "", "word": ""},
        "daytrade": {"status": "上昇ダウ", "bos": "", "time": 85},
        "swing": {"status": "上昇ダウ", "bos": "", "time": 70},
        "row_order": ["price", "5m", "15m", "1H", "4H"],
        "cloud_order": ["5m", "15m", "1H", "4H"],
        "clouds": [
            {"label": "5m", "tf": "5m", "gc": True, "fire_count": 0, "thickness": 8.49, "angle": 34.95, "elapsed": 80, "distance_from_price": 10.5, "distance_from_prev": 5.3, "topPrice": 151.50, "bottomPrice": 151.30},
            {"label": "15m", "tf": "15m", "gc": True, "fire_count": 0, "thickness": 8.19, "angle": 34.11, "elapsed": 65, "distance_from_price": 15.2, "distance_from_prev": 8.7, "topPrice": 151.60, "bottomPrice": 151.40},
            {"label": "1H", "tf": "1H", "gc": True, "fire_count": 2, "thickness": 4.87, "angle": 1.55, "elapsed": 95, "distance_from_price": 25.8, "distance_from_prev": 12.4, "topPrice": 151.80, "bottomPrice": 151.20}
        ],
        "price": 151.219
    },
    'fire_max': {
        "symbol": "EURJPY",
        "tf": "15",
        "time": 1761015000000,
        "state": {"flag": "買", "word": "強気"},
        "daytrade": {"status": "上昇ダウ", "bos": "BOS+1", "time": 120},
        "swing": {"status": "上昇ダウ", "bos": "", "time": 200},
        "row_order": ["price", "5m", "15m", "1H", "4H"],
        "cloud_order": ["5m", "15m", "1H", "4H"],
        "clouds": [
            {"label": "5m", "tf": "5m", "gc": False, "fire_count": 3, "thickness": 5.2, "angle": 25.3, "elapsed": 45},
            {"label": "15m", "tf": "15m", "gc": True, "fire_count": 10, "max_reached": True, "thickness": 12.5, "angle": 45.2, "elapsed": 150},
            {"label": "1H", "tf": "1H", "gc": True, "fire_count": 5, "thickness": 8.3, "angle": 30.1, "elapsed": 200}
        ],
        "price": 163.450
    },
    'multi_symbol': {
        "symbol": "GBPJPY",
        "tf": "5",
        "time": 1761015000000,
        "state": {"flag": "売", "word": "弱気"},
        "daytrade": {"status": "下降ダウ", "bos": "BOS-1", "time": 95},
        "swing": {"status": "下降ダウ", "bos": "BOS-2", "time": 300},
        "row_order": ["price", "5m", "15m", "1H", "4H"],
        "cloud_order": ["5m", "15m", "1H", "4H"],
        "clouds": [
            {"label": "5m", "tf": "5m", "gc": False, "fire_count": 1, "thickness": 6.8, "angle": 28.5, "elapsed": 60},
            {"label": "15m", "tf": "15m", "gc": False, "fire_count": 2, "thickness": 9.2, "angle": 32.8, "elapsed": 120},
            {"label": "1H", "tf": "1H", "gc": False, "fire_count": 0, "thickness": 3.5, "angle": 15.2, "elapsed": 180}
        ],
        "price": 188.325
    }
}

def run_test(env='local', test_case='normal'):
    """テストを実行"""
    url = TEST_ENVIRONMENTS.get(env)
    data = TEST_CASES.get(test_case)

    if not url or not data:
        print(f"❌ Invalid environment or test case")
        return False

    print(f"\n{'='*60}")
    print(f"🧪 テスト実行: {test_case} → {env}")
    print(f"{'='*60}")
    print(f"📤 送信先: {url}")
    print(f"📦 データ: {data['symbol']} - {len(data['clouds'])}雲")

    try:
        response = requests.post(url, json=data, timeout=10)

        print(f"\n📊 結果:")
        print(f"   ステータス: {response.status_code}")
        print(f"   レスポンス: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")

        # 検証
        if response.status_code == 200:
            result = response.json()
            if result.get('status') == 'success':
                print(f"\n✅ テスト成功！")
                print(f"   通知数: {result.get('notifications', 0)}")
                return True
            else:
                print(f"\n⚠️ サーバーエラー: {result.get('message')}")
                return False
        else:
            print(f"\n❌ HTTPエラー: {response.status_code}")
            return False

    except requests.exceptions.Timeout:
        print(f"\n❌ タイムアウト（10秒）")
        return False
    except Exception as e:
        print(f"\n❌ エラー: {e}")
        return False

def run_all_tests(env='local'):
    """全テストを実行"""
    print(f"\n🚀 全テストケースを実行: {env}")
    results = {}

    for test_case in TEST_CASES.keys():
        results[test_case] = run_test(env, test_case)

    # サマリー
    print(f"\n{'='*60}")
    print(f"📊 テストサマリー")
    print(f"{'='*60}")

    passed = sum(1 for r in results.values() if r)
    total = len(results)

    for test_case, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {test_case:20s} : {status}")

    print(f"\n   合計: {passed}/{total} 成功")

    return passed == total

if __name__ == '__main__':
    # 使い方
    # python test_webhook.py              → ローカルで通常テスト
    # python test_webhook.py local all    → ローカルで全テスト
    # python test_webhook.py render       → Renderで通常テスト
    # python test_webhook.py render all   → Renderで全テスト

    env = sys.argv[1] if len(sys.argv) > 1 else 'local'
    mode = sys.argv[2] if len(sys.argv) > 2 else 'normal'

    if env not in TEST_ENVIRONMENTS:
        print(f"❌ Invalid environment: {env}")
        print(f"   Available: {', '.join(TEST_ENVIRONMENTS.keys())}")
        sys.exit(1)

    if mode == 'all':
        success = run_all_tests(env)
        sys.exit(0 if success else 1)
    else:
        success = run_test(env, mode)
        sys.exit(0 if success else 1)