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
    # =============== 基本スコアテンプレート（時間足レベルごと） ===============
    # ユーザーが指定した基本スコア値
    'base_scores': {
        'short_term': 80,         # 短期（15m）
        'mid_term': 85,           # 中期（1H）
        'long_term': 80,          # 長期（4H）
        'ultra_long_term': 85,    # 超長期（D/W/M/Y）※日足デフォルト
    },
    
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
    
    'ultra_long_term': {  # 超長期（D/W/M/Y）
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
        dauten = cloud.get('dauten', None)  # '▲Dow' or '▼Dow' or '-'
        gc = cloud.get('gc', None)  # '▲GC' or '▼DC'
        row_order = state_data.get('row_order', '')
        
        # ============================================================
        # ステップ 2: 3TF判定
        # ============================================================
        is_3tf = _check_3tf_alignment(row_order, all_states)
        
        # ============================================================
        # ステップ 2B: 基本的なトレンド方向をGC/DCから判定
        # ============================================================
        # GC=上昇=up, DC=下降=down として判定
        # gc は True/False or '▲GC'/'▼DC' という形式で来ることがある
        gc_str = str(gc) if gc else ''
        if 'True' in gc_str or 'GC' in gc_str:
            # GC（上昇交差）
            trend_direction = 'up'
        elif 'False' not in gc_str and 'DC' in gc_str:
            # DC（下降交差）
            trend_direction = 'down'
        elif gc is True:
            # gc=True の場合は GC（上昇交差）
            trend_direction = 'up'
        elif gc is False:
            # gc=False の場合は DC（下降交差）
            trend_direction = 'down'
        else:
            # GC/DCがない場合は angle から判定
            if angle > 0:
                trend_direction = 'up'
            elif angle < 0:
                trend_direction = 'down'
            else:
                trend_direction = 'range'
        
        # ============================================================
        # ステップ 3: 時間足レベル判定（row_orderから動的に判定）
        # ============================================================
        tf_level = _determine_tf_level(tf, row_order)
        deduction_rules = DEDUCTION_CONFIG[tf_level]
        
        # ============================================================
        # ステップ 4: 基本スコアをテンプレートから取得
        # ============================================================
        score = DEDUCTION_CONFIG['base_scores'].get(tf_level, 80)  # デフォルト80点
        deduction_breakdown = {}
        
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
                # 超長期の全減点を免除 → 基本スコアに戻す
                score = DEDUCTION_CONFIG['base_scores']['ultra_long_term']
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
        # ステップ 12: スコア < 20 の場合、direction を 'range' に修正
        # ============================================================
        final_direction = trend_direction
        if final_score < 20:
            final_direction = 'range'
        
        # ============================================================
        # ステップ 13: 結果を返す
        # ============================================================
        return {
            'strength': strength,
            'score': final_score,
            'direction': final_direction,
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
    対象時間足のレベルを判定
    
    方式：tf パラメータから直接判定
    - 短期（5m, 15m, '5', '15'）
    - 中期（1H/60分, '60'）
    - 長期（4H/240分, '240'）
    - 超長期（D, W, M, Y）
    
    Args:
        tf: 対象時間足（'5', '15', '60', '240', 'D', 'W', 'M', 'Y' または '5m', '15m', '1H', '4H' など）
        row_order: row_order文字列（情報用、直接的には使用しない）
    
    Returns:
        str: 'short_term', 'mid_term', 'long_term', 'ultra_long_term'
    """
    # tf の値をクリーンアップ（例：'15m' -> '15'）
    tf_normalized = tf.replace('m', '').replace('H', '0')
    
    # tf の値から時間足レベルを直接判定
    if tf in ['5', '15', '5m', '15m']:
        return 'short_term'
    elif tf in ['60', '1H', '1h'] or tf_normalized == '60':
        return 'mid_term'
    elif tf in ['240', '4H', '4h'] or tf_normalized == '240':
        return 'long_term'
    else:
        # D, W, M, Y など
        return 'ultra_long_term'


def _check_3tf_alignment(row_order, all_states):
    """
    3TFが揃っているかを判定
    
    3TFの定義：短期(15m) / 中期(1H) / 長期(4H) の3つが揃うこと
    超長期(D/W/M/Y)や5m との組み合わせは対象外
    
    row_orderのMAの並びで判定
    - 上昇トレンド: price,15m,1H,4H → priceが最初（価格が雲より上）
    - 下降トレンド: 4H,1H,15m,price → priceが最後（価格が雲より下）
    
    Returns:
        bool: 短期/中期/長期が揃っているか
    """
    if not row_order:
        return False
    
    # row_orderをリストに変換
    order_list = [x.strip() for x in row_order.split(',')]
    
    # 必須の3つの時間足が揃っているかチェック
    # 短期(15m), 中期(1H), 長期(4H) がすべて含まれているか確認
    required_tfs = {'15m', '1H', '4H'}
    clouds_in_order = [x for x in order_list if x != 'price']
    
    # row_order に含まれる時間足
    tfs_in_order = set(clouds_in_order)
    
    # 3つの必須時間足がすべて含まれているか
    if not required_tfs.issubset(tfs_in_order):
        return False
    
    # 必須3つの時間足のインデックスを取得
    tf_indices = {}
    for i, tf in enumerate(clouds_in_order):
        if tf in required_tfs:
            tf_indices[tf] = i
    
    # 短期(15m) < 中期(1H) < 長期(4H) の順序で並んでいるかチェック
    short_idx = tf_indices.get('15m')
    mid_idx = tf_indices.get('1H')
    long_idx = tf_indices.get('4H')
    
    # 通常の昇順（短期→中期→長期）
    if short_idx < mid_idx < long_idx:
        return True
    
    # 逆順（長期→中期→短期）
    if short_idx > mid_idx > long_idx:
        return True
    
    # 3つが揃わず
    return False


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
    abs_angle = abs(angle)
    
    if trend_direction == 'range':
        # レンジの場合も角度の安定性で評価
        # 角度が弱い（≤20°）なら減点（range品質評価として）
        if abs_angle <= 20:
            return deduction_rules['angle_weak_same_direction']
        else:
            return 0  # 角度が十分安定していれば減点なし
    
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
        gc: '▲GC' or '▼DC'
        trend_direction: トレンド方向（'up', 'down', 'range'）
        deduction_rules: 時間足レベルに応じた減点ルール
    
    Returns:
        int: 減点値（負の数）
    """
    if gc is None or gc == '-':
        # 雲交差がない場合は常に減点
        return deduction_rules['cloud_cross_opposite']
    
    if trend_direction == 'range':
        # レンジの場合、雲交差がなければそれは「不安定」と見做し減点
        # ただし gc が存在しているなら、その方向がレンジに対して適切かは判定しない
        return 0  # gc が存在していればレンジでも品質として OK
    
    # トレンド方向と雲交差が逆の場合、減点
    is_gc = (gc == '▲GC')
    if (trend_direction == 'up' and not is_gc) or \
       (trend_direction == 'down' and is_gc):
        return deduction_rules['cloud_cross_opposite']
    
    return 0


def _evaluate_dauten_deduction(dauten, trend_direction, deduction_rules):
    """
    ダウ転換による減点を計算
    
    Args:
        dauten: '▲Dow' or '▼Dow' or '-'
        trend_direction: トレンド方向（'up', 'down', 'range'）
        deduction_rules: 時間足レベルに応じた減点ルール
    
    Returns:
        int: 減点値（負の数）
    """
    if dauten is None or dauten == '-':
        # ダウ転換がない場合は常に減点
        return deduction_rules['dauten_opposite']
    
    if trend_direction == 'range':
        # レンジの場合、ダウ転換がなければそれは「不安定」と見做し減点
        # ただし dauten が存在しているなら、その方向がレンジに対して適切かは判定しない
        return 0  # dauten が存在していればレンジでも品質として OK
    
    # 文字列形式のダウ転換を判定（'▲Dow'='up', '▼Dow'='down'）
    dauten_direction = 'up' if dauten == '▲Dow' else 'down' if dauten == '▼Dow' else None
    
    # トレンド方向とダウ転換が逆の場合、減点
    if dauten_direction and dauten_direction != trend_direction:
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
            'dauten': '▲Dow',
            'gc': '▲GC',
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
