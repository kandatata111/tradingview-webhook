import sqlite3

conn = sqlite3.connect('webhook_data.db')
c = conn.cursor()

c.execute('''SELECT symbol, price, cloud_5m_topPrice, cloud_5m_bottomPrice, 
             cloud_15m_topPrice, cloud_15m_bottomPrice, 
             cloud_1h_topPrice, cloud_1h_bottomPrice, 
             cloud_4h_topPrice, cloud_4h_bottomPrice 
             FROM current_states 
             WHERE symbol='USDJPY' 
             ORDER BY timestamp DESC LIMIT 1''')

row = c.fetchone()

if row:
    print(f"Symbol: {row[0]}")
    print(f"Price: {row[1]}")
    print(f"\n雲データ:")
    print(f"5m:  topPrice={row[2]}, bottomPrice={row[3]}")
    print(f"15m: topPrice={row[4]}, bottomPrice={row[5]}")
    print(f"1H:  topPrice={row[6]}, bottomPrice={row[7]}")
    print(f"4H:  topPrice={row[8]}, bottomPrice={row[9]}")
else:
    print("データが見つかりません")

conn.close()
