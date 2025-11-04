from flask import Flask, jsonify
import sqlite3

app = Flask(__name__)

@app.route('/test')
def test():
    conn = sqlite3.connect(r'c:\Users\kanda\Desktop\PythonData\TradingViewWebhook\webhook_data.db')
    c = conn.cursor()
    c.execute("SELECT symbol, timestamp FROM current_states ORDER BY timestamp DESC")
    rows = c.fetchall()
    conn.close()
    
    result = [{'symbol': r[0], 'timestamp': r[1]} for r in rows]
    return jsonify(result)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001)
