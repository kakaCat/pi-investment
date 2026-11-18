"""账户级计划 readiness 与运行时对账（REQ-261026140857-c192）"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional

from qs_plan.application.account_plan_compiler import build_desired_rules, diff_rules
from qs_plan.application.plan_generation_service import AccountPlanError, is_data_fresh
from qs_plan.domain.plan import (
    STATUS_HOLDING,
    STATUS_REDUCING,
    ItemConditionDraft,
    PlanItemDraft,
    ReadinessReason,
    validate_item_decision,
)


class PlanReadinessService:
    def __init__(
        self,
        *,
        unit_of_work_factory=None,
        position_provider=None,
        position_state_provider=None,
        interval_sec: Optional[int] = None,
        now_fn=lambda: datetime.now(timezone.utc),
    ):
        self._uow_factory = unit_of_work_factory
        self._position_provider = position_provider
        self._position_state_provider = position_state_provider or (lambda symbol: "none")
        self._interval_sec = interval_sec
        self._now = now_fn

    def evaluate(self, *, account: str, trade_date: date, stage: str = "runtime") -> Dict[str, Any]:
        if self._uow_factory is None:
            raise AccountPlanError("PLAN_UOW_MISSING", "未注入 TradingPlanUnitOfWork")
        reasons: List[ReadinessReason] = []
        plan_id = None
        revision_id = None

        with self._uow_factory() as uow:
            plan = uow.plans.find_account_plan(account)
            if plan is None:
                reasons.append(ReadinessReason("REVISION_MISSING", "账户主计划不存在"))
            else:
                plan_id = plan.id
                revision = uow.plans.find_revision_for_day(
                    plan.id, trade_date, statuses=("draft", "reviewing", "approved", "active")
                )
                if revision is None:
                    reasons.append(ReadinessReason("REVISION_MISSING", "今日 revision 尚未生成"))
                else:
                    revision_id = revision.id
                    reasons.extend(self._revision_reasons(uow, plan, revision, stage))

            run_id = uow.runs.start_run(
                account=account,
                trade_date=trade_date,
                run_kind="readiness",
                idempotency_key=None,
                attempt=1,
            )
            run_reasons = [
                {"code": reason.code, "message": reason.message, "item_id": reason.item_id}
                for reason in reasons
            ]
            uow.runs.finish_run(
                run_id,
                status="succeeded" if not reasons else "failed",
                reasons=run_reasons,
                error=None if not reasons else "readiness_not_ready",
            )
            uow.commit()

        return {
            "ready": not reasons,
            "status": "ready" if not reasons else "not_ready",
            "account": account,
            "trade_date": trade_date.isoformat(),
            "plan_id": plan_id,
            "revision_id": revision_id,
            "run_id": run_id,
            "checked_at": self._now().isoformat(),
            "reasons": [
                {"code": reason.code, "message": reason.message, "item_id": reason.item_id}
                for reason in reasons
            ],
        }

    def _revision_reasons(self, uow, plan, revision, stage: str) -> List[ReadinessReason]:
        reasons: List[ReadinessReason] = []
        if not is_data_fresh(revision.data_as_of, revision.trade_date):
            reasons.append(ReadinessReason("DATA_STALE", "revision 行情数据时点已过期"))
        if stage == "activation":
            if revision.status != "approved":
                reasons.append(ReadinessReason("REVIEW_REQUIRED", "revision 尚未 approved"))
        elif revision.status != "active":
            reasons.append(ReadinessReason("REVIEW_REQUIRED", "revision 尚未激活"))

        item_versions = uow.plans.list_item_versions_for_revision(revision.id)
        if not item_versions:
            reasons.append(ReadinessReason("REVISION_MISSING", "revision 没有计划项"))
            return reasons

        conditions_by_item_version = {}
        for item_version in item_versions:
            item = uow.plans.get_item(item_version.item_id)
            if item is None:
                reasons.append(
                    ReadinessReason("ITEM_INVALID", "计划项不存在", item_version.item_id)
                )
                continue
            item_version.item = item
            conditions = uow.plans.list_conditions(item_version.id)
            conditions_by_item_version[item_version.id] = conditions
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
            problems = validate_item_decision(
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
            for message in problems:
                code = (
                    "ENTRY_INCOMPLETE"
                    if "入场" in message
                    else (
                        "EXIT_INCOMPLETE"
                        if "stop_loss" in message or "reduce" in message
                        else "ITEM_INVALID"
                    )
                )
                reasons.append(ReadinessReason(code, message, item.id))

        if stage == "runtime" and revision.status == "active":
            desired = build_desired_rules(
                plan_id=plan.id,
                plan_version=revision.version,
                account=plan.account,
                item_versions=item_versions,
                conditions_by_item_version=conditions_by_item_version,
                position_state_for=self._position_state_provider,
                interval_sec=self._interval_sec,
            )
            diff = diff_rules(desired=desired, managed=uow.rules.list_managed_rules(plan.id))
            if diff["create"]:
                reasons.append(
                    ReadinessReason("RULE_MISSING", "缺失 %d 条托管规则" % len(diff["create"]))
                )
            if diff["update"]:
                reasons.append(
                    ReadinessReason("RULE_DRIFT", "%d 条托管规则与计划不一致" % len(diff["update"]))
                )
            if diff["retire"]:
                reasons.append(
                    ReadinessReason("RULE_ORPHAN", "存在 %d 条计划外托管规则" % len(diff["retire"]))
                )
            reasons.extend(self._position_reasons(uow, plan))
        return reasons

    def _position_reasons(self, uow, plan) -> List[ReadinessReason]:
        if self._position_provider is None:
            return []
        reasons: List[ReadinessReason] = []
        try:
            raw_positions = self._position_provider.list_positions(account=plan.account)
        except Exception as exc:  # noqa: BLE001 - 不能把持仓读取失败当成无持仓
            return [
                ReadinessReason(
                    "POSITION_READ_FAILED",
                    "账户持仓读取失败：%s" % exc,
                )
            ]
        if raw_positions is None:
            return [ReadinessReason("POSITION_READ_FAILED", "账户持仓读取失败")]
        positions = {position.symbol: int(position.qty or 0) for position in raw_positions}
        items = uow.plans.list_open_items(plan.id)
        states = {
            state.item_id: state
            for state in uow.plans.list_item_states([item.id for item in items])
        }
        item_symbols = {item.symbol: item for item in items}
        for symbol, qty in positions.items():
            if qty > 0 and symbol not in item_symbols:
                reasons.append(ReadinessReason("POSITION_UNMANAGED", "持仓未纳入计划", None))
        for item in items:
            state = states.get(item.id)
            if state is None:
                reasons.append(ReadinessReason("ITEM_INVALID", "计划项缺少执行状态", item.id))
                continue
            if (
                state.state in (STATUS_HOLDING, STATUS_REDUCING)
                and positions.get(item.symbol, 0) <= 0
            ):
                reasons.append(
                    ReadinessReason("POSITION_MISMATCH", "计划项持仓状态与实际持仓不一致", item.id)
                )
            if (
                state.state in ("planned", "ready")
                and positions.get(item.symbol, 0) > 0
                and int(state.filled_qty or 0) == 0
            ):
                reasons.append(
                    ReadinessReason(
                        "POSITION_MISMATCH",
                        "实际持仓尚未回写计划成交状态",
                        item.id,
                    )
                )
        return reasons
