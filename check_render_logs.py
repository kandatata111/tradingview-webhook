#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Render本番サーバーのログを確認
"""

import requests

RENDER_URL = "https://tradingview-webhook-s5x1.onrender.com"

print("=" * 100)
print("📋 Render本番サーバーのwebhook受信ログ")
print("=" * 100)

try:
    response = requests.get(f"{RENDER_URL}/api/webhook_logs", timeout=30)
    if response.status_code == 200:
        data = response.json()
        if 'logs' in data:
            logs = data['logs']
            
            # USDJPYの各時間軸の最後の受信を確認
            print("\n📊 USDJPY 各時間軸の最後の受信:")
            print("-" * 100)
            
            timeframes = ['5', '15', '60', '240', 'D']
            for tf in timeframes:
                matching = [log for log in logs if 'USDJPY' in log and f'/{tf}' in log or f' {tf} ' in log]
                if matching:
                    last_log = matching[-1]
                    print(f"\n{tf}分足: {last_log[:100]}...")
                else:
                    print(f"\n{tf}分足: ❌ 受信ログなし")
        else:
            print("ログデータが見つかりません")
    else:
        print(f"❌ HTTP {response.status_code}")
except Exception as e:
    print(f"❌ エラー: {e}")

print("\n" + "=" * 100)
