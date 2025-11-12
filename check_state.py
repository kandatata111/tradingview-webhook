import sqlite3, json
conn=sqlite3.connect('webhook_data.db')
c=conn.cursor()
c.execute('SELECT * FROM states WHERE symbol=? AND tf=? ORDER BY rowid DESC LIMIT 1', ('USDJPY', '5'))
row=c.fetchone()
cols=[d[0] for d in c.description]
conn.close()
if row:
    state=dict(zip(cols,row))
    state['clouds']=json.loads(state.get('clouds_json','[]'))
    print('State:', state.get('symbol'), state.get('tf'), 'clouds:', len(state['clouds']))
    for cloud in state['clouds']:
        print('  Cloud:', cloud.get('label'), 'gc:', cloud.get('gc'))
else:
    print('No state data')