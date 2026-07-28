"""条件委托（pending orders）服务层测试

盘前（非交易时段）可下 execute_at='market_open' 的挂单，
开盘后由 orchestrator 调 execute_pending_orders 自动撮合。

全部 mock repo/calendar，不依赖数据库；时间通过 now_fn 注入。
"""
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from application.services.account_trading_service import (
    AccountTradingService, TradingError,
)

REASON = '测试买入：技术面突破且放量，符合策略入场条件'


# ---------- fixtures ----------

@pytest.fixture()
def repo():
    return Mock()


@pytest.fixture()
def calendar():
    cal = Mock()
    cal.is_trading_day.return_value = True  # 默认交易日
    return cal


def _make_service(repo, calendar, now):
    return AccountTradingService(
        repo=repo, calendar=calendar, now_fn=lambda: now)


def _active_account(**overrides):
    defaults = dict(
        account_name='acc', status='active',
        cash_available=100000.0, cash_frozen=0.0,
        position_value=0.0, total_value=100000.0,
        peak_value=100000.0, initial_capital=100000.0,
        cumulative_return=0.0,
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _setup_trade_path(repo):
    """让 execute_trade 的完整护栏路径可走通（买入 100 股 @10）"""
    repo.get_account.return_value = _active_account()
    repo.get_account_for_update.return_value = repo.get_account.return_value
    repo.get_all_positions.return_value = []
    repo.get_trades_by_account.return_value = []
    repo.create_order.return_value = SimpleNamespace(id=1)
    repo.add_trade.return_value = 7


def _pending_order(**overrides):
    defaults = dict(
        id=1, account_name='acc', symbol='600519', action='buy',
        shares=100, amount=None, price_limit=None, reason=REASON,
        execute_at='market_open', status='pending',
        fail_reason=None, executed_trade_id=None,
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


# ---------- execute_trade + execute_at ----------

class TestPlacePendingOrder:
    """非交易时段 + execute_at='market_open' → 挂单"""

    def test_off_hours_with_execute_at_creates_pending(self, repo, calendar):
        svc = _make_service(repo, calendar, datetime(2026, 7, 28, 20, 0))
        repo.get_account.return_value = _active_account()
        repo.create_pending_order.return_value = SimpleNamespace(id=42)

        result = svc.execute_trade(
            'acc', 'buy', '600519', shares=100,
            reason=REASON, execute_at='market_open')

        assert result['status'] == 'pending'
        assert result['pending_order_id'] == 42
        assert '9:31' in result['message']
        repo.create_pending_order.assert_called_once()
        kwargs = repo.create_pending_order.call_args.kwargs
        assert kwargs['account_name'] == 'acc'
        assert kwargs['action'] == 'buy'
        assert kwargs['symbol'] == '600519'
        assert kwargs['shares'] == 100
        assert kwargs['execute_at'] == 'market_open'

    def test_off_hours_without_execute_at_still_422(self, repo, calendar):
        """现有行为不变：无 execute_at 时非交易时段仍拒绝"""
        svc = _make_service(repo, calendar, datetime(2026, 7, 28, 20, 0))
        with pytest.raises(TradingError) as exc:
            svc.execute_trade('acc', 'buy', '600519', shares=100, reason=REASON)
        assert exc.value.status_code == 422
        repo.create_pending_order.assert_not_called()

    def test_in_window_with_execute_at_executes_directly(self, repo, calendar):
        """交易时段内带 execute_at → 直接成交，不落挂单"""
        svc = _make_service(repo, calendar, datetime(2026, 7, 28, 10, 0))
        _setup_trade_path(repo)

        result = svc.execute_trade(
            'acc', 'buy', '600519', shares=100,
            reason=REASON, price=10.0, execute_at='market_open')

        assert result['order_status'] == 'filled'
        assert result['shares'] == 100
        repo.create_pending_order.assert_not_called()

    def test_pending_validates_reason(self, repo, calendar):
        svc = _make_service(repo, calendar, datetime(2026, 7, 28, 20, 0))
        with pytest.raises(TradingError) as exc:
            svc.execute_trade('acc', 'buy', '600519', shares=100,
                              reason='太短', execute_at='market_open')
        assert exc.value.status_code == 400
        repo.create_pending_order.assert_not_called()

    def test_pending_validates_action(self, repo, calendar):
        svc = _make_service(repo, calendar, datetime(2026, 7, 28, 20, 0))
        with pytest.raises(TradingError) as exc:
            svc.execute_trade('acc', 'hold', '600519', shares=100,
                              reason=REASON, execute_at='market_open')
        assert exc.value.status_code == 400
        repo.create_pending_order.assert_not_called()

    def test_pending_validates_account_exists(self, repo, calendar):
        svc = _make_service(repo, calendar, datetime(2026, 7, 28, 20, 0))
        repo.get_account.return_value = None
        with pytest.raises(TradingError) as exc:
            svc.execute_trade('ghost', 'buy', '600519', shares=100,
                              reason=REASON, execute_at='market_open')
        assert exc.value.status_code == 404
        repo.create_pending_order.assert_not_called()

    def test_pending_validates_account_active(self, repo, calendar):
        svc = _make_service(repo, calendar, datetime(2026, 7, 28, 20, 0))
        repo.get_account.return_value = _active_account(status='archived')
        with pytest.raises(TradingError) as exc:
            svc.execute_trade('acc', 'buy', '600519', shares=100,
                              reason=REASON, execute_at='market_open')
        assert exc.value.status_code == 409
        repo.create_pending_order.assert_not_called()

    def test_invalid_execute_at_rejected(self, repo, calendar):
        svc = _make_service(repo, calendar, datetime(2026, 7, 28, 20, 0))
        with pytest.raises(TradingError) as exc:
            svc.execute_trade('acc', 'buy', '600519', shares=100,
                              reason=REASON, execute_at='next_week')
        assert exc.value.status_code == 400
        repo.create_pending_order.assert_not_called()


# ---------- execute_pending_orders ----------

class TestExecutePendingOrders:
    def test_success_marks_executed(self, repo, calendar):
        svc = _make_service(repo, calendar, datetime(2026, 7, 28, 9, 31))
        _setup_trade_path(repo)
        svc._get_price = lambda symbol: 10.0  # 撮合时取价，避免真实行情
        repo.get_pending_orders.return_value = [_pending_order(id=1)]

        result = svc.execute_pending_orders()

        assert result['executed'] == 1
        assert result['failed'] == 0
        assert result['details'][0]['status'] == 'executed'
        assert result['details'][0]['trade_id'] == 7
        repo.update_pending_order_status.assert_called_once_with(
            1, 'executed', executed_trade_id=7)

    def test_guardrail_rejection_marks_failed(self, repo, calendar):
        """护栏拒绝（如账户不存在）→ failed + fail_reason"""
        svc = _make_service(repo, calendar, datetime(2026, 7, 28, 9, 31))
        repo.get_account.return_value = None  # 账户不存在 → 404
        repo.get_pending_orders.return_value = [_pending_order(id=2)]

        result = svc.execute_pending_orders()

        assert result['executed'] == 0
        assert result['failed'] == 1
        assert result['details'][0]['status'] == 'failed'
        assert '账户不存在' in result['details'][0]['fail_reason']
        repo.update_pending_order_status.assert_called_once_with(
            2, 'failed', fail_reason=result['details'][0]['fail_reason'])

    def test_idempotent_no_pending(self, repo, calendar):
        """无 pending 订单时是 no-op（每个 tick 幂等）"""
        svc = _make_service(repo, calendar, datetime(2026, 7, 28, 9, 32))
        repo.get_pending_orders.return_value = []

        result = svc.execute_pending_orders()

        assert result == {'executed': 0, 'failed': 0, 'details': []}
        repo.update_pending_order_status.assert_not_called()

    def test_mixed_outcomes(self, repo, calendar):
        svc = _make_service(repo, calendar, datetime(2026, 7, 28, 9, 31))
        _setup_trade_path(repo)
        svc._get_price = lambda symbol: 10.0  # 撮合时取价，避免真实行情
        orders = [_pending_order(id=1, account_name='acc'),
                  _pending_order(id=2, account_name='ghost')]
        repo.get_pending_orders.return_value = orders

        def get_account(name):
            return _active_account() if name == 'acc' else None
        repo.get_account.side_effect = get_account
        repo.get_account_for_update.side_effect = get_account

        result = svc.execute_pending_orders()

        assert result['executed'] == 1
        assert result['failed'] == 1
        assert repo.update_pending_order_status.call_count == 2


# ---------- cancel ----------

class TestCancelPendingOrder:
    def test_cancel_pending_success(self, repo, calendar):
        svc = _make_service(repo, calendar, datetime(2026, 7, 28, 20, 0))
        repo.get_pending_order.return_value = _pending_order(id=5)

        result = svc.cancel_pending_order('acc', 5)

        assert result['status'] == 'cancelled'
        assert result['pending_order_id'] == 5
        repo.update_pending_order_status.assert_called_once_with(5, 'cancelled')

    def test_cancel_executed_rejected(self, repo, calendar):
        svc = _make_service(repo, calendar, datetime(2026, 7, 28, 20, 0))
        repo.get_pending_order.return_value = _pending_order(id=5, status='executed')

        with pytest.raises(TradingError) as exc:
            svc.cancel_pending_order('acc', 5)
        assert exc.value.status_code == 409
        repo.update_pending_order_status.assert_not_called()

    def test_cancel_not_found(self, repo, calendar):
        svc = _make_service(repo, calendar, datetime(2026, 7, 28, 20, 0))
        repo.get_pending_order.return_value = None

        with pytest.raises(TradingError) as exc:
            svc.cancel_pending_order('acc', 999)
        assert exc.value.status_code == 404

    def test_cancel_other_account_rejected(self, repo, calendar):
        svc = _make_service(repo, calendar, datetime(2026, 7, 28, 20, 0))
        repo.get_pending_order.return_value = _pending_order(
            id=5, account_name='someone_else')

        with pytest.raises(TradingError) as exc:
            svc.cancel_pending_order('acc', 5)
        assert exc.value.status_code == 404
        repo.update_pending_order_status.assert_not_called()
