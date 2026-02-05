"""
トレンド強度計算 - 減点方式 v5.0（最終版）

【設計思想】
- 基本スコア100点からスタート（3TF Perfect Order = 完璧な状態）
- 各時間足の問題点で減点していく方式
- 3TFが揃わない場合も同じルールで減点→自然と低スコアになる
- 特別ルール：超長期が70Pips以上の距離確保で超長期の減点免除
"""

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
# TFレベルマッピング
# ============================================================
TF_LEVEL_MAP = {
    '5': 'short_term',
    '15': 'short_term',
    '60': 'mid_term',
    '240': 'long_term',
    'D': 'ultra_long_term',
    'W': 'ultra_long_term',
    'M': 'ultra_long_term',
    'Y': 'ultra_long_term',
}


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
        # ステップ 4: 時間足レベル判定
        # ============================================================
        tf_level = TF_LEVEL_MAP.get(tf, 'mid_term')
        deduction_rules = DEDUCTION_CONFIG[tf_level]
        
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
        if tf_level == 'ultra_long_term' and is_3tf:
            ultra_long_distance_threshold = DEDUCTION_CONFIG['special_rule']['ultra_long_distance_threshold']
            if distance_from_price >= ultra_long_distance_threshold:
                # 超長期の全減点を免除
                score = 100  # 超長期の減点をすべてリセット
                deduction_breakdown = {
                    'special_rule_applied': '超長期70Pips以上 - 全減点免除'
                }
        
        # ============================================================
        # ステップ 10: 最終スコアを0-100に制限
        # ============================================================
        final_score = max(0, min(100, score))
        
        # ============================================================
        # ステップ 11: 強度判定
        # ============================================================
        threshold = DEDUCTION_CONFIG['threshold']
        
        if final_score >= threshold['strong_trend']:
            strength = "極"
        elif final_score >= threshold['strong']:
            strength = "強"
        elif final_score >= threshold['medium']:
            strength = "中"
        elif final_score >= threshold['weak']:
            strength = "弱"
        else:
            strength = "横"
        
        # ============================================================
        # ステップ 12: 結果を返す
        # ============================================================
        return {
            'strength': strength,
            'score': final_score,
            'direction': po_direction,
            'breakdown': deduction_breakdown,
            'details': {
                'angle': round(angle, 1),
                'thickness': round(thickness, 1),
                'dauten': dauten,
                'gc': gc,
                'dc': dc,
                'row_order': row_order,
                'po_level': po_level,
                'distance_pips': round(distance_from_prev, 2),
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
        'strength': '横',
        'score': 0,
        'direction': 'range',
        'breakdown': {
            'reason': reason,
        },
        'details': {}
    }


def _evaluate_perfect_order(row_order, current_tf, all_states):
    """
    row_orderからPerfect Order状態を評価
    
    【修正】雲の配列でPO判定、priceの位置でブレイク度を評価
    - D,W,M,Y = D(短期)が上 = 上昇PO
    - Y,M,W,D = Y(長期)が上 = 下降PO
    
    Returns:
        (direction, level, deduction)
        - direction: 'up', 'down', 'range'
        - level: '4tf', '3tf', '2tf', '1tf', 'none'
        - deduction: 減点値（負の数）
    """
    config = DEDUCTION_CONFIG['perfect_order']
    
    if not row_order:
        return 'range', 'none', config['no_row_order']
    
    # row_orderをリストに変換
    order_list = [x.strip() for x in row_order.split(',')]
    
    # priceの位置を確認
    if 'price' not in order_list:
        return 'range', 'none', config['no_alignment']
    
    price_index = order_list.index('price')
    
    # priceを除外して雲のみの配列を取得
    clouds_only = [x for x in order_list if x != 'price']
    
    if len(clouds_only) == 0:
        return 'range', 'none', config['no_alignment']
    
    # 時間足の階層定義（短期→長期）
    tf_hierarchy = ['5m', '15m', '1H', '4H', 'D', 'W', 'M', 'Y']
    
    # 雲の配列が短期→長期の順序か確認
    clouds_in_hierarchy = [tf for tf in tf_hierarchy if tf in clouds_only]
    
    if clouds_only == clouds_in_hierarchy:
        # 短期→長期の順序 = 上昇PO（短期雲が上）
        direction = 'up'
    elif clouds_only == list(reversed(clouds_in_hierarchy)):
        # 長期→短期の順序 = 下降PO（長期雲が上）
        direction = 'down'
    else:
        # 順序が乱れている = レンジ
        return 'range', 'none', config['no_alignment']
    
    # 整列TF数を判定
    aligned_count = len(clouds_only)
    
    if aligned_count >= 4:
        level = '4tf'
        deduction = config['4tf_perfect']
    elif aligned_count == 3:
        level = '3tf'
        deduction = config['3tf_aligned']
    elif aligned_count == 2:
        level = '2tf'
        deduction = config['2tf_aligned']
    elif aligned_count == 1:
        level = '1tf'
        deduction = config['1tf_only']
    else:
        level = 'none'
        deduction = config['no_alignment']
    
    return direction, level, deduction


def _evaluate_angle_weakness(angle):
    """角度の弱さを評価（減点）"""
    config = DEDUCTION_CONFIG['angle_weakness']
    abs_angle = abs(angle)
    
    if abs_angle >= config['strong'][0]:
        return config['strong'][1]
    elif abs_angle >= config['moderate'][0]:
        return config['moderate'][1]
    elif abs_angle >= config['weak'][0]:
        return config['weak'][1]
    elif abs_angle >= config['very_weak'][0]:
        return config['very_weak'][1]
    else:
        return config['flat'][1]


def _evaluate_thickness_weakness(thickness):
    """厚みの弱さを評価（減点）"""
    config = DEDUCTION_CONFIG['thickness_weakness']
    
    if thickness >= config['thick'][0]:
        return config['thick'][1]
    elif thickness >= config['moderate'][0]:
        return config['moderate'][1]
    elif thickness >= config['thin'][0]:
        return config['thin'][1]
    elif thickness >= config['very_thin'][0]:
        return config['very_thin'][1]
    else:
        return config['ultra_thin'][1]


def _evaluate_contradictions(po_direction, dauten, angle, gc):
    """
    矛盾を検出してペナルティ
    
    【修正】gc:true=GC, gc:false=DC として判定
    
    Args:
        po_direction: Perfect Orderの方向（'up', 'down', 'range'）
        dauten: ダウ転換（'up', 'down', None）
        angle: 雲の角度（符号付き）
        gc: 雲交差（True=GC, False=DC, None=データなし）
    
    Returns:
        (deduction, details)
    """
    config = DEDUCTION_CONFIG['contradiction']
    contradictions = []
    total_deduction = 0
    
    # Perfect Orderがrangeの場合は矛盾チェックなし
    if po_direction == 'range':
        return 0, []
    
    # 1. dauten方向の矛盾
    if dauten and dauten != po_direction:
        contradictions.append(f'dauten={dauten} vs PO={po_direction}')
        total_deduction += config['dauten_mismatch']
    
    # 2. angle符号の矛盾
    if angle != 0:
        angle_direction = 'up' if angle > 0 else 'down'
        if angle_direction != po_direction:
            contradictions.append(f'angle={angle:.1f}° vs PO={po_direction}')
            total_deduction += config['angle_mismatch']
    
    # 3. GC/DC矛盾
    # gc:true = GC（ゴールデンクロス）
    # gc:false = DC（デッドクロス）
    is_gc = (gc == True)
    is_dc = (gc == False)
    
    if is_gc and po_direction == 'down':
        # 下降PO中にGC発生 = 矛盾
        contradictions.append(f'GC vs PO=down')
        total_deduction += config['gc_dc_mismatch']
    elif is_dc and po_direction == 'up':
        # 上昇PO中にDC発生 = 矛盾
        contradictions.append(f'DC vs PO=up')
        total_deduction += config['gc_dc_mismatch']
    
    # 複数矛盾の場合、個別合計ではなく固定ペナルティ
    if len(contradictions) >= 2:
        total_deduction = config['multiple']
    
    return total_deduction, contradictions


def _evaluate_data_absence(dauten, row_order, clouds):
    """データ欠損を評価（減点）
    
    【修正】gc/dcは常に存在するため、チェック不要
    """
    config = DEDUCTION_CONFIG['data_absence']
    deduction = 0
    
    if dauten is None:
        deduction += config['dauten_none']
    
    if not row_order or row_order == '':
        deduction += config['row_order_empty']
    
    if not clouds or len(clouds) == 0:
        deduction += config['clouds_empty']
    
    return deduction


def _evaluate_upper_tf_influence(current_tf, po_direction, all_states):
    """上位足の影響を評価（減点）"""
    config = DEDUCTION_CONFIG['upper_tf_influence']
    
    if not all_states or po_direction == 'range':
        return 0
    
    # TF階層マッピング
    tf_hierarchy = {
        '5': 0,
        '15': 1,
        '60': 2,
        '240': 3,
    }
    
    if current_tf not in tf_hierarchy:
        return 0
    
    current_level = tf_hierarchy[current_tf]
    deduction = 0
    
    # 1段階上位と2段階上位をチェック
    for level_diff in [1, 2]:
        upper_level = current_level + level_diff
        upper_tf_map = {0: '5', 1: '15', 2: '60', 3: '240'}
        
        if upper_level in upper_tf_map:
            upper_tf = upper_tf_map[upper_level]
            upper_state = all_states.get(upper_tf, {})
            upper_row_order = upper_state.get('row_order', '')
            
            if upper_row_order:
                upper_direction, _, _ = _evaluate_perfect_order(
                    upper_row_order, upper_tf, None
                )
                
                # 逆方向の場合、減点
                if upper_direction != 'range' and upper_direction != po_direction:
                    if level_diff == 1:
                        deduction += config['1level_opposite']
                    elif level_diff == 2:
                        deduction += config['2level_opposite']
            else:
                # 上位データなし
                if level_diff == 1:
                    deduction += config['no_upper_data']
    
    return deduction


def _evaluate_distance_issue(distance_pips):
    """
    距離の問題を評価（減点）
    
    Args:
        distance_pips: cloud0のdistance_from_prev（絶対値、Pips単位）
    """
    config = DEDUCTION_CONFIG['distance_issue']
    
    # 閾値順にチェック
    for level, (threshold, deduction) in config.items():
        if distance_pips < threshold:
            return deduction
    
    # どの閾値にも該当しない場合（最大減点）
    return config['very_far'][1]


# ============================================================
# 【テスト】計算例
# ============================================================
if __name__ == '__main__':
    # テストケース1: USDJPY 15m（期待: 下降70点程度）
    test_usdjpy_15m = {
        'clouds': [{
            'angle': -32.18,
            'thickness': 8.76,
            'distance_from_prev': 2.68,
            'dauten': 'up',  # 矛盾あり
            'gc': False,
            'dc': False,
        }],
        'row_order': 'D,4H,1H,15m,price'  # Perfect 下降PO
    }
    
    result1 = calculate_trend_strength_v2('15', test_usdjpy_15m, None)
    
    print("=" * 60)
    print("テストケース1: USDJPY 15m")
    print("=" * 60)
    print(f"強度: {result1['strength']}")
    print(f"スコア: {result1['score']}/100")
    print(f"方向: {result1['direction']}")
    print()
    print("減点内訳:")
    for k, v in result1['breakdown'].items():
        print(f"  {k}: {v}")
    print()
    print("詳細情報:")
    for k, v in result1['details'].items():
        print(f"  {k}: {v}")
    print()
    
    # テストケース2: GBPUSD 1H（期待: 上昇94点程度）
    test_gbpusd_1h = {
        'clouds': [{
            'angle': 42.5,
            'thickness': 65.3,
            'distance_from_prev': 8.2,
            'dauten': 'up',
            'gc': True,
            'dc': False,
        }],
        'row_order': 'price,15m,1H,4H,D'  # Perfect 上昇PO
    }
    
    result2 = calculate_trend_strength_v2('60', test_gbpusd_1h, None)
    
    print("=" * 60)
    print("テストケース2: GBPUSD 1H")
    print("=" * 60)
    print(f"強度: {result2['strength']}")
    print(f"スコア: {result2['score']}/100")
    print(f"方向: {result2['direction']}")
    print()
    print("減点内訳:")
    for k, v in result2['breakdown'].items():
        print(f"  {k}: {v}")
    print()
    print("詳細情報:")
    for k, v in result2['details'].items():
        print(f"  {k}: {v}")
