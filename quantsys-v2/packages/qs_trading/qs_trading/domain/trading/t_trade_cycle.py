from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from qs_trading.domain.trading.exceptions import TradingError
from qs_trading.domain.trading.services.trade_guard_service import TradeGuardService

MODE_REMIND_ONLY = "remind_only"
MODE_AUTO_SIM = "auto_sim"
STATUS_WAITING_SELL = "waiting_sell"
STATUS_WAITING_BUYBACK = "waiting_buyback"
STATUS_COMPLETED = "completed"
STATUS_CANCELLED = "cancelled"
ACTIVE_STATUSES = (STATUS_WAITING_SELL, STATUS_WAITING_BUYBACK)
STATUSES = ACTIVE_STATUSES + (STATUS_COMPLETED, STATUS_CANCELLED)
ACCOUNT_MODES = {
    "user_main_simulation": MODE_REMIND_ONLY,
    "agent_brain": MODE_AUTO_SIM,
}
MONEY = Decimal("0.01")


def _decimal(value, field: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except Exception as exc:
        raise TradingError(f"{field} 必须是数值", 400) from exc
    if not result.is_finite() or result <= 0:
        raise TradingError(f"{field} 必须是正数", 400)
    return result


def _money(value: Decimal) -> Decimal:
    return value.quantize(MONEY, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class TTradeSpec:
    account: str
    symbol: str
    upper_price: Decimal
    lower_price: Decimal
    shares: int
    available_shares: int
    reason: str
    invalidation: str = ""
    slippage_bps: Decimal = Decimal("10")

    @property
    def mode(self) -> str:
        return mode_for_account(self.account)


@dataclass(frozen=True)
class LegFill:
    trade_id: int
    action: str
    shares: int
    price: Decimal
    commission: Decimal = Decimal("0")
    stamp_duty: Decimal = Decimal("0")
    transfer_fee: Decimal = Decimal("0")

    @property
    def fees(self) -> Decimal:
        return self.commission + self.stamp_duty + self.transfer_fee


@dataclass(frozen=True)
class FeeEstimate:
    gross_pnl: Decimal
    total_fees: Decimal
    slippage_cost: Decimal
    net_pnl: Decimal


def mode_for_account(account: str) -> str:
    try:
        return ACCOUNT_MODES[str(account or "").strip()]
    except KeyError as exc:
        raise TradingError(f"账户 {account!r} 未开通区间T MVP", 403) from exc


def validate_spec(spec: TTradeSpec) -> None:
    if not spec.symbol or not str(spec.symbol).isdigit() or len(str(spec.symbol)) != 6:
        raise TradingError("symbol 必须是6位数字股票代码", 400)
    if spec.upper_price <= spec.lower_price:
        raise TradingError("上沿价必须大于下沿价", 400)
    if not isinstance(spec.shares, int) or isinstance(spec.shares, bool):
        raise TradingError("做T数量必须是整数", 400)
    if spec.shares <= 0 or spec.shares % 100 != 0:
        raise TradingError("做T数量必须是100股正整数倍", 400)
    max_shares = int(spec.available_shares // 300) * 100
    if max_shares <= 0 or spec.shares > max_shares:
        raise TradingError(
            f"做T数量不得超过可卖持仓的1/3：可卖 {spec.available_shares} 股，"
            f"本次上限 {max(max_shares, 0)} 股",
            422,
            details={"max_t_shares": max(max_shares, 0)},
        )
    if len((spec.reason or "").strip()) < 10:
        raise TradingError("做T理由至少10字", 400)
    if spec.slippage_bps < 0 or spec.slippage_bps > 500:
        raise TradingError("滑点缓冲必须在 0~500 bps", 400)


def estimate_fees(action: str, price: Decimal, shares: int) -> Decimal:
    amount = price * shares
    commission = max(
        _money(amount * Decimal(str(TradeGuardService.COMMISSION_RATE))),
        Decimal(str(TradeGuardService.COMMISSION_MIN)),
    )
    stamp = (
        _money(amount * Decimal(str(TradeGuardService.STAMP_DUTY_RATE)))
        if action.upper() == "SELL"
        else Decimal("0")
    )
    transfer = _money(amount * Decimal(str(TradeGuardService.TRANSFER_FEE_RATE)))
    return commission + stamp + transfer


def estimate_cycle(spec: TTradeSpec) -> FeeEstimate:
    validate_spec(spec)
    sell_price = spec.upper_price
    buy_price = spec.lower_price
    gross = _money((sell_price - buy_price) * spec.shares)
    fees = estimate_fees("SELL", sell_price, spec.shares) + estimate_fees(
        "BUY", buy_price, spec.shares
    )
    slippage = _money(
        (sell_price + buy_price)
        * spec.shares
        * spec.slippage_bps
        / Decimal("10000")
    )
    return FeeEstimate(gross, _money(fees), slippage, _money(gross - fees - slippage))


def expected_action(status: str) -> str:
    if status == STATUS_WAITING_SELL:
        return "SELL"
    if status == STATUS_WAITING_BUYBACK:
        return "BUY"
    raise TradingError(f"做T状态 {status} 不允许继续成交", 409)


def status_after_fill(status: str, action: str) -> str:
    expected = expected_action(status)
    normalized = str(action or "").upper()
    if normalized != expected:
        raise TradingError(f"当前做T腿要求 {expected}，收到 {normalized}", 409)
    return STATUS_WAITING_BUYBACK if normalized == "SELL" else STATUS_COMPLETED


def completed_net_pnl(sell: LegFill, buyback: LegFill) -> Decimal:
    if sell.action.upper() != "SELL" or buyback.action.upper() != "BUY":
        raise TradingError("做T结算必须按 SELL/BUY 两腿提供", 400)
    if sell.shares != buyback.shares:
        raise TradingError("做T两腿数量不一致，不能按完整周期结算", 409)
    return _money(
        (sell.price - buyback.price) * sell.shares - sell.fees - buyback.fees
    )


def make_fill(
    *,
    trade_id: int,
    action: str,
    shares: int,
    price,
    commission=0,
    stamp_duty=0,
    transfer_fee=0,
) -> LegFill:
    return LegFill(
        trade_id=int(trade_id),
        action=str(action or "").upper(),
        shares=int(shares),
        price=_decimal(price, "成交价"),
        commission=Decimal(str(commission or 0)),
        stamp_duty=Decimal(str(stamp_duty or 0)),
        transfer_fee=Decimal(str(transfer_fee or 0)),
    )
