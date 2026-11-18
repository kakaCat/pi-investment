from __future__ import annotations

from typing import Any, Dict, Optional

from qs_trading.domain.trading.t_trade_cycle import (
    STATUS_WAITING_BUYBACK,
    STATUS_WAITING_SELL,
)


class TTradeWatchService:
    def __init__(self, *, rule_repo, cycle_repo):
        self.rule_repo = rule_repo
        self.cycle_repo = cycle_repo

    @staticmethod
    def _field(event, name):
        if isinstance(event, dict):
            return event.get(name)
        return getattr(event, name, None)

    def on_fill(self, event) -> Dict[str, Any]:
        cycle_id = self._field(event, "t_trade_id")
        if cycle_id is None:
            return {"status": "skipped", "reason": "no_t_trade_id"}
        cycle = self.cycle_repo.get(cycle_id)
        if cycle is None:
            raise ValueError(f"做T周期不存在: {cycle_id}")
        return self.reconcile(cycle)

    def _retire(self, rule_id: Optional[int]) -> None:
        if rule_id is None:
            return
        rule = self.rule_repo.get_by_id(rule_id)
        if rule is None:
            return
        if (not bool(getattr(rule, "enabled", True))
                and getattr(rule, "rule_state", "active") == "archived"):
            return
        self.rule_repo.update_fields(
            rule_id,
            enabled=False,
            rule_state="archived",
            invalid_reason="t_trade_cycle_state_changed",
        )

    def _active_rule(self, rule_id: Optional[int]):
        if rule_id is None:
            return None
        rule = self.rule_repo.get_by_id(rule_id)
        if rule is None or not bool(getattr(rule, "enabled", True)):
            return None
        if getattr(rule, "rule_state", "active") != "active":
            return None
        return rule

    def _create_leg_rule(self, cycle, leg: str):
        is_sell = leg == "sell"
        price = float(cycle.upper_price if is_sell else cycle.lower_price)
        params = {
            "action": "sell" if is_sell else "buy",
            "reference_price": price,
            "quantity": int(cycle.shares),
            "invalidation": cycle.invalidation or "止损、区间失效或数据异常时取消做T",
            "t_trade_id": int(cycle.id),
            "leg": leg,
            "mode": cycle.mode,
            "buyback_price": float(cycle.lower_price),
        }
        return self.rule_repo.create_rule(
            symbol=cycle.symbol,
            conditions=[{
                "type": "price_break",
                "params": {"price": price, "direction": "above" if is_sell else "below"},
            }],
            context=f"t_trade:{cycle.id} {leg}",
            account=cycle.account,
            linked_account=cycle.account,
            intent="t_trade",
            action_params=params,
            position_state="holding",
            watch_tier=30,
            trigger_channel="agent",
            created_by="t_trade",
        )

    def reconcile(self, cycle) -> Dict[str, Any]:
        try:
            if cycle.status == STATUS_WAITING_SELL:
                self._retire(cycle.buyback_rule_id)
                if self._active_rule(cycle.sell_rule_id) is None:
                    cycle.sell_rule_id = self._create_leg_rule(cycle, "sell").id
            elif cycle.status == STATUS_WAITING_BUYBACK:
                self._retire(cycle.sell_rule_id)
                if self._active_rule(cycle.buyback_rule_id) is None:
                    cycle.buyback_rule_id = self._create_leg_rule(cycle, "buyback").id
            else:
                self._retire(cycle.sell_rule_id)
                self._retire(cycle.buyback_rule_id)
            cycle.rule_sync = {
                "status": "ok",
                "cycle_status": cycle.status,
                "sell_rule_id": cycle.sell_rule_id,
                "buyback_rule_id": cycle.buyback_rule_id,
            }
            self.cycle_repo.commit()
            return {"status": "ok", **cycle.rule_sync}
        except Exception as exc:
            cycle.rule_sync = {"status": "error", "error": str(exc)[:500]}
            self.cycle_repo.commit()
            raise
