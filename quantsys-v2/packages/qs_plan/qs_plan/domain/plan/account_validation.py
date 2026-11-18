"""账户级计划项领域校验（REQ-261026140857-c192，纯逻辑，无 I/O）"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Iterable, List, Optional, Sequence

from .account_models import ItemConditionDraft, PlanItemDraft

ACTIONS = ("buy", "add", "observe", "sell", "reduce_risk", "hold", "avoid")
HORIZONS = ("day", "swing")
COMBINATORS = ("all_of", "any_of")
CONDITION_ROLES = (
    "entry",
    "add_position",
    "trend_observe",
    "stop_loss",
    "reduce",
    "exit_reduce",
)
SETUP_TYPES = (
    "breakout",
    "pullback",
    "trend_follow",
    "mean_reversion",
    "risk_off",
    "event_driven",
    "observe",
    "custom",
)


def _weight_ok(value) -> bool:
    """权重合法性：None 或 [0,1] 实数。

    2026-11-11（w-191eb58c）：ORM 从 NUMERIC 列读出的 Decimal 不是
    int/float 子类，旧实现把它误判为非法，导致 trading_plan_generate_daily
    连续两日全盘失败（hold 项 target_weight 来自上一版本，全是 Decimal）。
    显式接受 Decimal；bool 与字符串仍拒绝。
    """
    if value is None:
        return True
    if isinstance(value, bool) or isinstance(value, str):
        return False
    if not isinstance(value, (int, float, Decimal)):
        return False
    try:
        return 0 <= float(value) <= 1
    except (TypeError, ValueError):
        return False


def validate_item_decision(
    item: PlanItemDraft,
    conditions: Sequence[ItemConditionDraft],
    *,
    activation: bool = False,
    now: Optional[datetime] = None,
) -> List[str]:
    """校验计划项决策。activation=True 时执行 preflight 完整性检查。"""
    problems: List[str] = []
    if not item.symbol:
        problems.append("symbol 必填")
    if item.action not in ACTIONS:
        problems.append(
            "action 必须是 buy/add/observe/sell/reduce_risk/hold/avoid 之一"
        )
    if item.setup_type is not None and item.setup_type not in SETUP_TYPES:
        problems.append("setup_type 不受支持：%s" % item.setup_type)
    if item.horizon not in HORIZONS:
        problems.append("horizon 必须是 day/swing")
    if not item.thesis.strip():
        problems.append("thesis 必填")
    if not item.invalidation.strip():
        problems.append("invalidation 必填")
    if not _weight_ok(item.target_weight):
        problems.append("target_weight 必须在 0～1")
    if not _weight_ok(item.max_weight):
        problems.append("max_weight 必须在 0～1")
    if item.target_qty is not None and (
        not isinstance(item.target_qty, int) or item.target_qty < 0
    ):
        problems.append("target_qty 必须是 >=0 的整数")
    if item.entry_combinator not in COMBINATORS:
        problems.append("entry_combinator 必须是 all_of/any_of")

    if activation and item.entry_valid_until is not None and now is not None:
        if item.entry_valid_until <= now:
            problems.append("entry_valid_until 已过期")

    role_conditions: dict[str, list[ItemConditionDraft]] = {}
    for index, condition in enumerate(conditions or []):
        if condition.item_id != item.item_id:
            problems.append("条件 item_id 与计划项不一致")
            continue
        role = condition.role
        if role not in CONDITION_ROLES:
            problems.append(
                "条件角色必须是 entry/add_position/trend_observe/stop_loss/reduce/exit_reduce"
            )
            continue
        condition_valid = True
        if condition.batch < 0 or condition.sequence < 0:
            problems.append("条件 batch/sequence 必须非负")
            condition_valid = False
        if not condition.condition_type:
            problems.append("条件 type 必填")
            condition_valid = False
        if not isinstance(condition.params, dict):
            problems.append("条件 params 必须是对象")
            condition_valid = False
        threshold = condition.invalidation_threshold_pct
        if threshold is not None:
            try:
                threshold_value = float(threshold)
            except (TypeError, ValueError):
                threshold_value = None
            if (
                isinstance(threshold, bool)
                or threshold_value is None
                or not (0 < threshold_value <= 100)
            ):
                problems.append("invalidation_threshold_pct 必须在 (0,100]")
                condition_valid = False
        if condition_valid:
            role_conditions.setdefault(role, []).append(condition)

    if activation:
        if item.action == "buy" and not role_conditions.get("entry"):
            problems.append("buy 计划项必须补全入场条件")
        if item.action == "add" and not role_conditions.get("add_position"):
            problems.append("add 计划项必须补全加仓条件")
        if item.action == "observe" and not role_conditions.get("trend_observe"):
            problems.append("observe 计划项必须补全观察条件")
        if item.action in ("sell", "hold") and not (
            role_conditions.get("stop_loss")
            or role_conditions.get("reduce")
            or role_conditions.get("exit_reduce")
        ):
            problems.append(
                "sell/hold 计划项至少要有 stop_loss/reduce/exit_reduce 之一"
            )
        if item.action == "reduce_risk" and not role_conditions.get("exit_reduce"):
            problems.append("reduce_risk 计划项必须补全风控减仓条件")
        if item.action == "avoid":
            if role_conditions:
                problems.append("avoid 计划项不得配置执行条件")
        if (
            item.action in ("buy", "add")
            and item.target_weight is None
            and item.target_qty is None
        ):
            problems.append("buy/add 计划项必须给出 target_weight 或 target_qty")
    return problems


def validate_items_unique_open(items: Iterable[PlanItemDraft]) -> List[str]:
    """校验同一次决策中不存在同标的多个未关闭项。"""
    seen = {}
    problems = []
    for item in items:
        key = item.symbol
        if key in seen:
            problems.append("同一标的存在多个计划项：%s" % item.symbol)
        seen[key] = item.item_id
    return problems
