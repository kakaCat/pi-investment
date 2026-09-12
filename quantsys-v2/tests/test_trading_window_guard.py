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
    """下午盘边界 + **收盘截止窗口**（RFC 016 §8.1 裁定 B，2026-09-12 有意收紧）

    旧断言允许到 15:00 整；收敛到 MarketSessionPolicy 后，端点闭合虽把 15:00 视为盘中，
    但每段末尾 `ORDER_CUTOFF_SECONDS`(60s) 内不再接受新委托 → 14:59 与 15:00 均拒。
    """
    svc = _svc(is_trading_day=True)
    svc._check_trading_window(datetime(2026, 7, 27, 13, 0))
    svc._check_trading_window(datetime(2026, 7, 27, 14, 58))          # 距收盘 120s > 60s
    with pytest.raises(TradingError, match='临近休市'):
        svc._check_trading_window(datetime(2026, 7, 27, 14, 59))      # 距收盘 60s，已截止
    with pytest.raises(TradingError, match='临近休市'):
        svc._check_trading_window(datetime(2026, 7, 27, 15, 0))       # 端点闭合算盘中，但已截止
    with pytest.raises(TradingError, match='非交易时段'):
        svc._check_trading_window(datetime(2026, 7, 27, 15, 1))


def test_morning_close_cutoff_window():
    """上午盘同样有截止窗口（11:29 起拒单，11:28 仍可）"""
    svc = _svc(is_trading_day=True)
    svc._check_trading_window(datetime(2026, 7, 27, 11, 28))
    with pytest.raises(TradingError, match='临近休市'):
        svc._check_trading_window(datetime(2026, 7, 27, 11, 29))
    with pytest.raises(TradingError, match='临近休市'):
        svc._check_trading_window(datetime(2026, 7, 27, 11, 30))


def test_after_close_rejected():
    svc = _svc(is_trading_day=True)
    with pytest.raises(TradingError, match='非交易时段'):
        svc._check_trading_window(datetime(2026, 7, 27, 18, 0))


# ---------- execute_trade 集成点 ----------

def _make_tradable_svc(now: datetime = None):
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
    repo.get_account_for_update.return_value = account  # 事务内锁行后复核使用
    repo.get_all_positions.return_value = []
    repo.create_order.return_value = MagicMock(id=1)
    repo.add_trade.return_value = 1
    # 2026-09-11（w-8f2c4cc5）：固定时钟到交易时段内。
    # 原先不传 now_fn = 用真实时钟：本用例只 mock 了应用层 _check_trading_window，
    # 但 execute_trade 还会走 domain TradeGuardService.validate_trading_window
    # （now_fn=self.now_fn，真实时钟）→ 非交易时段跑测试必失败（时间依赖型假失败）。
    svc = AccountTradingService(
        repo=repo, calendar=MagicMock(),
        now_fn=lambda: now or datetime(2026, 7, 27, 10, 0),  # 默认周一上午盘
    )
    svc._get_price = MagicMock(return_value=10.0)
    return svc


def test_execute_trade_invokes_guard_by_default():
    """默认不传 allow_off_hours：收盘后委托必须被交易时段护栏拒绝。

    2026-09-11（w-8f2c4cc5）修正陈旧断言：时段校验已下沉到 domain
    TradeGuardService，execute_trade 不再调用应用层 self._check_trading_window
    —— 原用例 mock 该方法后断言"被调用一次"，在 domain 化之后恒为 0 次，
    即"断言一个永不执行的 mock"（且用真实时钟，非交易时段还会先抛异常）。
    现改为断言真实契约：默认路径 = 非交易时段拒绝。
    """
    svc = _make_tradable_svc(now=datetime(2026, 7, 27, 18, 0))  # 周一收盘后

    with pytest.raises(TradingError, match='非交易时段'):
        svc.execute_trade(
            account_name='agent_virtual', action='buy', symbol='601398',
            amount=1000, reason='测试交易时段护栏默认开启')


def test_execute_trade_skips_guard_with_allow_off_hours():
    """allow_off_hours=True 时同一时点放行（回放/补录模式），真实下单路径走通"""
    svc = _make_tradable_svc(now=datetime(2026, 7, 27, 18, 0))

    svc.execute_trade(
        account_name='agent_virtual', action='buy', symbol='601398',
        amount=1000, reason='测试回放模式绕过时段护栏',
        allow_off_hours=True)

    # 真实断言：绕开时段护栏后确实走到下单（create_order 被调用）
    svc.repo.create_order.assert_called()
