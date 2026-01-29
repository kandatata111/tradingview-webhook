"""
トレンド強度計算のテストスクリプト（Phase 3）
"""

from ichimoku_utils import (
    get_distance_level, 
    get_multi_cloud_bonus, 
    apply_decay_correction, 
    calculate_trend_strength
)

print('=' * 60)
print('Phase 3: トレンド強度計算テスト')
print('=' * 60)
print()

# テスト1: 距離レベル判定
print('【テスト1】 get_distance_level()')
print('-' * 60)

test_cases = [
    (25, 100, '非常に近い', 3),   # 25/100 = 25% < 50%
    (75, 100, '近い', 2),         # 75/100 = 75% < 100%
    (150, 100, '普通', 1),        # 150/100 = 150% < 200%
    (250, 100, '遠い', 0),        # 250/100 = 250% >= 200%
]

all_passed = True
for distance, thickness, expected_name, expected_points in test_cases:
    level_name, points = get_distance_level(distance, thickness)
    passed = (level_name == expected_name and points == expected_points)
    status = '✓' if passed else '✗'
    all_passed = all_passed and passed
    print(f'{status} distance={distance:3}, thickness={thickness:3} → {level_name:12} ({points}点) [期待: {expected_name} ({expected_points}点)]')

print()

# テスト2: 減衰補正
print('【テスト2】 apply_decay_correction()')
print('-' * 60)

decay_tests = [
    (100, '普通', False, 100.0),   # 補正なし
    (100, '遠い', False, 70.0),    # ×0.7
    (100, '普通', True, 50.0),     # ×0.5
    (100, '遠い', True, 35.0),     # ×0.7 × 0.5
]

for score, distance_level, has_reverse, expected in decay_tests:
    result = apply_decay_correction(score, distance_level, has_reverse)
    passed = abs(result - expected) < 0.01
    status = '✓' if passed else '✗'
    all_passed = all_passed and passed
    reverse_str = '逆方向あり' if has_reverse else '逆方向なし'
    print(f'{status} スコア{score}, {distance_level:12}, {reverse_str} → {result:5.1f} [期待: {expected}]')

print()

# テスト3: トレンド強度計算
print('【テスト3】 calculate_trend_strength()')
print('-' * 60)

# テストケース1: 強いトレンド
strong_state = {
    'clouds': [{
        'angle': 40.0,         # 高角度
        'thickness': 80.0,     # 厚い雲
        'distance_from_prev': 50.0,
        'dauten': 'up'
    }]
}

result = calculate_trend_strength('15m', strong_state)
print(f'強いトレンドのテスト:')
print(f'  基本スコア: {result["base_score"]} 点')
print(f'  ボーナス: {result["bonus"]} 点')
print(f'  最終スコア: {result["score"]} 点')
print(f'  強度判定: {result["strength"]}')
print(f'  距離レベル: {result["distance_level"]}')
print()

# テストケース2: 弱いトレンド
weak_state = {
    'clouds': [{
        'angle': 10.0,         # 低角度
        'thickness': 20.0,     # 薄い雲
        'distance_from_prev': 300.0,  # 遠い
        'dauten': 'up'
    }]
}

result2 = calculate_trend_strength('15m', weak_state)
print(f'弱いトレンドのテスト:')
print(f'  基本スコア: {result2["base_score"]} 点')
print(f'  ボーナス: {result2["bonus"]} 点')
print(f'  最終スコア: {result2["score"]} 点')
print(f'  強度判定: {result2["strength"]}')
print(f'  距離レベル: {result2["distance_level"]}')
print()

# テストケース3: 多雲ボーナス
print('【テスト4】 get_multi_cloud_bonus()')
print('-' * 60)

all_states = {
    '5m': {
        'clouds': [{'dauten': 'up', 'distance_from_prev': 30, 'thickness': 100}]
    },
    '15m': {
        'clouds': [{'dauten': 'up', 'distance_from_prev': 40, 'thickness': 100}]
    },
    '1H': {
        'clouds': [{'dauten': 'up', 'distance_from_prev': 50, 'thickness': 100}]
    }
}

bonus = get_multi_cloud_bonus('15m', all_states, 'up')
print(f'15m の多雲ボーナス (隣接する 5m, 1H が同方向): {bonus} 点')

print()

# 総合判定
print('=' * 60)
if all_passed:
    print('✅ 全てのテストが成功しました')
else:
    print('⚠️ 一部のテストが失敗しました')
print('=' * 60)
