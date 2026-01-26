import sqlite3

conn = sqlite3.connect('webhook_data.db')
cursor = conn.cursor()

cursor.execute('PRAGMA table_info(states)')
print('States table schema:')
for row in cursor.fetchall():
    print(row)

print('\nSample data for USDJPY:')
cursor.execute('SELECT * FROM states WHERE symbol = "USDJPY" LIMIT 1')
columns = [description[0] for description in cursor.description]
print('Columns:', columns)

conn.close()
