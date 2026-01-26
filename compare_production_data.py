#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
本番DBと提供されたJSONコードを照合するスクリプト
"""

import sqlite3
import json
from datetime import datetime
import pytz

# 提供されたJSONデータ
json_data = {
    "D": {
        "symbol": "USDJPY",
        "tf": "D",
        "time": 1769119200000,
        "daytrade": {
            "status": "下降ダウ",
            "bos": "-",
            "time": "26/01/23/07:00"
        },
        "clouds": [
            {
                "label": "D",
                "tf": "D",
                "dauten": "down",
                "bos_count": 0,
                "dauten_start_time": 1769119200000,
                "dauten_start_time_str": "26/01/23/07:00"
            }
        ]
    },
    "240": {
        "symbol": "USDJPY",
        "tf": "240",
        "time": 1769392800000,
        "daytrade": {
            "status": "下降ダウ",
            "bos": "-",
            "time": "26/01/23/23:00"
        },
        "clouds": [
            {
                "label": "4H",
                "tf": "4H",
                "dauten": "down",
                "bos_count": 0,
                "dauten_start_time": 1769176800000,
                "dauten_start_time_str": "26/01/23/23:00"
            }
        ]
    },
    "60": {
        "symbol": "USDJPY",
        "tf": "60",
        "time": 1769414400000,
        "daytrade": {
            "status": "下降ダウ",
            "bos": "BOS-1",
            "time": "26/01/23/02:00"
        },
        "clouds": [
            {
                "label": "1H",
                "tf": "1H",
                "dauten": "down",
                "bos_count": 0,
                "dauten_start_time": 1769101200000,
                "dauten_start_time_str": "26/01/23/02:00"
            }
        ]
    },
    "15": {
        "symbol": "USDJPY",
        "tf": "15",
        "time": 1769418000000,
        "daytrade": {
            "status": "上昇ダウ",
            "bos": "-",
            "time": "26/01/26/15:00"
        },
        "clouds": [
            {
                "label": "15m",
                "tf": "15m",
                "dauten": "up",
                "bos_count": 0,
                "dauten_start_time": 1769407200000,
                "dauten_start_time_str": "26/01/26/15:00"
            }
        ]
    }
}

# DBファイルパス
db_path = 'webhook_data.db'

# 日本時間タイムゾーン
jst = pytz.timezone('Asia/Tokyo')

def format_timestamp(ts_str):
    """ISO形式のタイムスタンプを読みやすい形式に変換"""
    if not ts_str or ts_str == 'N/A':
        return 'N/A'
    try:
        dt = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
        dt_jst = dt.astimezone(jst)
        return dt_jst.strftime('%y/%m/%d/%H:%M')
    except:
        return ts_str

def unix_to_str(unix_ms):
    """UNIXタイムスタンプ（ミリ秒）を読みやすい形式に変換"""
    if not unix_ms:
        return 'N/A'
    try:
        dt = datetime.fromtimestamp(unix_ms / 1000, tz=jst)
        return dt.strftime('%y/%m/%d/%H:%M')
    except:
        return str(unix_ms)

def compare_data():
    """DBとJSONデータを比較"""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        print("=" * 100)
        print("📊 本番DB vs 提供されたJSONコード - 比較レポート")
        print("=" * 100)
        print()
        
        for tf_key, json_tf_data in json_data.items():
            tf = json_tf_data['tf']
            symbol = json_tf_data['symbol']
            
            print(f"\n{'=' * 100}")
            print(f"⏱️  時間軸: {tf} ({tf_key})")
            print(f"{'=' * 100}")
            
            # DBからデータを取得
            cursor.execute("""
                SELECT timestamp, daytrade_status, daytrade_bos, daytrade_time, 
                       clouds_json
                FROM states 
                WHERE symbol = ? AND tf = ?
                ORDER BY timestamp DESC 
                LIMIT 1
            """, (symbol, tf))
            
            db_row = cursor.fetchone()
            
            if not db_row:
                print(f"❌ DBにデータがありません")
                print(f"\n📤 JSONから送信されたデータ:")
                print(f"   ダウ転: {json_tf_data['daytrade']['status']}")
                print(f"   ダウ転時間: {json_tf_data['daytrade']['time']}")
                print(f"   BOS: {json_tf_data['daytrade']['bos']}")
                if json_tf_data['clouds']:
                    cloud = json_tf_data['clouds'][0]
                    print(f"   雲のダウ転: {cloud['dauten']}")
                    print(f"   雲のBOS数: {cloud['bos_count']}")
                    print(f"   雲のダウ転時間: {cloud['dauten_start_time_str']}")
                continue
            
            db_timestamp, db_daytrade_status, db_daytrade_bos, db_daytrade_time, \
            db_clouds_json = db_row
            
            # タイムスタンプを変換
            db_ts_formatted = format_timestamp(db_timestamp)
            json_ts_formatted = unix_to_str(json_tf_data['time'])
            
            print(f"\n📅 タイムスタンプ:")
            print(f"   DB:   {db_ts_formatted} ({db_timestamp})")
            print(f"   JSON: {json_ts_formatted} (Unix: {json_tf_data['time']})")
            
            # daytrade 比較
            print(f"\n📈 Daytrade情報:")
            json_daytrade = json_tf_data['daytrade']
            
            status_match = "✅" if db_daytrade_status == json_daytrade['status'] else "❌"
            print(f"   ダウ転: {status_match}")
            print(f"      DB:   {db_daytrade_status}")
            print(f"      JSON: {json_daytrade['status']}")
            
            bos_match = "✅" if db_daytrade_bos == json_daytrade['bos'] else "❌"
            print(f"   BOS: {bos_match}")
            print(f"      DB:   {db_daytrade_bos}")
            print(f"      JSON: {json_daytrade['bos']}")
            
            time_match = "✅" if db_daytrade_time == json_daytrade['time'] else "❌"
            print(f"   ダウ転時間: {time_match}")
            print(f"      DB:   {db_daytrade_time}")
            print(f"      JSON: {json_daytrade['time']}")
            
            # clouds内のダウ転情報を比較
            if json_tf_data['clouds'] and db_clouds_json:
                print(f"\n☁️  Clouds配列のダウ転情報:")
                json_cloud = json_tf_data['clouds'][0]
                
                try:
                    db_clouds = json.loads(db_clouds_json)
                    # 該当する時間軸の雲を探す
                    db_cloud = None
                    for cloud in db_clouds:
                        if cloud.get('label') == json_cloud['label']:
                            db_cloud = cloud
                            break
                    
                    if db_cloud:
                        dauten_match = "✅" if db_cloud.get('dauten') == json_cloud['dauten'] else "❌"
                        print(f"   ダウ転: {dauten_match}")
                        print(f"      DB:   {db_cloud.get('dauten')}")
                        print(f"      JSON: {json_cloud['dauten']}")
                        
                        bos_count_match = "✅" if db_cloud.get('bos_count') == json_cloud['bos_count'] else "❌"
                        print(f"   BOS数: {bos_count_match}")
                        print(f"      DB:   {db_cloud.get('bos_count')}")
                        print(f"      JSON: {json_cloud['bos_count']}")
                        
                        dauten_time_match = "✅" if db_cloud.get('dauten_start_time_str') == json_cloud['dauten_start_time_str'] else "❌"
                        print(f"   ダウ転時間: {dauten_time_match}")
                        print(f"      DB:   {db_cloud.get('dauten_start_time_str')}")
                        print(f"      JSON: {json_cloud['dauten_start_time_str']}")
                    else:
                        print(f"   ❌ DBのclouds配列に該当する時間軸が見つかりません")
                        print(f"      探している: {json_cloud['label']}")
                except json.JSONDecodeError:
                    print(f"   ❌ DBのclouds JSONのパースに失敗")
        
        conn.close()
        
        print("\n" + "=" * 100)
        print("📋 分析完了")
        print("=" * 100)
        
    except Exception as e:
        print(f"❌ エラー: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    compare_data()
