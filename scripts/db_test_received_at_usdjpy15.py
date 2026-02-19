import sqlite3, pytz, datetime
DB=r"c:\Users\kanda\Desktop\PythonData\TradingViewWebhook\webhook_data.db"
con=sqlite3.connect(DB)
con.row_factory=sqlite3.Row
c=con.cursor()
row=c.execute("select rowid, symbol, tf, timestamp, received_at from states where symbol='USDJPY' and tf in ('15','15m')").fetchone()
print('ORIGINAL:', dict(row) if row else 'not found')
if not row:
    con.close()
    raise SystemExit('row not found')
orig_received = row['received_at']
# set test received_at to now_jst - 25 minutes
jst = pytz.timezone('Asia/Tokyo')
now = datetime.datetime.now(jst)
test_received = (now - datetime.timedelta(minutes=25)).isoformat()
print('SETTING received_at ->', test_received)
c.execute("update states set received_at=? where rowid=?", (test_received, row['rowid']))
con.commit()
row2=c.execute("select rowid, symbol, tf, timestamp, received_at from states where rowid=?", (row['rowid'],)).fetchone()
print('UPDATED:', dict(row2))
# compute diff minutes
updateTime = datetime.datetime.fromisoformat(row2['received_at'])
now2 = datetime.datetime.now(pytz.utc).astimezone(jst)
diff = (now2 - updateTime).total_seconds()/60.0
print('diff minutes =', round(diff,1))
# restore
print('RESTORING original received_at ->', orig_received)
c.execute("update states set received_at=? where rowid=?", (orig_received, row['rowid']))
con.commit()
row3=c.execute("select rowid, symbol, tf, timestamp, received_at from states where rowid=?", (row['rowid'],)).fetchone()
print('RESTORED:', dict(row3))
con.close()
