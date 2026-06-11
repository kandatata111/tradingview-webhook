import re
path = 'webhook_error.log'
with open(path, 'r', encoding='utf-8', errors='ignore') as f:
    for line in f:
        if 'Processing rule "PO_5m"' in line or 'Rule "PO_5m" result: all_matched=True' in line or 'Emitted new_notification event for rule "PO_5m"' in line:
            print(line.rstrip())