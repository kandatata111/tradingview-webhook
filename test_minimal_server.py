from flask import Flask
from flask_socketio import SocketIO

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

@app.route('/test')
def test():
    return "OK"

if __name__ == '__main__':
    print("Starting minimal test server...")
    socketio.run(app, host='0.0.0.0', port=5001, debug=True, use_reloader=False)
    print("Server ended")
