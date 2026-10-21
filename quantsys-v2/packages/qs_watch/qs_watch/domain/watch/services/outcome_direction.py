"""预判方向推断（2026-10-20 P3 预判验证闭环）

纯函数：一条触发当时「市场被预判往哪走」。写进 outcome 行后不再变——
命中率统计的分母分子都以这个快照为准（事后改口径 = 篡改历史）。

推断顺序：
  1) intent 优先：exit_* → down（预判跌/回避）；entry → up（预判涨）；
  2) 无 intent 按条件线方向兜底：below（跌破/伏击区）→ up（预判反弹）；
     above（上破/压力位）→ down（预判回落）；
  3) 都判不出 → None（该触发不参与命中率统计，仍记录涨跌幅样本）。
"""
from typing import Any, Dict, Optional

EXIT_INTENTS = {'exit_stop', 'exit_reduce', 'exit_take_profit'}
ENTRY_INTENTS = {'entry'}

#: 命中阈值（%）：|涨跌幅| 超过才算「预判兑现/落空」，±2% 以内算震荡不定论
HIT_THRESHOLD_PCT = 2.0


def infer_expected_direction(intent: Optional[str],
                             condition: Optional[Dict[str, Any]]) -> Optional[str]:
    intent = (intent or '').strip()
    if intent in EXIT_INTENTS:
        return 'down'
    if intent in ENTRY_INTENTS:
        return 'up'
    cond = condition or {}
    params = cond.get('params') or {}
    if cond.get('type') == 'staged_break':
        direction = (params.get('touch') or {}).get('direction')
    else:
        direction = params.get('direction')
    if direction == 'below':
        return 'up'
    if direction == 'above':
        return 'down'
    return None


def judge_hit(expected_direction: Optional[str],
              pct_change: Optional[float],
              threshold_pct: float = HIT_THRESHOLD_PCT) -> Optional[bool]:
    """预判是否命中（三段式）：兑现→True；反向击穿→False；±阈值带内→None（震荡不定论）。

    方向或涨跌幅缺失同样 None。None 不计入命中率分母——命中率只统计「有定论」的样本。
    """
    if expected_direction is None or pct_change is None:
        return None
    if expected_direction == 'up':
        if pct_change >= threshold_pct:
            return True
        if pct_change <= -threshold_pct:
            return False
        return None
    if pct_change <= -threshold_pct:
        return True
    if pct_change >= threshold_pct:
        return False
    return None
