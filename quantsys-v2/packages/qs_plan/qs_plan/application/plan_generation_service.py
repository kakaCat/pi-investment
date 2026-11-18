"""账户级每日计划生成（REQ-261026140857-c192）

provider 在数据库写事务外执行；revision、items、conditions、states、event 和 run 成功状态在同一事务内落库。
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Dict, Optional, Sequence

from sqlalchemy.exc import IntegrityError

from qs_plan.domain.plan import (
    ItemConditionDraft,
    PlanItemDraft,
    STATUS_HOLDING,
    STATUS_REDUCING,
    initial_item_state,
    validate_item_decision,
    validate_items_unique_open,
)

PENDING_REVISION_STATUSES = ("draft", "reviewing", "approved", "active")


class AccountPlanError(Exception):
    def __init__(self, code: str, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


def is_data_fresh(data_as_of, trade_date: date) -> bool:
    """盘前允许使用最近一个交易日的数据，拒绝未来数据和漏同步的旧数据。"""
    if data_as_of is None:
        return False
    data_date = data_as_of.date()
    if data_date > trade_date:
        return False
    try:
        from qs_ops.application.services.trading_day_guard import TradingDayGuard

        def is_trading_day(value: date) -> bool:
            return bool(TradingDayGuard.is_trading_day(value))

    except Exception:  # noqa: BLE001 - 交易日组件不可用时退化为工作日

        def is_trading_day(value: date) -> bool:
            return value.weekday() < 5

    if not is_trading_day(data_date):
        return False
    previous = trade_date - timedelta(days=1)
    while previous >= trade_date - timedelta(days=14) and not is_trading_day(previous):
        previous -= timedelta(days=1)
    return previous <= data_date <= trade_date


def _condition_view(condition: ItemConditionDraft) -> Dict[str, Any]:
    return {
        "item_id": condition.item_id,
        "role": condition.role,
        "condition_type": condition.condition_type,
        "params": condition.params,
        "batch": condition.batch,
        "sequence": condition.sequence,
    }


def _copy_conditions_for_item(conditions, item_id: int):
    """把上一 revision 的条件行复制为当前 item 的领域条件。"""
    return [
        ItemConditionDraft(
            item_id=item_id,
            role=condition.role,
            condition_type=condition.condition_type,
            params=dict(condition.params or {}),
            batch=condition.batch,
            sequence=condition.sequence,
            invalidation_threshold_pct=condition.invalidation_threshold_pct,
        )
        for condition in conditions or []
    ]


def _infer_setup_type(entry_conditions, action: str) -> str:
    if action == "reduce_risk":
        return "risk_off"
    if action == "observe":
        return "observe"
    types = {condition.get("type") for condition in entry_conditions or []}
    if "staged_break" in types or "volume_surge" in types:
        return "breakout"
    if "ma_break" in types:
        return "trend_follow"
    if "rsi" in types:
        return "mean_reversion"
    if "price_break" in types:
        directions = {
            (condition.get("params") or {}).get("direction")
            for condition in entry_conditions
            if condition.get("type") == "price_break"
        }
        if directions == {"below"}:
            return "pullback"
        return "breakout"
    return "custom"


class PlanGenerationService:
    def __init__(
        self,
        decision_provider=None,
        position_provider=None,
        unit_of_work_factory=None,
        now_fn=lambda: datetime.now(timezone.utc),
    ):
        self._decision_provider = decision_provider
        self._position_provider = position_provider
        self._uow_factory = unit_of_work_factory
        self._now = now_fn

    def generate(
        self,
        *,
        account: str,
        trade_date: date,
        actor: str,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not account:
            raise AccountPlanError("PLAN_ACCOUNT_REQUIRED", "account 必填")
        if not isinstance(trade_date, date):
            raise AccountPlanError("PLAN_SPEC_INVALID", "trade_date 必须是 date")
        if self._decision_provider is None:
            raise AccountPlanError("PLAN_PROVIDER_MISSING", "未注入 PortfolioDecisionProvider")
        if self._position_provider is None:
            raise AccountPlanError("PLAN_PROVIDER_MISSING", "未注入 PositionProvider")
        if self._uow_factory is None:
            raise AccountPlanError("PLAN_UOW_MISSING", "未注入 TradingPlanUnitOfWork")

        run_id = self._start_run(
            account=account, trade_date=trade_date, idempotency_key=idempotency_key
        )
        try:
            decision = self._decision_provider.build(account=account, trade_date=trade_date)
            positions = self._position_provider.list_positions(account=account)
            result = self._generate_revision(
                account=account,
                trade_date=trade_date,
                actor=actor,
                idempotency_key=idempotency_key,
                decision=decision,
                positions=positions,
                run_id=run_id,
            )
            return result
        except Exception as exc:
            code = getattr(exc, "code", type(exc).__name__)
            self._finish_run(run_id, status="failed", error="%s: %s" % (code, exc))
            raise

    def _start_run(self, *, account: str, trade_date: date, idempotency_key: Optional[str]) -> int:
        attempt = 1
        while True:
            try:
                with self._uow_factory() as uow:
                    run_id = uow.runs.start_run(
                        account=account,
                        trade_date=trade_date,
                        run_kind="generate",
                        idempotency_key=idempotency_key,
                        attempt=attempt,
                    )
                    uow.commit()
                    return run_id
            except IntegrityError as exc:
                if "uq_trading_plan_runs_idempotency_attempt" not in str(exc):
                    raise
                attempt += 1

    def _finish_run(
        self,
        run_id: int,
        *,
        status: str,
        reasons: Optional[Sequence[Dict[str, Any]]] = None,
        error: Optional[str] = None,
    ) -> None:
        try:
            with self._uow_factory() as uow:
                uow.runs.finish_run(run_id, status=status, reasons=reasons or [], error=error)
                uow.commit()
        except Exception:
            # 运行记录补写失败不能掩盖生成失败的原始异常。
            pass

    def _generate_revision(
        self,
        *,
        account: str,
        trade_date: date,
        actor: str,
        idempotency_key: Optional[str],
        decision,
        positions,
        run_id: int,
    ) -> Dict[str, Any]:
        if decision.account != account:
            raise AccountPlanError("PLAN_ACCOUNT_MISMATCH", "组合决策账户与请求账户不一致")
        if decision.trade_date != trade_date:
            raise AccountPlanError("PLAN_DATA_STALE", "组合决策交易日与请求交易日不一致")
        if not is_data_fresh(decision.data_as_of, trade_date):
            raise AccountPlanError(
                "PLAN_DATA_STALE",
                "行情 data_as_of=%s 不是最近有效交易日，不能用于 trade_date=%s"
                % (decision.data_as_of.date(), trade_date),
            )

        targets_by_symbol = {target.symbol: target for target in decision.targets}
        positions_by_symbol = {position.symbol: int(position.qty or 0) for position in positions}
        symbols = sorted(set(targets_by_symbol) | set(positions_by_symbol))

        with self._uow_factory() as uow:
            plan = uow.plans.lock_account_plan(account)
            if plan is None:
                plan = uow.plans.create_account_plan(account=account, actor=actor)

            existing = uow.plans.find_revision_for_day(
                plan.id, trade_date, statuses=PENDING_REVISION_STATUSES
            )
            if existing is not None:
                uow.runs.finish_run(run_id, status="succeeded", reasons=[], error=None)
                uow.commit()
                return {
                    "plan_id": plan.id,
                    "revision_id": existing.id,
                    "version": existing.version,
                    "status": existing.status,
                    "existing": True,
                    "run_id": run_id,
                }

            next_version = (uow.plans.max_version(plan.id) or 0) + 1
            revision = uow.plans.add_version(
                plan_id=plan.id,
                version=next_version,
                trade_date=trade_date,
                status="draft",
                data_as_of=decision.data_as_of,
                market_gate=decision.market_gate,
                risk_budget=decision.risk_budget,
                generation_key=idempotency_key,
                created_by=actor,
            )
            open_items = uow.plans.list_open_items(plan.id)
            item_by_symbol = {item.symbol: item for item in open_items}
            states_by_item = {
                state.item_id: state
                for state in uow.plans.list_item_states([item.id for item in open_items])
            }

            created_items = 0
            reused_items = 0
            item_drafts = []
            condition_drafts = []
            for symbol in symbols:
                target = targets_by_symbol.get(symbol)
                position_qty = positions_by_symbol.get(symbol, 0)
                if target is None and position_qty <= 0:
                    continue

                item = item_by_symbol.get(symbol)
                if item is None:
                    item = uow.plans.create_item(plan_id=plan.id, symbol=symbol)
                    created_items += 1
                else:
                    reused_items += 1

                previous_version = uow.plans.latest_item_version(item.id)
                previous_conditions = (
                    uow.plans.list_conditions(previous_version.id) if previous_version else []
                )
                previous_by_role = {}
                for condition in _copy_conditions_for_item(previous_conditions, item.id):
                    previous_by_role.setdefault(condition.role, []).append(condition)

                if target is None:
                    action = "hold"
                    horizon = previous_version.horizon if previous_version else "swing"
                    target_weight = previous_version.target_weight if previous_version else None
                    target_qty = position_qty or (
                        previous_version.target_qty if previous_version else None
                    )
                    thesis = previous_version.thesis if previous_version else "组合外持仓管理"
                    invalidation = (
                        previous_version.invalidation if previous_version else "持仓处置待复核"
                    )
                    entry_valid_until = (
                        previous_version.entry_valid_until if previous_version else None
                    )
                    combinator = previous_version.entry_combinator if previous_version else "all_of"
                    entry_conditions = previous_by_role.get("entry", [])
                    stop_conditions = previous_by_role.get("stop_loss", [])
                    reduce_conditions = previous_by_role.get("reduce", [])
                    evidence = previous_version.evidence if previous_version else {}
                    setup_type = previous_version.setup_type if previous_version else None
                else:
                    previous_state = states_by_item.get(item.id)
                    action = target.action or (
                        "hold"
                        if previous_state
                        and previous_state.state in (STATUS_HOLDING, STATUS_REDUCING)
                        else "buy"
                    )
                    if action == "add" and position_qty <= 0:
                        raise AccountPlanError(
                            "PLAN_SPEC_INVALID",
                            "add 计划项必须有真实持仓，不能按空仓加仓：%s" % symbol,
                        )
                    if action == "reduce_risk" and position_qty <= 0:
                        raise AccountPlanError(
                            "PLAN_SPEC_INVALID",
                            "reduce_risk 计划项必须有真实持仓，不能按空仓减仓：%s" % symbol,
                        )
                    horizon = target.horizon
                    target_weight = target.target_weight
                    target_qty = target.target_qty
                    thesis = target.thesis or "组合决策目标"
                    invalidation = target.invalidation or "组合目标失效"
                    entry_valid_until = target.entry_valid_until
                    combinator = target.entry_combinator or "all_of"
                    setup_type = target.setup_type or _infer_setup_type(
                        target.entry_conditions, action
                    )
                    entry_role = {
                        "buy": "entry",
                        "add": "add_position",
                        "observe": "trend_observe",
                    }.get(action, "entry")
                    entry_conditions = [
                        ItemConditionDraft(
                            item_id=item.id,
                            role=entry_role,
                            condition_type=condition.get("type"),
                            params=condition.get("params") or {},
                            sequence=index,
                            invalidation_threshold_pct=condition.get("invalidation_threshold_pct"),
                        )
                        for index, condition in enumerate(target.entry_conditions or [])
                    ] or previous_by_role.get(entry_role, [])
                    stop_conditions = (
                        [
                            ItemConditionDraft(
                                item_id=item.id,
                                role="stop_loss",
                                condition_type=(target.stop_loss or {}).get("type"),
                                params=(
                                    (target.stop_loss or {}).get("params")
                                    or {"value": (target.stop_loss or {}).get("value")}
                                ),
                            )
                        ]
                        if target.stop_loss
                        else previous_by_role.get("stop_loss", [])
                    )
                    reduce_role = "exit_reduce" if action == "reduce_risk" else "reduce"
                    reduce_conditions = [
                        ItemConditionDraft(
                            item_id=item.id,
                            role=reduce_role,
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
                            sequence=0,
                        )
                        for index, batch in enumerate(target.reduce_plan or [])
                    ] or previous_by_role.get(reduce_role, [])
                    evidence = target.evidence

                # 守卫要求 buy/add 必须带入场有效期（ENTRY_VALID_UNTIL_REQUIRED）；
                # provider 未提供时按 horizon 给默认值：day→当日 15:00（Asia/Shanghai），
                # swing→T+3 15:00。历史生成器从未写入该字段，曾致全部计划项买入 422。
                if entry_valid_until is None and action in ("buy", "add"):
                    try:
                        from zoneinfo import ZoneInfo

                        _tz = ZoneInfo("Asia/Shanghai")
                    except Exception:  # noqa: BLE001 - zoneinfo 数据缺失时退化为固定 +08:00
                        _tz = timezone(timedelta(hours=8))
                    _days = 0 if horizon == "day" else 3
                    _base = max(trade_date, datetime.now(_tz).date())
                    entry_valid_until = datetime.combine(
                        _base + timedelta(days=_days), time(15, 0), tzinfo=_tz
                    )

                draft = PlanItemDraft(
                    item_id=item.id,
                    symbol=symbol,
                    action=action,
                    horizon=horizon,
                    target_weight=target_weight,
                    target_qty=target_qty,
                    entry_combinator=combinator,
                    thesis=thesis,
                    invalidation=invalidation,
                    entry_valid_until=entry_valid_until,
                    evidence=evidence,
                    setup_type=setup_type,
                )
                item_drafts.append(draft)
                condition_drafts.extend(entry_conditions + stop_conditions + reduce_conditions)

                execution_batch = (
                    previous_version.execution_batch
                    if target is None and previous_version
                    else target.execution_batch if target else None
                )
                max_chase_pct = (
                    previous_version.max_chase_pct
                    if target is None and previous_version
                    else target.max_chase_pct if target else None
                )
                # price_break/above 入场守卫要求非负 max_chase_pct（ENTRY_CHASE_LIMIT_REQUIRED）；
                # provider 未提供时给默认 5%——允许阈值上方 5% 以内的追价，超过即拒单。
                if max_chase_pct is None:
                    _entry_for_chase = entry_conditions or previous_by_role.get(
                        "add_position" if action == "add" else "entry", []
                    )
                    if any(
                        c.condition_type == "price_break"
                        and (c.params or {}).get("direction") == "above"
                        for c in _entry_for_chase
                    ):
                        max_chase_pct = 5.0
                item_version = uow.plans.add_item_version(
                    revision_id=revision.id,
                    item_id=item.id,
                    action=action,
                    horizon=horizon,
                    target_weight=target_weight,
                    target_qty=target_qty,
                    execution_batch=execution_batch,
                    max_chase_pct=max_chase_pct,
                    entry_combinator=combinator,
                    thesis=thesis,
                    invalidation=invalidation,
                    entry_valid_until=entry_valid_until,
                    evidence=evidence,
                    setup_type=setup_type,
                )
                for condition in entry_conditions + stop_conditions + reduce_conditions:
                    uow.plans.add_condition(
                        item_version_id=item_version.id,
                        role=condition.role,
                        condition_type=condition.condition_type,
                        params=condition.params,
                        batch=condition.batch,
                        sequence=condition.sequence,
                        invalidation_threshold_pct=condition.invalidation_threshold_pct,
                    )

                state = states_by_item.get(item.id)
                entry_ready = bool(entry_conditions)
                initial_state = initial_item_state(action, position_qty, entry_ready=entry_ready)
                uow.plans.upsert_item_state(
                    item_id=item.id,
                    state=initial_state,
                    target_qty=target_qty,
                    existing=state,
                )

            problems = validate_items_unique_open(item_drafts)
            for draft in item_drafts:
                own_conditions = [
                    condition
                    for condition in condition_drafts
                    if condition.item_id == draft.item_id
                ]
                problems.extend(validate_item_decision(draft, own_conditions))
            if problems:
                raise AccountPlanError("PLAN_SPEC_INVALID", "；".join(problems))

            uow.plans.set_draft_revision(plan, revision.id)
            uow.plans.record_event(
                plan_id=plan.id,
                item_id=None,
                plan_version=revision.version,
                kind="generation",
                detail={
                    "trade_date": trade_date.isoformat(),
                    "created_items": created_items,
                    "reused_items": reused_items,
                    "symbols": symbols,
                },
                reason="生成账户计划 revision",
                actor=actor,
            )
            uow.runs.finish_run(run_id, status="succeeded", reasons=[], error=None)
            uow.commit()
            plan_id = plan.id
            revision_id = revision.id
            revision_version = revision.version
            revision_status = revision.status

        return {
            "plan_id": plan_id,
            "revision_id": revision_id,
            "version": revision_version,
            "status": revision_status,
            "existing": False,
            "run_id": run_id,
            "items": len(item_drafts),
        }
