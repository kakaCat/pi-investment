"""账户级计划生成的外部输入端口（REQ-261026140857-c192）"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Dict, Optional, Protocol, Tuple


@dataclass(frozen=True)
class TargetAllocation:
    symbol: str
    target_weight: Optional[float] = None
    target_qty: Optional[int] = None
    horizon: str = "swing"
    thesis: str = ""
    invalidation: str = ""
    entry_valid_until: Optional[datetime] = None
    entry_conditions: Tuple[Dict[str, Any], ...] = ()
    stop_loss: Optional[Dict[str, Any]] = None
    reduce_plan: Tuple[Dict[str, Any], ...] = ()
    evidence: Dict[str, Any] = field(default_factory=dict)
    action: Optional[str] = None
    setup_type: Optional[str] = None
    entry_combinator: str = "all_of"
    execution_batch: Optional[int] = None
    max_chase_pct: Optional[float] = None


@dataclass(frozen=True)
class PortfolioDecision:
    account: str
    trade_date: date
    data_as_of: datetime
    targets: Tuple[TargetAllocation, ...]
    market_gate: Dict[str, Any] = field(default_factory=dict)
    risk_budget: Dict[str, Any] = field(default_factory=dict)
    evidence: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PositionView:
    symbol: str
    qty: int


class PortfolioDecisionProvider(Protocol):
    def build(self, *, account: str, trade_date: date) -> PortfolioDecision: ...


class PositionProvider(Protocol):
    def list_positions(self, *, account: str) -> Tuple[PositionView, ...]: ...
