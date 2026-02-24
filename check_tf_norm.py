import sqlite3
conn=sqlite3.connect('webhook_data.db')
c=conn.cursor()
c.execute('SELECT symbol, tf, tf_normalized FROM states')
for r in c.fetchall():
    print(r)
conn.close()
