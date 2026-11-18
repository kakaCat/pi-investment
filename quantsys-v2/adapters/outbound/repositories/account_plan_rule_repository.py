"""账户级计划规则仓储（REQ-261026140857-c192）

与 AccountPlanRepository 共用调用方 session；不在仓储方法内 commit，保证激活是单事务。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from adapters.outbound.repositories.watch_rule_repository import WatchRule
from infrastructure.persistence.orm.models.trading_plan import (
    TradingPlanRule,
    TradingPlanVersion,
)
from infrastructure.persistence.orm.models.watch_todo import WatchRuleChange


class AccountPlanRuleRepository:
    def __init__(self, session: Session):
        self.session = session

    def list_managed_rules(self, plan_id: int) -> List[Dict[str, Any]]:
        mappings = (
            self.session.query(TradingPlanRule)
            .filter(TradingPlanRule.plan_id == plan_id)
            .filter(TradingPlanRule.item_id.isnot(None))
            .all()
        )
        out: List[Dict[str, Any]] = []
        for mapping in mappings:
            rule = self.session.get(WatchRule, int(mapping.rule_id))
            if rule is None:
                continue
            out.append(
                {
                    "rule_id": int(rule.id),
                    "item_id": int(mapping.item_id),
                    "role": mapping.role,
                    "batch": int(mapping.batch or 0),
                    "plan_version": (
                        int(mapping.plan_version) if mapping.plan_version is not None else None
                    ),
                    "symbol": rule.symbol,
                    "enabled": bool(rule.enabled),
                    "conditions": rule.conditions,
                    "intent": rule.intent,
                    "position_state": rule.position_state,
                    "interval_sec": rule.interval_sec,
                    "action_params": rule.action_params,
                    "context": rule.context,
                    "invalidation_threshold_pct": rule.invalidation_threshold_pct,
                }
            )
        return out

    def create_rule(self, payload: Dict[str, Any]) -> int:
        role = payload["role"]
        is_exit = role in ("stop_loss", "reduce", "exit_reduce")
        rule = WatchRule(
            symbol=payload["symbol"],
            conditions=payload["conditions"],
            context=payload.get("context"),
            created_by=payload.get("actor") or "agent",
            account=payload.get("account"),
            linked_account=payload.get("account"),
            intent=payload.get("intent"),
            action_hint={
                "trigger_level": "L2" if is_exit else "L1",
                "action_on_trigger": "sell" if is_exit else "buy",
                "requires_agent": True,
            },
            action_params=payload.get("action_params"),
            position_state=payload.get("position_state") or "none",
            interval_sec=payload.get("interval_sec"),
            plan_id=payload.get("plan_id"),
            item_id=payload.get("item_id"),
            invalidation_threshold_pct=payload.get("invalidation_threshold_pct"),
            rule_state="active",
            trigger_channel="agent",
            process_state="pending",
            engine="v2",
        )
        self.session.add(rule)
        self.session.flush()
        mapping = TradingPlanRule(
            plan_id=payload["plan_id"],
            role=role,
            symbol=payload["symbol"],
            batch=int(payload.get("batch") or 0),
            rule_id=int(rule.id),
            item_id=int(payload["item_id"]),
            plan_version=int(payload["plan_version"]),
        )
        self.session.add(mapping)
        self.session.flush()
        return int(rule.id)

    def update_rule(self, rule_id: int, payload: Dict[str, Any]) -> None:
        rule = self.session.get(WatchRule, int(rule_id))
        if rule is None:
            raise LookupError("托管规则不存在：%s" % rule_id)
        rule.symbol = payload["symbol"]
        rule.conditions = payload["conditions"]
        rule.context = payload.get("context")
        rule.intent = payload.get("intent")
        rule.action_params = payload.get("action_params")
        rule.position_state = payload.get("position_state") or "none"
        rule.interval_sec = payload.get("interval_sec")
        rule.plan_id = payload.get("plan_id")
        rule.item_id = payload.get("item_id")
        rule.invalidation_threshold_pct = payload.get("invalidation_threshold_pct")
        rule.enabled = True
        rule.rule_state = "active"
        rule.engine = "v2"
        self.session.flush()

    def retire_rule(self, rule_id: int, reason: str) -> None:
        rule = self.session.get(WatchRule, int(rule_id))
        if rule is None:
            return
        banner = "[计划退役] %s" % reason
        old_context = rule.context or ""
        rule.enabled = False
        rule.rule_state = "archived"
        rule.context = (banner + "\n" + old_context).strip()
        self.session.flush()

    def record_audit(
        self, *, rule_id: int, changed_by: str, before: Any, after: Any, reason: str
    ) -> None:
        if not str(reason or "").strip():
            raise ValueError("reason 必填：规则变更必须写明理由")
        self.session.add(
            WatchRuleChange(
                rule_id=int(rule_id),
                changed_by=changed_by,
                change_kind="plan_compile",
                before=before,
                after=after,
                reason=str(reason).strip(),
            )
        )
        self.session.flush()

    def supersede_current_revision(self, plan_id: int, exclude_revision_id: int) -> None:
        rows = (
            self.session.query(TradingPlanVersion)
            .filter(TradingPlanVersion.plan_id == plan_id)
            .filter(TradingPlanVersion.status == "active")
            .filter(TradingPlanVersion.id != exclude_revision_id)
            .all()
        )
        from datetime import datetime, timezone

        for row in rows:
            row.status = "superseded"
            row.superseded_at = datetime.now(timezone.utc)

    def activate_revision(self, revision_id: int) -> None:
        from datetime import datetime, timezone

        revision = self.session.get(TradingPlanVersion, int(revision_id))
        if revision is None:
            raise LookupError("revision 不存在：%s" % revision_id)
        revision.status = "active"
        revision.activated_at = datetime.now(timezone.utc)
