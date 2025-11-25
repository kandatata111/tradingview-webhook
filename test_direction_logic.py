# テスト: 方向判定ロジック

# 複数条件の場合、各条件から方向を収集
condition_directions = []

# テストデータ
conditions = [
    {'field': 'dauten', 'value_found': 'up'},
    {'field': 'gc', 'value_found': False}
]

for cond in conditions:
    field = cond['field']
    found_value = cond['value_found']
    
    direction = None
    if field == 'dauten':
        if found_value == 'up':
            direction = 'up'
        elif found_value == 'down':
            direction = 'down'
    elif field == 'gc':
        if found_value is True:
            direction = 'up'
        elif found_value is False:
            direction = 'down'
    
    condition_directions.append(direction)
    print(f'Field: {field}, Value: {found_value}, Direction: {direction}')

print(f'\nAll directions: {condition_directions}')

# 方向の整合性をチェック
valid_directions = [d for d in condition_directions if d is not None]
print(f'Valid directions: {valid_directions}')

if len(valid_directions) > 1:
    if len(set(valid_directions)) > 1:
        print('❌ Direction mismatch - NOT firing')
    else:
        print(f'✅ Direction aligned: {valid_directions[0]} - FIRING')
else:
    print('Only one direction or no direction info')
