"""账户级计划 item → WatchEngine 规则的编译（REQ-261026140857-c192，纯逻辑）"""

from __future__ import annotations

from typing import Any, Callable, Dict, Iterable, List, Mapping, Tuple

RuleKey = Tuple[int, str, int]


def _stop_dsl(condition_type: str, params: Mapping[str, Any]) -> Dict[str, Any]:
    if condition_type == "price_break":
        return {"type": "price_break", "params": dict(params or {})}
    if condition_type == "price":
        return {
            "type": "price_break",
            "params": {"price": (params or {}).get("value"), "direction": "below"},
        }
    if condition_type in ("pct", "pnl_pct"):
        return {
            "type": "pnl_pct",
            "params": {
                "pct": (params or {}).get("value", (params or {}).get("pct")),
                "direction": "below",
            },
        }
    return {"type": condition_type, "params": dict(params or {})}


def _entry_dsl(condition_type: str, params: Mapping[str, Any]) -> Dict[str, Any]:
    return {"type": condition_type, "params": dict(params or {})}


def _reduce_dsl(condition) -> Dict[str, Any]:
    if condition.condition_type in ("pct", "pnl_pct"):
        return {
            "type": "pnl_pct",
            "params": {
                "pct": (condition.params or {}).get(
                    "pct", (condition.params or {}).get("value")
                ),
                "direction": "above",
            },
        }
    return _entry_dsl(condition.condition_type, condition.params)


def _with_combinator(
    conditions: List[Dict[str, Any]], combinator: str
) -> List[Dict[str, Any]]:
    if len(conditions) <= 1:
        return conditions
    return [
        {
            "type": "combined",
            "params": {
                "operator": "OR" if combinator == "any_of" else "AND",
                "conditions": conditions,
            },
        }
    ]


def build_desired_rules(
    *,
    plan_id: int,
    plan_version: int,
    account: str,
    item_versions: Iterable[Any],
    conditions_by_item_version: Mapping[int, List[Any]],
    position_state_for: Callable[[str], str],
    interval_sec: int | None = None,
    actor: str = "agent",
) -> Dict[RuleKey, Dict[str, Any]]:
    """把 approved revision 的 item 决策展开为规则期望集。"""
    desired: Dict[RuleKey, Dict[str, Any]] = {}
    invalidation_by_item_role = {}
    for item_version in item_versions or []:
        item = getattr(item_version, "item", None)
        symbol = getattr(item, "symbol", None) if item is not None else None
        item_id = int(item_version.item_id)
        action = item_version.action
        if action == "avoid" or not symbol:
            continue

        conditions = list(conditions_by_item_version.get(item_version.id, []))
        invalidation_by_item_role.update(
            {
                (item_id, condition.role): condition.invalidation_threshold_pct
                for condition in conditions
                if condition.invalidation_threshold_pct is not None
            }
        )
        entry_role_by_action = {
            "buy": "entry",
            "add": "add_position",
            "observe": "trend_observe",
        }
        entry_role = entry_role_by_action.get(action)
        if entry_role:
            entry_conditions = _with_combinator(
                [
                    _entry_dsl(condition.condition_type, condition.params)
                    for condition in conditions
                    if condition.role == entry_role
                ],
                item_version.entry_combinator,
            )
            if entry_conditions:
                desired[(item_id, entry_role, 0)] = {
                    "symbol": symbol,
                    "conditions": entry_conditions,
                    "intent": entry_role,
                    "position_state": (
                        "none" if action == "observe" else position_state_for(symbol) or "none"
                    ),
                    "action_params": {
                        "action": "observe" if action == "observe" else "buy",
                        "position_pct": (
                            (float(item_version.target_weight) * 100.0)
                            if item_version.target_weight is not None
                            else None
                        ),
                        "setup_type": item_version.setup_type,
                    },
                    "context": "计划 #%d v%d · item #%d %s · %s"
                    % (
                        plan_id,
                        plan_version,
                        item_id,
                        entry_role,
                        item_version.setup_type or "custom",
                    ),
                }

        stop_conditions = [
            _stop_dsl(condition.condition_type, condition.params)
            for condition in conditions
            if condition.role == "stop_loss"
        ]
        for index, condition in enumerate(stop_conditions):
            desired[(item_id, "stop_loss", index)] = {
                "symbol": symbol,
                "conditions": [condition],
                "intent": "exit_stop",
                "position_state": position_state_for(symbol) or "none",
                "action_params": {
                    "action": "sell",
                    "invalidation": item_version.invalidation,
                    "setup_type": item_version.setup_type,
                },
                "context": "计划 #%d v%d · item #%d 止损"
                % (plan_id, plan_version, item_id),
            }

        reduce_conditions = [
            condition for condition in conditions if condition.role == "reduce"
        ]
        for condition in reduce_conditions:
            batch = int(condition.batch or 0)
            pct = (condition.params or {}).get("pct")
            sell_ratio = (condition.params or {}).get("sell_ratio", 1.0)
            desired[(item_id, "reduce", batch)] = {
                "symbol": symbol,
                "conditions": [_reduce_dsl(condition)],
                "intent": "exit_take_profit",
                "position_state": position_state_for(symbol) or "none",
                "action_params": {
                    "action": "reduce",
                    "position_pct": round(float(sell_ratio) * 100),
                    "setup_type": item_version.setup_type,
                },
                "context": "计划 #%d v%d · item #%d 减仓第 %d 批"
                % (plan_id, plan_version, item_id, batch + 1),
            }

        exit_reduce_conditions = [
            condition for condition in conditions if condition.role == "exit_reduce"
        ]
        for condition in exit_reduce_conditions:
            batch = int(condition.batch or 0)
            pct = (condition.params or {}).get("pct")
            sell_ratio = (condition.params or {}).get("sell_ratio", 1.0)
            desired[(item_id, "exit_reduce", batch)] = {
                "symbol": symbol,
                "conditions": [_reduce_dsl(condition)],
                "intent": "exit_reduce",
                "position_state": position_state_for(symbol) or "none",
                "action_params": {
                    "action": "reduce",
                    "position_pct": round(float(sell_ratio) * 100),
                    "setup_type": item_version.setup_type,
                },
                "context": "计划 #%d v%d · item #%d 风控减仓第 %d 批"
                % (plan_id, plan_version, item_id, batch + 1),
            }

    for payload in desired.values():
        item_id = next(key[0] for key, value in desired.items() if value is payload)
        role = next(key[1] for key, value in desired.items() if value is payload)
        invalidation_threshold = invalidation_by_item_role.get((item_id, role))
        if invalidation_threshold is not None:
            payload["invalidation_threshold_pct"] = invalidation_threshold
        payload.update(
            {
                "plan_id": plan_id,
                "item_id": payload.get("_item_id")
                or next(key[0] for key, value in desired.items() if value is payload),
                "plan_version": plan_version,
                "account": account,
                "batch": next(
                    key[2] for key, value in desired.items() if value is payload
                ),
                "role": next(
                    key[1] for key, value in desired.items() if value is payload
                ),
                "interval_sec": interval_sec,
                "enabled": True,
                "actor": actor,
            }
        )
    return desired


def diff_rules(
    *, desired: Dict[RuleKey, Dict[str, Any]], managed: List[Dict[str, Any]]
) -> Dict[str, List[Dict[str, Any]]]:
    existing = {
        (int(rule["item_id"]), str(rule["role"]), int(rule.get("batch") or 0)): rule
        for rule in managed
    }
    create: List[Dict[str, Any]] = []
    update: List[Dict[str, Any]] = []
    retire: List[Dict[str, Any]] = []

    for key, payload in desired.items():
        have = existing.get(key)
        if have is None:
            create.append({"key": key, "payload": payload})
            continue
        if _changed(have, payload):
            update.append(
                {
                    "key": key,
                    "rule_id": have["rule_id"],
                    "from": dict(have),
                    "payload": payload,
                }
            )

    for key, have in existing.items():
        if key not in desired:
            retire.append({"key": key, "rule_id": have["rule_id"], "from": dict(have)})

    return {"create": create, "update": update, "retire": retire}


def _changed(have: Dict[str, Any], want: Dict[str, Any]) -> bool:
    fields = (
        "symbol",
        "conditions",
        "intent",
        "interval_sec",
        "action_params",
        "plan_version",
        "invalidation_threshold_pct",
    )
    for field in fields:
        if have.get(field) != want.get(field):
            return True
    if bool(have.get("enabled")) is bool(want.get("enabled", True)):
        return False
    return not (
        want.get("role") in ("stop_loss", "reduce", "exit_reduce")
        and want.get("position_state") == "none"
        and not have.get("enabled")
    )
