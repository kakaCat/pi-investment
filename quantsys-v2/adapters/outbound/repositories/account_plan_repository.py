"""账户级交易计划关系仓储（REQ-261026140857-c192）

仓储只使用调用方注入的 session，不自行 commit/close。事务边界由 TradingPlanUnitOfWork 控制。
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, Iterable, Optional, Sequence

from sqlalchemy import func, text
from sqlalchemy.orm import Session

from infrastructure.persistence.orm.models.trading_plan import (
    TradingPlan,
    TradingPlanCondition,
    TradingPlanEvent,
    TradingPlanFillReceipt,
    TradingPlanItem,
    TradingPlanItemState,
    TradingPlanItemVersion,
    TradingPlanRun,
    TradingPlanVersion,
)


class AccountPlanRepository:
    def __init__(self, session: Session):
        self.session = session

    # ── 主计划与 revision ───────────────────────────────────────
    def lock_account_plan(self, account: str) -> Optional[TradingPlan]:
        return (
            self.session.query(TradingPlan)
            .filter(TradingPlan.account == account)
            .filter(TradingPlan.plan_kind == "account")
            .filter(TradingPlan.status.notin_(("closed", "archived")))
            .with_for_update()
            .first()
        )

    def find_account_plan(self, account: str) -> Optional[TradingPlan]:
        return (
            self.session.query(TradingPlan)
            .filter(TradingPlan.account == account)
            .filter(TradingPlan.plan_kind == "account")
            .filter(TradingPlan.status.notin_(("closed", "archived")))
            .first()
        )

    def create_account_plan(self, *, account: str, actor: str) -> TradingPlan:
        plan = TradingPlan(
            account=account,
            name="%s 账户交易计划" % account,
            horizon=None,
            status="draft",
            spec=None,
            draft_spec=None,
            version=1,
            plan_kind="account",
            created_by=actor,
        )
        self.session.add(plan)
        self.session.flush()
        return plan

    def find_revision_for_day(
        self, plan_id: int, trade_date: date, statuses: Sequence[str]
    ) -> Optional[TradingPlanVersion]:
        return (
            self.session.query(TradingPlanVersion)
            .filter(TradingPlanVersion.plan_id == plan_id)
            .filter(TradingPlanVersion.trade_date == trade_date)
            .filter(TradingPlanVersion.status.in_(statuses))
            .order_by(TradingPlanVersion.version.desc())
            .first()
        )

    def max_version(self, plan_id: int) -> int:
        value = (
            self.session.query(func.max(TradingPlanVersion.version))
            .filter(TradingPlanVersion.plan_id == plan_id)
            .scalar()
        )
        return int(value or 0)

    def add_version(
        self,
        *,
        plan_id: int,
        version: int,
        trade_date: date,
        status: str,
        data_as_of,
        market_gate: Optional[Dict[str, Any]],
        risk_budget: Optional[Dict[str, Any]],
        generation_key: Optional[str],
        created_by: str,
    ) -> TradingPlanVersion:
        row = TradingPlanVersion(
            plan_id=plan_id,
            version=version,
            trade_date=trade_date,
            status=status,
            data_as_of=data_as_of,
            market_gate=market_gate or {},
            risk_budget=risk_budget or {},
            generation_key=generation_key,
            created_by=created_by,
        )
        self.session.add(row)
        self.session.flush()
        return row

    def set_draft_revision(self, plan: TradingPlan, revision_id: int) -> None:
        plan.draft_revision_id = revision_id
        plan.lock_version = int(plan.lock_version or 1) + 1
        if plan.current_revision_id is None and plan.status == "draft":
            plan.status = "draft"

    def record_event(
        self,
        *,
        plan_id: int,
        item_id: Optional[int],
        plan_version: Optional[int],
        kind: str,
        detail: Optional[Dict[str, Any]] = None,
        reason: Optional[str] = None,
        actor: str = "system",
        decision_audit_id: Optional[str] = None,
        from_status: Optional[str] = None,
        to_status: Optional[str] = None,
    ) -> None:
        self.session.add(
            TradingPlanEvent(
                plan_id=plan_id,
                item_id=item_id,
                plan_version=plan_version,
                kind=kind,
                detail=detail or {},
                reason=reason,
                actor=actor,
                decision_audit_id=decision_audit_id,
                from_status=from_status,
                to_status=to_status,
            )
        )

    def lock_plan_by_id(self, plan_id: int) -> Optional[TradingPlan]:
        return (
            self.session.query(TradingPlan)
            .filter(TradingPlan.id == int(plan_id))
            .filter(TradingPlan.plan_kind == "account")
            .with_for_update()
            .first()
        )

    def lock_revision(self, *, plan_id: int, revision_id: int) -> Optional[TradingPlanVersion]:
        return (
            self.session.query(TradingPlanVersion)
            .filter(TradingPlanVersion.id == int(revision_id))
            .filter(TradingPlanVersion.plan_id == int(plan_id))
            .with_for_update()
            .first()
        )

    def find_version_by_number(self, plan_id: int, version: int) -> Optional[TradingPlanVersion]:
        return (
            self.session.query(TradingPlanVersion)
            .filter(TradingPlanVersion.plan_id == int(plan_id))
            .filter(TradingPlanVersion.version == int(version))
            .first()
        )

    def list_item_versions_for_revision(self, revision_id: int) -> list[TradingPlanItemVersion]:
        return (
            self.session.query(TradingPlanItemVersion)
            .filter(TradingPlanItemVersion.revision_id == int(revision_id))
            .order_by(TradingPlanItemVersion.id)
            .all()
        )

    def get_item(self, item_id: int) -> Optional[TradingPlanItem]:
        return self.session.get(TradingPlanItem, int(item_id))

    # ── 计划项 ────────────────────────────────────────────────
    def list_open_items(self, plan_id: int) -> list[TradingPlanItem]:
        return (
            self.session.query(TradingPlanItem)
            .filter(TradingPlanItem.plan_id == plan_id)
            .filter(TradingPlanItem.closed_at.is_(None))
            .with_for_update()
            .all()
        )

    def create_item(
        self, *, plan_id: int, symbol: str, legacy_plan_id: Optional[int] = None
    ) -> TradingPlanItem:
        item = TradingPlanItem(plan_id=plan_id, symbol=symbol, legacy_plan_id=legacy_plan_id)
        self.session.add(item)
        self.session.flush()
        return item

    def latest_item_version(self, item_id: int) -> Optional[TradingPlanItemVersion]:
        return (
            self.session.query(TradingPlanItemVersion)
            .join(TradingPlanVersion, TradingPlanItemVersion.revision_id == TradingPlanVersion.id)
            .filter(TradingPlanItemVersion.item_id == item_id)
            .order_by(TradingPlanVersion.version.desc(), TradingPlanItemVersion.id.desc())
            .first()
        )

    def list_conditions(self, item_version_id: int) -> list[TradingPlanCondition]:
        return (
            self.session.query(TradingPlanCondition)
            .filter(TradingPlanCondition.item_version_id == item_version_id)
            .order_by(
                TradingPlanCondition.role, TradingPlanCondition.batch, TradingPlanCondition.sequence
            )
            .all()
        )

    def get_item_version_for_revision(
        self, *, revision_id: int, item_id: int
    ) -> Optional[TradingPlanItemVersion]:
        return (
            self.session.query(TradingPlanItemVersion)
            .filter(TradingPlanItemVersion.revision_id == int(revision_id))
            .filter(TradingPlanItemVersion.item_id == int(item_id))
            .first()
        )

    def delete_conditions(self, *, item_version_id: int, roles: Sequence[str]) -> None:
        self.session.query(TradingPlanCondition).filter(
            TradingPlanCondition.item_version_id == int(item_version_id),
            TradingPlanCondition.role.in_(list(roles)),
        ).delete(synchronize_session=False)
        self.session.flush()

    def add_item_version(
        self,
        *,
        revision_id: int,
        item_id: int,
        action: str,
        horizon: str,
        target_weight,
        target_qty,
        execution_batch: Optional[int],
        max_chase_pct: Optional[float],
        entry_combinator: str,
        thesis: str,
        invalidation: str,
        entry_valid_until,
        evidence: Dict[str, Any],
        setup_type: Optional[str] = None,
    ) -> TradingPlanItemVersion:
        row = TradingPlanItemVersion(
            revision_id=revision_id,
            item_id=item_id,
            action=action,
            setup_type=setup_type,
            horizon=horizon,
            target_weight=target_weight,
            target_qty=target_qty,
            execution_batch=execution_batch,
            max_chase_pct=max_chase_pct,
            entry_combinator=entry_combinator,
            thesis=thesis,
            invalidation=invalidation,
            entry_valid_until=entry_valid_until,
            evidence=evidence or {},
        )
        self.session.add(row)
        self.session.flush()
        return row

    def add_condition(
        self,
        *,
        item_version_id: int,
        role: str,
        condition_type: str,
        params: Dict[str, Any],
        batch: int = 0,
        sequence: int = 0,
        invalidation_threshold_pct=None,
    ) -> TradingPlanCondition:
        row = TradingPlanCondition(
            item_version_id=item_version_id,
            role=role,
            condition_type=condition_type,
            params=params or {},
            batch=batch,
            sequence=sequence,
            invalidation_threshold_pct=invalidation_threshold_pct,
        )
        self.session.add(row)
        self.session.flush()
        return row

    def list_item_states(self, item_ids: Iterable[int]) -> list[TradingPlanItemState]:
        ids = [int(item_id) for item_id in item_ids]
        if not ids:
            return []
        return (
            self.session.query(TradingPlanItemState)
            .filter(TradingPlanItemState.item_id.in_(ids))
            .with_for_update()
            .all()
        )

    def upsert_item_state(
        self,
        *,
        item_id: int,
        state: str,
        target_qty: Optional[int],
        existing: Optional[TradingPlanItemState] = None,
    ) -> TradingPlanItemState:
        row = existing
        if row is None:
            row = self.session.get(TradingPlanItemState, item_id)
        if row is None:
            row = TradingPlanItemState(item_id=item_id, state=state, target_qty=target_qty)
            self.session.add(row)
        elif target_qty is not None:
            row.target_qty = target_qty
        self.session.flush()
        return row

    def get_fill_receipt(self, trade_id: str) -> Optional[TradingPlanFillReceipt]:
        return self.session.get(TradingPlanFillReceipt, str(trade_id))

    def add_fill_receipt(
        self,
        *,
        trade_id: str,
        plan_id: int,
        item_id: int,
        plan_version: int,
        side: str,
        qty: int,
        remaining_qty: Optional[int],
    ) -> TradingPlanFillReceipt:
        row = TradingPlanFillReceipt(
            trade_id=str(trade_id),
            plan_id=int(plan_id),
            item_id=int(item_id),
            plan_version=int(plan_version),
            side=side,
            qty=int(qty),
            remaining_qty=remaining_qty,
        )
        self.session.add(row)
        self.session.flush()
        return row

    def lock_item_state(self, item_id: int) -> Optional[TradingPlanItemState]:
        return (
            self.session.query(TradingPlanItemState)
            .filter(TradingPlanItemState.item_id == int(item_id))
            .with_for_update()
            .first()
        )

    def item_sold_qty(self, item_id: int) -> int:
        value = (
            self.session.query(func.coalesce(func.sum(TradingPlanFillReceipt.qty), 0))
            .filter(TradingPlanFillReceipt.item_id == int(item_id))
            .filter(TradingPlanFillReceipt.side == "sell")
            .scalar()
        )
        return int(value or 0)

    def attribute_simulation_trade(
        self, *, trade_id: str, plan_id: int, item_id: int, plan_version: int
    ) -> None:
        self.session.execute(
            text(
                "UPDATE quant.simulation_trades SET plan_id=:plan_id, item_id=:item_id, "
                "plan_version=:plan_version WHERE id = CAST(:trade_id AS integer)"
            ),
            {
                "plan_id": int(plan_id),
                "item_id": int(item_id),
                "plan_version": int(plan_version),
                "trade_id": str(trade_id),
            },
        )


class PlanRunRepository:
    def __init__(self, session: Session):
        self.session = session

    def start_run(
        self,
        *,
        account: str,
        trade_date: date,
        run_kind: str,
        idempotency_key: Optional[str],
        attempt: int,
    ) -> int:
        row = TradingPlanRun(
            account=account,
            trade_date=trade_date,
            run_kind=run_kind,
            idempotency_key=idempotency_key,
            attempt=attempt,
            status="running",
        )
        self.session.add(row)
        self.session.flush()
        return int(row.id)

    def finish_run(
        self, run_id: int, *, status: str, reasons: Sequence[Dict[str, Any]], error: Optional[str]
    ) -> None:
        row = self.session.get(TradingPlanRun, run_id)
        if row is None:
            raise LookupError("运行记录不存在：%s" % run_id)
        row.status = status
        row.reasons = list(reasons or [])
        row.error = error
        self.session.flush()
