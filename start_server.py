import sys
sys.path.insert(0, r'c:\Users\kanda\Desktop\PythonData\TradingViewWebhook')

import render_server

if __name__ == '__main__':
    render_server.app.run(host='0.0.0.0', port=5000, debug=False)
