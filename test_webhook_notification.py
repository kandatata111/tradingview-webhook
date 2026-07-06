#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Webhook 通知テスト - ルール発火時の音声再生確認
"""
import requests
import json
import time
from datetime import datetime
import pytz

# Server URL
SERVER_URL = 'http://localhost:5001'
WEBHOOK_ENDPOINT = f'{SERVER_URL}/webhook'

# Test data for webhook
test_webhook_data = {
    "symbol": "USDJPY",
    "tf": "5",
    "price": 149.25,
    "time": 1234567890,
    "sent_time": "26/02/19/00:30",
    "state": {
        "flag": "A",
        "word": "Uptrend"
    },
    "daytrade": {
        "status": "Long",
        "bos": "2",
        "time": "2026-02-19T00:30:00+09:00"
    },
    "swing": {
        "status": "Long",
        "bos": "1",
        "time": "2026-02-19T00:20:00+09:00"
    },
    "row_order": ["5m", "15m", "1H", "4H"],
    "cloud_order": ["senkou_a", "senkou_b"],
    "clouds": [
        {
            "label": "5m",
            "tf": "5m",
            "dauten": "▲Dow",
            "gc": "▲GC",
            "po": "▲P2",
            "bos_count": 2,
            "angle": 45.5
        },
        {
            "label": "15m",
            "tf": "15m",
            "dauten": "▲Dow",
            "gc": "▲GC",
            "po": "▲P1",
            "bos_count": 1,
            "angle": 35.2
        },
        {
            "label": "1H",
            "tf": "1H",
            "dauten": "▲Dow",
            "gc": "▲GC",
            "po": "▲P3",
            "bos_count": 1,
            "angle": 25.1
        },
        {
            "label": "4H",
            "tf": "4H",
            "dauten": "▲Dow",
            "gc": "▲GC",
            "po": "-",
            "bos_count": 0,
            "angle": 15.0
        }
    ],
    "meta": {
        "source": "TradingView",
        "strategy": "Ichimoku Cloud"
    }
}

def send_webhook_test():
    """Send test webhook to server"""
    print(f"\n{'='*60}")
    print(f"🔔 WEBHOOK TEST - Sending notification test")
    print(f"{'='*60}")
    print(f"Timestamp: {datetime.now(pytz.timezone('Asia/Tokyo')).isoformat()}")
    print(f"Target: {WEBHOOK_ENDPOINT}")
    print(f"Payload symbol: {test_webhook_data['symbol']}")
    print(f"Payload tf: {test_webhook_data['tf']}")
    
    try:
        # Send webhook
        print(f"\n📤 Sending webhook...")
        response = requests.post(
            WEBHOOK_ENDPOINT,
            json=test_webhook_data,
            headers={'Content-Type': 'application/json'},
            timeout=10
        )
        
        print(f"✓ Response status: {response.status_code}")
        print(f"✓ Response body: {response.text}")
        
        if response.status_code == 200:
            print(f"\n✅ Webhook sent successfully!")
            print(f"   - Check server logs for '[FIRE] Emitted new_notification' message")
            print(f"   - Check browser console for '[SOCKET] Received new_notification' message")
            return True
        else:
            print(f"\n❌ Webhook failed! Status: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error sending webhook: {e}")
        return False

def check_notifications():
    """Check if notifications were recorded"""
    print(f"\n{'='*60}")
    print(f"📋 CHECKING NOTIFICATIONS")
    print(f"{'='*60}")
    
    try:
        notifications_path = 'notifications.json'
        import os
        if os.path.exists(notifications_path):
            with open(notifications_path, 'r', encoding='utf-8') as f:
                notifications = json.load(f)
                print(f"✓ Found {len(notifications)} notification(s) in notifications.json")
                if notifications:
                    latest = notifications[-1]
                    print(f"\nLatest notification:")
                    print(f"  - Rule: {latest.get('rule_name', 'N/A')}")
                    print(f"  - Symbol: {latest.get('symbol', 'N/A')}")
                    print(f"  - Message: {latest.get('message', 'N/A')}")
                    print(f"  - Direction: {latest.get('direction', 'N/A')}")
                    print(f"  - Voice settings: {latest.get('voice_settings', {})}")
                    return True
        else:
            print(f"⚠ notifications.json not found")
            return False
    except Exception as e:
        print(f"❌ Error checking notifications: {e}")
        return False

def main():
    print(f"\n{'='*60}")
    print(f"🎵 WEBHOOK NOTIFICATION VOICE TEST SUITE")
    print(f"{'='*60}\n")
    print(f"⚠️  Before running this test:")
    print(f"   1. Make sure the server is running")
    print(f"   2. Open browser to http://localhost:5001")
    print(f"   3. Open DevTools console (F12) to see socket events")
    print(f"   4. Make sure at least ONE rule is enabled\n")
    
    # Check if server is running
    print(f"🔍 Checking server connection...")
    try:
        health = requests.get(f'{SERVER_URL}/health', timeout=5)
        if health.status_code == 200:
            print(f"✅ Server is running!")
        else:
            print(f"❌ Server responded with status {health.status_code}")
            return
    except Exception as e:
        print(f"❌ Cannot connect to server at {SERVER_URL}")
        print(f"   Error: {e}")
        print(f"   Make sure to run: python render_server.py")
        return
    
    # Send webhook test
    success = send_webhook_test()
    
    # Wait a moment for processing
    print(f"\n⏳ Waiting 2 seconds for processing...")
    time.sleep(2)
    
    # Check notifications
    check_notifications()
    
    print(f"\n{'='*60}")
    print(f"🔧 TROUBLESHOOTING:")
    print(f"{'='*60}")
    print(f"If voice did NOT play:")
    print(f"  1. Check browser console (F12) for '[SOCKET] Received new_notification'")
    print(f"  2. Check server logs for '[FIRE] Emitted new_notification'")
    print(f"  3. Check if notifications.json contains the fired notification")
    print(f"  4. Verify that at least one rule has voice_settings configured")
    print(f"  5. Check if voice_settings contain 'message' or 'message_up'/'message_down'")
    print(f"\nIf socket event is received but voice doesn't play:")
    print(f"  1. Check browser console for '[PLAY_NOTIFICATION]' messages")
    print(f"  2. Check for '[VOICE_ALERT]' messages")
    print(f"  3. Verify browser Web Speech API is enabled")
    print(f"  4. Check if browser volume is not muted")
    print(f"{'='*60}\n")

if __name__ == '__main__':
    main()
