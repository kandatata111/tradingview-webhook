#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
最新の日足JSONコード（26/01/23送信分）を本番サーバーに送信
"""

import requests
import json
import time

# Render本番サーバーURL
RENDER_URL = "https://tradingview-webhook-s5x1.onrender.com/webhook"

# 最新の日足JSONコード（26/01/23 AM7:00送信分）
daily_data = [
    {"symbol":"GBPUSD","tf":"D","time":1769119200000,"daytrade":{"status":"上昇ダウ","bos":"BOS-1","time":"25/11/26/07:00"},"row_order":["Y","price","D","W","M"],"cloud_order":["D","W","M","Y"],"clouds":[{"label":"D","tf":"D","gc":True,"thickness":15.1526735576,"angle":35.8360348113,"elapsed":0,"cross_start_time":1769119200000,"elapsed_str":"26/01/23/07:00","in_cloud":False,"star":False,"distance_from_price":172.5436632212,"distance_from_prev":172.5436632212,"topPrice":1.3480432674,"bottomPrice":1.346528,"dauten":"up","bos_count":0,"dauten_start_time":1764108000000,"dauten_start_time_str":"25/11/26/07:00"}],"price":1.36454},
    
    {"symbol":"GBPAUD","tf":"D","time":1769119200000,"daytrade":{"status":"下降ダウ","bos":"-","time":"26/01/15/07:00"},"row_order":["M","W","D","price","Y"],"cloud_order":["D","W","M","Y"],"clouds":[{"label":"D","tf":"D","gc":False,"thickness":107.8509999539,"angle":-35.9219970308,"elapsed":24480,"cross_start_time":1767650400000,"elapsed_str":"26/01/06/07:00","in_cloud":False,"star":False,"distance_from_price":-189.1795000231,"distance_from_prev":-189.1795000231,"topPrice":2.0032705,"bottomPrice":1.9924854,"dauten":"down","bos_count":0,"dauten_start_time":1768428000000,"dauten_start_time_str":"26/01/15/07:00"}],"price":1.97896},
    
    {"symbol":"USDJPY","tf":"D","time":1769119200000,"daytrade":{"status":"下降ダウ","bos":"-","time":"26/01/23/07:00"},"row_order":["D","price","W","M","Y"],"cloud_order":["D","W","M","Y"],"clouds":[{"label":"D","tf":"D","gc":True,"thickness":24.098899093,"angle":-35.6387377562,"elapsed":50400,"cross_start_time":1766095200000,"elapsed_str":"25/12/19/07:00","in_cloud":False,"star":False,"distance_from_price":-180.4894495464,"distance_from_prev":-180.4894495464,"topPrice":157.6613889909,"bottomPrice":157.4204,"dauten":"down","bos_count":0,"dauten_start_time":1769119200000,"dauten_start_time_str":"26/01/23/07:00"}],"price":155.736},
    
    {"symbol":"AUDUSD","tf":"D","time":1769119200000,"daytrade":{"status":"上昇ダウ","bos":"BOS-2","time":"25/12/03/07:00"},"row_order":["Y","price","D","W","M"],"cloud_order":["D","W","M","Y"],"clouds":[{"label":"D","tf":"D","gc":True,"thickness":44.3299115491,"angle":35.8659696247,"elapsed":80640,"cross_start_time":1764280800000,"elapsed_str":"25/11/28/07:00","in_cloud":False,"star":False,"distance_from_price":152.1000442255,"distance_from_prev":152.1000442255,"topPrice":0.6766364912,"bottomPrice":0.6722035,"dauten":"up","bos_count":0,"dauten_start_time":1764712800000,"dauten_start_time_str":"25/12/03/07:00"}],"price":0.68963},
    
    {"symbol":"EURUSD","tf":"D","time":1769119200000,"daytrade":{"status":"上昇ダウ","bos":"BOS-1","time":"25/12/03/07:00"},"row_order":["price","Y","D","W","M"],"cloud_order":["D","W","M","Y"],"clouds":[{"label":"D","tf":"D","gc":True,"thickness":13.2038720124,"angle":35.7838381001,"elapsed":0,"cross_start_time":1769119200000,"elapsed_str":"26/01/23/07:00","in_cloud":False,"star":False,"distance_from_price":123.8380639938,"distance_from_prev":123.8380639938,"topPrice":1.1710463872,"bottomPrice":1.169726,"dauten":"up","bos_count":0,"dauten_start_time":1764712800000,"dauten_start_time_str":"25/12/03/07:00"}],"price":1.18277},
    
    {"symbol":"GBPJPY","tf":"D","time":1769119200000,"daytrade":{"status":"上昇ダウ","bos":"BOS-2","time":"25/11/18/07:00"},"row_order":["price","D","W","M","Y"],"cloud_order":["D","W","M","Y"],"clouds":[{"label":"D","tf":"D","gc":True,"thickness":55.9298926229,"angle":35.8298419899,"elapsed":102240,"cross_start_time":1762984800000,"elapsed_str":"25/11/13/07:00","in_cloud":True,"star":True,"distance_from_price":26.2300536886,"distance_from_prev":26.2300536886,"topPrice":212.5253489262,"bottomPrice":211.96605,"dauten":"up","bos_count":0,"dauten_start_time":1763416800000,"dauten_start_time_str":"25/11/18/07:00"}],"price":212.508},
    
    {"symbol":"EURGBP","tf":"D","time":1769119200000,"daytrade":{"status":"下降ダウ","bos":"-","time":"25/12/24/07:00"},"row_order":["W","D","price","M","Y"],"cloud_order":["D","W","M","Y"],"clouds":[{"label":"D","tf":"D","gc":True,"thickness":0.2165786254,"angle":-33.9077679764,"elapsed":1440,"cross_start_time":1769032800000,"elapsed_str":"26/01/22/07:00","in_cloud":False,"star":False,"distance_from_price":-18.3832893126,"distance_from_prev":-18.3832893126,"topPrice":0.8687291579,"bottomPrice":0.8687075,"dauten":"down","bos_count":0,"dauten_start_time":1766527200000,"dauten_start_time_str":"25/12/24/07:00"}],"price":0.86688},
    
    {"symbol":"EURAUD","tf":"D","time":1769119200000,"daytrade":{"status":"下降ダウ","bos":"BOS-2","time":"25/12/04/07:00"},"row_order":["W","M","D","price","Y"],"cloud_order":["D","W","M","Y"],"clouds":[{"label":"D","tf":"D","gc":False,"thickness":93.1999855205,"angle":-35.9169260801,"elapsed":43200,"cross_start_time":1766527200000,"elapsed_str":"25/12/24/07:00","in_cloud":False,"star":False,"distance_from_price":-200.0350072398,"distance_from_prev":-200.0350072398,"topPrice":1.7402635,"bottomPrice":1.7309435014,"dauten":"down","bos_count":0,"dauten_start_time":1764799200000,"dauten_start_time_str":"25/12/04/07:00"}],"price":1.7156},
    
    {"symbol":"EURJPY","tf":"D","time":1769119200000,"daytrade":{"status":"上昇ダウ","bos":"BOS-9","time":"25/05/01/06:00"},"row_order":["D","price","W","M","Y"],"cloud_order":["D","W","M","Y"],"clouds":[{"label":"D","tf":"D","gc":True,"thickness":48.7752291462,"angle":35.756856021,"elapsed":157020,"cross_start_time":1759698000000,"elapsed_str":"25/10/06/06:00","in_cloud":True,"star":True,"distance_from_price":-16.1176145731,"distance_from_prev":-16.1176145731,"topPrice":184.6290522915,"bottomPrice":184.1413,"dauten":"up","bos_count":0,"dauten_start_time":1746046800000,"dauten_start_time_str":"25/05/01/06:00"}],"price":184.224},
    
    {"symbol":"AUDJPY","tf":"D","time":1769119200000,"daytrade":{"status":"上昇ダウ","bos":"BOS-5","time":"25/09/03/06:00"},"row_order":["price","D","W","M","Y"],"cloud_order":["D","W","M","Y"],"clouds":[{"label":"D","tf":"D","gc":True,"thickness":85.3131107717,"angle":35.8977736312,"elapsed":157020,"cross_start_time":1759698000000,"elapsed_str":"25/10/06/06:00","in_cloud":False,"star":False,"distance_from_price":113.9534446141,"distance_from_prev":113.9534446141,"topPrice":106.6690311077,"bottomPrice":105.8159,"dauten":"up","bos_count":0,"dauten_start_time":1756846800000,"dauten_start_time_str":"25/09/03/06:00"}],"price":107.382}
]

print("=" * 100)
print("📤 最新の日足JSONコード（26/01/23送信分）を本番サーバーに送信")
print("=" * 100)
print(f"\n送信先: {RENDER_URL}")
print(f"通貨ペア数: {len(daily_data)}通貨ペア")
print()

success_count = 0
fail_count = 0

for i, data in enumerate(daily_data, 1):
    symbol = data['symbol']
    daytrade_time = data.get('daytrade', {}).get('time', '')
    
    print(f"{i}. {symbol} (ダウ転時間: {daytrade_time})...")
    
    try:
        response = requests.post(RENDER_URL, json=data, timeout=10)
        if response.status_code == 200:
            print(f"   ✅ 成功")
            success_count += 1
        else:
            print(f"   ❌ 失敗 - HTTP {response.status_code}")
            print(f"      {response.text}")
            fail_count += 1
    except Exception as e:
        print(f"   ❌ エラー - {e}")
        fail_count += 1
    
    time.sleep(0.5)

print("\n" + "=" * 100)
print(f"📊 送信完了: ✅ 成功 {success_count}件 / ❌ 失敗 {fail_count}件")
print("=" * 100)

if success_count == len(daily_data):
    print("\n✅ すべての日足データの送信に成功しました")
    print("\n⏳ 5秒後にDBを確認します...")
    time.sleep(5)
    
    # DBを確認
    print("\n" + "=" * 100)
    print("📥 本番DBをダウンロードして確認")
    print("=" * 100)
    
    try:
        download_url = "https://tradingview-webhook-s5x1.onrender.com/download_db"
        response = requests.get(download_url, timeout=30)
        
        if response.status_code == 200:
            with open("latest_daily_check_db.db", "wb") as f:
                f.write(response.content)
            
            import sqlite3
            conn = sqlite3.connect("latest_daily_check_db.db")
            cursor = conn.cursor()
            
            print("\n日足データの確認:")
            print("-" * 100)
            
            for data in daily_data:
                symbol = data['symbol']
                expected_time = data.get('daytrade', {}).get('time', '')
                
                cursor.execute("""
                    SELECT timestamp, daytrade_status, daytrade_bos, daytrade_time
                    FROM states
                    WHERE symbol = ? AND tf = 'D'
                """, (symbol,))
                
                row = cursor.fetchone()
                if row:
                    timestamp, status, bos, time_val = row
                    match = "✅" if time_val == expected_time else "❌"
                    print(f"\n{match} {symbol}:")
                    print(f"   タイムスタンプ: {timestamp}")
                    print(f"   ダウ転: {status}")
                    print(f"   BOS: {bos}")
                    print(f"   ダウ転時間: {time_val} (期待値: {expected_time})")
                else:
                    print(f"\n❌ {symbol}: DBにデータなし")
            
            conn.close()
            
    except Exception as e:
        print(f"❌ DB確認エラー: {e}")

print("\n" + "=" * 100)
