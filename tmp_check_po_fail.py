import re
path = 'webhook_error.log'
with open(path, 'r', encoding='utf-8', errors='ignore') as f:
    lines = f.readlines()
for i, line in enumerate(lines):
    if 'Processing rule "PO_5m"' in line or 'Rule "PO_5m" result: all_matched=False' in line or 'Condition not met:' in line:
        start = max(0, i-5)
        end = min(len(lines), i+5)
        print('--- block ---')
        for j in range(start, end):
            print(lines[j].rstrip())
