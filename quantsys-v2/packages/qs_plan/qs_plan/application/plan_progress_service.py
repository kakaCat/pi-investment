"""账户级计划成交推进（REQ-261026140857-c192）

trade_id 的 fill receipt 是幂等凭证；receipt、item state、批次规则和事件在同一事务内提交。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional

from qs_plan.application.plan_generation_service import AccountPlanError
from qs_plan.domain.plan import evaluate_item_transition, transition_for_fill


class PlanProgressService:
    def __init__(
        self,
        *,
        unit_of_work_factory=None,
        remaining_qty_provider: Optional[Callable[[str, str], Optional[int]]] = None,
        now_fn=lambda: datetime.now(timezone.utc),
    ):
        self._uow_factory = unit_of_work_factory
        self._remaining_qty_provider = remaining_qty_provider
        self._now = now_fn

    def on_fill(
        self,
        *,
        account: str,
        symbol: str,
        side: str,
        qty: int,
        remaining_qty: Optional[int] = None,
        trade_id: Any,
        plan_id: Optional[int] = None,
        item_id: Optional[int] = None,
        plan_version: Optional[int] = None,
    ) -> Dict[str, Any]:
        if self._uow_factory is None:
            raise AccountPlanError("PLAN_UOW_MISSING", "未注入 TradingPlanUnitOfWork")
        if plan_id is None or item_id is None or plan_version is None or trade_id is None:
            raise AccountPlanError(
                "PLAN_ITEM_ATTRIBUTION_REQUIRED",
                "新计划成交必须提供 plan_id/item_id/plan_version/trade_id",
            )
        side = str(side or "").lower()
        if side not in ("buy", "sell"):
            raise AccountPlanError("PLAN_SPEC_INVALID", "side 必须是 buy/sell")
        qty = int(qty or 0)
        if qty <= 0:
            raise AccountPlanError("PLAN_SPEC_INVALID", "qty 必须为正数")
        trade_key = str(trade_id)

        with self._uow_factory() as uow:
            existing = uow.plans.get_fill_receipt(trade_key)
            if existing is not None:
                state = uow.plans.lock_item_state(existing.item_id)
                return {
                    "status": "duplicate",
                    "trade_id": trade_key,
                    "plan_id": existing.plan_id,
                    "item_id": existing.item_id,
                    "item_state": state.state if state else None,
                }

            plan = uow.plans.lock_plan_by_id(plan_id)
            if plan is None or plan.account != account:
                raise AccountPlanError("PLAN_NOT_FOUND", "成交计划与账户不匹配")
            revision = uow.plans.find_version_by_number(plan.id, plan_version)
            if revision is None or revision.status != "active":
                raise AccountPlanError("PLAN_STATE_ILLEGAL", "成交 plan_version 不是当前激活版本")

            item = uow.plans.get_item(item_id)
            if item is None or item.plan_id != plan.id or item.symbol != symbol:
                raise AccountPlanError(
                    "PLAN_ITEM_ATTRIBUTION_REQUIRED", "成交 item_id 与计划/标的不匹配"
                )

            state = uow.plans.lock_item_state(item_id)
            if state is None:
                raise AccountPlanError("PLAN_NOT_FOUND", "计划项执行状态不存在：%s" % item_id)
            item_version = uow.plans.latest_item_version(item_id)
            if item_version is None:
                raise AccountPlanError("PLAN_NOT_FOUND", "计划项决策不存在：%s" % item_id)

            remaining = remaining_qty
            if remaining is None:
                if self._remaining_qty_provider is None:
                    raise AccountPlanError("PLAN_PROVIDER_MISSING", "未注入持仓剩余量 provider")
                remaining = self._remaining_qty_provider(account, symbol)
            if remaining is None:
                return {
                    "status": "degraded",
                    "reason": "position_read_failed",
                    "trade_id": trade_key,
                    "item_id": item_id,
                }
            remaining = int(remaining)

            receipt = uow.plans.add_fill_receipt(
                trade_id=trade_key,
                plan_id=plan.id,
                item_id=item.id,
                plan_version=revision.version,
                side=side,
                qty=qty,
                remaining_qty=remaining,
            )

            if state.state == "planned" and side == "buy":
                entry_role = {"buy": "entry", "add": "add_position"}.get(item_version.action)
                if entry_role and any(
                    condition.role == entry_role
                    for condition in uow.plans.list_conditions(item_version.id)
                ):
                    state.state = "ready"
                    state.lock_version = int(state.lock_version or 1) + 1

            target_state = transition_for_fill(side, remaining)
            ok, reason = evaluate_item_transition(state.state, target_state)
            if not ok:
                raise AccountPlanError("PLAN_STATE_ILLEGAL", reason or "非法计划项迁移")

            state.state = target_state
            state.filled_qty = int(state.filled_qty or 0) + qty
            state.remaining_qty = remaining
            state.last_fill_at = self._now()
            state.lock_version = int(state.lock_version or 1) + 1

            sold_qty = 0
            sold_ratio = 0.0
            retired_batches = []
            if side == "sell":
                sold_qty = int(state.initial_sold_qty or 0) + uow.plans.item_sold_qty(item.id)
                denominator = sold_qty + max(remaining, 0)
                sold_ratio = (
                    1.0
                    if remaining <= 0 and sold_qty > 0
                    else (sold_qty / denominator if denominator > 0 else 0.0)
                )
                for rule in uow.rules.list_managed_rules(plan.id):
                    if (
                        rule["item_id"] != item.id
                        or rule["role"] not in ("reduce", "exit_reduce")
                        or not rule["enabled"]
                    ):
                        continue
                    condition = (rule.get("conditions") or [{}])[0]
                    trigger_pct = (condition.get("params") or {}).get("pct")
                    if trigger_pct is not None and sold_ratio >= float(trigger_pct) / 100.0:
                        uow.rules.retire_rule(rule["rule_id"], "减仓批次累计成交已达标")
                        uow.rules.record_audit(
                            rule_id=rule["rule_id"],
                            changed_by="system",
                            before=rule,
                            after={"enabled": False, "sold_ratio": round(sold_ratio, 6)},
                            reason="累计减仓比例达到批次边界",
                        )
                        retired_batches.append(rule["batch"])

            uow.plans.attribute_simulation_trade(
                trade_id=trade_key,
                plan_id=plan.id,
                item_id=item.id,
                plan_version=revision.version,
            )
            uow.plans.record_event(
                plan_id=plan.id,
                item_id=item.id,
                plan_version=revision.version,
                kind="fill",
                actor="system",
                detail={
                    "trade_id": trade_key,
                    "side": side,
                    "qty": qty,
                    "remaining_qty": remaining,
                    "item_state": target_state,
                    "filled_qty": state.filled_qty,
                    "sold_qty": sold_qty,
                    "sold_ratio": round(sold_ratio, 6),
                    "retired_batches": retired_batches,
                },
                reason="计划项成交推进",
            )
            uow.commit()

            return {
                "status": "ok",
                "trade_id": trade_key,
                "plan_id": plan.id,
                "item_id": item.id,
                "plan_version": revision.version,
                "item_state": target_state,
                "filled_qty": state.filled_qty,
                "remaining_qty": remaining,
                "sold_qty": sold_qty,
                "sold_ratio": round(sold_ratio, 6),
                "retired_batches": retired_batches,
            }
