#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ノートAPI動作確認用テストスクリプト
"""
import requests
import json
import os
from pathlib import Path

BASE_URL = "http://localhost:5000"

def test_api():
    print("=" * 80)
    print("ノートAPI動作確認テスト")
    print("=" * 80)
    
    # 1. 現在のファイルの状態を確認
    notes_path = Path(__file__).parent / "notes_data.json"
    print(f"\n【ファイル確認】")
    print(f"ファイルパス: {notes_path}")
    print(f"存在状態: {'存在' if notes_path.exists() else '未作成'}")
    if notes_path.exists():
        try:
            with open(notes_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            print(f"現在の内容: {len(data) if isinstance(data, list) else 'dict'} 個のアイテム")
            if isinstance(data, list) and len(data) > 0:
                print(f"  - 最初のページ: '{data[0].get('title', 'N/A')}'")
                if 'sections' in data[0]:
                    print(f"    セクション数: {len(data[0]['sections'])}")
        except Exception as e:
            print(f"ファイル読み込みエラー: {e}")
    
    # 2. APIからのロード確認
    print(f"\n【API: GET /api/load_notes】")
    try:
        response = requests.get(f"{BASE_URL}/api/load_notes", timeout=5)
        print(f"ステータス: {response.status_code}")
        data = response.json()
        print(f"レスポンス: {json.dumps(data, ensure_ascii=False, indent=2)[:300]}...")
        
        if data.get('status') == 'success':
            notes = data.get('notes', [])
            print(f"✓ ロード成功: {len(notes) if isinstance(notes, list) else 'dict'} 個のアイテム")
        else:
            print(f"✗ エラー: {data.get('msg', 'Unknown error')}")
    except Exception as e:
        print(f"✗ リクエストエラー: {e}")
    
    # 3. テストデータの保存
    print(f"\n【API: POST /api/save_notes】")
    test_data = [
        {
            "id": 999,
            "title": "テストページ",
            "sections": [
                {
                    "title": "テストセクション",
                    "content": "これはテスト保存のデータです。\nブラウザを再起動してもこのデータが表示されれば成功です。",
                    "images": []
                }
            ],
            "lastModified": "2025-11-19T00:00:00.000Z"
        }
    ]
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/save_notes",
            json=test_data,
            headers={"Content-Type": "application/json"},
            timeout=5
        )
        print(f"ステータス: {response.status_code}")
        result = response.json()
        print(f"レスポンス: {json.dumps(result, ensure_ascii=False)}")
        
        if result.get('status') == 'success':
            print(f"✓ 保存成功")
        else:
            print(f"✗ エラー: {result.get('msg', 'Unknown error')}")
    except Exception as e:
        print(f"✗ リクエストエラー: {e}")
    
    # 4. 保存後の確認
    print(f"\n【保存後の確認】")
    try:
        response = requests.get(f"{BASE_URL}/api/load_notes", timeout=5)
        if response.status_code == 200:
            data = response.json()
            notes = data.get('notes', [])
            print(f"ロード件数: {len(notes) if isinstance(notes, list) else 'dict'}")
            if isinstance(notes, list) and len(notes) > 0:
                # テストデータが含まれているか確認
                test_found = any(n.get('id') == 999 for n in notes)
                if test_found:
                    print(f"✓ テストデータが正常に保存・ロードされました")
                else:
                    print(f"✗ テストデータが見つかりません")
    except Exception as e:
        print(f"✗ リクエストエラー: {e}")
    
    # 5. ファイルシステムの確認
    print(f"\n【ファイルシステム確認】")
    if notes_path.exists():
        try:
            with open(notes_path, 'r', encoding='utf-8') as f:
                saved_data = json.load(f)
            print(f"ファイルに保存されたアイテム数: {len(saved_data) if isinstance(saved_data, list) else 'dict'}")
            # テストデータが含まれているか確認
            if isinstance(saved_data, list):
                test_found = any(item.get('id') == 999 for item in saved_data)
                if test_found:
                    print(f"✓ ファイルにテストデータが存在します")
                else:
                    print(f"✗ ファイルにテストデータが見つかりません")
        except Exception as e:
            print(f"✗ ファイル読み込みエラー: {e}")
    else:
        print(f"✗ ファイルが存在しません")
    
    print("\n" + "=" * 80)
    print("テスト完了")
    print("=" * 80)

if __name__ == "__main__":
    test_api()
