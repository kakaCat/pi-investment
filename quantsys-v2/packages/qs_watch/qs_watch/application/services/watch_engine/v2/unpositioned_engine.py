"""unpositioned_engine —— 非持仓类判定（REQ-261022235419-2299 / t4，FR-5）

未持仓票（D-4 用户裁定「未持仓看到买入范围等级」）：

- ``entry``            买入范围：到买点价触发提醒
- ``trend_observe``    观察：只读记录，不产生交易动作

设计要点：

1. **纯判定**：输入 rule + quote，输出 Judgment；不落库不投递。
2. **仅非持仓适用**：持仓票的买入语义不成立（已有仓位），由调用方按持仓分流；
   本模块不读持仓真值（分流已在 tick 层，architecture.md ③）。
3. 条件求值复用 V1 的 ``conditions.evaluate``（黑盒复用）。
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

import structlog

logger = structlog.get_logger(__name__)

#: 非持仓类意图（买入范围 + 观察；观察不产生交易动作但保留判定以便留痕）
UNPOSITIONED_INTENTS = (
    'entry',
    'trend_observe',
)


@dataclass
class Judgment:
    """非持仓类判定结果（值对象）。"""

    intent: str
    triggered: bool = False
    hit_conditions: List[Dict[str, Any]] = field(default_factory=list)
    suppressed_conditions: List[Dict[str, Any]] = field(default_factory=list)
    degraded: bool = False
    distance_ratio: Optional[float] = None
    reason: str = ''
    #: 观察类不进交易通道；agent 通道只留痕，direct 通道可发观察提醒
    observe_only: bool = False


def _intent_of(rule) -> str:
    return str(getattr(rule, 'intent', '') or '').strip()


def evaluate(rule, quote, now: Optional[datetime] = None,
             ctx: Optional[Any] = None, staged_manager=None) -> Judgment:
    """非持仓类判定：买入范围 / 观察。

    返回 Judgment：
        - 非非持仓类 intent → triggered=False, reason='not_unpositioned_intent'
        - 买入范围到点 → triggered=True
        - 观察类命中 → triggered=True 且 observe_only=True（不交易；agent 通道只留痕）
    """
    intent = _intent_of(rule)
    if intent not in UNPOSITIONED_INTENTS:
        return Judgment(intent=intent, triggered=False, reason='not_unpositioned_intent')

    from ..rules.conditions import EvalContext

    if ctx is None:
        _cost = getattr(rule, 'cost_price', None)
        try:
            _cost = float(_cost) if _cost is not None else None
        except (TypeError, ValueError):
            _cost = None  # Decimal/脏值统一转 float（条件 DSL 用 float 运算）
        ctx = EvalContext(cost_price=_cost)

    from .condition_evaluator import evaluate_conditions
    batch = evaluate_conditions(rule, quote, ctx, now, staged_manager=staged_manager)
    observe_only = intent == 'trend_observe'
    return Judgment(
        intent=intent,
        triggered=bool(batch.hits),
        hit_conditions=batch.hits,
        suppressed_conditions=batch.suppressed,
        degraded=batch.degraded,
        distance_ratio=batch.distance_ratio,
        reason='' if batch.hits else 'no_condition_hit',
        observe_only=observe_only,
    )
