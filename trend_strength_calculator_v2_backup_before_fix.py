"""
トレンド強度計算 - 減点方式 v5.0（最終版）

【設計思想】
- 基本スコア100点からスタート（3TF Perfect Order = 完璧な状態）
- 各時間足の問題点で減点していく方式
- 3TFが揃わない場合も同じルールで減点→自然と低スコアになる
- 特別ルール：超長期が70Pips以上の距離確保で超長期の減点免除

【修正履歴】
- v5.0.1 (2026/02/04): 時間足レベルをrow_orderから動的に判定するように修正
"""

# バージョン識別子（サーバーログに出力）
VERSION = "v5.0.1_dynamic_tf_level_20260204"

print(f"[IMPORT] trend_strength_calculator_v2.py {VERSION} loaded")

# ============================================================
# 【設定】減点方式の配点マスター v5.0
# ============================================================
DEDUCTION_CONFIG = {
    # =============== 減点ルール表（各時間足ごと） ===============
    'short_term': {  # 短期（15m）
        'angle_weak_same_direction': -10,      # 角度弱さ（20°以下同方向）
        'angle_opposite_30_or_less': -20,      # 角度逆方向(30°以下)
        'angle_opposite_30_plus': -30,         # 角度逆方向(30°以上)
        'thickness_low': -10,                  # 厚さ不足（≤5Pips）
        'cloud_cross_opposite': -10,           # 雲交差逆方向
        'dauten_opposite': -10,                # ダウ逆方向
    },
    
    'mid_term': {  # 中期（1H）
        'angle_weak_same_direction': -15,
        'angle_opposite_30_or_less': -30,
        'angle_opposite_30_plus': -45,
        'thickness_low': -15,
        'cloud_cross_opposite': -15,
        'dauten_opposite': -10,
    },
    
    'long_term': {  # 長期（4H）
        'angle_weak_same_direction': -20,
        'angle_opposite_30_or_less': -40,
        'angle_opposite_30_plus': -60,
        'thickness_low': -20,
        'cloud_cross_opposite': -20,
        'dauten_opposite': -10,
    },
    
    'ultra_long_term': {  # 超長期（D/W/Y）
        'angle_weak_same_direction': -20,
        'angle_opposite_30_or_less': -40,
        'angle_opposite_30_plus': -60,
        'thickness_low': -20,
        'cloud_cross_opposite': -20,
        'dauten_opposite': -10,
    },
    
    # =============== 判定閾値 ===============
    'threshold': {
        'strong_trend': 80,    # 強いトレンド: 80-100点
        'trend': 60,           # トレンド: 60-79点
        'weak_trend': 40,      # 弱いトレンド: 40-59点
        'very_weak': 20,       # 非常に弱いトレンド: 20-39点
        'range': 0,            # レンジ/無効: 0-19点
    },
    
    # =============== 特別ルール閾値 ===============
    'special_rule': {
        'ultra_long_distance_threshold': 70,  # 70Pips以上で超長期減点免除
    }
}


# ============================================================
# TFレベルマッピング（動的判定用の階層定義）
# ============================================================
# 注意：時間足レベルは固定ではなく、row_orderから動的に判定する
# 例：Dの行を計算する時 → row_order='D,W,M,Y,price' → Dが短期、Wが中期、Mが長期、Yが超長期
TF_HIERARCHY = ['5m', '15m', '1H', '4H', 'D', 'W', 'M', 'Y']


def calculate_trend_strength_v2(tf, state_data, all_states=None):
    """
    トレンド強度を計算（減点方式 v5.0）
    
    Args:
        tf: 対象時間足（'5', '15', '60', '240', 'D', 'W', 'M', 'Y'）
        state_data: 当該時間足の状態データ
        all_states: 全タイムフレームの状態データ（3TF判定・特別ルール用）
    
    Returns:
        dict: {
            'strength': str,           # 「強いトレンド」「トレンド」「弱いトレンド」「非常に弱いトレンド」「レンジ」
            'score': int,              # 最終スコア（0-100点）
            'direction': str,          # 'up', 'down', 'range'
            'breakdown': dict,         # スコア内訳（デバッグ用）
            'details': dict            # 詳細情報
        }
    """
    try:
        # ============================================================
        # ステップ 1: 基本データ取得
        # ============================================================
        clouds = state_data.get('clouds', [])
        if not clouds:
            return _return_range('clouds_empty')
        
        cloud = clouds[0] if isinstance(clouds, list) else clouds
        
        # 基本データ
        angle = cloud.get('angle', 0)  # 符号付き
        thickness = abs(cloud.get('thickness', 0))
        distance_from_price = abs(cloud.get('distance_from_prev', 0))  # 価格と雲中心MAの距離
        dauten = cloud.get('dauten', None)  # 'up' or 'down'
        gc = cloud.get('gc', None)  # True=GC, False=DC
        row_order = state_data.get('row_order', '')
        
        # ============================================================
        # ステップ 2: 3TF判定とトレンド方向の決定
        # ============================================================
        is_3tf, trend_direction = _check_3tf_alignment(row_order, all_states)
        
        # ============================================================
        # ステップ 3: 基本スコア100点からスタート
        # ============================================================
        score = 100
        deduction_breakdown = {}
        
        # ============================================================
        # ステップ 4: 時間足レベル判定（row_orderから動的に判定）
        # ============================================================
        tf_level = _determine_tf_level(tf, row_order)
        deduction_rules = DEDUCTION_CONFIG[tf_level]
        
        print(f"[CALC] tf={tf}, row_order={row_order}, tf_level={tf_level}, direction={trend_direction}")
        
        # ============================================================
        # ステップ 5: 角度減点の判定
        # ============================================================
        angle_deduction = _evaluate_angle_deduction(
            angle, trend_direction, deduction_rules
        )
        score += angle_deduction
        deduction_breakdown['angle'] = angle_deduction
        
        # ============================================================
        # ステップ 6: 厚さ不足の減点
        # ============================================================
        thickness_deduction = 0
        if thickness <= 5:
            thickness_deduction = deduction_rules['thickness_low']
            score += thickness_deduction
        deduction_breakdown['thickness'] = thickness_deduction
        
        # ============================================================
        # ステップ 7: 雲交差逆方向の減点
        # ============================================================
        cloud_cross_deduction = _evaluate_cloud_cross_deduction(
            gc, trend_direction, deduction_rules
        )
        score += cloud_cross_deduction
        deduction_breakdown['cloud_cross'] = cloud_cross_deduction
        
        # ============================================================
        # ステップ 8: ダウ逆方向の減点
        # ============================================================
        dauten_deduction = _evaluate_dauten_deduction(
            dauten, trend_direction, deduction_rules
        )
        score += dauten_deduction
        deduction_breakdown['dauten'] = dauten_deduction
        
        # ============================================================
        # ステップ 9: 特別ルール（超長期70Pips以上）
        # ============================================================
        special_rule_applied = False
        if tf_level == 'ultra_long_term' and is_3tf:
            ultra_long_distance_threshold = DEDUCTION_CONFIG['special_rule']['ultra_long_distance_threshold']
            if distance_from_price >= ultra_long_distance_threshold:
                # 超長期の全減点を免除
                score = 100  # 超長期の減点をすべてリセット
                deduction_breakdown = {
                    'special_rule_applied': '超長期70Pips以上 - 全減点免除'
                }
                special_rule_applied = True
        
        # ============================================================
        # ステップ 10: 最終スコアを0-100に制限
        # ============================================================
        final_score = max(0, min(100, score))
        
        # ============================================================
        # ステップ 11: 強度判定
        # ============================================================
        threshold = DEDUCTION_CONFIG['threshold']
        
        if final_score >= threshold['strong_trend']:
            strength = "強いトレンド"
        elif final_score >= threshold['trend']:
            strength = "トレンド"
        elif final_score >= threshold['weak_trend']:
            strength = "弱いトレンド"
        elif final_score >= threshold['very_weak']:
            strength = "非常に弱いトレンド"
        else:
            strength = "レンジ"
        
        # ============================================================
        # ステップ 12: 結果を返す
        # ============================================================
        return {
            'strength': strength,
            'score': final_score,
            'direction': trend_direction,
            'breakdown': deduction_breakdown,
            'details': {
                'angle': round(angle, 1),
                'thickness': round(thickness, 1),
                'dauten': dauten,
                'gc': gc,
                'row_order': row_order,
                'is_3tf': is_3tf,
                'tf_level': tf_level,
                'distance_pips': round(distance_from_price, 2),
                'special_rule_applied': special_rule_applied,
            }
        }
        
    except Exception as e:
        print(f'[ERROR] calculate_trend_strength_v2: {e}')
        import traceback
        traceback.print_exc()
        return _return_range('exception')


def _return_range(reason=''):
    """レンジを返す"""
    return {
        'strength': 'レンジ',
        'score': 0,
        'direction': 'range',
        'breakdown': {
            'reason': reason,
        },
        'details': {}
    }


def _determine_tf_level(tf, row_order):
    """
    row_orderから時間足レベルを動的に判定
    
    例：
    - row_order='15m,1H,4H,D,price' → 15mが短期、1Hが中期、4Hが長期、Dが超長期
    - row_order='D,W,M,Y,price' → Dが短期、Wが中期、Mが長期、Yが超長期
    
    Args:
        tf: 対象時間足（'5', '15', '60', '240', 'D', 'W', 'M', 'Y'）
        row_order: 'D,W,M,Y,price' のような順序文字列
    
    Returns:
        str: 'short_term', 'mid_term', 'long_term', 'ultra_long_term'
    """
    if not row_order:
        # デフォルト判定
        if tf in ['5', '15']:
            return 'short_term'
        elif tf == '60':
            return 'mid_term'
        elif tf == '240':
            return 'long_term'
        else:
            return 'ultra_long_term'
    
    # row_orderをリストに変換
    order_list = [x.strip() for x in row_order.split(',')]
    
    # priceを除外してMA（雲）のみの配列を取得
    clouds_only = [x for x in order_list if x != 'price']
    
    if len(clouds_only) < 1:
        return 'short_term'
    
    # tf_normalized形式（'5m', '15m', '1H', '4H', 'D', 'W', 'M', 'Y'）に変換
    tf_map = {
        '5': '5m',
        '15': '15m',
        '60': '1H',
        '240': '4H',
        'D': 'D',
        'W': 'W',
        'M': 'M',
        'Y': 'Y',
    }
    tf_normalized = tf_map.get(tf, tf)
    
    # clouds_only内でtf_normalizedが何番目か
    try:
        position = clouds_only.index(tf_normalized)
    except ValueError:
        # 見つからない場合はデフォルト判定
        return 'short_term'
    
    # 位置に応じてレベルを判定
    # 0番目（最初）= 短期
    # 1番目 = 中期
    # 2番目 = 長期
    # 3番目以降 = 超長期
    if position == 0:
        return 'short_term'
    elif position == 1:
        return 'mid_term'
    elif position == 2:
        return 'long_term'
    else:
        return 'ultra_long_term'


def _check_3tf_alignment(row_order, all_states):
    """
    3TFが揃っているかを判定
    
    3TFの定義：短期MA > 中期MA > 長期MA（上昇）または 短期MA < 中期MA < 長期MA（下降）
    row_orderのMAの並びで判定
    
    Returns:
        (is_3tf, trend_direction)
        - is_3tf: bool（3TF揃っているか）
        - trend_direction: 'up', 'down', 'range'
    """
    if not row_order:
        return False, 'range'
    
    # row_orderをリストに変換
    order_list = [x.strip() for x in row_order.split(',')]
    
    # priceを除外してMA（雲）のみの配列を取得
    clouds_only = [x for x in order_list if x != 'price']
    
    if len(clouds_only) < 3:
        return False, 'range'
    
    # 各雲の階層インデックスを取得
    cloud_indices = []
    for cloud in clouds_only:
        try:
            idx = TF_HIERARCHY.index(cloud)
            cloud_indices.append((cloud, idx))
        except ValueError:
            continue
    
    if len(cloud_indices) < 3:
        return False, 'range'
    
    # 連続する3つの雲が階層順序に沿っているかチェック
    # row_orderは雲と価格の位置関係を表す：
    # - 上昇トレンド: price,短期,中期,長期 → priceが最初（価格が雲より上）
    # - 下降トレンド: 長期,中期,短期,price → priceが最後（価格が雲より下）
    
    # priceの位置を確認
    if 'price' not in order_list:
        return False, 'range'
    
    price_index = order_list.index('price')
    
    # 連続する3つの雲が階層順序に沿っているかチェック
    for i in range(len(cloud_indices) - 2):
        three_clouds = cloud_indices[i:i+3]
        indices = [idx for _, idx in three_clouds]
        
        # 短期→中期→長期の順序で並んでいるか
        if indices[0] < indices[1] < indices[2]:
            # priceが雲より上（最初）なら上昇トレンド
            if price_index == 0:
                return True, 'up'
            # priceが雲より下（最後）なら下降トレンド
            else:
                return True, 'down'
        
        # 長期→中期→短期の順序で並んでいるか
        if indices[0] > indices[1] > indices[2]:
            # priceが雲より上（最初）なら上昇トレンド
            if price_index == 0:
                return True, 'up'
            # priceが雲より下（最後）なら下降トレンド
            else:
                return True, 'down'
    
    # 3TF揃わず
    return False, 'range'


def _evaluate_angle_deduction(angle, trend_direction, deduction_rules):
    """
    角度による減点を計算
    
    Args:
        angle: 雲の角度（符号付き）
        trend_direction: トレンド方向（'up', 'down', 'range'）
        deduction_rules: 時間足レベルに応じた減点ルール
    
    Returns:
        int: 減点値（負の数）
    """
    if trend_direction == 'range':
        return 0
    
    abs_angle = abs(angle)
    
    # トレンド方向と角度の符号が一致するか
    is_same_direction = (trend_direction == 'up' and angle > 0) or \
                        (trend_direction == 'down' and angle < 0)
    
    if is_same_direction:
        # 同方向の場合、20°以下なら減点
        if abs_angle <= 20:
            return deduction_rules['angle_weak_same_direction']
        else:
            return 0  # 減点なし
    else:
        # 逆方向の場合
        if abs_angle <= 30:
            return deduction_rules['angle_opposite_30_or_less']
        else:
            return deduction_rules['angle_opposite_30_plus']


def _evaluate_cloud_cross_deduction(gc, trend_direction, deduction_rules):
    """
    雲交差による減点を計算
    
    Args:
        gc: True=GC, False=DC
        trend_direction: トレンド方向（'up', 'down', 'range'）
        deduction_rules: 時間足レベルに応じた減点ルール
    
    Returns:
        int: 減点値（負の数）
    """
    if trend_direction == 'range' or gc is None:
        return 0
    
    # GC=上昇、DC=下降
    is_gc = (gc == True)
    
    # トレンド方向と雲交差が逆の場合、減点
    if (trend_direction == 'up' and not is_gc) or \
       (trend_direction == 'down' and is_gc):
        return deduction_rules['cloud_cross_opposite']
    
    return 0


def _evaluate_dauten_deduction(dauten, trend_direction, deduction_rules):
    """
    ダウ転換による減点を計算
    
    Args:
        dauten: 'up' or 'down'
        trend_direction: トレンド方向（'up', 'down', 'range'）
        deduction_rules: 時間足レベルに応じた減点ルール
    
    Returns:
        int: 減点値（負の数）
    """
    if trend_direction == 'range' or dauten is None:
        return 0
    
    # トレンド方向とダウ転換が逆の場合、減点
    if dauten != trend_direction:
        return deduction_rules['dauten_opposite']
    
    return 0


def get_scoring_rules_info():
    """
    スコア表とルールをTooltip用に返す
    """
    return {
        '基本スコア': '100点（3TF揃った状態）',
        '減点ルール': DEDUCTION_CONFIG,
        '特別ルール': '超長期が70Pips以上価格と距離を確保できていれば、超長期に関する全ての減点なし',
        '判定閾値': {
            '80-100点': '強いトレンド',
            '60-79点': 'トレンド',
            '40-59点': '弱いトレンド',
            '20-39点': '非常に弱いトレンド',
            '0-19点': 'レンジ/無効',
        }
    }


# ============================================================
# 【テスト】計算例
# ============================================================
if __name__ == '__main__':
    # テストケース1: 3TF揃った、完璧な状態
    test_case_1 = {
        'clouds': [{
            'angle': 35.0,
            'thickness': 60.0,
            'distance_from_prev': 80.0,
            'dauten': 'up',
            'gc': True,
        }],
        'row_order': 'price,15m,1H,4H'
    }
    
    result1 = calculate_trend_strength_v2('15', test_case_1, None)
    
    print("=" * 60)
    print("テストケース1: 3TF揃った完璧な状態")
    print("=" * 60)
    print(f"強度: {result1['strength']}")
    print(f"スコア: {result1['score']}/100")
    print(f"方向: {result1['direction']}")
    print()
    print("減点内訳:")
    for k, v in result1['breakdown'].items():
        print(f"  {k}: {v}")
    print()
    
    # テストケース2: 3TF揃わない、中期と長期がDC
    test_case_2 = {
        'clouds': [{
            'angle': -30.0,
            'thickness': 10.0,
            'distance_from_prev': 30.0,
            'dauten': 'down',
            'gc': False,
        }],
        'row_order': '4H,1H,price,15m'  # 15mだけGC、他DC
    }
    
    result2 = calculate_trend_strength_v2('60', test_case_2, None)
    
    print("=" * 60)
    print("テストケース2: 3TF揃わない状態")
    print("=" * 60)
    print(f"強度: {result2['strength']}")
    print(f"スコア: {result2['score']}/100")
    print(f"方向: {result2['direction']}")
    print()
    print("減点内訳:")
    for k, v in result2['breakdown'].items():
        print(f"  {k}: {v}")
    print()
    
    # テストケース3: 超長期、70Pips以上（特別ルール適用）
    test_case_3 = {
        'clouds': [{
            'angle': 15.0,  # 角度弱い
            'thickness': 3.0,  # 厚さ不足
            'distance_from_prev': 80.0,  # 70Pips以上
            'dauten': 'down',  # ダウ逆方向
            'gc': False,  # 雲交差逆方向
        }],
        'row_order': 'price,1H,4H,D'  # 3TF揃った
    }
    
    result3 = calculate_trend_strength_v2('D', test_case_3, None)
    
    print("=" * 60)
    print("テストケース3: 超長期70Pips以上（特別ルール）")
    print("=" * 60)
    print(f"強度: {result3['strength']}")
    print(f"スコア: {result3['score']}/100")
    print(f"方向: {result3['direction']}")
    print()
    print("減点内訳:")
    for k, v in result3['breakdown'].items():
        print(f"  {k}: {v}")
    print()
    
    # ルール情報表示
    print("=" * 60)
    print("スコアリングルール情報（Tooltip用）")
    print("=" * 60)
    import json
    rules_info = get_scoring_rules_info()
    print(json.dumps(rules_info, indent=2, ensure_ascii=False))
