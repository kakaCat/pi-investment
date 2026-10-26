"""PlanCompiler：计划 spec → 盯盘规则（WatchEngine 执行面）的幂等编译器（t5）

设计口径（D-8）：
- **qs_plan 不执行任何盯盘/下单**——它只把计划编译成 watch_rules，执行=WatchEngine；
- 编译是**幂等 diff**：键 = (role, symbol)；同 spec 重编译 0 变更；
- 托管规则带 plan_id + role；写 rule 的 position_state 用持仓真值（D-8 附带修日频兜底缺口）；
- 每次编译落 watch_rule_changes 审计（change_kind=plan_compile）；
- 单次编译失败 → 按已完成操作逆序补偿（新建退役 / 更新恢复 / 退役恢复），不留半编译状态。

规则生成映射：
  entry.conditions              → role=entry    （intent=entry）
  exit.stop_loss (pct/price)    → role=stop_loss（intent=exit_stop；pct→pnl_pct below，price→price_break below）
  exit.reduce_plan[i]           → role=reduce   （intent=exit_take_profit；pnl_pct above + action_params.position_pct）
  schedule.interval_sec         → 每条规则的 interval_sec
"""

from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

import structlog

logger = structlog.get_logger(__name__)

ROLE_ENTRY = "entry"
ROLE_STOP_LOSS = "stop_loss"
ROLE_REDUCE = "reduce"

AUDIT_KIND = "plan_compile"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _targets(spec: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [t for t in (spec.get("targets") or []) if isinstance(t, dict) and t.get("symbol")]


def desired_rules(
    spec: Dict[str, Any], plan_id: int, account: str, position_state_for: Callable[[str], str]
) -> Dict[Tuple[str, str, Any], Dict[str, Any]]:
    """把 spec 展开成期望规则集（键 = (role, symbol, batch)）。"""
    desired: Dict[Tuple[str, str, Any], Dict[str, Any]] = {}
    interval = (spec.get("schedule") or {}).get("interval_sec")
    entry = spec.get("entry") or {}
    exit_spec = spec.get("exit") or {}
    entry_pending = bool((entry or {}).get("pending"))
    for t in _targets(spec):
        symbol = t["symbol"]
        # 待补/空条件：不生成入场规则（只盯止损），防止空条件规则或占位追高条件上线
        if not entry_pending and (entry.get("conditions") or []):
            desired[(ROLE_ENTRY, symbol, None)] = {
                "symbol": symbol,
                "batch": None,
                "plan_id": plan_id,
                "role": ROLE_ENTRY,
                "intent": "entry",
                "conditions": entry.get("conditions") or [],
                "account": account,
                "interval_sec": interval,
                "position_state": "none",
                "context": "计划 #%d · 入场条件（编译产物，改条件请改计划）" % plan_id,
                "action_params": {"action": "buy", "position_pct": t.get("budget_pct")},
            }
        sl = exit_spec.get("stop_loss")
        if sl:
            desired[(ROLE_STOP_LOSS, symbol, None)] = {
                "symbol": symbol,
                "batch": None,
                "plan_id": plan_id,
                "role": ROLE_STOP_LOSS,
                "intent": "exit_stop",
                "conditions": [_stop_condition(sl)],
                "account": account,
                "interval_sec": interval,
                "position_state": position_state_for(symbol) or "none",
                "context": "计划 #%d · 止损（宪法级，触发即执行）" % plan_id,
                "action_params": {"action": "sell", "invalidation": "止损触发"},
            }
        for i, batch in enumerate(exit_spec.get("reduce_plan") or []):
            desired[(ROLE_REDUCE, symbol, i)] = {
                "symbol": symbol,
                "batch": i,
                "plan_id": plan_id,
                "role": ROLE_REDUCE,
                "intent": "exit_take_profit",
                "conditions": [
                    {"type": "pnl_pct", "params": {"pct": batch["at_pct"], "direction": "above"}}
                ],
                "account": account,
                "interval_sec": interval,
                "position_state": position_state_for(symbol) or "none",
                "context": "计划 #%d · 减仓第 %d 批（+%s%% 卖 %d%%）"
                % (plan_id, i + 1, batch["at_pct"], round(batch["sell_ratio"] * 100)),
                "action_params": {
                    "action": "reduce",
                    "position_pct": round(batch["sell_ratio"] * 100),
                },
            }
    return desired


def _stop_condition(stop: Dict[str, Any]) -> Dict[str, Any]:
    kind, value = stop.get("type"), stop.get("value")
    if kind == "price":
        return {"type": "price_break", "params": {"price": value, "direction": "below"}}
    # pct / atr 都落在 pnl_pct（atr 的倍数折算由计划生成端负责，编译不做二次换算）
    return {"type": "pnl_pct", "params": {"pct": value, "direction": "below"}}


class PlanCompiler:
    """spec → watch_rules 幂等编译器。

    port 需提供：
      list_managed(plan_id) -> [{rule_id, role, symbol, batch, enabled, conditions,
                                 intent, interval_sec, position_state, action_params,
                                 context}]
      create_rule(payload) -> rule_id
      update_rule(rule_id, payload) -> None
      retire_rule(rule_id, reason) -> None
      record_audit(plan_id, rule_id, change_kind, before, after, reason) -> None
      link_rule(plan_id, rule_id, role, symbol) -> None   （写 trading_plan_rules 映射）
    """

    def __init__(self, port, now_fn: Callable[[], datetime] = _utcnow):
        self.port = port
        self._now = now_fn

    def diff(
        self,
        plan,
        spec: Optional[Dict[str, Any]] = None,
        position_state_for: Optional[Callable[[str], str]] = None,
    ) -> Dict[str, List[Dict[str, Any]]]:
        spec = spec if spec is not None else plan.spec
        desired = desired_rules(
            spec, plan.id, plan.account, position_state_for or (lambda s: "none")
        )
        existing = {
            (r["role"], r["symbol"], r.get("batch")): r for r in self.port.list_managed(plan.id)
        }
        create, update, retire = [], [], []
        for key, want in desired.items():
            have = existing.get(key)
            if have is None:
                create.append({"key": key, "payload": want})
            elif self._changed(have, want):
                update.append(
                    {
                        "key": key,
                        "rule_id": have["rule_id"],
                        "from": self._snapshot(have),
                        "payload": want,
                    }
                )
        for key, have in existing.items():
            if key not in desired:
                retire.append(
                    {"key": key, "rule_id": have["rule_id"], "from": self._snapshot(have)}
                )
        return {"create": create, "update": update, "retire": retire}

    def apply(
        self,
        plan,
        spec: Optional[Dict[str, Any]] = None,
        position_state_for: Optional[Callable[[str], str]] = None,
        reason: str = "编译计划",
    ) -> Dict[str, int]:
        """执行编译；失败按操作逆序补偿，不留半编译状态。

        补偿口径：新建 → 退役；更新 → 恢复更新前快照；退役 → 按退役前快照恢复。
        补偿失败只记日志，不掩盖触发回滚的原始异常。
        """
        plan_diff = self.diff(plan, spec=spec, position_state_for=position_state_for)
        created: List[int] = []
        updated: List[Dict[str, Any]] = []
        retired: List[Dict[str, Any]] = []
        try:
            for item in plan_diff["create"]:
                payload = item["payload"]
                rule_id = self.port.create_rule(payload)
                created.append(rule_id)
                self.port.link_rule(
                    plan.id, rule_id, payload["role"], payload["symbol"], payload.get("batch") or 0
                )
                self.port.record_audit(
                    plan.id, rule_id, AUDIT_KIND, None, self._snapshot(payload), reason
                )
            for item in plan_diff["update"]:
                self.port.update_rule(item["rule_id"], item["payload"])
                updated.append({"rule_id": item["rule_id"], "before": item["from"]})
                self.port.record_audit(
                    plan.id,
                    item["rule_id"],
                    AUDIT_KIND,
                    item["from"],
                    self._snapshot(item["payload"]),
                    reason,
                )
            for item in plan_diff["retire"]:
                self.port.retire_rule(item["rule_id"], "计划不再包含该规则（%s）" % reason)
                retired.append({"rule_id": item["rule_id"], "before": item["from"]})
                self.port.record_audit(
                    plan.id, item["rule_id"], AUDIT_KIND, item["from"], {"enabled": False}, reason
                )
        except Exception:
            for item in reversed(retired):
                self._restore_rule(item["rule_id"], item["before"])
            for item in reversed(updated):
                self._restore_rule(item["rule_id"], item["before"])
            for rule_id in reversed(created):
                try:
                    self.port.retire_rule(rule_id, "编译失败回滚")
                except Exception:  # noqa: BLE001 - 补偿失败只记日志，不掩盖原始错误
                    logger.error("编译回滚失败", rule_id=rule_id)
            raise
        return {
            "created": len(plan_diff["create"]),
            "updated": len(plan_diff["update"]),
            "retired": len(plan_diff["retire"]),
        }

    def _restore_rule(self, rule_id: int, before: Optional[Dict[str, Any]]) -> None:
        try:
            self.port.update_rule(rule_id, dict(before or {}))
        except Exception as exc:  # noqa: BLE001 - 补偿失败只记日志，不掩盖原始错误
            logger.error("编译回滚恢复规则失败", rule_id=rule_id, error=str(exc))

    @staticmethod
    def _snapshot(rule: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "symbol": rule.get("symbol"),
            "role": rule.get("role"),
            "batch": rule.get("batch"),
            "intent": rule.get("intent"),
            "enabled": rule.get("enabled", True),
            "conditions": rule.get("conditions"),
            "interval_sec": rule.get("interval_sec"),
            "position_state": rule.get("position_state"),
            "action_params": rule.get("action_params"),
            "context": rule.get("context"),
        }

    def _changed(self, have: Dict[str, Any], want: Dict[str, Any]) -> bool:
        for field in (
            "conditions",
            "intent",
            "interval_sec",
            "position_state",
            "action_params",
            "context",
        ):
            if have.get(field) != want.get(field):
                return True
        if have.get("enabled", True) is False:
            return True
        return False
