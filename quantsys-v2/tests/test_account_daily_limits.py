"""账户级日买入限额测试（服务端硬护栏）"""
import pytest
from unittest.mock import MagicMock

from application.services.account_trading_service import (
    AccountTradingService,
    TradingError,
)


class FakeTrade:
    def __init__(self, action, amount):
        self.action = action
        self.amount = amount


def _svc_with_trades(trades):
    repo = MagicMock()
    repo.get_trades_by_account.return_value = trades
    return AccountTradingService(repo=repo)


def test_daily_buy_count_limit_reached():
    svc = _svc_with_trades([FakeTrade('buy', 1000)] * 5)
    with pytest.raises(TradingError, match='单日买入笔数超限'):
        svc._check_daily_buy_limits('agent_virtual', 1000, 100000)


def test_daily_buy_count_under_limit_passes():
    svc = _svc_with_trades([FakeTrade('buy', 1000)] * 4)
    svc._check_daily_buy_limits('agent_virtual', 1000, 100000)  # 不抛异常


def test_daily_buy_amount_limit():
    """今日已买 4.5 万，再买 1 万 → 5.5 万 > 总资产 10 万的 50%"""
    svc = _svc_with_trades([FakeTrade('buy', 45000)])
    with pytest.raises(TradingError, match='单日买入金额超限'):
        svc._check_daily_buy_limits('agent_virtual', 10000, 100000)


def test_daily_buy_amount_at_boundary_passes():
    """已买 4 万 + 本次 1 万 = 5 万 = 50%，不超限"""
    svc = _svc_with_trades([FakeTrade('buy', 40000)])
    svc._check_daily_buy_limits('agent_virtual', 10000, 100000)  # 不抛异常


def test_sell_trades_not_counted():
    """卖出不计入买入限额"""
    svc = _svc_with_trades([FakeTrade('sell', 90000)] * 10)
    svc._check_daily_buy_limits('agent_virtual', 10000, 100000)  # 不抛异常
