"""账户级计划草稿修改与审核（REQ-261026140857-c192）"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from qs_plan.application.plan_generation_service import AccountPlanError
from qs_plan.domain.plan import (
    ItemConditionDraft,
    PlanItemDraft,
    validate_item_decision,
)


class AccountPlanDraftService:
    def __init__(self, *, unit_of_work_factory=None, now_fn=lambda: datetime.now(timezone.utc)):
        self._uow_factory = unit_of_work_factory
        self._now = now_fn

    def patch(
        self,
        *,
        plan_id: int,
        expected_version: int,
        item_patches: List[Dict[str, Any]],
        actor: str,
        decision_audit_id: Optional[str],
        reason: Optional[str],
    ) -> Dict[str, Any]:
        self._require_uow()
        self._require_agent_audit(actor, decision_audit_id)
        if not isinstance(item_patches, list) or not item_patches:
            raise AccountPlanError("PLAN_SPEC_INVALID", "item_patches 必须是非空数组")

        with self._uow_factory() as uow:
            plan, revision = self._lock_draft(uow, plan_id, expected_version)
            diffs = []
            for patch in item_patches:
                item_id = patch.get("item_id")
                if item_id is None:
                    raise AccountPlanError("PLAN_SPEC_INVALID", "item_patch.item_id 必填")
                item_version = uow.plans.get_item_version_for_revision(
                    revision_id=revision.id, item_id=int(item_id)
                )
                if item_version is None:
                    raise AccountPlanError(
                        "PLAN_SPEC_INVALID", "item_id 不属于当前 revision：%s" % item_id
                    )

                changed = {}
                for field in (
                    "action",
                    "horizon",
                    "target_weight",
                    "target_qty",
                    "thesis",
                    "invalidation",
                    "entry_valid_until",
                    "execution_batch",
                    "max_chase_pct",
                    "setup_type",
                ):
                    if field in patch:
                        setattr(item_version, field, patch[field])
                        changed[field] = patch[field]

                if "entry" in patch:
                    entry = patch["entry"] or {}
                    item_version.entry_combinator = (
                        entry.get("combinator") or item_version.entry_combinator
                    )
                    if "valid_until" in entry:
                        item_version.entry_valid_until = _as_datetime(entry["valid_until"])
                    self._replace_entry_conditions(uow, item_version, entry)
                    changed["entry"] = entry
                if "exit" in patch:
                    self._replace_exit_conditions(uow, item_version, patch["exit"] or {})
                    changed["exit"] = patch["exit"]

                revision.status = "reviewing"
                diffs.append({"item_id": int(item_id), "changes": changed})

            plan.lock_version = int(plan.lock_version or 1) + 1
            uow.plans.record_event(
                plan_id=plan.id,
                item_id=None,
                plan_version=revision.version,
                kind="spec_change",
                detail={"items": diffs},
                reason=reason or "修改账户计划草稿",
                actor=actor,
                decision_audit_id=decision_audit_id,
            )
            uow.commit()
            return {
                "plan_id": plan.id,
                "revision_id": revision.id,
                "draft_version": revision.version,
                "lock_version": plan.lock_version,
                "status": revision.status,
                "diff": diffs,
            }

    def apply(
        self,
        *,
        plan_id: int,
        expected_version: int,
        actor: str,
        decision_audit_id: Optional[str],
        reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        self._require_uow()
        self._require_agent_audit(actor, decision_audit_id)
        with self._uow_factory() as uow:
            plan, revision = self._lock_draft(uow, plan_id, expected_version)
            problems = []
            for item_version in uow.plans.list_item_versions_for_revision(revision.id):
                item = uow.plans.get_item(item_version.item_id)
                if item is None:
                    problems.append("计划项不存在：%s" % item_version.item_id)
                    continue
                draft = PlanItemDraft(
                    item_id=item.id,
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
                conditions = uow.plans.list_conditions(item_version.id)
                problems.extend(
                    validate_item_decision(
                        draft,
                        [
                            ItemConditionDraft(
                                item_id=item.id,
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
                    "计划项尚未完整，不能 approved",
                    {"reasons": [{"code": "ITEM_INVALID", "message": p} for p in problems]},
                )

            revision.status = "approved"
            revision.reviewed_by = actor
            revision.reviewed_at = self._now()
            plan.lock_version = int(plan.lock_version or 1) + 1
            uow.plans.record_event(
                plan_id=plan.id,
                item_id=None,
                plan_version=revision.version,
                kind="status_change",
                from_status="reviewing",
                to_status="approved",
                reason=reason or "审核通过账户计划 revision",
                actor=actor,
                decision_audit_id=decision_audit_id,
            )
            uow.commit()
            return {
                "plan_id": plan.id,
                "revision_id": revision.id,
                "version": revision.version,
                "status": "approved",
                "reviewed_by": revision.reviewed_by,
                "reviewed_at": revision.reviewed_at.isoformat(),
            }

    def _lock_draft(self, uow, plan_id: int, expected_version: int):
        plan = uow.plans.lock_plan_by_id(plan_id)
        if plan is None:
            raise AccountPlanError("PLAN_NOT_FOUND", "账户主计划不存在：%s" % plan_id)
        revision = uow.plans.lock_revision(plan_id=plan.id, revision_id=plan.draft_revision_id or 0)
        if revision is None or revision.version != expected_version:
            # 回带当前版本号，客户端可据此重读重试；draft_revision_id 为空（如已激活）时
            # 退回该计划最新版本号，避免回传 null 让客户端无从重试
            current = revision.version if revision is not None else uow.plans.max_version(plan.id)
            raise AccountPlanError(
                "VERSION_CONFLICT",
                "计划版本已变化，请重读后重试",
                {
                    "current_version": current,
                    "expected_version": expected_version,
                },
            )
        if revision.status not in ("draft", "reviewing"):
            raise AccountPlanError("PLAN_STATE_ILLEGAL", "只有 draft/reviewing revision 可以修改")
        return plan, revision

    def _replace_entry_conditions(self, uow, item_version, entry: Dict[str, Any]) -> None:
        conditions = entry.get("conditions") or []
        role = {
            "buy": "entry",
            "add": "add_position",
            "observe": "trend_observe",
        }.get(item_version.action, "entry")
        uow.plans.delete_conditions(item_version_id=item_version.id, roles=(role,))
        for index, condition in enumerate(conditions):
            uow.plans.add_condition(
                item_version_id=item_version.id,
                role=role,
                condition_type=condition.get("type"),
                params=condition.get("params") or {},
                sequence=index,
                invalidation_threshold_pct=condition.get("invalidation_threshold_pct"),
            )

    def _replace_exit_conditions(self, uow, item_version, exit_spec: Dict[str, Any]) -> None:
        uow.plans.delete_conditions(
            item_version_id=item_version.id, roles=("stop_loss", "reduce", "exit_reduce")
        )
        stop = exit_spec.get("stop_loss")
        if stop:
            uow.plans.add_condition(
                item_version_id=item_version.id,
                role="stop_loss",
                condition_type=stop.get("type"),
                params=stop.get("params") or {"value": stop.get("value")},
            )
        for index, batch in enumerate(exit_spec.get("reduce_plan") or []):
            uow.plans.add_condition(
                item_version_id=item_version.id,
                role="reduce",
                condition_type=batch.get("type") or "pnl_pct",
                params=(
                    batch.get("params")
                    or {
                        "pct": batch.get("at_pct"),
                        "direction": "above",
                        "sell_ratio": batch.get("sell_ratio", 1.0),
                    }
                ),
                batch=index,
            )
        for index, batch in enumerate(exit_spec.get("risk_reduce_plan") or []):
            uow.plans.add_condition(
                item_version_id=item_version.id,
                role="exit_reduce",
                condition_type=batch.get("type") or "pnl_pct",
                params=(
                    batch.get("params")
                    or {
                        "pct": batch.get("at_pct"),
                        "direction": "above",
                        "sell_ratio": batch.get("sell_ratio", 1.0),
                    }
                ),
                batch=index,
                invalidation_threshold_pct=batch.get("invalidation_threshold_pct"),
            )

    @staticmethod
    def _require_agent_audit(actor: str, decision_audit_id: Optional[str]) -> None:
        if actor == "agent" and not decision_audit_id:
            raise AccountPlanError(
                "DECISION_AUDIT_REQUIRED", "agent 修改必须提供 decision_audit_id"
            )

    def _require_uow(self) -> None:
        if self._uow_factory is None:
            raise AccountPlanError("PLAN_UOW_MISSING", "未注入 TradingPlanUnitOfWork")


def _as_datetime(value):
    if isinstance(value, str):
        return datetime.fromisoformat(value)
    return value
