#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
提供された日足JSONコードを本番サーバーに送信
"""

import requests
import json
import time

# Render本番サーバーURL
RENDER_URL = "https://tradingview-webhook-s5x1.onrender.com/webhook"

# 提供された日足JSONコード
daily_data = [
    {"symbol":"GBPJPY","tf":"D","time":1769032800000,"daytrade":{"status":"上昇ダウ","bos":"BOS-2","time":"25/11/18/07:00"},"row_order":["price","D","W","M","Y"],"cloud_order":["D","W","M","Y"],"clouds":[{"label":"D","tf":"D","gc":True,"thickness":65.6954243168,"angle":35.8472539986,"elapsed":100800,"cross_start_time":1762984800000,"elapsed_str":"25/11/13/07:00","in_cloud":False,"star":False,"distance_from_price":172.5272878416,"distance_from_prev":172.5272878416,"topPrice":212.5292042432,"bottomPrice":211.87225,"dauten":"up","bos_count":0,"dauten_start_time":1763416800000,"dauten_start_time_str":"25/11/18/07:00"}],"price":213.926},
    
    {"symbol":"USDJPY","tf":"D","time":1769032800000,"daytrade":{"status":"上昇ダウ","bos":"BOS-3","time":"25/09/25/06:00"},"row_order":["price","D","W","M","Y"],"cloud_order":["D","W","M","Y"],"clouds":[{"label":"D","tf":"D","gc":True,"thickness":65.8053211136,"angle":35.7043483126,"elapsed":48960,"cross_start_time":1766095200000,"elapsed_str":"25/12/19/07:00","in_cloud":False,"star":False,"distance_from_price":66.7773394432,"distance_from_prev":66.7773394432,"topPrice":158.0892532111,"bottomPrice":157.4312,"dauten":"up","bos_count":0,"dauten_start_time":1758747600000,"dauten_start_time_str":"25/09/25/06:00"}],"price":158.428},
    
    {"symbol":"GBPUSD","tf":"D","time":1769032800000,"daytrade":{"status":"上昇ダウ","bos":"-","time":"25/11/26/07:00"},"row_order":["Y","price","D","W","M"],"cloud_order":["D","W","M","Y"],"clouds":[{"label":"D","tf":"D","gc":False,"thickness":14.5867323185,"angle":35.1859645607,"elapsed":12960,"cross_start_time":1768255200000,"elapsed_str":"26/01/13/07:00","in_cloud":False,"star":False,"distance_from_price":51.6333661592,"distance_from_prev":51.6333661592,"topPrice":1.345836,"bottomPrice":1.3443773268,"dauten":"up","bos_count":0,"dauten_start_time":1764108000000,"dauten_start_time_str":"25/11/26/07:00"}],"price":1.35027},
    
    {"symbol":"EURGBP","tf":"D","time":1769032800000,"daytrade":{"status":"下降ダウ","bos":"-","time":"25/12/24/07:00"},"row_order":["W","price","D","M","Y"],"cloud_order":["D","W","M","Y"],"clouds":[{"label":"D","tf":"D","gc":True,"thickness":1.7958183199,"angle":33.1545271384,"elapsed":0,"cross_start_time":1769032800000,"elapsed_str":"26/01/22/07:00","in_cloud":False,"star":False,"distance_from_price":15.2970908401,"distance_from_prev":15.2970908401,"topPrice":0.8691400818,"bottomPrice":0.8689605,"dauten":"down","bos_count":0,"dauten_start_time":1766527200000,"dauten_start_time_str":"25/12/24/07:00"}],"price":0.87058},
    
    {"symbol":"EURUSD","tf":"D","time":1769032800000,"daytrade":{"status":"上昇ダウ","bos":"-","time":"25/12/03/07:00"},"row_order":["price","Y","D","W","M"],"cloud_order":["D","W","M","Y"],"clouds":[{"label":"D","tf":"D","gc":False,"thickness":10.3136008737,"angle":35.3595480896,"elapsed":23040,"cross_start_time":1767650400000,"elapsed_str":"26/01/06/07:00","in_cloud":False,"star":False,"distance_from_price":65.6318004369,"distance_from_prev":65.6318004369,"topPrice":1.1694725,"bottomPrice":1.1684411399,"dauten":"up","bos_count":0,"dauten_start_time":1764712800000,"dauten_start_time_str":"25/12/03/07:00"}],"price":1.17552},
    
    {"symbol":"GBPAUD","tf":"D","time":1769032800000,"daytrade":{"status":"下降ダウ","bos":"-","time":"26/01/15/07:00"},"row_order":["M","W","D","price","Y"],"cloud_order":["D","W","M","Y"],"clouds":[{"label":"D","tf":"D","gc":False,"thickness":95.5245554992,"angle":-35.9224005149,"elapsed":23040,"cross_start_time":1767650400000,"elapsed_str":"26/01/06/07:00","in_cloud":False,"star":False,"distance_from_price":-264.2727222504,"distance_from_prev":-264.2727222504,"topPrice":2.0050435,"bottomPrice":1.9954910445,"dauten":"down","bos_count":0,"dauten_start_time":1768428000000,"dauten_start_time_str":"26/01/15/07:00"}],"price":1.97384},
    
    {"symbol":"AUDUSD","tf":"D","time":1769032800000,"daytrade":{"status":"上昇ダウ","bos":"BOS-2","time":"25/12/03/07:00"},"row_order":["Y","price","D","W","M"],"cloud_order":["D","W","M","Y"],"clouds":[{"label":"D","tf":"D","gc":True,"thickness":25.0154474489,"angle":35.7998754814,"elapsed":79200,"cross_start_time":1764280800000,"elapsed_str":"25/11/28/07:00","in_cloud":False,"star":False,"distance_from_price":116.0172762756,"distance_from_prev":116.0172762756,"topPrice":0.6737490447,"bottomPrice":0.6712475,"dauten":"up","bos_count":0,"dauten_start_time":1764712800000,"dauten_start_time_str":"25/12/03/07:00"}],"price":0.6841},
    
    {"symbol":"EURAUD","tf":"D","time":1769032800000,"daytrade":{"status":"下降ダウ","bos":"BOS-2","time":"25/12/04/07:00"},"row_order":["W","D","M","price","Y"],"cloud_order":["D","W","M","Y"],"clouds":[{"label":"D","tf":"D","gc":False,"thickness":79.4883156362,"angle":-35.9045297153,"elapsed":41760,"cross_start_time":1766527200000,"elapsed_str":"25/12/24/07:00","in_cloud":False,"star":False,"distance_from_price":-198.275842182,"distance_from_prev":-198.275842182,"topPrice":1.742302,"bottomPrice":1.7343531684,"dauten":"down","bos_count":0,"dauten_start_time":1764799200000,"dauten_start_time_str":"25/12/04/07:00"}],"price":1.7185},
    
    {"symbol":"AUDJPY","tf":"D","time":1769032800000,"daytrade":{"status":"上昇ダウ","bos":"BOS-5","time":"25/09/03/06:00"},"row_order":["price","D","W","M","Y"],"cloud_order":["D","W","M","Y"],"clouds":[{"label":"D","tf":"D","gc":True,"thickness":83.5393576099,"angle":35.9014304386,"elapsed":155580,"cross_start_time":1759698000000,"elapsed_str":"25/10/06/06:00","in_cloud":False,"star":False,"distance_from_price":227.8103211951,"distance_from_prev":227.8103211951,"topPrice":106.5105935761,"bottomPrice":105.6752,"dauten":"up","bos_count":0,"dauten_start_time":1756846800000,"dauten_start_time_str":"25/09/03/06:00"}],"price":108.371},
    
    {"symbol":"EURJPY","tf":"D","time":1769032800000,"daytrade":{"status":"上昇ダウ","bos":"BOS-9","time":"25/05/01/06:00"},"row_order":["price","D","W","M","Y"],"cloud_order":["D","W","M","Y"],"clouds":[{"label":"D","tf":"D","gc":True,"thickness":60.5563911787,"angle":35.8457454249,"elapsed":155580,"cross_start_time":1759698000000,"elapsed_str":"25/10/06/06:00","in_cloud":False,"star":False,"distance_from_price":182.5718044106,"distance_from_prev":182.5718044106,"topPrice":184.7190639118,"bottomPrice":184.1135,"dauten":"up","bos_count":0,"dauten_start_time":1746046800000,"dauten_start_time_str":"25/05/01/06:00"}],"price":186.242}
]

print("=" * 100)
print("📤 日足JSONコードを本番サーバーに送信")
print("=" * 100)

success_count = 0
fail_count = 0

for data in daily_data:
    symbol = data['symbol']
    print(f"\n送信中: {symbol} 日足...")
    
    try:
        response = requests.post(RENDER_URL, json=data, timeout=10)
        if response.status_code == 200:
            print(f"  ✅ 成功: {symbol}")
            success_count += 1
        else:
            print(f"  ❌ 失敗: {symbol} - HTTP {response.status_code}")
            fail_count += 1
    except Exception as e:
        print(f"  ❌ エラー: {symbol} - {e}")
        fail_count += 1
    
    time.sleep(0.5)

print("\n" + "=" * 100)
print(f"📊 送信完了: 成功 {success_count}件 / 失敗 {fail_count}件")
print("=" * 100)
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
        with open("daily_check_db.db", "wb") as f:
            f.write(response.content)
        
        import sqlite3
        conn = sqlite3.connect("daily_check_db.db")
        cursor = conn.cursor()
        
        print("\n日足データの確認:")
        print("-" * 100)
        
        for data in daily_data:
            symbol = data['symbol']
            cursor.execute("""
                SELECT timestamp, daytrade_status, daytrade_bos, daytrade_time
                FROM states
                WHERE symbol = ? AND tf = 'D'
            """, (symbol,))
            
            row = cursor.fetchone()
            if row:
                timestamp, status, bos, time_val = row
                print(f"\n✅ {symbol}:")
                print(f"   タイムスタンプ: {timestamp}")
                print(f"   ダウ転: {status}")
                print(f"   BOS: {bos}")
                print(f"   ダウ転時間: {time_val}")
            else:
                print(f"\n❌ {symbol}: DBにデータなし")
        
        conn.close()
        
except Exception as e:
    print(f"❌ DB確認エラー: {e}")

print("\n" + "=" * 100)
