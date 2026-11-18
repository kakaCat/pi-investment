"""position_engine —— 持仓类判定（REQ-261022235419-2299 / t3，FR-4）

持仓票四操作（D-4 用户裁定「持仓的看止盈止损减仓增仓」）：

- ``add_position``      增仓：回调加仓点
- ``exit_take_profit``  止盈
- ``exit_stop``         止损（宪法级：任何情况必达）
- ``exit_reduce``       减仓

设计要点（architecture.md IF-4 / backend.md）：

1. **纯判定**：输入 rule + quote + 持仓真值，输出 Judgment；不做 IO、不落库、
   不投递 —— 投递归 notify_agent / notify_feishu（t7/t8）。
2. **止损 fail-open**：持仓真值不可知或显示空仓时，止损仍照常判定并留
   ``state_mismatch`` 痕迹（宁可多判一次，不漏真止损 = 资损）。
3. **其余三操作需 holding**：空仓时增仓/止盈/减仓无意义，返回未触发 + 理由，
   不产生通知。
4. 条件求值复用 V1 的 ``conditions.evaluate``（黑盒复用，不重写 DSL）。
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

import structlog

logger = structlog.get_logger(__name__)

#: 持仓类四操作（与 V1 TRADE_INTENTS 子集对齐）
POSITION_INTENTS = (
    'add_position',
    'exit_take_profit',
    'exit_stop',
    'exit_reduce',
)

#: 宪法级意图：持仓状态异常时 fail-open 照常判定（止损保护线不能因状态断言被跳过）
CONSTITUTIONAL_INTENTS = ('exit_stop',)

#: 持仓真值取值域（与仓储 normalize_position_state 同源）
POSITION_STATE_HOLDING = 'holding'
POSITION_STATE_NONE = 'none'

#: 状态不一致留痕原因（供 tick 落 state_mismatch 事件）
MISMATCH_STOP_WITHOUT_HOLDING = 'stop_without_holding'
MISMATCH_UNREADABLE = 'unreadable'


@dataclass
class Judgment:
    """持仓类判定结果（值对象，不落库）。

    ``triggered`` 为 True 表示该规则本拍命中，应交给路由（t6）。
    ``state_mismatch`` 非空表示持仓状态与意图不一致但已 fail-open 求值 ——
    由调用方在**真触发时**留痕（未触发不刷事件，避免噪声淹没真异常）。
    ``reason`` 为未触发时的可读原因（skip 口径）。
    """

    intent: str
    triggered: bool = False
    hit_conditions: List[Dict[str, Any]] = field(default_factory=list)
    suppressed_conditions: List[Dict[str, Any]] = field(default_factory=list)
    state_mismatch: Optional[str] = None
    degraded: bool = False
    distance_ratio: Optional[float] = None
    reason: str = ''


def _intent_of(rule) -> str:
    return str(getattr(rule, 'intent', '') or '').strip()


def _position_state_of(rule) -> Optional[str]:
    """读规则上的持仓真值；缺失/非法返回 None（不可知）。"""
    state = getattr(rule, 'position_state', None)
    if state is None:
        return None
    text = str(state).strip().lower()
    if text in (POSITION_STATE_HOLDING, POSITION_STATE_NONE):
        return text
    return None


def evaluate(rule, quote, position: Optional[str] = None,
             now: Optional[datetime] = None,
             ctx: Optional[Any] = None, staged_manager=None) -> Judgment:
    """持仓类判定：增仓 / 止盈 / 止损 / 减仓。

    参数：
        rule:     规则对象（读 intent / conditions / position_state / cost_price）
        quote:    实时报价（需有 .price；条件求值可能需要 .prev_close 等）
        position: 显式持仓真值（holding / none）；None 时回落读 rule.position_state
        now:      判定时刻（条件求值用）
        ctx:      条件求值上下文（EvalContext）；None 时按 rule 构造最小上下文

    返回 Judgment：
        - 非持仓类 intent → triggered=False, reason='not_position_intent'
        - 持仓真值不可知 → 除止损外不判（reason='position_unknown'）；止损 fail-open
        - 空仓 + 非止损 → 不判（reason='not_holding'）
        - 条件命中 → triggered=True, hit_conditions=[...]
    """
    intent = _intent_of(rule)
    if intent not in POSITION_INTENTS:
        return Judgment(intent=intent, triggered=False, reason='not_position_intent')

    state = position if position is not None else _position_state_of(rule)
    state = str(state).strip().lower() if state is not None else None

    mismatch: Optional[str] = None

    # ── 持仓状态门（fail-open 口径）────────────────────────────────────
    if state not in (POSITION_STATE_HOLDING, POSITION_STATE_NONE):
        # 不可知：止损照常判（留痕），其余不判
        if intent in CONSTITUTIONAL_INTENTS:
            mismatch = MISMATCH_UNREADABLE
        else:
            return Judgment(intent=intent, triggered=False, reason='position_unknown')
    elif state != POSITION_STATE_HOLDING:
        # 确认空仓
        if intent in CONSTITUTIONAL_INTENTS:
            # 止损空仓：状态可能滞后 → fail-open 照常判定，真触发时留痕
            mismatch = MISMATCH_STOP_WITHOUT_HOLDING
        else:
            # 增仓/止盈/减仓：无仓可操作
            return Judgment(intent=intent, triggered=False, reason='not_holding')

    # ── 条件求值（复用 V1 DSL）─────────────────────────────────────────
    from ..rules.conditions import EvalContext

    if ctx is None:
        # 缺省最小上下文：成本价从规则取（止盈/止损模板与 pnl 类条件需要）
        _cost = getattr(rule, 'cost_price', None)
        try:
            _cost = float(_cost) if _cost is not None else None
        except (TypeError, ValueError):
            _cost = None  # Decimal/脏值统一转 float（条件 DSL 用 float 运算）
        ctx = EvalContext(cost_price=_cost)

    from .condition_evaluator import evaluate_conditions
    batch = evaluate_conditions(rule, quote, ctx, now, staged_manager=staged_manager)
    return Judgment(
        intent=intent,
        triggered=bool(batch.hits),
        hit_conditions=batch.hits,
        suppressed_conditions=batch.suppressed,
        state_mismatch=mismatch if batch.hits else None,
        degraded=batch.degraded,
        distance_ratio=batch.distance_ratio,
        reason='' if batch.hits else 'no_condition_hit',
    )
