"""
ichimoku_utils.py

イチモク・トレンド判定・ルール評価のビジネスロジック専用モジュール
render_server.py から分離して保守性を向上
"""

import sqlite3
import os
import pytz
import json
from datetime import datetime


# データベースパス（render_server.py と同じ）
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PERSISTENT_DIR = os.getenv('PERSISTENT_STORAGE_PATH', BASE_DIR)
DB_PATH = os.path.join(PERSISTENT_DIR, 'webhook_data.db')


# ============================================================
# 【設定】トレンド強度計算の配点マスター（100点満点版）
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
        'dauten_confirmed': 20,   # ダウ転換確認時: +20点（15→20に増加）
        
        # 雲整列（Perfect Order等）
        'cloud_align_perfect': 20,    # 4本全て整列: +20点（15→20に増加）
        'cloud_align_3tf': 12,        # 3本整列: +12点（10→12に増加）
        'cloud_align_2tf': 6,         # 2本整列: +6点（5→6に増加）
        'cloud_align_match': 5,       # 整列方向 = ダウ転換方向一致: +5点
        
        # 多雲ボーナス（隣接TF同方向かつ距離近い）
        'multi_cloud_adjacent': 12,   # 隣接（1段階差）: +12点（10→12に増加）
        'multi_cloud_1step': 6,       # 1段階離れ（2段階差）: +6点（5→6に増加）
        'multi_cloud_2step': 3,       # 2段階以上: +3点（2→3に増加）
        
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
        'extreme': 70,    # 「極」: 70点以上（80→70に引き下げ）
        'strong': 50,     # 「強」: 50-69点（60→50に引き下げ）
        'medium': 35,     # 「中」: 35-49点（40→35に引き下げ）
        'weak': 18,       # 「弱」: 18-34点（20→18に引き下げ）
        'range': 0,       # 「横」: 0-17点
    }
}


def calculate_trend(cloud_data, config):
    """
    トレンドを判定する
    
    Args:
        cloud_data: 各時間足の雲データ（dict）
                   - gc: True/False
                   - angle: 雲角度（度）
                   - thickness: 雲厚み（Pips）
                   - dauten: "up"/"down"
        config: トレンド判定設定（dict）
                - use_angle: True/False
                - angle_threshold: 閾値（度）
                - use_thickness: True/False
                - thickness_threshold: 閾値（Pips）
                - use_dauten: True/False
    
    Returns:
        str: "↗上昇", "↘下降", "レンジ"
    """
    if not cloud_data or not config:
        return "レンジ"
    
    conditions = []  # 各条件の方向を記録（1=上昇, -1=下降）
    
    # 雲角度チェック
    if config.get('use_angle', False):
        angle = cloud_data.get('angle', 0)
        threshold = config.get('angle_threshold', 20)
        if abs(angle) >= threshold:
            # 角度の符号で方向判定（正=上昇、負=下降）
            direction = 1 if angle > 0 else -1
            conditions.append(direction)
        else:
            return "レンジ"  # 閾値未達
    
    # 雲厚みチェック
    if config.get('use_thickness', False):
        thickness = cloud_data.get('thickness', 0)
        threshold = config.get('thickness_threshold', 5)
        gc = cloud_data.get('gc', False)
        if abs(thickness) >= threshold:
            # GC/DCで方向判定（GC=上昇、DC=下降）
            direction = 1 if gc else -1
            conditions.append(direction)
        else:
            return "レンジ"  # 閾値未達
    
    # ダウ転チェック
    if config.get('use_dauten', False):
        dauten = cloud_data.get('dauten', '')
        if dauten == 'up':
            conditions.append(1)
        elif dauten == 'down':
            conditions.append(-1)
        else:
            return "レンジ"  # ダウ転なし
    
    # 有効な条件がない場合
    if not conditions:
        return "レンジ"
    
    # 全ての条件が同じ方向か確認
    if all(c == 1 for c in conditions):
        return "↗上昇"
    elif all(c == -1 for c in conditions):
        return "↘下降"
    else:
        return "レンジ"  # 方向不一致


def is_fx_market_open():
    """
    FX市場の営業時間を判定（データ受信ベース）
    最後のJSON受信から1時間以内なら営業中と判定
    """
    try:
        # 最後の受信時刻を取得
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('SELECT last_receive_time FROM market_status WHERE id = 1')
        row = c.fetchone()
        conn.close()
        
        if not row or not row[0]:
            return False  # 未受信
        
        # 時刻をパース
        last_time = datetime.fromisoformat(row[0])
        utc_now = datetime.now(pytz.UTC)
        
        # 1時間以内受信で営業中
        time_diff = (utc_now - last_time).total_seconds()
        return time_diff <= 3600  # 1時間 = 3600秒
        
    except Exception as e:
        print(f'[ERROR] is_fx_market_open check failed: {e}')
        return False  # エラー時は休場


def _get_nth_weekday(year, month, weekday, n):
    """
    指定された年月の第n番目の曜日を取得
    weekday: 0=月, 1=火, ..., 6=日
    n: 第n番目
    """
    first_day = datetime(year, month, 1)
    first_weekday = first_day.weekday()

    # 第1日曜日までの日数
    days_to_first = (weekday - first_weekday) % 7

    # 第n日曜日
    target_date = 1 + days_to_first + (n - 1) * 7

    return target_date


# ========== ルール評価ヘルパー関数 ==========

def _find_cloud_field(state, label, field):
    """雲データから指定フィールドを検索"""
    try:
        clouds = state.get('clouds', [])
        # helper: normalize label to minutes if possible
        def _tf_to_minutes(s):
            try:
                if s is None:
                    return None
                ss = str(s).strip().lower()
                if ss.isdigit():
                    return int(ss)
                # endswith m (minutes)
                if ss.endswith('m'):
                    return int(ss[:-1])
                # endswith h (hours)
                if ss.endswith('h'):
                    return int(ss[:-1]) * 60
                # contains 'min'
                if 'min' in ss:
                    num = ''.join([c for c in ss if c.isdigit()])
                    return int(num) if num else None
                # fallback: try to parse digits
                digits = ''.join([c for c in ss if c.isdigit()])
                if digits:
                    return int(digits)
            except Exception:
                return None
            return None

        req_min = _tf_to_minutes(label)
        for c in clouds:
            c_label = c.get('label')
            # exact match first
            if str(c_label) == str(label):
                val = c.get(field)
                # Special handling: if field is 'gc' and not present in cloud object,
                # default to False (DC) to match frontend display behavior
                if field == 'gc' and val is None and field not in c:
                    return False  # Default to False/DC when gc field is missing
                return val
            # try normalized minutes match
            try:
                cmin = _tf_to_minutes(c_label)
                if req_min is not None and cmin is not None and req_min == cmin:
                    val = c.get(field)
                    if field == 'gc' and val is None and field not in c:
                        return False  # Default to False/DC when gc field is missing
                    return val
            except Exception:
                pass
    except Exception:
        pass
    return None


def _parse_time_to_ms(val):
    """時刻をミリ秒に変換"""
    try:
        if val is None:
            return None
        if isinstance(val, (int, float)):
            return int(val)
        s = str(val).strip()
        if s.isdigit():
            return int(s)
        # try YY/MM/DD/HH:MM like '25/10/31/21:35'
        parts = s.split('/')
        if len(parts) >= 4:
            yy = int(parts[0]); mm = int(parts[1]); dd = int(parts[2]); timepart = parts[3]
            hh, mi = 0, 0
            if ':' in timepart:
                hp = timepart.split(':'); hh = int(hp[0]); mi = int(hp[1])
            else:
                hh = int(timepart)
            year = 2000 + yy if yy < 100 else yy
            dt = datetime(year, mm, dd, hh, mi)
            return int(dt.timestamp() * 1000)
    except Exception:
        return None
    return None


def _normalize_actual(field, val):
    """フィールド値を正規化（比較用）"""
    try:
        if val is None:
            return None
        
        # gc: boolean を表示文字列に変換
        if field in ('gc',):
            if isinstance(val, bool):
                return 'GC' if val else 'DC'
            s = str(val).strip().lower()
            if s in ('true','1','yes','y','gc','▲gc'):
                return 'GC'
            if s in ('false','0','no','n','dc','▼dc'):
                return 'DC'
            return 'GC' if s else 'DC'

        # dauten: 正規化
        if field in ('dauten',):
            s = str(val).strip().lower()
            if '▲' in s or 'up' in s or s == '上' or s == '上昇':
                return '上昇'
            if '▼' in s or 'down' in s or s == '下' or s == '下降':
                return '下降'
            return s

        # bos_count: そのまま
        if field in ('bos_count',):
            return val

        # 数値フィールド
        if field in ('distance_from_prev','distance_from_price','angle','thickness'):
            try:
                return float(val)
            except Exception:
                return val

        return val
    except Exception:
        return val


def _compare_values(a, op, b):
    """値を比較（演算子対応）"""
    try:
        if a is None:
            return False
        
        # bを適切な型に変換
        if isinstance(b, str):
            b_lower = b.strip().lower()
            if b_lower in ('true','false'):
                b_val = (b_lower == 'true')
            elif b_lower in ('gc','▲gc','ゴールデンクロス','golden','goldencross'):
                b_val = 'GC'
            elif b_lower in ('dc','▼dc','デッドクロス','dead','deadcross'):
                b_val = 'DC'
            elif b_lower in ('up','▲','▲dow','上','上昇','upward'):
                b_val = '上昇'
            elif b_lower in ('down','▼','▼dow','下','下降','downward'):
                b_val = '下降'
            else:
                try:
                    b_val = float(b)
                except Exception:
                    b_val = b
        else:
            b_val = b

        # aをb_valの型に合わせる
        if isinstance(b_val, (int, float)):
            try:
                a_val = float(a)
            except Exception:
                return False
        elif isinstance(b_val, bool):
            try:
                if isinstance(a, bool):
                    a_val = a
                elif isinstance(a, (int, float)):
                    a_val = bool(a)
                else:
                    sa = str(a).strip().lower()
                    a_val = sa in ('true','1','yes','y')
            except Exception:
                a_val = False
        else:
            # 文字列比較（大文字小文字無視）
            if isinstance(a, str):
                a_val = a.strip().upper()
                if isinstance(b_val, str):
                    b_val = b_val.strip().upper()
            else:
                a_val = a

        if op == '==':
            return a_val == b_val
        if op == '!=':
            return a_val != b_val
        if op == '>':
            return a_val > b_val
        if op == '<':
            return a_val < b_val
        if op == '>=':
            return a_val >= b_val
        if op == '<=':
            return a_val <= b_val
    except Exception:
        return False
    return False


def _evaluate_rule_match(rule, cloud_data):
    """ルールが現在のデータにマッチするか評価（簡易版）
    
    本番の _evaluate_rules_with_db_state と同じロジックを使用
    """
    try:
        direction = None
        all_matched = True
        condition_directions = []
        
        # 条件をチェック
        conditions = rule.get('conditions', [])
        if conditions:
            for cond in conditions:
                tf_label = cond.get('timeframe') or cond.get('label')
                field = cond.get('field')
                value = cond.get('value')
                
                tf_data = cloud_data.get(tf_label, {})
                found_value = tf_data.get(field)
                
                condition_met = False
                
                # 存在チェック（valueが空の場合）
                if value is None or value == '':
                    if field == 'gc':
                        condition_met = found_value is not None
                    elif field == 'dauten':
                        condition_met = found_value in ['up', 'down']
                    elif field == 'bos_count':
                        try:
                            bos_num = int(found_value) if found_value else 0
                            condition_met = bos_num > 0
                        except:
                            condition_met = False
                    else:
                        condition_met = found_value is not None and found_value != ''
                else:
                    condition_met = found_value == value
                
                if not condition_met:
                    all_matched = False
                    break
                
                # 各フィールドから方向を判定
                cond_direction = None
                if field == 'dauten':
                    if found_value == 'up':
                        cond_direction = 'up'
                    elif found_value == 'down':
                        cond_direction = 'down'
                elif field == 'gc':
                    if found_value is True:
                        cond_direction = 'up'
                    elif found_value is False:
                        cond_direction = 'down'
                elif field == 'bos_count':
                    # bos_countの方向はdautenから取得
                    dauten_for_bos = tf_data.get('dauten')
                    if dauten_for_bos == 'up':
                        cond_direction = 'up'
                    elif dauten_for_bos == 'down':
                        cond_direction = 'down'
                
                condition_directions.append(cond_direction)
        
        if not all_matched:
            return None
        
        # 複数条件の場合、方向の整合性をチェック
        if len(condition_directions) > 1:
            valid_directions = [d for d in condition_directions if d is not None]
            if len(valid_directions) > 1 and len(set(valid_directions)) > 1:
                # 方向が一致しない
                return None
        
        # 雲整列条件をチェック（cloud_orderを使用）
        cloud_align = rule.get('cloudAlign', {})
        
        # alignment_is_active の判定（本番側と同じロジック）
        alignment_is_active = False
        tfs_check = cloud_align.get('timeframes') or cloud_align.get('tfs', [])
        if cloud_align.get('allTimeframes') or (tfs_check and len(tfs_check) > 0):
            alignment_is_active = True
        
        alignment_direction = None
        
        if alignment_is_active and all_matched:
            timeframes = tfs_check if tfs_check else ['5m', '15m', '1H', '4H']
            if cloud_align.get('allTimeframes') and not tfs_check:
                timeframes = ['5m', '15m', '1H', '4H']
            
            # cloud_dataから cloud_order を取得
            cloud_order = cloud_data.get('__cloud_order__')
            
            if cloud_order:
                # cloud_order は '5m,15m,1H,4H,価格' のような文字列
                cloud_order_list = [x.strip() for x in cloud_order.split(',')]
                
                # 「価格」を除外してTFのみ抽出
                cloud_order_tfs = [x for x in cloud_order_list if x in ['5m', '15m', '1H', '4H']]
                
                # 選択されたTFのみを抽出（順序を保持）
                selected_order = [x for x in cloud_order_tfs if x in timeframes]
                
                # 期待する昇順と降順
                expected_asc = timeframes  # ['5m', '15m', '1H', '4H']
                expected_desc = list(reversed(timeframes))  # ['4H', '1H', '15m', '5m']
                
                # 整列判定
                is_aligned = (selected_order == expected_asc or selected_order == expected_desc)
                
                if is_aligned:
                    # 整列方向を判定
                    if selected_order == expected_asc:
                        alignment_direction = 'up'
                    else:
                        alignment_direction = 'down'
                    direction = alignment_direction
                else:
                    return None
            else:
                # cloud_orderがない場合は不一致
                return None
        else:
            # 雲整列条件がない場合、条件から方向を判定
            valid_directions = [d for d in condition_directions if d is not None]
            if valid_directions:
                direction = valid_directions[0]
        
        return direction
    except Exception as e:
        print(f'[_evaluate_rule_match] Error: {e}')
        import traceback
        traceback.print_exc()
        return None


# ========== トレンド強度計算（Phase 3） ==========

def get_distance_level(distance, thickness):
    """距離レベルを判定（4段階）
    
    Args:
        distance: 前雲からの距離（Pips）
        thickness: 雲の厚み（Pips）
    
    Returns:
        tuple: (level_name, points)
            - level_name: "非常に近い", "近い", "普通", "遠い"
            - points: 3, 2, 1, 0
    """
    if thickness == 0 or thickness is None:
        return ("遠い", 0)
    
    distance_ratio = abs(distance) / abs(thickness) * 100
    
    if distance_ratio < 50:
        return ("非常に近い", 3)
    elif distance_ratio < 100:
        return ("近い", 2)
    elif distance_ratio < 200:
        return ("普通", 1)
    else:
        return ("遠い", 0)


def get_multi_cloud_bonus(tf, all_states, direction):
    """多雲ボーナスを計算
    
    Args:
        tf: 対象時間足（'5m', '15m', '1H', '4H'）
        all_states: 全タイムフレームの状態データ
        direction: 現在のトレンド方向（'up' or 'down'）
    
    Returns:
        int: ボーナスポイント（0, 10, 20, 40）
    """
    # タイムフレームの順序
    tf_order = ['5m', '15m', '1H', '4H']
    
    if tf not in tf_order:
        return 0
    
    current_index = tf_order.index(tf)
    bonus = 0
    
    # 隣接する時間足をチェック
    adjacent_tfs = []
    if current_index > 0:
        adjacent_tfs.append((tf_order[current_index - 1], current_index - 1))  # 下位足
    if current_index < len(tf_order) - 1:
        adjacent_tfs.append((tf_order[current_index + 1], current_index + 1))  # 上位足
    
    for adj_tf, adj_index in adjacent_tfs:
        adj_state = all_states.get(adj_tf, {})
        adj_clouds = adj_state.get('clouds', [])
        
        if not adj_clouds:
            continue
        
        adj_cloud = adj_clouds[0] if isinstance(adj_clouds, list) else adj_clouds
        adj_direction = adj_cloud.get('dauten', '')
        adj_distance = adj_cloud.get('distance_from_prev', 0)
        adj_thickness = adj_cloud.get('thickness', 1)
        
        # 方向が同じかチェック
        is_same_direction = (
            (direction == 'up' and adj_direction == 'up') or
            (direction == 'down' and adj_direction == 'down')
        )
        
        if is_same_direction:
            # 距離レベルを取得
            distance_level, _ = get_distance_level(adj_distance, adj_thickness)
            
            # 距離が近い場合のみボーナス
            if distance_level in ["非常に近い", "近い"]:
                # 隣接（1段階差）
                if abs(adj_index - current_index) == 1:
                    bonus = max(bonus, 40)
                # 1段階離れ（2段階差）
                elif abs(adj_index - current_index) == 2:
                    bonus = max(bonus, 20)
                # 2段階以上離れ
                else:
                    bonus = max(bonus, 10)
    
    return bonus


def apply_decay_correction(score, distance_level_name, has_reverse_direction):
    """減衰補正を適用
    
    Args:
        score: 基本スコア
        distance_level_name: 距離レベル名（"遠い", "非常に近い"等）
        has_reverse_direction: 逆方向の雲が存在するか
    
    Returns:
        float: 補正後のスコア
    """
    corrected_score = score
    
    # 遠い場合: ×0.7
    if distance_level_name == "遠い":
        corrected_score *= 0.7
    
    # 逆方向がある場合: ×0.5
    if has_reverse_direction:
        corrected_score *= 0.5
    
    return corrected_score


def calculate_trend_strength(tf, state_data, all_states=None):
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
            return _return_range_result()
        
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
            align_score, align_detail = _calculate_cloud_alignment_bonus_v2(
                tf, all_states, dauten, bonus_config
            )
            bonus_score += align_score
            bonus_breakdown.update(align_detail)
        
        # 3-3. 多雲ボーナス
        if all_states:
            multi_score, multi_detail = _calculate_multi_cloud_bonus_v2(
                tf, all_states, dauten, bonus_config
            )
            bonus_score += multi_score
            bonus_breakdown.update(multi_detail)
        
        # 3-4. 距離レベルボーナス
        distance_score, distance_detail = _calculate_distance_bonus_v2(
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
        if all_states and _has_reverse_direction_v2(tf, all_states, dauten):
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
        print(f'[ERROR] calculate_trend_strength: {e}')
        import traceback
        traceback.print_exc()
        return _return_range_result()


def _return_range_result():
    """レンジ結果を返す"""
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


def _calculate_cloud_alignment_bonus_v2(tf, all_states, dauten, bonus_config):
    """雲整列ボーナスを計算（v2）"""
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


def _calculate_multi_cloud_bonus_v2(tf, all_states, dauten, bonus_config):
    """多雲ボーナスを計算（v2）"""
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


def _calculate_distance_bonus_v2(distance_from_prev, thickness, bonus_config):
    """距離レベルボーナスを計算（v2）"""
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


def _has_reverse_direction_v2(tf, all_states, dauten):
    """逆方向の雲が存在するかチェック（v2）"""
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


