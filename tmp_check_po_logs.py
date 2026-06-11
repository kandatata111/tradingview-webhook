import re
path = 'webhook_error.log'
with open(path, 'r', encoding='utf-8', errors='ignore') as f:
    for line in f:
        if 'PO_5m' in line or 'PO_15m' in line or 'Emitted new_notification event for rule' in line:
            print(line.rstrip())