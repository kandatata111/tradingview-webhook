#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Scan the SQLite DBs for occurrences of display-style TF labels (e.g. '15m','1H','4H')
and print affected rows from the `states` table so the user can decide remediation.
"""
import sqlite3
import os

HERE = os.path.dirname(os.path.dirname(__file__))
DBS = [os.path.join(HERE, 'webhook_data.db'), os.path.join(HERE, 'render_production_db.db')]
LABELS = ['15m', '1H', '4H']

if __name__ == '__main__':
    for db in DBS:
        if not os.path.exists(db):
            print(f"DB not found: {db}")
            continue
        print('\n' + '='*80)
        print(f"Scanning DB: {db}")
        print('='*80)
        conn = sqlite3.connect(db)
        cur = conn.cursor()

        # Print table schema for `states` (to help locate correct columns)
        try:
            print('\nTable schema for states:')
            cur.execute("PRAGMA table_info(states)")
            for col in cur.fetchall():
                print('  ', col)
        except Exception as e:
            print('  could not read schema:', e)

        # Search row_order (stored as TEXT/JSON) and clouds_json
        label_like = " OR ".join([f"row_order LIKE '%{lbl}%'" for lbl in LABELS])
        try:
            # use rowid + available columns (some DBs don't have id column)
            cur.execute(f"SELECT rowid, symbol, tf, row_order FROM states WHERE {label_like} ORDER BY rowid DESC LIMIT 100")
            rows = cur.fetchall()
            if rows:
                print(f"\nFound in row_order ({len(rows)} rows):")
                for r in rows:
                    print(f"  id={r[0]} symbol={r[1]} tf={r[2]} row_order={r[3]}")
            else:
                print('\nNo matches in row_order')
        except Exception as e:
            print('Error querying row_order:', e)

        label_like2 = " OR ".join([f"clouds_json LIKE '%{lbl}%'" for lbl in LABELS])
        try:
            cur.execute(f"SELECT rowid, symbol, tf, clouds_json FROM states WHERE {label_like2} ORDER BY rowid DESC LIMIT 200")
            rows = cur.fetchall()
            if rows:
                print(f"\nFound in clouds_json ({len(rows)} rows):")
                for r in rows:
                    snippet = (r[3] or '')[:400].replace('\n',' ')
                    print(f"  id={r[0]} symbol={r[1]} tf={r[2]} clouds_json_snippet={snippet}...")
            else:
                print('\nNo matches in clouds_json')
        except Exception as e:
            print('Error querying clouds_json:', e)

        conn.close()
    print('\nScan complete.')
