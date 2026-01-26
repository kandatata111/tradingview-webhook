import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'webhook_data.db')
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

print("States table schema:")
cursor.execute('PRAGMA table_info(states)')
for row in cursor.fetchall():
    print(f"  {row}")

print("\nSample data from states (last 3 rows):")
cursor.execute('SELECT * FROM states ORDER BY rowid DESC LIMIT 3')
for row in cursor.fetchall():
    print(f"  {row}")

conn.close()
