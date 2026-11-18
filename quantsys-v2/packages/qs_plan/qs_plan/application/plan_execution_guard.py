"""计划归因交易的执行前硬校验。"""

from __future__ import annotations

import re
from datetime import date, datetime, timezone
from typing import Any, Callable, Dict, Optional

from sqlalchemy import text

from qs_plan.application.plan_generation_service import AccountPlanError
from qs_plan.application.plan_readiness_service import PlanReadinessService


class PlanExecutionGuard:
    def __init__(
        self,
        *,
        unit_of_work_factory=None,
        readiness_service_factory: Optional[Callable[[str], Any]] = None,
        now_date: Callable[[], date] = date.today,
        now_fn: Optional[Callable[[], datetime]] = None,
    ):
        self._uow_factory = unit_of_work_factory
        self._readiness_service_factory = readiness_service_factory
        self._now_date = now_date
        self._now = now_fn or (lambda: datetime.now(timezone.utc))

    def validate(
        self,
        *,
        account: str,
        action: str,
        symbol: str,
        reason: Optional[str],
        plan_id: Optional[int],
        item_id: Optional[int],
        plan_version: Optional[int],
        signal_grade: Optional[str],
        decision_audit_id: Optional[str],
        execute_at: Optional[str] = None,
        price: Optional[float] = None,
    ) -> Dict[str, Any]:
        action = str(action or "").upper()
        supplied = (plan_id, item_id, plan_version)
        complete = all(value is not None for value in supplied)
        if action != "BUY" and not complete:
            return {"required": False}
        referenced = bool(re.search(r"(?:计划|plan)\s*#\s*\d+", reason or "", re.IGNORECASE))
        if not any(value is not None for value in supplied) and not referenced:
            return {"required": False}
        if not complete:
            raise AccountPlanError(
                "PLAN_ATTRIBUTION_REQUIRED",
                "计划交易必须同时提供 plan_id/item_id/plan_version",
            )
        if action == "BUY":
            if execute_at is not None:
                raise AccountPlanError(
                    "PLAN_PENDING_UNSUPPORTED",
                    "计划挂单尚未支持归因持久化，禁止转为普通挂单",
                )
            if str(signal_grade or "").upper() not in ("A", "B"):
                raise AccountPlanError(
                    "SIGNAL_GRADE_NOT_ALLOWED",
                    "计划买入必须提供 A/B 级信号，C 级或缺省禁止买入",
                )
            if not str(decision_audit_id or "").strip():
                raise AccountPlanError(
                    "DECISION_AUDIT_REQUIRED",
                    "计划买入必须提供事前 decision_audit_id",
                )
        if self._uow_factory is None:
            raise AccountPlanError("PLAN_UOW_MISSING", "未注入 TradingPlanUnitOfWork")

        with self._uow_factory() as uow:
            plan = uow.plans.lock_plan_by_id(int(plan_id))
            if plan is None or plan.account != account:
                raise AccountPlanError("PLAN_NOT_FOUND", "计划与交易账户不匹配")
            revision = uow.plans.lock_revision(
                plan_id=plan.id, revision_id=plan.current_revision_id or 0
            )
            if (
                revision is None
                or revision.status != "active"
                or revision.version != int(plan_version)
            ):
                raise AccountPlanError(
                    "PLAN_VERSION_STALE", "计划不是当前激活版本，请重读后再交易"
                )
            item_version = uow.plans.get_item_version_for_revision(
                revision_id=revision.id, item_id=int(item_id)
            )
            item = uow.plans.get_item(int(item_id))
            if item_version is None or item is None or item.symbol.split(".")[0] != symbol.split(".")[0]:
                raise AccountPlanError(
                    "PLAN_ITEM_MISMATCH", "计划项与交易标的不匹配"
                )
            if action == "BUY" and item_version.action not in ("buy", "add"):
                raise AccountPlanError(
                    "PLAN_STATE_ILLEGAL", "当前计划项不允许新增买入"
                )
            if action == "BUY":
                self._validate_entry_constraints(uow, item_version, price)
                self._validate_batch(uow, plan, item_version)

        if action == "BUY":
            readiness_service = (
                self._readiness_service_factory(account)
                if self._readiness_service_factory is not None
                else PlanReadinessService(unit_of_work_factory=self._uow_factory)
            )
            readiness = readiness_service.evaluate(
                account=account, trade_date=self._now_date(), stage="runtime"
            )
            if not readiness.get("ready"):
                raise AccountPlanError(
                    "PLAN_NOT_READY",
                    "计划 readiness 未通过，禁止新增买入",
                    {"reasons": readiness.get("reasons") or []},
                )
        return {
            "required": True,
            "plan_id": int(plan_id),
            "item_id": int(item_id),
            "plan_version": int(plan_version),
        }

    def _validate_entry_constraints(self, uow, item_version, price: Optional[float]) -> None:
        if item_version.execution_batch is None or int(item_version.execution_batch) <= 0:
            raise AccountPlanError(
                "PLAN_BATCH_REQUIRED", "计划买入必须配置正整数 execution_batch"
            )
        valid_until = item_version.entry_valid_until
        if valid_until is None:
            raise AccountPlanError(
                "ENTRY_VALID_UNTIL_REQUIRED", "计划买入必须配置入场有效期"
            )
        if valid_until.tzinfo is None:
            valid_until = valid_until.replace(tzinfo=timezone.utc)
        if valid_until <= self._now():
            raise AccountPlanError("ENTRY_EXPIRED", "计划入场条件已过期")
        conditions = uow.plans.list_conditions(item_version.id)
        entry_role = "add_position" if item_version.action == "add" else "entry"
        thresholds = [
            float((condition.params or {}).get("price"))
            for condition in conditions
            if condition.role == entry_role
            and condition.condition_type == "price_break"
            and (condition.params or {}).get("direction") == "above"
            and (condition.params or {}).get("price") is not None
        ]
        if not thresholds:
            return
        if item_version.max_chase_pct is None or float(item_version.max_chase_pct) < 0:
            raise AccountPlanError(
                "ENTRY_CHASE_LIMIT_REQUIRED", "price_break 买入必须配置非负 max_chase_pct"
            )
        if isinstance(price, bool) or not isinstance(price, (int, float)) or float(price) <= 0:
            raise AccountPlanError(
                "ENTRY_PRICE_REQUIRED", "price_break 买入必须提供有效决策价 price"
            )
        threshold = thresholds[0]
        max_price = threshold * (1 + float(item_version.max_chase_pct) / 100.0)
        if float(price) > max_price + 1e-9:
            raise AccountPlanError(
                "ENTRY_CHASE_EXCEEDED",
                "决策价 %.4f 超过入场阈值 %.4f 的追高上限 %.4f（max_chase_pct=%.3f%%）"
                % (float(price), threshold, max_price, float(item_version.max_chase_pct)),
                {
                    "price": float(price),
                    "threshold": threshold,
                    "max_price": max_price,
                    "max_chase_pct": float(item_version.max_chase_pct),
                },
            )

    def _validate_batch(self, uow, plan, item_version) -> None:
        batch = int(item_version.execution_batch)
        trade_date = self._now_date()
        params = {
            "account": plan.account,
            "plan_id": plan.id,
            "trade_date": trade_date,
            "batch": batch,
        }
        join = (
            "FROM quant.simulation_trades t "
            "JOIN quant.trading_plan_item_versions iv ON iv.item_id=t.item_id "
            "JOIN quant.trading_plan_versions v ON v.id=iv.revision_id "
            "AND v.plan_id=t.plan_id AND v.version=t.plan_version "
            "WHERE t.account_name=:account AND t.plan_id=:plan_id "
            "AND iv.execution_batch IS NOT NULL AND iv.execution_batch<>:batch "
        )
        same_day = uow.session.execute(
            text("SELECT 1 " + join + "AND t.trade_date=:trade_date LIMIT 1"),
            params,
        ).scalar()
        if same_day:
            raise AccountPlanError(
                "PLAN_BATCH_CONFLICT",
                "今日已执行其他批次，禁止跨批买入",
                {"trade_date": trade_date.isoformat(), "execution_batch": batch},
            )
        previous = uow.session.execute(
            text(
                "SELECT max(t.trade_date) " + join + "AND t.trade_date<:trade_date"
            ),
            params,
        ).scalar()
        if previous is not None and (trade_date - previous).days < 7:
            raise AccountPlanError(
                "PLAN_BATCH_INTERVAL",
                "不同批次至少间隔 7 天",
                {
                    "trade_date": trade_date.isoformat(),
                    "previous_batch_trade_date": previous.isoformat(),
                    "execution_batch": batch,
                },
            )
