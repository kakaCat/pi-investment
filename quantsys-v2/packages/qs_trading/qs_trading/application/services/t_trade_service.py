from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from qs_trading.domain.trading.exceptions import TradingError
from qs_trading.domain.trading.t_trade_cycle import (
    ACTIVE_STATUSES,
    MODE_AUTO_SIM,
    MODE_REMIND_ONLY,
    STATUS_CANCELLED,
    STATUS_COMPLETED,
    STATUS_WAITING_BUYBACK,
    TTradeSpec,
    completed_net_pnl,
    estimate_cycle,
    expected_action,
    make_fill,
    status_after_fill,
)


def validate_expected_return(spec: TTradeSpec):
    estimate = estimate_cycle(spec)
    if estimate.net_pnl <= 0:
        raise TradingError(
            f"预期费后收益不足：毛价差 {estimate.gross_pnl}，费用 {estimate.total_fees}，"
            f"滑点缓冲 {estimate.slippage_cost}",
            422,
            details={
                "expected_gross_pnl": float(estimate.gross_pnl),
                "expected_fees": float(estimate.total_fees),
                "expected_slippage_cost": float(estimate.slippage_cost),
                "expected_net_pnl": float(estimate.net_pnl),
            },
        )
    return estimate


def apply_fill_to_cycle(cycle, fill, *, filled_at: Optional[datetime] = None):
    if int(getattr(cycle, "sell_trade_id", 0) or 0) == fill.trade_id:
        return cycle
    if int(getattr(cycle, "buyback_trade_id", 0) or 0) == fill.trade_id:
        return cycle
    new_status = status_after_fill(cycle.status, fill.action)
    if fill.shares != int(cycle.shares):
        raise TradingError(
            f"做T成交数量必须为 {cycle.shares} 股，实际 {fill.shares} 股", 409
        )
    if fill.action == "SELL":
        if fill.price < Decimal(str(cycle.upper_price)):
            raise TradingError("卖出成交价低于做T上沿，不能登记为本周期成交", 422)
        cycle.sell_trade_id = fill.trade_id
        cycle.sell_price = fill.price
        cycle.sell_commission = fill.commission
        cycle.sell_stamp_duty = fill.stamp_duty
        cycle.sell_transfer_fee = fill.transfer_fee
        cycle.sell_filled_at = filled_at or datetime.now()
    else:
        if cycle.status != STATUS_WAITING_BUYBACK:
            raise TradingError("卖出老仓成交后才允许回补", 409)
        if fill.price > Decimal(str(cycle.lower_price)):
            raise TradingError("回补成交价高于做T下沿，不能登记为本周期成交", 422)
        cycle.buyback_trade_id = fill.trade_id
        cycle.buyback_price = fill.price
        cycle.buyback_commission = fill.commission
        cycle.buyback_stamp_duty = fill.stamp_duty
        cycle.buyback_transfer_fee = fill.transfer_fee
        cycle.buyback_filled_at = filled_at or datetime.now()
        sell = make_fill(
            trade_id=cycle.sell_trade_id,
            action="SELL",
            shares=cycle.shares,
            price=cycle.sell_price,
            commission=cycle.sell_commission,
            stamp_duty=cycle.sell_stamp_duty,
            transfer_fee=cycle.sell_transfer_fee,
        )
        net = completed_net_pnl(sell, fill)
        cycle.gross_pnl = ((sell.price - fill.price) * cycle.shares).quantize(
            Decimal("0.01")
        )
        cycle.total_fees = sell.fees + fill.fees
        cycle.net_pnl = net
        cycle.completed_at = filled_at or datetime.now()
    cycle.status = new_status
    cycle.lock_version = int(cycle.lock_version or 0) + 1
    cycle.updated_at = filled_at or datetime.now()
    return cycle


class TTradeService:
    def __init__(self, *, repo, simulation_repo, trading_service=None, now_fn=None):
        self.repo = repo
        self.simulation_repo = simulation_repo
        self.trading_service = trading_service
        self.now_fn = now_fn or datetime.now

    def _trading(self):
        if self.trading_service is None:
            from qs_trading.application.services.account_trading_service import (
                AccountTradingService,
            )

            self.trading_service = AccountTradingService(
                repo=self.simulation_repo, now_fn=self.now_fn
            )
        return self.trading_service

    def create_cycle(
        self, *, account: str, symbol: str, upper_price, lower_price,
        shares: int, reason: str, invalidation: str = "", slippage_bps=10,
    ):
        position = self.simulation_repo.get_position(account, symbol)
        available = int(getattr(position, "shares_available", 0) or 0)
        try:
            spec = TTradeSpec(
                account=account,
                symbol=str(symbol or "").strip(),
                upper_price=Decimal(str(upper_price)),
                lower_price=Decimal(str(lower_price)),
                shares=shares,
                available_shares=available,
                reason=reason,
                invalidation=invalidation or "",
                slippage_bps=Decimal(str(slippage_bps)),
            )
        except Exception as exc:
            raise TradingError("上下沿价格或滑点缓冲格式非法", 400) from exc
        estimate = validate_expected_return(spec)
        if self.repo.find_active(spec.account, spec.symbol) is not None:
            raise TradingError(f"{spec.account}/{spec.symbol} 已有活动做T周期", 409)
        values = {
            "account": spec.account,
            "symbol": spec.symbol,
            "mode": spec.mode,
            "status": "waiting_sell",
            "upper_price": spec.upper_price,
            "lower_price": spec.lower_price,
            "shares": spec.shares,
            "available_shares_at_creation": available,
            "slippage_bps": spec.slippage_bps,
            "expected_gross_pnl": estimate.gross_pnl,
            "expected_fees": estimate.total_fees,
            "expected_slippage_cost": estimate.slippage_cost,
            "expected_net_pnl": estimate.net_pnl,
            "reason": spec.reason.strip(),
            "invalidation": spec.invalidation.strip() or None,
            "lock_version": 1,
        }
        try:
            cycle = self.repo.create(values)
            self.repo.commit()
            return cycle
        except TradingError:
            self.repo.rollback()
            raise
        except Exception as exc:
            self.repo.rollback()
            raise TradingError(f"创建做T周期失败: {exc}", 500) from exc

    def get_cycle(self, cycle_id: int):
        cycle = self.repo.get(cycle_id)
        if cycle is None:
            raise TradingError(f"做T周期不存在: {cycle_id}", 404)
        return cycle

    def execute(self, cycle_id: int, *, price=None):
        cycle = self.get_cycle(cycle_id)
        if cycle.mode != MODE_AUTO_SIM:
            raise TradingError("该账户为 remind_only，做T只能提醒，禁止代下单", 403)
        action = expected_action(cycle.status)
        limit = cycle.upper_price if action == "SELL" else cycle.lower_price
        result = self._trading().execute_trade(
            account_name=cycle.account,
            action=action,
            symbol=cycle.symbol,
            shares=int(cycle.shares),
            price_limit=float(limit),
            price=price,
            reason=f"t_trade:{cycle.id} {cycle.reason}",
            strategy_name="range_t",
            t_trade_id=int(cycle.id),
            t_trade_repo=self.repo,
        )
        return {"trade": result, "cycle": cycle.to_dict()}

    def record_fill(self, cycle_id: int, trade_id: int):
        if not isinstance(trade_id, int) or isinstance(trade_id, bool) or trade_id <= 0:
            raise TradingError("record-fill 必须提供正整数 trade_id", 400)
        cycle = self.repo.get(cycle_id, for_update=True)
        if cycle is None:
            raise TradingError(f"做T周期不存在: {cycle_id}", 404)
        if cycle.mode != MODE_REMIND_ONLY:
            raise TradingError("自动模拟周期必须通过 execute 成交，不能登记外部成交", 409)
        expected_action(cycle.status)
        if self.repo.trade_in_use(trade_id):
            raise TradingError(f"成交 {trade_id} 已关联其他做T周期或当前腿", 409)
        trade = self.repo.get_trade(trade_id)
        if trade is None:
            raise TradingError(f"成交记录不存在: {trade_id}", 404)
        if trade.account_name != cycle.account or trade.symbol != cycle.symbol:
            raise TradingError("成交账户或标的与做T周期不一致", 409)
        if trade.action != expected_action(cycle.status):
            raise TradingError("成交方向与当前做T腿不一致", 409)
        fill = make_fill(
            trade_id=trade.id,
            action=trade.action,
            shares=trade.shares,
            price=trade.filled_price,
            commission=trade.commission,
            stamp_duty=trade.stamp_duty,
            transfer_fee=trade.transfer_fee,
        )
        try:
            apply_fill_to_cycle(
                cycle, fill, filled_at=trade.trade_time or self.now_fn()
            )
            self.repo.commit()
            return cycle
        except TradingError:
            self.repo.rollback()
            raise
        except Exception as exc:
            self.repo.rollback()
            raise TradingError(f"登记做T成交失败: {exc}", 500) from exc

    def cancel(self, cycle_id: int, reason: str):
        cycle = self.repo.get(cycle_id, for_update=True)
        if cycle is None:
            raise TradingError(f"做T周期不存在: {cycle_id}", 404)
        if cycle.status not in ACTIVE_STATUSES:
            raise TradingError(f"做T状态 {cycle.status} 不能取消", 409)
        if len((reason or "").strip()) < 3:
            raise TradingError("取消原因至少3字", 400)
        cycle.status = STATUS_CANCELLED
        cycle.cancel_reason = reason.strip()
        cycle.cancelled_at = self.now_fn()
        cycle.updated_at = self.now_fn()
        cycle.lock_version = int(cycle.lock_version or 0) + 1
        self.repo.commit()
        return cycle
