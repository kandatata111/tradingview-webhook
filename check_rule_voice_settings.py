#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ルール定義確認スクリプト - voice_settings が正しく保存されているか確認
"""
import sqlite3
import json
import os

DB_PATH = 'webhook_data.db'

def check_rules_voice_settings():
    """確認: ルールに voice_settings が含まれているか"""
    if not os.path.exists(DB_PATH):
        print(f"❌ Database not found: {DB_PATH}")
        return
    
    print(f"\n{'='*70}")
    print(f"📋 RULE VOICE SETTINGS CHECK")
    print(f"{'='*70}\n")
    
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        # Get all rules
        c.execute('SELECT id, name, enabled, rule_json FROM rules ORDER BY created_at DESC')
        rows = c.fetchall()
        conn.close()
        
        if not rows:
            print(f"⚠️  No rules found in database")
            return
        
        print(f"Found {len(rows)} rule(s)\n")
        
        for idx, (rule_id, rule_name, enabled, rule_json) in enumerate(rows, 1):
            print(f"{idx}. Rule: '{rule_name}' (ID: {rule_id})")
            print(f"   Status: {'✅ ENABLED' if enabled else '❌ DISABLED'}")
            
            # Parse rule_json
            try:
                rule_data = json.loads(rule_json) if rule_json else {}
                
                # Check for voice settings
                voice_settings = rule_data.get('voice', {})
                
                if voice_settings:
                    print(f"   ✓ Voice settings found:")
                    print(f"     - message: {voice_settings.get('message', 'N/A')}")
                    print(f"     - message_up: {voice_settings.get('message_up') or voice_settings.get('messageUp', 'N/A')}")
                    print(f"     - message_down: {voice_settings.get('message_down') or voice_settings.get('messageDown', 'N/A')}")
                    print(f"     - chime_file: {voice_settings.get('chime_file') or voice_settings.get('chime', 'N/A')}")
                    print(f"     - voice_file: {voice_settings.get('voice_file') or voice_settings.get('voiceFile', 'N/A')}")
                    print(f"     - insert_symbol: {voice_settings.get('insert_symbol') or voice_settings.get('insertSymbol', 'N/A')}")
                    print(f"     - play_chime_first: {voice_settings.get('play_chime_first') or voice_settings.get('playChimeFirst', 'N/A')}")
                    print(f"     - Full settings: {json.dumps(voice_settings, ensure_ascii=False, indent=6)}")
                else:
                    print(f"   ❌ No voice settings found (empty or missing)")
                    print(f"   - Full rule_data keys: {list(rule_data.keys())}")
                    if rule_json:
                        print(f"   - Full rule_json: {rule_json[:200]}...")
                
                # Check for conditions
                conditions = rule_data.get('conditions', [])
                if conditions:
                    print(f"   ✓ Has {len(conditions)} condition(s)")
                else:
                    print(f"   ⚠️  No conditions found")
                
            except Exception as e:
                print(f"   ❌ Error parsing rule_json: {e}")
            
            print()
        
        print(f"{'='*70}\n")
        print(f"🔍 DIAGNOSTIC SUMMARY:")
        print(f"{'='*70}")
        print(f"✓ If you see 'Voice settings found' above:")
        print(f"  → Rule voice settings are saved correctly")
        print(f"  → Problem is likely on CLIENT SIDE or SOCKET communication")
        print(f"\n❌ If you see 'No voice settings found':")
        print(f"  → Rules were saved without voice settings")
        print(f"  → Edit and save rules again with voice settings enabled")
        print(f"\n🔧 Next steps:")
        print(f"1. If voice_settings exist: Run test_webhook_notification.py")
        print(f"2. Check browser console (F12) for '[SOCKET] Received new_notification'")
        print(f"3. Check server logs for '[FIRE] [DEBUG] Notification object'")
        print(f"4. If message is empty: Voice won't play (expected behavior)")
        print(f"5. If voice_settings missing: Edit rule and add voice message, then save")
        print(f"{'='*70}\n")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    check_rules_voice_settings()
