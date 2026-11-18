"""账户计划项状态机（REQ-261026140857-c192，纯逻辑，无 I/O）"""

from __future__ import annotations

from typing import Optional, Tuple

STATUS_PLANNED = "planned"
STATUS_READY = "ready"
STATUS_ENTERING = "entering"
STATUS_HOLDING = "holding"
STATUS_REDUCING = "reducing"
STATUS_EXITED = "exited"
STATUS_CANCELLED = "cancelled"

ITEM_STATUSES = (
    STATUS_PLANNED,
    STATUS_READY,
    STATUS_ENTERING,
    STATUS_HOLDING,
    STATUS_REDUCING,
    STATUS_EXITED,
    STATUS_CANCELLED,
)

LEGAL_ITEM_TRANSITIONS = {
    STATUS_PLANNED: {STATUS_READY, STATUS_CANCELLED},
    STATUS_READY: {STATUS_ENTERING, STATUS_HOLDING, STATUS_EXITED, STATUS_CANCELLED},
    STATUS_ENTERING: {STATUS_HOLDING, STATUS_EXITED, STATUS_CANCELLED},
    STATUS_HOLDING: {STATUS_REDUCING, STATUS_EXITED, STATUS_CANCELLED},
    STATUS_REDUCING: {STATUS_EXITED, STATUS_CANCELLED},
    STATUS_EXITED: set(),
    STATUS_CANCELLED: set(),
}


def is_legal_item_transition(from_status: str, to_status: str) -> bool:
    return to_status in LEGAL_ITEM_TRANSITIONS.get(from_status, set())


def evaluate_item_transition(from_status: str, to_status: str) -> Tuple[bool, Optional[str]]:
    """计划项迁移守卫，返回 (ok, reason)。"""
    if from_status not in LEGAL_ITEM_TRANSITIONS:
        return False, "未知计划项状态：%s" % from_status
    if to_status not in ITEM_STATUSES:
        return False, "未知目标状态：%s" % to_status
    if from_status == to_status:
        return False, "状态未变化（%s）" % from_status
    if not is_legal_item_transition(from_status, to_status):
        return False, "不允许的计划项迁移：%s → %s" % (from_status, to_status)
    return True, None


def initial_item_state(action: str, position_qty: int, *, entry_ready: bool) -> str:
    """根据决策类型、已有持仓和入场完整性推导初始状态。"""
    if action in ("avoid", "observe"):
        return STATUS_PLANNED
    if action in ("buy", "add"):
        return STATUS_READY if entry_ready else STATUS_PLANNED
    if action in ("sell", "reduce_risk"):
        return STATUS_REDUCING if position_qty > 0 else STATUS_PLANNED
    return STATUS_HOLDING if position_qty > 0 else STATUS_PLANNED


def transition_for_fill(action: str, remaining_qty: int) -> str:
    """成交后的目标状态。调用方应先校验该迁移是否合法。"""
    if action == "buy":
        return STATUS_EXITED if remaining_qty <= 0 else STATUS_HOLDING
    if action == "sell":
        return STATUS_EXITED if remaining_qty <= 0 else STATUS_REDUCING
    return STATUS_HOLDING if remaining_qty > 0 else STATUS_EXITED
