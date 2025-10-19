from flask import Flask, request, jsonify
import os
import json
from pydub import AudioSegment
from pydub.playback import play
from win10toast import ToastNotifier

app = Flask(__name__)
toaster = ToastNotifier()

# Load voice configuration
def load_voice_config():
    try:
        with open('voice_config.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print("voice_config.json not found, using defaults")
        return {'volume': 0}

voice_config = load_voice_config()

# Sound file mapping
SOUND_MAP = {
    'short_up': 'sounds/short_up.wav',
    'short_dn': 'sounds/short_dn.wav',
    'mid_up': 'sounds/mid_up.wav',
    'mid_dn': 'sounds/mid_dn.wav',
    'long_up': 'sounds/long_up.wav',
    'long_dn': 'sounds/long_dn.wav',
    'ultra_up': 'sounds/ultra_up.wav',
    'ultra_dn': 'sounds/ultra_dn.wav',
    'max_reached': 'sounds/max_reached.wav',
}

# Play sound based on alert type
def play_sound(alert_type):
    sound_file = SOUND_MAP.get(alert_type)
    if sound_file and os.path.exists(sound_file):
        try:
            sound = AudioSegment.from_wav(sound_file)
            volume_adjustment = voice_config.get('volume', 0)
            sound = sound + volume_adjustment  # Adjust volume (dB)
            play(sound)
            print(f"✓ Played sound: {sound_file}")
        except Exception as e:
            print(f"✗ Sound playback error: {e}")
    else:
        print(f"✗ Sound file not found: {alert_type} ({sound_file})")

# Show desktop notification
def show_notification(title, message):
    try:
        toaster.show_toast(
            title,
            message,
            icon_path=None,
            duration=10,
            threaded=True
        )
        print(f"✓ Notification shown: {title}")
    except Exception as e:
        print(f"✗ Notification error: {e}")

@app.route('/alert', methods=['POST'])
def receive_alert():
    try:
        data = request.json
        print(f"\n{'='*50}")
        print(f"📨 Received alert: {data}")
        print(f"{'='*50}")
        
        alert_type = data.get('alert_type', 'unknown')
        message = data.get('message', 'No message')
        symbol = data.get('symbol', 'UNKNOWN')
        price = data.get('price', 0)
        cloud_label = data.get('cloud_label', '')
        
        # Show desktop notification
        notification_title = f"🔔 {symbol} - {cloud_label}"
        notification_message = f"{message}\n価格: {price}"
        show_notification(notification_title, notification_message)
        
        # Play sound
        play_sound(alert_type)
        
        return jsonify({'status': 'success'}), 200
        
    except Exception as e:
        print(f"✗ Error: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'healthy'}), 200

@app.route('/test', methods=['GET'])
def test():
    """テスト用エンドポイント"""
    test_data = {
        'alert_type': 'short_up',
        'message': 'テスト通知',
        'symbol': 'TEST',
        'price': 12345.67
    }
    receive_alert_internal(test_data)
    return jsonify({'status': 'test executed', 'data': test_data}), 200

def receive_alert_internal(data):
    """内部テスト用"""
    alert_type = data.get('alert_type', 'unknown')
    message = data.get('message', 'No message')
    symbol = data.get('symbol', 'UNKNOWN')
    price = data.get('price', 0)
    
    notification_title = f"🔔 {symbol} - {alert_type}"
    notification_message = f"{message}\n価格: {price}"
    show_notification(notification_title, notification_message)
    play_sound(alert_type)

if __name__ == '__main__':
    print("="*60)
    print("🚀 Local Client Started")
    print("="*60)
    print(f"📍 Running on: http://localhost:5001")
    print(f"🔊 Sound files directory: sounds/")
    print(f"🎵 Volume adjustment: {voice_config.get('volume', 0)} dB")
    print(f"🧪 Test endpoint: http://localhost:5001/test")
    print("="*60)
    print("\n待機中... (Ctrl+C で終了)")
    
    app.run(host='0.0.0.0', port=5001, debug=True)
