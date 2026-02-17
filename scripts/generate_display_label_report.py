#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generate a JSON report of DB rows that contain display-style TF labels (e.g. '15m','1H','4H').
"""
import sqlite3
import os
import json

HERE = os.path.dirname(os.path.dirname(__file__))
DBS = [os.path.join(HERE, 'webhook_data.db'), os.path.join(HERE, 'render_production_db.db')]
LABELS = ['5m', '15m', '1H', '4H']
OUT_DIR = os.path.join(HERE, 'diagnosis')
OUT_FILE = os.path.join(OUT_DIR, 'display_label_report.json')

os.makedirs(OUT_DIR, exist_ok=True)
report = []

for db in DBS:
    if not os.path.exists(db):
        continue
    conn = sqlite3.connect(db)
    cur = conn.cursor()

    # clouds_json
    label_like2 = " OR ".join([f"clouds_json LIKE '%{lbl}%'" for lbl in LABELS])
    try:
        cur.execute(f"SELECT rowid, symbol, tf, clouds_json FROM states WHERE {label_like2} ORDER BY rowid DESC LIMIT 1000")
        for row in cur.fetchall():
            rowid, symbol, tf, clouds_json = row
            report.append({
                'db': os.path.basename(db),
                'table': 'states',
                'column': 'clouds_json',
                'rowid': rowid,
                'symbol': symbol,
                'tf': tf,
                'value_snippet': (clouds_json or '')[:500]
            })
    except Exception:
        pass

    # row_order
    label_like = " OR ".join([f"row_order LIKE '%{lbl}%'" for lbl in LABELS])
    try:
        cur.execute(f"SELECT rowid, symbol, tf, row_order FROM states WHERE {label_like} ORDER BY rowid DESC LIMIT 1000")
        for row in cur.fetchall():
            rowid, symbol, tf, row_order = row
            report.append({
                'db': os.path.basename(db),
                'table': 'states',
                'column': 'row_order',
                'rowid': rowid,
                'symbol': symbol,
                'tf': tf,
                'value_snippet': (row_order or '')[:200]
            })
    except Exception:
        pass

    conn.close()

with open(OUT_FILE, 'w', encoding='utf-8') as f:
    json.dump(report, f, ensure_ascii=False, indent=2)

print(f"Report written: {OUT_FILE} (entries: {len(report)})")
