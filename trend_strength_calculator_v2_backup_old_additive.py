"""
トレンド強度計算 - 100点満点版（拡張性重視）

このモジュールは以下の特徴を持ちます：
1. スコアを100点満点に正規化
2. 配点をコンフィグ化（TREND_SCORE_CONFIG）
3. 計算ステップを明確化
4. 実装後の修正を容易に
"""

# ============================================================
# 【設定】トレンド強度計算の配点マスター
# ============================================================
# 修正必要な場合はこの辞書を調整するだけで OK
# 
TREND_SCORE_CONFIG = {
    # =============== 基本スコア ===============
    'base': {
        'angle_max': 45,          # 45度を最高スコア対象
        'angle_weight': 30,       # 角度の配点（全100点中30点）
        'thickness_max': 100,     # 100Pipsを最高スコア対象
        'thickness_weight': 20,   # 厚みの配点（全100点中20点）
    },
    
    # =============== ボーナス ===============
    'bonus': {
        # ダウ転換
        'dauten_confirmed': 15,   # ダウ転換確認時: +15点
        
        # 雲整列（Perfect Order等）
        'cloud_align_perfect': 15,    # 4本全て整列: +15点
        'cloud_align_3tf': 10,        # 3本整列: +10点
        'cloud_align_2tf': 5,         # 2本整列: +5点
        'cloud_align_match': 5,       # 整列方向 = ダウ転換方向一致: +5点
        
        # 多雲ボーナス（隣接TF同方向かつ距離近い）
        'multi_cloud_adjacent': 10,   # 隣接（1段階差）: +10点
        'multi_cloud_1step': 5,       # 1段階離れ（2段階差）: +5点
        'multi_cloud_2step': 2,       # 2段階以上: +2点
        
        # 距離レベル
        'distance_very_close': 2,     # <50%: +2点
        'distance_close': 1,          # 50-100%: +1点
        'distance_normal': 0,         # 100-200%: +0点
        'distance_far': 0,            # >200%: +0点
        
        # BOS継続
        'bos_count_3plus': 3,         # BOS >= 3: +3点
        'bos_count_1_2': 1,           # BOS 1-2: +1点
        
        # GC/DC強度
        'in_cloud_gc_match': 3,       # 価格が雲内 + GC一致: +3点
    },
    
    # =============== 減衰補正 ===============
    'decay': {
        'distance_far': 0.7,          # 距離「遠い」時: ×0.7
        'reverse_direction': 0.5,     # 逆方向雲あり: ×0.5
        'in_cloud_gc_mismatch': 0.8,  # 価格が雲内でGC不一致: ×0.8
    },
    
    # =============== 判定閾値 ===============
    'threshold': {
        'extreme': 80,    # 「極」: 80点以上
        'strong': 60,     # 「強」: 60-79点
        'medium': 40,     # 「中」: 40-59点
        'weak': 20,       # 「弱」: 20-39点
        'range': 0,       # 「横」: 0-19点
    }
}


def calculate_trend_strength_v2(tf, state_data, all_states=None):
    """
    トレンド強度を計算（100点満点版）
    
    Args:
        tf: 対象時間足（'5m', '15m', '1H', '4H'）
        state_data: 当該時間足の状態データ
        all_states: 全タイムフレームの状態データ（多雲ボーナス計算用）
    
    Returns:
        dict: {
            'strength': str,           # 「極」「強」「中」「弱」「横」
            'score': int,              # 最終スコア（0-100点）
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
            return _return_range()
        
        cloud = clouds[0] if isinstance(clouds, list) else clouds
        
        angle = abs(cloud.get('angle', 0))
        thickness = abs(cloud.get('thickness', 0))
        distance_from_prev = cloud.get('distance_from_prev', 0)
        dauten = cloud.get('dauten', '')
        gc = cloud.get('gc', False)
        in_cloud = cloud.get('in_cloud', False)
        bos_count = cloud.get('bos_count', 0)
        
        # ============================================================
        # ステップ 2: 基本スコア計算（0-50点）
        # ============================================================
        base_config = TREND_SCORE_CONFIG['base']
        
        # 角度スコア
        angle_ratio = min(1.0, angle / base_config['angle_max'])
        angle_score = angle_ratio * base_config['angle_weight']
        
        # 厚みスコア
        thickness_ratio = min(1.0, thickness / base_config['thickness_max'])
        thickness_score = thickness_ratio * base_config['thickness_weight']
        
        base_score = angle_score + thickness_score
        
        # ============================================================
        # ステップ 3: ボーナス計算（0-50点以上）
        # ============================================================
        bonus_config = TREND_SCORE_CONFIG['bonus']
        bonus_score = 0
        bonus_breakdown = {}
        
        # 3-1. ダウ転換ボーナス
        if dauten in ['up', 'down']:
            bonus_score += bonus_config['dauten_confirmed']
            bonus_breakdown['dauten'] = bonus_config['dauten_confirmed']
        
        # 3-2. 雲整列ボーナス
        if all_states:
            align_score, align_detail = _calculate_cloud_alignment_bonus(
                tf, all_states, dauten, bonus_config
            )
            bonus_score += align_score
            bonus_breakdown.update(align_detail)
        
        # 3-3. 多雲ボーナス
        if all_states:
            multi_score, multi_detail = _calculate_multi_cloud_bonus(
                tf, all_states, dauten, bonus_config
            )
            bonus_score += multi_score
            bonus_breakdown.update(multi_detail)
        
        # 3-4. 距離レベルボーナス
        distance_score, distance_detail = _calculate_distance_bonus(
            distance_from_prev, thickness, bonus_config
        )
        bonus_score += distance_score
        bonus_breakdown.update(distance_detail)
        
        # 3-5. BOS継続ボーナス
        if bos_count >= 3:
            bonus_score += bonus_config['bos_count_3plus']
            bonus_breakdown['bos_3plus'] = bonus_config['bos_count_3plus']
        elif bos_count >= 1:
            bonus_score += bonus_config['bos_count_1_2']
            bonus_breakdown['bos_1_2'] = bonus_config['bos_count_1_2']
        
        # 3-6. GC/DC強度ボーナス
        if in_cloud and gc:
            bonus_score += bonus_config['in_cloud_gc_match']
            bonus_breakdown['gc_match'] = bonus_config['in_cloud_gc_match']
        
        # 3-7. パターン2: 近接同時交差ボーナス（新機能）
        if all_states:
            pattern2_score, pattern2_detail = _detect_proximity_cross_bonus(
                tf, state_data, all_states
            )
            if pattern2_score > 0:
                print(f'[PATTERN2] {tf}: +{pattern2_score}点 - {pattern2_detail}')
            bonus_score += pattern2_score
            bonus_breakdown.update(pattern2_detail)
        
        # 3-8. パターン3: 押し目/戻り目ボーナス（新機能）
        if all_states:
            pattern3_score, pattern3_detail = _detect_pullback_entry_bonus(
                tf, state_data, all_states
            )
            if pattern3_score > 0:
                print(f'[PATTERN3] {tf}: +{pattern3_score}点 - {pattern3_detail}')
            bonus_score += pattern3_score
            bonus_breakdown.update(pattern3_detail)
        
        # 3-9. 距離依存の上位足影響度（新機能）
        if all_states:
            influence_score, influence_detail = _calculate_upper_cloud_influence(
                tf, state_data, all_states
            )
            if influence_score > 0:
                print(f'[INFLUENCE] {tf}: +{influence_score}点 - {influence_detail}')
            bonus_score += influence_score
            bonus_breakdown.update(influence_detail)
        
        # ============================================================
        # ステップ 4: 減衰補正前のスコア
        # ============================================================
        raw_score = base_score + bonus_score
        
        # ============================================================
        # ステップ 5: 減衰補正（乗数）
        # ============================================================
        decay_config = TREND_SCORE_CONFIG['decay']
        decay_factor = 1.0
        decay_details = []
        
        # 距離が遠い場合
        distance_ratio = abs(distance_from_prev) / (thickness if thickness > 0 else 1) * 100
        if distance_ratio > 200:
            decay_factor *= decay_config['distance_far']
            decay_details.append(('distance_far', decay_config['distance_far']))
        
        # 逆方向の雲がある場合
        if all_states and _has_reverse_direction(tf, all_states, dauten):
            decay_factor *= decay_config['reverse_direction']
            decay_details.append(('reverse_direction', decay_config['reverse_direction']))
        
        # 価格が雲内でGC不一致の場合
        if in_cloud and not gc:
            decay_factor *= decay_config['in_cloud_gc_mismatch']
            decay_details.append(('gc_mismatch', decay_config['in_cloud_gc_mismatch']))
        
        # ============================================================
        # ステップ 6: 最終スコア（正規化）
        # ============================================================
        # 最大スコア = 基本50 + ボーナス50
        max_possible_score = 100
        normalized_score = min(100, (raw_score / max_possible_score) * 100)
        final_score = int(normalized_score * decay_factor)
        final_score = max(0, min(100, final_score))  # 0-100の範囲内
        
        # ============================================================
        # ステップ 7: 強度判定
        # ============================================================
        threshold = TREND_SCORE_CONFIG['threshold']
        
        if final_score >= threshold['extreme']:
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
        # ステップ 8: 結果を返す
        # ============================================================
        return {
            'strength': strength,
            'score': final_score,
            'breakdown': {
                'base_score': int(base_score),
                'bonus_score': int(bonus_score),
                'bonus_details': bonus_breakdown,
                'raw_score': int(raw_score),
                'decay_factor': round(decay_factor, 2),
                'decay_details': decay_details,
            },
            'details': {
                'angle': round(angle, 1),
                'thickness': round(thickness, 1),
                'dauten': dauten,
                'in_cloud': in_cloud,
                'bos_count': bos_count,
                'distance_ratio': round(distance_ratio, 1),
            }
        }
        
    except Exception as e:
        print(f'[ERROR] calculate_trend_strength_v2: {e}')
        import traceback
        traceback.print_exc()
        return _return_range()


def _return_range():
    """レンジを返す"""
    return {
        'strength': '横',
        'score': 0,
        'breakdown': {
            'base_score': 0,
            'bonus_score': 0,
            'bonus_details': {},
            'raw_score': 0,
            'decay_factor': 1.0,
            'decay_details': [],
        },
        'details': {}
    }


def _calculate_cloud_alignment_bonus(tf, all_states, dauten, bonus_config):
    """雲整列ボーナスを計算"""
    bonus = 0
    details = {}
    
    # 全TFのダウ転換方向を確認
    aligned_count = 0
    for check_tf in ['5m', '15m', '1H', '4H']:
        check_state = all_states.get(check_tf, {})
        check_clouds = check_state.get('clouds', [])
        if check_clouds:
            check_cloud = check_clouds[0] if isinstance(check_clouds, list) else check_clouds
            check_dauten = check_cloud.get('dauten', '')
            if check_dauten == dauten:
                aligned_count += 1
    
    # 整列度合いで加点
    if aligned_count == 4:
        bonus += bonus_config['cloud_align_perfect']
        details['cloud_align_perfect'] = bonus_config['cloud_align_perfect']
    elif aligned_count == 3:
        bonus += bonus_config['cloud_align_3tf']
        details['cloud_align_3tf'] = bonus_config['cloud_align_3tf']
    elif aligned_count == 2:
        bonus += bonus_config['cloud_align_2tf']
        details['cloud_align_2tf'] = bonus_config['cloud_align_2tf']
    
    # 整列方向がダウ転換と一致
    if aligned_count >= 2 and dauten:
        bonus += bonus_config['cloud_align_match']
        details['cloud_align_match'] = bonus_config['cloud_align_match']
    
    return bonus, details


def _calculate_multi_cloud_bonus(tf, all_states, dauten, bonus_config):
    """多雲ボーナスを計算"""
    bonus = 0
    details = {}
    
    tf_order = ['5m', '15m', '1H', '4H']
    if tf not in tf_order:
        return 0, {}
    
    current_index = tf_order.index(tf)
    
    # 隣接TFをチェック
    for adj_index in [current_index - 1, current_index + 1]:
        if 0 <= adj_index < len(tf_order):
            adj_tf = tf_order[adj_index]
            adj_state = all_states.get(adj_tf, {})
            adj_clouds = adj_state.get('clouds', [])
            
            if adj_clouds:
                adj_cloud = adj_clouds[0] if isinstance(adj_clouds, list) else adj_clouds
                adj_dauten = adj_cloud.get('dauten', '')
                adj_distance = adj_cloud.get('distance_from_prev', 0)
                adj_thickness = adj_cloud.get('thickness', 1)
                
                # 方向が同じかチェック
                if (dauten == 'up' and adj_dauten == 'up') or \
                   (dauten == 'down' and adj_dauten == 'down'):
                    
                    # 距離レベルを取得
                    distance_ratio = abs(adj_distance) / (abs(adj_thickness) if adj_thickness != 0 else 1) * 100
                    
                    if distance_ratio < 100:  # 近い場合のみ
                        step_diff = abs(adj_index - current_index)
                        if step_diff == 1:
                            bonus += bonus_config['multi_cloud_adjacent']
                            details['multi_cloud_adjacent'] = bonus_config['multi_cloud_adjacent']
                        elif step_diff == 2:
                            bonus += bonus_config['multi_cloud_1step']
                            details['multi_cloud_1step'] = bonus_config['multi_cloud_1step']
                        else:
                            bonus += bonus_config['multi_cloud_2step']
                            details['multi_cloud_2step'] = bonus_config['multi_cloud_2step']
    
    return bonus, details


def _calculate_distance_bonus(distance_from_prev, thickness, bonus_config):
    """距離レベルボーナスを計算"""
    bonus = 0
    details = {}
    
    if thickness == 0 or thickness is None:
        return 0, {}
    
    distance_ratio = abs(distance_from_prev) / abs(thickness) * 100
    
    if distance_ratio < 50:
        bonus = bonus_config['distance_very_close']
        details['distance_very_close'] = bonus
    elif distance_ratio < 100:
        bonus = bonus_config['distance_close']
        details['distance_close'] = bonus
    
    return bonus, details


def _has_reverse_direction(tf, all_states, dauten):
    """逆方向の雲が存在するかチェック"""
    for check_tf in ['5m', '15m', '1H', '4H']:
        if check_tf == tf:
            continue
        check_state = all_states.get(check_tf, {})
        check_clouds = check_state.get('clouds', [])
        if check_clouds:
            check_cloud = check_clouds[0] if isinstance(check_clouds, list) else check_clouds
            check_dauten = check_cloud.get('dauten', '')
            if (dauten == 'up' and check_dauten == 'down') or \
               (dauten == 'down' and check_dauten == 'up'):
                return True
    return False


# ============================================================
# 【新機能】パターン2&3実装
# ============================================================

def _get_ma1(cloud_data):
    """
    MA1（雲の先端）を取得
    GCの場合は上側、DCの場合は下側
    """
    gc = cloud_data.get('gc', False)
    top_price = cloud_data.get('topPrice', 0)
    bottom_price = cloud_data.get('bottomPrice', 0)
    
    if gc:
        return top_price  # 上側
    else:
        return bottom_price  # 下側


def _calculate_ma1_distance(cloud1, cloud2):
    """2つの雲のMA1間距離を計算（pips）"""
    ma1_1 = _get_ma1(cloud1)
    ma1_2 = _get_ma1(cloud2)
    return abs(ma1_1 - ma1_2) * 100  # pips換算（仮定：1単位=100pips）


def _detect_proximity_cross_bonus(tf, state_data, all_states):
    """
    パターン2: 近接同時交差ボーナス
    
    条件:
    - 15m-1H: MA1距離20pips以内、時間差300分以内
    - 1H-4H: MA1距離40pips以内、時間差1200分以内
    - 角度30°以上、厚み10pips以上、同方向
    """
    bonus = 0
    details = {}
    
    clouds = state_data.get('clouds', [])
    if not clouds:
        return 0, {}
    cloud = clouds[0] if isinstance(clouds, list) else clouds
    
    angle = abs(cloud.get('angle', 0))
    thickness = abs(cloud.get('thickness', 0))
    dauten = cloud.get('dauten', '')
    cross_time = cloud.get('cross_start_time', 0)
    
    # 基本条件チェック
    if angle < 30 or thickness < 10 or dauten not in ['up', 'down']:
        return 0, {}
    
    # === 15m-1H 近接チェック ===
    if tf == '15m':
        state_1h = all_states.get('1H', {})
        clouds_1h = state_1h.get('clouds', [])
        if clouds_1h:
            cloud_1h = clouds_1h[0] if isinstance(clouds_1h, list) else clouds_1h
            
            # MA1距離
            distance = _calculate_ma1_distance(cloud, cloud_1h)
            
            # 時間差
            cross_time_1h = cloud_1h.get('cross_start_time', 0)
            time_diff_sec = abs(cross_time - cross_time_1h)
            time_diff_min = time_diff_sec / 60 if cross_time and cross_time_1h else 9999
            
            # 1H条件
            angle_1h = abs(cloud_1h.get('angle', 0))
            thickness_1h = abs(cloud_1h.get('thickness', 0))
            dauten_1h = cloud_1h.get('dauten', '')
            
            if (distance <= 20 and
                time_diff_min <= 300 and
                angle_1h >= 30 and
                thickness_1h >= 10 and
                dauten == dauten_1h):
                bonus += 25
                details['pattern2_15m_1h'] = 25
    
    # === 1H評価時: 15m-1H + 1H-4H ===
    elif tf == '1H':
        # 15m-1H近接
        state_15m = all_states.get('15m', {})
        clouds_15m = state_15m.get('clouds', [])
        if clouds_15m:
            cloud_15m = clouds_15m[0] if isinstance(clouds_15m, list) else clouds_15m
            distance = _calculate_ma1_distance(cloud, cloud_15m)
            cross_time_15m = cloud_15m.get('cross_start_time', 0)
            time_diff_min = abs(cross_time - cross_time_15m) / 60 if cross_time and cross_time_15m else 9999
            
            angle_15m = abs(cloud_15m.get('angle', 0))
            thickness_15m = abs(cloud_15m.get('thickness', 0))
            dauten_15m = cloud_15m.get('dauten', '')
            
            if (distance <= 20 and
                time_diff_min <= 300 and
                angle_15m >= 30 and
                thickness_15m >= 10 and
                dauten == dauten_15m):
                bonus += 25
                details['pattern2_15m_1h'] = 25
        
        # 1H-4H近接
        state_4h = all_states.get('4H', {})
        clouds_4h = state_4h.get('clouds', [])
        if clouds_4h:
            cloud_4h = clouds_4h[0] if isinstance(clouds_4h, list) else clouds_4h
            distance = _calculate_ma1_distance(cloud, cloud_4h)
            cross_time_4h = cloud_4h.get('cross_start_time', 0)
            time_diff_min = abs(cross_time - cross_time_4h) / 60 if cross_time and cross_time_4h else 9999
            
            angle_4h = abs(cloud_4h.get('angle', 0))
            thickness_4h = abs(cloud_4h.get('thickness', 0))
            dauten_4h = cloud_4h.get('dauten', '')
            
            if (distance <= 40 and
                time_diff_min <= 1200 and
                angle_4h >= 30 and
                thickness_4h >= 10 and
                dauten == dauten_4h):
                bonus += 35
                details['pattern2_1h_4h'] = 35
    
    # === 4H-1H 近接チェック ===
    elif tf == '4H':
        state_1h = all_states.get('1H', {})
        clouds_1h = state_1h.get('clouds', [])
        if clouds_1h:
            cloud_1h = clouds_1h[0] if isinstance(clouds_1h, list) else clouds_1h
            distance = _calculate_ma1_distance(cloud, cloud_1h)
            cross_time_1h = cloud_1h.get('cross_start_time', 0)
            time_diff_min = abs(cross_time - cross_time_1h) / 60 if cross_time and cross_time_1h else 9999
            
            angle_1h = abs(cloud_1h.get('angle', 0))
            thickness_1h = abs(cloud_1h.get('thickness', 0))
            dauten_1h = cloud_1h.get('dauten', '')
            
            if (distance <= 40 and
                time_diff_min <= 1200 and
                angle_1h >= 30 and
                thickness_1h >= 10 and
                dauten == dauten_1h):
                bonus += 35
                details['pattern2_1h_4h'] = 35
    
    return bonus, details


def _detect_pullback_entry_bonus(tf, state_data, all_states):
    """
    パターン3: 押し目/戻り目ボーナス
    
    条件:
    - 上位足がトレンド中
    - 短期雲が上位雲のMA1に30pips以内
    - 短期足が同方向転換
    - 上位足の雲交差から20バー以内 = 初回押し目
    """
    bonus = 0
    details = {}
    
    clouds = state_data.get('clouds', [])
    if not clouds:
        return 0, {}
    cloud = clouds[0] if isinstance(clouds, list) else clouds
    
    dauten = cloud.get('dauten', '')
    angle = abs(cloud.get('angle', 0))
    thickness = abs(cloud.get('thickness', 0))
    current_time = state_data.get('timestamp', 0)
    
    if dauten not in ['up', 'down'] or angle < 30 or thickness < 10:
        return 0, {}
    
    # === 15m → 1H押し目 ===
    if tf == '15m':
        state_upper = all_states.get('1H', {})
        clouds_upper = state_upper.get('clouds', [])
        if clouds_upper:
            cloud_upper = clouds_upper[0] if isinstance(clouds_upper, list) else clouds_upper
            dauten_upper = cloud_upper.get('dauten', '')
            
            if dauten == dauten_upper:
                # MA1距離
                distance = _calculate_ma1_distance(cloud, cloud_upper)
                
                if distance <= 30:
                    bonus += 20
                    details['pattern3_pullback'] = 20
                    
                    # 初回押し目判定（雲交差からの経過時間）
                    cross_time_upper = cloud_upper.get('cross_start_time', 0)
                    if current_time and cross_time_upper:
                        elapsed_sec = current_time - cross_time_upper
                        elapsed_bars = elapsed_sec / 3600  # 1H = 1バー
                        
                        if elapsed_bars <= 20:
                            bonus += 15
                            details['pattern3_first_pullback'] = 15
    
    # === 1H → 4H押し目 ===
    elif tf == '1H':
        state_upper = all_states.get('4H', {})
        clouds_upper = state_upper.get('clouds', [])
        if clouds_upper:
            cloud_upper = clouds_upper[0] if isinstance(clouds_upper, list) else clouds_upper
            dauten_upper = cloud_upper.get('dauten', '')
            
            if dauten == dauten_upper:
                distance = _calculate_ma1_distance(cloud, cloud_upper)
                
                if distance <= 30:
                    bonus += 20
                    details['pattern3_pullback'] = 20
                    
                    cross_time_upper = cloud_upper.get('cross_start_time', 0)
                    if current_time and cross_time_upper:
                        elapsed_sec = current_time - cross_time_upper
                        elapsed_bars = elapsed_sec / (4 * 3600)  # 4H = 1バー
                        
                        if elapsed_bars <= 20:
                            bonus += 15
                            details['pattern3_first_pullback'] = 15
    
    return bonus, details


def _calculate_upper_cloud_influence(tf, state_data, all_states):
    """
    距離依存の上位足影響度
    
    短期雲が上位雲に近いほど、上位雲の角度・厚みが評価に影響
    """
    bonus = 0
    details = {}
    
    clouds = state_data.get('clouds', [])
    if not clouds:
        return 0, {}
    cloud = clouds[0] if isinstance(clouds, list) else clouds
    
    # === 15m → 1H影響 ===
    if tf == '15m':
        state_upper = all_states.get('1H', {})
        clouds_upper = state_upper.get('clouds', [])
        if clouds_upper:
            cloud_upper = clouds_upper[0] if isinstance(clouds_upper, list) else clouds_upper
            distance = _calculate_ma1_distance(cloud, cloud_upper)
            
            # 影響度計算
            if distance <= 30:
                influence = 1.5
            elif distance <= 100:
                influence = 1.0
            elif distance <= 200:
                influence = 0.6
            else:
                influence = 0.3
            
            if influence > 0.5:
                angle_upper = abs(cloud_upper.get('angle', 0))
                thickness_upper = abs(cloud_upper.get('thickness', 0))
                
                angle_bonus = (angle_upper / 45) * 5 * influence
                thickness_bonus = (thickness_upper / 100) * 5 * influence
                
                upper_bonus = int(angle_bonus + thickness_bonus)
                if upper_bonus > 0:
                    bonus += upper_bonus
                    details['upper_1h_influence'] = upper_bonus
    
    # === 1H → 4H影響 ===
    elif tf == '1H':
        state_upper = all_states.get('4H', {})
        clouds_upper = state_upper.get('clouds', [])
        if clouds_upper:
            cloud_upper = clouds_upper[0] if isinstance(clouds_upper, list) else clouds_upper
            distance = _calculate_ma1_distance(cloud, cloud_upper)
            
            if distance <= 30:
                influence = 1.5
            elif distance <= 100:
                influence = 1.0
            elif distance <= 200:
                influence = 0.6
            else:
                influence = 0.3
            
            if influence > 0.5:
                angle_upper = abs(cloud_upper.get('angle', 0))
                thickness_upper = abs(cloud_upper.get('thickness', 0))
                
                angle_bonus = (angle_upper / 45) * 5 * influence
                thickness_bonus = (thickness_upper / 100) * 5 * influence
                
                upper_bonus = int(angle_bonus + thickness_bonus)
                if upper_bonus > 0:
                    bonus += upper_bonus
                    details['upper_4h_influence'] = upper_bonus
    
    return bonus, details


def _has_reverse_direction(tf, all_states, dauten):
    """逆方向の雲が存在するかチェック"""
    for check_tf in ['5m', '15m', '1H', '4H']:
        if check_tf == tf:
            continue
        check_state = all_states.get(check_tf, {})
        check_clouds = check_state.get('clouds', [])
        if check_clouds:
            check_cloud = check_clouds[0] if isinstance(check_clouds, list) else check_clouds
            check_dauten = check_cloud.get('dauten', '')
            if (dauten == 'up' and check_dauten == 'down') or \
               (dauten == 'down' and check_dauten == 'up'):
                return True
    return False


# ============================================================
# 【テスト】計算例
# ============================================================
if __name__ == '__main__':
    # テストデータ
    test_state = {
        'clouds': [{
            'angle': 40,
            'thickness': 80,
            'distance_from_prev': 50,
            'dauten': 'up',
            'gc': True,
            'in_cloud': False,
            'bos_count': 2,
        }]
    }
    
    test_all_states = {
        '5m': {
            'clouds': [{
                'dauten': 'up',
                'distance_from_prev': 30,
                'thickness': 40,
            }]
        },
        '15m': {
            'clouds': [{
                'dauten': 'up',
                'distance_from_prev': 40,
                'thickness': 50,
            }]
        },
        '1H': {
            'clouds': [{
                'dauten': 'up',
                'distance_from_prev': 50,
                'thickness': 80,
            }]
        },
        '4H': {
            'clouds': [{
                'dauten': 'up',
                'distance_from_prev': 100,
                'thickness': 150,
            }]
        },
    }
    
    result = calculate_trend_strength_v2('1H', test_state, test_all_states)
    
    print("=" * 60)
    print("トレンド強度計算結果（テスト）")
    print("=" * 60)
    print(f"強度: {result['strength']}")
    print(f"スコア: {result['score']}/100")
    print()
    print("スコア内訳:")
    breakdown = result['breakdown']
    print(f"  基本スコア: {breakdown['base_score']}")
    print(f"  ボーナス: {breakdown['bonus_score']}")
    print(f"    - {breakdown['bonus_details']}")
    print(f"  補正前: {breakdown['raw_score']}")
    print(f"  減衰率: {breakdown['decay_factor']}")
    print(f"    - {breakdown['decay_details']}")
    print()
    print("詳細情報:")
    for k, v in result['details'].items():
        print(f"  {k}: {v}")
