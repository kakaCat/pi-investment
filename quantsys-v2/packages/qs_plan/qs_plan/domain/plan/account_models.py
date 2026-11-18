"""账户级交易计划领域值对象（REQ-261026140857-c192）

纯数据模型，无 I/O、无 SQLAlchemy 依赖。数据库行在仓储层映射为这里的值对象。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class PlanItemDraft:
    """单个 revision 中一个计划项的决策值。"""

    item_id: int
    symbol: str
    action: str
    horizon: str
    target_weight: Optional[float] = None
    max_weight: Optional[float] = None
    target_qty: Optional[int] = None
    entry_combinator: str = "all_of"
    thesis: str = ""
    invalidation: str = ""
    entry_valid_until: Optional[datetime] = None
    evidence: Dict[str, Any] = field(default_factory=dict)
    setup_type: Optional[str] = None


@dataclass(frozen=True)
class ItemConditionDraft:
    """计划项条件。角色与批次是规则语义的一部分。"""

    item_id: int
    role: str
    condition_type: str
    params: Dict[str, Any]
    batch: int = 0
    sequence: int = 0
    invalidation_threshold_pct: Optional[float] = None


@dataclass(frozen=True)
class ItemStateView:
    """计划项当前执行状态。"""

    item_id: int
    state: str
    target_qty: Optional[int]
    filled_qty: int
    remaining_qty: Optional[int]
    initial_position_qty: int
    initial_sold_qty: int
    lock_version: int


@dataclass(frozen=True)
class ReadinessReason:
    """机器可读的 readiness 阻塞原因。"""

    code: str
    message: str
    item_id: Optional[int] = None


@dataclass(frozen=True)
class ReadinessResult:
    ready: bool
    status: str
    reasons: tuple[ReadinessReason, ...] = ()
