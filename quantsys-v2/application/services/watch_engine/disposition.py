"""盯盘触发处置决策（REQ-f08def，2026-09-11，w-c8cae280）

为什么需要：实测近 200 条触发 agent_response 全为 null —— 引擎喊了，无人处置，
"触发→处置率" = 0%。本模块把"这条触发由谁处置、要不要叫醒 agent"变成**确定性函数**，
让机械可判的触发零 LLM 成本落地，agent 只按摘要批量唤醒（用户硬约束：token 成本）。

状态取值：
  pending        待处置（需人/agent 决策）
  auto_observed  机械归档（规则声明 observe/message → 系统按预案观察）
  deduped        去重合并（同标的同向在去重窗内已有触发）
  escalated      进 agent 摘要队列（L2 / escalation_policy 命中）
  handled        已处置（有动作）
  ignored        知悉但不动作（必须带 reason）
  expired        超期未处置（盘后清单兜底）
  legacy_unknown 状态机上线前的历史数据（不参与处置率统计）
"""

# 去重窗：同标的 + 同方向在该窗口内只通知一次（实测同规则同向多阈值重复通知间隔 0.46 秒，
# 601600 六条规则语义重合会在一次跌穿里响 4+ 次）
DEDUP_WINDOW_SEC = 60

DISPOSITION_PENDING = 'pending'
DISPOSITION_AUTO_OBSERVED = 'auto_observed'
DISPOSITION_DEDUPED = 'deduped'
DISPOSITION_ESCALATED = 'escalated'
DISPOSITION_HANDLED = 'handled'
DISPOSITION_IGNORED = 'ignored'
DISPOSITION_EXPIRED = 'expired'
DISPOSITION_LEGACY = 'legacy_unknown'

# 需要在盘后清单里继续追的未收敛状态
UNRESOLVED = (DISPOSITION_PENDING, DISPOSITION_ESCALATED)


def normalize_symbol(symbol) -> str:
    """'601600.SH' -> '601600'（跨规则去重必须先统一口径）"""
    return str(symbol or '').split('.')[0].strip()


def direction_of(condition) -> str:
    """条件方向：above / below / 其它类型名。用于去重键与同向合并判定。"""
    params = (condition or {}).get('params') or {}
    d = params.get('direction')
    if d in ('above', 'below'):
        return d
    return str((condition or {}).get('type') or 'unknown')


def dedup_key(rule, condition):
    """去重键 = (归一化标的, 方向)。同标的同向的重复触发合并为一条通知。"""
    return (normalize_symbol(getattr(rule, 'symbol', '')), direction_of(condition))


def action_hint_of(rule) -> dict:
    ah = getattr(rule, 'action_hint', None)
    return ah if isinstance(ah, dict) else {}


def decide(rule, condition, escalated: bool = False):
    """返回 (disposition, reason)。纯函数，便于单测。

    优先级：升级/L2 > 规则声明的机械动作 > 默认待处置。
    """
    if escalated:
        return DISPOSITION_ESCALATED, 'L2 行动层或升级策略命中 → 进 agent 摘要队列'
    ah = action_hint_of(rule)
    level = str(ah.get('trigger_level') or '').upper()
    act = str(ah.get('action_on_trigger') or '').lower()
    if level == 'L2':
        return DISPOSITION_ESCALATED, '规则分级 L2 行动层 → 进 agent 摘要队列'
    if act in ('observe', 'message'):
        return DISPOSITION_AUTO_OBSERVED, f'规则声明 action_on_trigger={act} → 系统按预案观察，不唤醒 agent'
    if act in ('buy', 'sell'):
        return DISPOSITION_PENDING, f'规则声明 action_on_trigger={act} → 需人工/agent 决策'
    return DISPOSITION_PENDING, '默认待处置（规则未声明触发动作）'


def is_resolved(disposition: str) -> bool:
    """是否已收敛到终态（用于处置率统计）"""
    return disposition in (
        DISPOSITION_AUTO_OBSERVED, DISPOSITION_DEDUPED,
        DISPOSITION_HANDLED, DISPOSITION_IGNORED, DISPOSITION_EXPIRED,
    )
