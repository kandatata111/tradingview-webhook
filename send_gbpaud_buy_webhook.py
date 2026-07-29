#!/usr/bin/env python3
import requests
import datetime

url = 'http://localhost:5000/webhook'
now = datetime.datetime.now()
payload = {
    'symbol': 'GBPAUD',
    'tf': '5',
    'price': 1.8500,
    'time': int(now.timestamp() * 1000),
    'sent_time': now.strftime('%y/%m/%d/%H:%M'),
    'state': {'flag': 'A', 'word': 'Uptrend'},
    'daytrade': {
        'status': 'Long',
        'bos': '2',
        'time': now.strftime('%Y-%m-%dT%H:%M:%S+09:00')
    },
    'swing': {
        'status': 'Long',
        'bos': '1',
        'time': now.strftime('%Y-%m-%dT%H:%M:%S+09:00')
    },
    'row_order': ['5m', '15m', '1H', '4H'],
    'cloud_order': ['5m', '15m', '1H', '4H'],
    'clouds': [
        {'label': '5m', 'tf': '5m', 'dauten': '▲Dow', 'gc': '▲GC', 'po': '▲P2', 'bos_count': 2, 'angle': 12.0},
        {'label': '15m', 'tf': '15m', 'dauten': '▲Dow', 'gc': '▲GC', 'po': '▲P1', 'bos_count': 1, 'angle': 8.5},
        {'label': '1H', 'tf': '1H', 'dauten': '▲Dow', 'gc': '▲GC', 'po': '-', 'bos_count': 0, 'angle': 6.0},
        {'label': '4H', 'tf': '4H', 'dauten': '▲Dow', 'gc': '▲GC', 'po': '-', 'bos_count': 0, 'angle': 4.0}
    ],
    'meta': {'source': 'test', 'strategy': 'GBPAUD buy 5m PO'}
}

print('Sending GBPAUD buy webhook to', url)
print('Payload:', payload)
try:
    r = requests.post(url, json=payload, timeout=10)
    print('Response status:', r.status_code)
    print('Response body:', r.text)
except Exception as e:
    print('Error sending webhook:', e)
    raise
