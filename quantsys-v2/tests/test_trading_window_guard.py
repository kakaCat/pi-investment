"""交易时段护栏测试（A股规则：交易日 9:30-11:30 / 13:00-15:00 才能成交）"""
from datetime import datetime
from unittest.mock import MagicMock

import pytest

from application.services.account_trading_service import (
    AccountTradingService,
    TradingError,
)


def _svc(is_trading_day: bool = True):
    repo = MagicMock()
    calendar = MagicMock()
    calendar.is_trading_day.return_value = is_trading_day
    return AccountTradingService(repo=repo, calendar=calendar)


# ---------- _check_trading_window 单元测试 ----------

def test_sunday_rejected():
    svc = _svc(is_trading_day=False)
    with pytest.raises(TradingError, match='非交易日'):
        svc._check_trading_window(datetime(2026, 7, 26, 10, 0))  # 周日


def test_trading_day_morning_session_passes():
    svc = _svc(is_trading_day=True)
    svc._check_trading_window(datetime(2026, 7, 27, 10, 0))  # 周一上午盘


def test_open_boundary_930_passes_925_rejected():
    svc = _svc(is_trading_day=True)
    svc._check_trading_window(datetime(2026, 7, 27, 9, 30))
    with pytest.raises(TradingError, match='非交易时段'):
        svc._check_trading_window(datetime(2026, 7, 27, 9, 25))


def test_lunch_break_rejected():
    svc = _svc(is_trading_day=True)
    with pytest.raises(TradingError, match='非交易时段'):
        svc._check_trading_window(datetime(2026, 7, 27, 12, 0))


def test_afternoon_session_boundaries():
    svc = _svc(is_trading_day=True)
    svc._check_trading_window(datetime(2026, 7, 27, 13, 0))
    svc._check_trading_window(datetime(2026, 7, 27, 15, 0))
    with pytest.raises(TradingError, match='非交易时段'):
        svc._check_trading_window(datetime(2026, 7, 27, 15, 1))


def test_after_close_rejected():
    svc = _svc(is_trading_day=True)
    with pytest.raises(TradingError, match='非交易时段'):
        svc._check_trading_window(datetime(2026, 7, 27, 18, 0))


# ---------- execute_trade 集成点 ----------

def _make_tradable_svc():
    """构造一个能通过全部前置校验的 service（mock repo）"""
    repo = MagicMock()
    account = MagicMock()
    account.status = 'active'
    account.cash_available = 100000.0
    account.cash_frozen = 0.0
    account.total_value = 100000.0
    account.initial_capital = 100000.0
    account.peak_value = 100000.0
    repo.get_account.return_value = account
    repo.get_all_positions.return_value = []
    repo.create_order.return_value = MagicMock(id=1)
    repo.add_trade.return_value = 1
    svc = AccountTradingService(repo=repo, calendar=MagicMock())
    svc._get_price = MagicMock(return_value=10.0)
    return svc


def test_execute_trade_invokes_guard_by_default():
    svc = _make_tradable_svc()
    svc._check_trading_window = MagicMock()

    svc.execute_trade(
        account_name='agent_virtual', action='buy', symbol='601398',
        amount=1000, reason='测试交易时段护栏默认开启')

    svc._check_trading_window.assert_called_once()


def test_execute_trade_skips_guard_with_allow_off_hours():
    svc = _make_tradable_svc()
    svc._check_trading_window = MagicMock()

    svc.execute_trade(
        account_name='agent_virtual', action='buy', symbol='601398',
        amount=1000, reason='测试回放模式绕过时段护栏',
        allow_off_hours=True)

    svc._check_trading_window.assert_not_called()
