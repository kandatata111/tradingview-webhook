import sqlite3

DB_PATH = r'C:\Users\kanda\Desktop\PythonData\TradingViewWebhook\webhook_data.db'
conn = sqlite3.connect(DB_PATH)
conn.execute('DELETE FROM fire_history WHERE symbol = ?', ('USDJPY',))
conn.commit()
conn.close()
print('Cleared fire history for USDJPY')
