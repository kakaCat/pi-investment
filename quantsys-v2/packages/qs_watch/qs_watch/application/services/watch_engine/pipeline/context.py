"""触发流水线的共享上下文（TriggerContext）与 trace 记录。

为什么要显式上下文：`_process_condition` 的 15 步里，后一步要读前一步的结论
（升级理由 → 处置决策；处置结论 → 市场门/去重/通知渲染；trigger → 待办/记账）。
把这些中间量收进一个对象，阶段之间只传 ctx，不再靠深层缩进里的散装局部变量。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:  # 仅类型标注：engine 反向 import pipeline，运行时不能成环
    from qs_watch.application.services.watch_engine.engine import WatchEngine

#: trace 条目状态：阶段执行完毕 / 在此终止 / 抛异常
TRACE_DONE = 'done'
TRACE_STOP = 'stop'
TRACE_ERROR = 'error'


@dataclass
class StageTrace:
    """单个阶段的执行留痕（流水线的可观测性事实源）。

    status 三态：
      · done  —— 阶段执行完毕放行；
      · stop  —— 阶段在此终止（reason = 终止路径，后续阶段未执行）；
      · error —— 阶段抛异常（异常继续上抛，不改变既有的失败语义）。
    """

    stage: str
    status: str = TRACE_DONE
    reason: str = ''


@dataclass
class TriggerContext:
    """单条条件「评估后」流水线的全部输入与中间结论。

    输入（tick 传入，阶段只读）：engine / rule / idx / cond / quote / result /
    now / events / env_gate / verify_confirm。
    中间结论（阶段写入，后续阶段读）：env_exempt_reason / escalation_reason /
    trigger_level / disposition / disposition_reason / action_amount /
    notify_level / trigger / buffered / dup_of / merged_from_rule。
    """

    engine: 'WatchEngine'
    rule: Any
    idx: int
    cond: dict
    quote: Any
    result: Any
    now: datetime
    events: List[Dict[str, Any]]
    env_gate: Optional[tuple] = None
    verify_confirm: bool = False

    # ── 阶段间传递的中间结论 ──────────────────────────────
    env_exempt_reason: str = ''
    escalation_reason: Any = None
    trigger_level: str = ''
    disposition: str = ''
    disposition_reason: str = ''
    action_amount: Optional[float] = None
    notify_level: Optional[str] = None
    trigger: Any = None
    buffered: bool = False
    dup_of: Any = None
    merged_from_rule: Any = None

    # ── 可观测性 ──────────────────────────────────────────
    trace: List[StageTrace] = field(default_factory=list)
    stop_reason: Optional[str] = None

    @property
    def trace_names(self) -> List[str]:
        """已执行（或已终止）的阶段名，按执行顺序。"""
        return [entry.stage for entry in self.trace]

    @property
    def stopped_at(self) -> Optional[str]:
        """终止阶段名；跑完整条流水线时为 None。"""
        if not self.trace:
            return None
        last = self.trace[-1]
        return last.stage if last.status in (TRACE_STOP, TRACE_ERROR) else None
