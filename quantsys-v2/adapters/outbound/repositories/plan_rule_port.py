"""计划编译器的生产端口（t6）：把 PlanCompiler 的 port 协议落到 watch 仓储。

口径：
- 托管规则的**唯一写点**是编译器（经本端口）；其他写方（自愈/人工 force）会改用
  watch 既有通道，由引擎侧记 drift——本端口不提供「按规则 id 直改」的能力给外部；
- 规则 payload 里的 role/batch 落 `trading_plan_rules` 映射（PK 含 batch）；
- 每次变更写 `watch_rule_changes` 审计（change_kind=plan_compile）。
"""

from typing import Any, Dict, List

import structlog

logger = structlog.get_logger(__name__)

AUDIT_CHANGED_BY = "agent"
AUDIT_CHANGE_KIND = "plan_compile"


class PlanRulePort:
    def __init__(self, rule_repo=None, plan_repo=None, change_repo=None):
        from adapters.outbound.repositories.watch_rule_repository import WatchRuleRepository
        from adapters.outbound.repositories.trading_plan_repository import TradingPlanRepository
        from adapters.outbound.repositories.watch_rule_change_repository import (
            WatchRuleChangeRepository,
        )

        self.rule_repo = rule_repo or WatchRuleRepository()
        self.plan_repo = plan_repo or TradingPlanRepository()
        self.change_repo = change_repo or WatchRuleChangeRepository()

    # ── 读 ────────────────────────────────────────────────
    def list_managed(self, plan_id: int) -> List[Dict[str, Any]]:
        rules = self.rule_repo.list_by_plan(plan_id, include_disabled=True)
        mappings = {m.rule_id: m for m in self.plan_repo.list_rule_mappings(plan_id)}
        out: List[Dict[str, Any]] = []
        for r in rules:
            m = mappings.get(getattr(r, "id", None))
            if m is None:
                # 有 plan_id 但无映射行：视为孤儿托管规则，role 用 unknown（编译会退役它）
                role, batch = "unknown", 0
            else:
                role, batch = m.role, m.batch
            out.append(
                {
                    "rule_id": getattr(r, "id", None),
                    "role": role,
                    "batch": batch,
                    "symbol": getattr(r, "symbol", None),
                    "enabled": bool(getattr(r, "enabled", True)),
                    "conditions": getattr(r, "conditions", None),
                    "intent": getattr(r, "intent", None),
                    "interval_sec": getattr(r, "interval_sec", None),
                    "position_state": getattr(r, "position_state", None),
                    "action_params": getattr(r, "action_params", None),
                    "context": getattr(r, "context", None),
                }
            )
        return out

    # ── 写 ────────────────────────────────────────────────
    def create_rule(self, payload: Dict[str, Any]) -> int:
        account = payload.get("account")
        is_exit = payload.get("role") in ("stop_loss", "reduce")
        action_hint = (
            {
                "trigger_level": "L2",
                "action_on_trigger": "sell",
                "requires_agent": True,
            }
            if is_exit
            else {
                "trigger_level": "L1",
                "action_on_trigger": "buy",
                "requires_agent": True,
            }
        )
        rule = self.rule_repo.create_rule(
            symbol=payload["symbol"],
            conditions=payload["conditions"],
            context=payload.get("context"),
            created_by="agent",
            account=account,
            linked_account=account,
            intent=payload.get("intent"),
            action_hint=action_hint,
            action_params=payload.get("action_params"),
            position_state=payload.get("position_state"),
            interval_sec=payload.get("interval_sec"),
            plan_id=payload.get("plan_id"),
        )
        return rule.id

    def update_rule(self, rule_id: int, payload: Dict[str, Any]) -> None:
        fields = {
            "conditions": payload["conditions"],
            "intent": payload.get("intent"),
            "position_state": payload.get("position_state"),
            "interval_sec": payload.get("interval_sec"),
            "action_params": payload.get("action_params"),
            "context": payload.get("context"),
            "enabled": payload.get("enabled", True),
        }
        self.rule_repo.update_fields(rule_id, **fields)

    def retire_rule(self, rule_id: int, reason: str) -> None:
        rule = self.rule_repo.get_by_id(rule_id)
        old_context = (getattr(rule, "context", None) or "") if rule else ""
        banner = "[计划退役] %s" % reason
        self.rule_repo.update_fields(
            rule_id, enabled=False, context=(banner + "\n" + old_context).strip()
        )

    # ── 映射 + 审计 ────────────────────────────────────────
    def link_rule(self, plan_id: int, rule_id: int, role: str, symbol: str, batch: int = 0) -> None:
        self.plan_repo.record_rule_mapping(plan_id, rule_id, role, symbol, batch=batch)

    def record_audit(
        self, plan_id: int, rule_id: int, change_kind: str, before: Any, after: Any, reason: str
    ) -> None:
        try:
            self.change_repo.record(
                rule_id=rule_id,
                changed_by=AUDIT_CHANGED_BY,
                change_kind=AUDIT_CHANGE_KIND,
                before=before,
                after=after,
                reason="[plan %s] %s" % (plan_id, reason),
            )
        except Exception as e:  # noqa: BLE001 - 审计失败不阻断编译（与成交审计口径一致）
            logger.error("计划编译审计写入失败", plan_id=plan_id, rule_id=rule_id, error=str(e))
