"""账户级计划原子激活（REQ-261026140857-c192）

preflight → item 规则 diff → 规则/映射/审计/revision 指针同一事务提交。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional

from qs_plan.application.account_plan_compiler import build_desired_rules, diff_rules
from qs_plan.application.plan_generation_service import AccountPlanError
from qs_plan.domain.plan import (
    ItemConditionDraft,
    PlanItemDraft,
    ReadinessReason,
    validate_item_decision,
)


class PlanActivationService:
    def __init__(
        self,
        *,
        unit_of_work_factory=None,
        position_state_provider: Optional[Callable[[str], str]] = None,
        interval_sec: Optional[int] = None,
        now_fn=lambda: datetime.now(timezone.utc),
    ):
        self._uow_factory = unit_of_work_factory
        self._position_state_provider = position_state_provider or (lambda symbol: "none")
        self._interval_sec = interval_sec
        self._now = now_fn

    def activate(
        self,
        *,
        plan_id: int,
        expected_version: int,
        actor: str,
        decision_audit_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        if self._uow_factory is None:
            raise AccountPlanError("PLAN_UOW_MISSING", "未注入 TradingPlanUnitOfWork")

        with self._uow_factory() as uow:
            plan = uow.plans.lock_plan_by_id(plan_id)
            if plan is None:
                raise AccountPlanError("PLAN_NOT_FOUND", "账户主计划不存在：%s" % plan_id)
            if plan.status in ("closed", "archived"):
                raise AccountPlanError("PLAN_STATE_ILLEGAL", "已关闭/归档计划不能激活")

            revision = uow.plans.lock_revision(
                plan_id=plan_id, revision_id=plan.draft_revision_id or 0
            )
            if revision is None or revision.version != expected_version:
                raise AccountPlanError("VERSION_CONFLICT", "计划版本已变化，请重读后重试")
            if revision.status != "approved":
                raise AccountPlanError("PLAN_REVIEW_REQUIRED", "revision 尚未 approved，不能激活")

            item_versions = uow.plans.list_item_versions_for_revision(revision.id)
            if not item_versions:
                raise AccountPlanError("PLAN_NOT_READY", "approved revision 没有计划项")

            problems = []
            conditions_by_item_version = {}
            drafts = []
            for item_version in item_versions:
                item = uow.plans.get_item(item_version.item_id)
                if item is None:
                    problems.append("计划项不存在：%s" % item_version.item_id)
                    continue
                item_version.item = item
                conditions = uow.plans.list_conditions(item_version.id)
                conditions_by_item_version[item_version.id] = conditions
                drafts.append(
                    PlanItemDraft(
                        item_id=item_version.item_id,
                        symbol=item.symbol,
                        action=item_version.action,
                        horizon=item_version.horizon,
                        target_weight=(
                            float(item_version.target_weight)
                            if item_version.target_weight is not None
                            else None
                        ),
                        target_qty=item_version.target_qty,
                        entry_combinator=item_version.entry_combinator,
                        thesis=item_version.thesis,
                        invalidation=item_version.invalidation,
                        entry_valid_until=item_version.entry_valid_until,
                        evidence=item_version.evidence or {},
                        setup_type=item_version.setup_type,
                    )
                )
                problems.extend(
                    validate_item_decision(
                        drafts[-1],
                        [
                            ItemConditionDraft(
                                item_id=condition.item_version_id and item_version.item_id,
                                role=condition.role,
                                condition_type=condition.condition_type,
                                params=condition.params or {},
                                batch=condition.batch,
                                sequence=condition.sequence,
                                invalidation_threshold_pct=condition.invalidation_threshold_pct,
                            )
                            for condition in conditions
                        ],
                        activation=True,
                        now=self._now(),
                    )
                )
            if problems:
                raise AccountPlanError(
                    "PLAN_NOT_READY",
                    "激活前校验失败",
                    {
                        "reasons": [
                            {"code": "ITEM_INVALID", "message": message} for message in problems
                        ]
                    },
                )

            states = {
                state.item_id: state
                for state in uow.plans.list_item_states(
                    [item_version.item_id for item_version in item_versions]
                )
            }
            ready_item_ids = []
            entry_roles = {"buy": "entry", "add": "add_position"}
            for item_version in item_versions:
                state = states.get(item_version.item_id)
                entry_role = entry_roles.get(item_version.action)
                if (
                    state is not None
                    and state.state == "planned"
                    and entry_role is not None
                    and any(
                        condition.role == entry_role
                        for condition in conditions_by_item_version[item_version.id]
                    )
                ):
                    state.state = "ready"
                    state.lock_version = int(state.lock_version or 1) + 1
                    ready_item_ids.append(item_version.item_id)

            desired = build_desired_rules(
                plan_id=plan.id,
                plan_version=revision.version,
                account=plan.account,
                item_versions=item_versions,
                conditions_by_item_version=conditions_by_item_version,
                position_state_for=self._position_state_provider,
                interval_sec=self._interval_sec,
                actor=actor,
            )
            managed = uow.rules.list_managed_rules(plan.id)
            diff = diff_rules(desired=desired, managed=managed)

            for item in diff["create"]:
                rule_id = uow.rules.create_rule(item["payload"])
                uow.rules.record_audit(
                    rule_id=rule_id,
                    changed_by=actor,
                    before=None,
                    after=_audit_snapshot(item["payload"]),
                    reason="计划激活创建规则",
                )
            for item in diff["update"]:
                uow.rules.update_rule(item["rule_id"], item["payload"])
                uow.rules.record_audit(
                    rule_id=item["rule_id"],
                    changed_by=actor,
                    before=item["from"],
                    after=_audit_snapshot(item["payload"]),
                    reason="计划激活更新规则",
                )
            for item in diff["retire"]:
                uow.rules.retire_rule(item["rule_id"], "计划 revision 更新，旧规则退役")
                uow.rules.record_audit(
                    rule_id=item["rule_id"],
                    changed_by=actor,
                    before=item["from"],
                    after={"enabled": False, "reason": "计划 revision 更新，旧规则退役"},
                    reason="计划激活退役规则",
                )

            uow.rules.supersede_current_revision(plan.id, exclude_revision_id=revision.id)
            uow.rules.activate_revision(revision.id)
            plan.current_revision_id = revision.id
            plan.draft_revision_id = None
            plan.status = "active"
            plan.lock_version = int(plan.lock_version or 1) + 1
            plan.activated_at = plan.activated_at or self._now()
            uow.plans.record_event(
                plan_id=plan.id,
                item_id=None,
                plan_version=revision.version,
                kind="compile",
                detail={
                    "create": len(diff["create"]),
                    "update": len(diff["update"]),
                    "retire": len(diff["retire"]),
                    "ready_item_ids": ready_item_ids,
                    "revision_status": "active",
                },
                reason="激活账户计划 revision",
                actor=actor,
                decision_audit_id=decision_audit_id,
            )
            uow.commit()

            return {
                "plan_id": plan.id,
                "revision_id": revision.id,
                "version": revision.version,
                "status": "active",
                "compiled": {
                    "create": len(diff["create"]),
                    "update": len(diff["update"]),
                    "retire": len(diff["retire"]),
                },
            }


def _audit_snapshot(payload: Dict[str, Any]) -> Dict[str, Any]:
    keys = (
        "symbol",
        "conditions",
        "intent",
        "position_state",
        "interval_sec",
        "action_params",
        "context",
        "plan_version",
        "item_id",
        "role",
        "batch",
    )
    return {key: payload.get(key) for key in keys}
