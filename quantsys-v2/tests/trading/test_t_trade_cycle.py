from decimal import Decimal

import pytest

from qs_trading.domain.trading.exceptions import TradingError
from qs_trading.domain.trading.t_trade_cycle import (
    STATUS_COMPLETED,
    STATUS_WAITING_BUYBACK,
    STATUS_WAITING_SELL,
    TTradeSpec,
    completed_net_pnl,
    estimate_cycle,
    expected_action,
    make_fill,
    mode_for_account,
    status_after_fill,
)


def spec(**overrides):
    values = dict(
        account="agent_brain",
        symbol="002007",
        upper_price=Decimal("13.55"),
        lower_price=Decimal("12.19"),
        shares=100,
        available_shares=300,
        reason="明确区间内小仓位验证反向做T闭环",
    )
    values.update(overrides)
    return TTradeSpec(**values)


def test_account_mode_is_server_derived():
    assert mode_for_account("agent_brain") == "auto_sim"
    assert mode_for_account("user_main_simulation") == "remind_only"
    with pytest.raises(TradingError):
        mode_for_account("agent_virtual")


def test_estimate_includes_minimum_commissions_stamp_transfer_and_slippage():
    result = estimate_cycle(spec())
    assert result.gross_pnl == Decimal("136.00")
    assert result.total_fees > Decimal("10")
    assert result.slippage_cost > 0
    assert result.net_pnl == result.gross_pnl - result.total_fees - result.slippage_cost
    assert result.net_pnl > 0


def test_rejects_third_position_overflow_and_bad_range():
    with pytest.raises(TradingError) as exc:
        estimate_cycle(spec(shares=200))
    assert exc.value.status_code == 422
    assert exc.value.details["max_t_shares"] == 100
    with pytest.raises(TradingError):
        estimate_cycle(spec(upper_price=Decimal("12"), lower_price=Decimal("13")))


def test_expected_net_must_cover_costs():
    from qs_trading.application.services.t_trade_service import validate_expected_return

    with pytest.raises(TradingError) as exc:
        validate_expected_return(
            spec(upper_price=Decimal("12.20"), lower_price=Decimal("12.19"))
        )
    assert "费后" in str(exc.value)


def test_state_machine_does_not_allow_buyback_before_sell():
    assert expected_action(STATUS_WAITING_SELL) == "SELL"
    with pytest.raises(TradingError):
        status_after_fill(STATUS_WAITING_SELL, "BUY")
    assert status_after_fill(STATUS_WAITING_SELL, "SELL") == STATUS_WAITING_BUYBACK
    assert status_after_fill(STATUS_WAITING_BUYBACK, "BUY") == STATUS_COMPLETED
    with pytest.raises(TradingError):
        expected_action(STATUS_COMPLETED)


def test_completed_pnl_uses_actual_prices_and_all_fees():
    sell = make_fill(
        trade_id=1, action="SELL", shares=100, price="13.50",
        commission="5", stamp_duty="0.68", transfer_fee="0.01",
    )
    buy = make_fill(
        trade_id=2, action="BUY", shares=100, price="12.20",
        commission="5", transfer_fee="0.01",
    )
    assert completed_net_pnl(sell, buy) == Decimal("119.30")
