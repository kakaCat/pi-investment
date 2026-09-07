"""
TradeGuardService 单元测试

测试覆盖：
- 交易时段校验
- 每日限额校验
- 资金充足性校验
- 持仓充足性校验
- 仓位比例校验
- 完整交易校验
"""

import pytest
from datetime import datetime, date, time as dt_time
from unittest.mock import Mock, MagicMock

from domain.trading.services.trade_guard_service import TradeGuardService, TradingError


class MockAccount:
    """Mock 账户"""
    def __init__(self, name, cash_available=100000, cash_frozen=0, status='active',
                 total_value=None, initial_capital=100000):
        self.account_name = name
        self.cash_available = cash_available
        self.cash_frozen = cash_frozen
        self.status = status
        self.total_value = total_value
        self.initial_capital = initial_capital


class MockPosition:
    """Mock 持仓"""
    def __init__(self, symbol, shares_total, shares_available, avg_cost,
                 current_price=None, market_value=None):
        self.symbol = symbol
        self.shares_total = shares_total
        self.shares_available = shares_available
        self.avg_cost = avg_cost
        self.current_price = current_price
        self.market_value = market_value


class MockTrade:
    """Mock 成交"""
    def __init__(self, action, amount):
        self.action = action
        self.amount = amount


class TestTradingWindow:
    """交易时段校验测试"""

    def test_validate_trading_window_success(self):
        """正常交易时段"""
        # 2026-09-01 是周一（交易日），10:00 在交易时段
        mock_calendar = Mock()
        mock_calendar.is_trading_day.return_value = True
        mock_repo = Mock()

        guard = TradeGuardService(
            repo=mock_repo,
            calendar=mock_calendar,
            now_fn=lambda: datetime(2026, 9, 1, 10, 0, 0)
        )

        # 应该不抛异常
        guard.validate_trading_window()

    def test_validate_trading_window_non_trading_day(self):
        """非交易日"""
        mock_calendar = Mock()
        mock_calendar.is_trading_day.return_value = False
        mock_repo = Mock()

        guard = TradeGuardService(
            repo=mock_repo,
            calendar=mock_calendar,
            now_fn=lambda: datetime(2026, 9, 6, 10, 0, 0)  # 周六
        )

        with pytest.raises(TradingError) as exc_info:
            guard.validate_trading_window()

        assert '非交易日' in str(exc_info.value)
        assert exc_info.value.status_code == 422

    def test_validate_trading_window_before_open(self):
        """开盘前"""
        mock_calendar = Mock()
        mock_calendar.is_trading_day.return_value = True
        mock_repo = Mock()

        guard = TradeGuardService(
            repo=mock_repo,
            calendar=mock_calendar,
            now_fn=lambda: datetime(2026, 9, 1, 9, 0, 0)  # 9:00
        )

        with pytest.raises(TradingError) as exc_info:
            guard.validate_trading_window()

        assert '非交易时段' in str(exc_info.value)
        assert exc_info.value.status_code == 422

    def test_validate_trading_window_lunch_break(self):
        """午休时段"""
        mock_calendar = Mock()
        mock_calendar.is_trading_day.return_value = True
        mock_repo = Mock()

        guard = TradeGuardService(
            repo=mock_repo,
            calendar=mock_calendar,
            now_fn=lambda: datetime(2026, 9, 1, 12, 0, 0)  # 12:00
        )

        with pytest.raises(TradingError) as exc_info:
            guard.validate_trading_window()

        assert '非交易时段' in str(exc_info.value)

    def test_validate_trading_window_afternoon_session(self):
        """下午盘"""
        mock_calendar = Mock()
        mock_calendar.is_trading_day.return_value = True
        mock_repo = Mock()

        guard = TradeGuardService(
            repo=mock_repo,
            calendar=mock_calendar,
            now_fn=lambda: datetime(2026, 9, 1, 14, 30, 0)  # 14:30
        )

        # 应该不抛异常
        guard.validate_trading_window()

    def test_is_in_trading_window_true(self):
        """is_in_trading_window 返回 True"""
        mock_calendar = Mock()
        mock_calendar.is_trading_day.return_value = True
        mock_repo = Mock()

        guard = TradeGuardService(
            repo=mock_repo,
            calendar=mock_calendar,
            now_fn=lambda: datetime(2026, 9, 1, 10, 0, 0)
        )

        assert guard.is_in_trading_window() is True

    def test_is_in_trading_window_false(self):
        """is_in_trading_window 返回 False"""
        mock_calendar = Mock()
        mock_calendar.is_trading_day.return_value = False
        mock_repo = Mock()

        guard = TradeGuardService(
            repo=mock_repo,
            calendar=mock_calendar,
            now_fn=lambda: datetime(2026, 9, 6, 10, 0, 0)
        )

        assert guard.is_in_trading_window() is False


class TestDailyBuyLimits:
    """每日限额校验测试"""

    def test_validate_daily_buy_limits_success(self):
        """正常情况"""
        mock_repo = Mock()
        mock_repo.get_trades_by_account.return_value = []  # 今日无交易

        guard = TradeGuardService(repo=mock_repo)

        # 应该不抛异常
        guard.validate_daily_buy_limits(
            account_name='test',
            trade_amount=10000,
            total_value=100000
        )

    def test_validate_daily_buy_limits_count_exceeded(self):
        """笔数超限"""
        mock_repo = Mock()
        # 今日已买 5 笔
        mock_repo.get_trades_by_account.return_value = [
            MockTrade('BUY', 10000) for _ in range(5)
        ]

        guard = TradeGuardService(repo=mock_repo)

        with pytest.raises(TradingError) as exc_info:
            guard.validate_daily_buy_limits(
                account_name='test',
                trade_amount=10000,
                total_value=100000
            )

        assert '单日买入笔数超限' in str(exc_info.value)
        assert exc_info.value.status_code == 422

    def test_validate_daily_buy_limits_amount_exceeded(self):
        """金额超限"""
        mock_repo = Mock()
        # 今日已买 40000
        mock_repo.get_trades_by_account.return_value = [
            MockTrade('BUY', 40000)
        ]

        guard = TradeGuardService(repo=mock_repo)

        with pytest.raises(TradingError) as exc_info:
            # 本次 15000，总计 55000，超过 50%
            guard.validate_daily_buy_limits(
                account_name='test',
                trade_amount=15000,
                total_value=100000
            )

        assert '单日买入金额超限' in str(exc_info.value)
        assert exc_info.value.status_code == 422

    def test_validate_daily_buy_limits_ignore_sell(self):
        """忽略卖出交易"""
        mock_repo = Mock()
        # 今日有卖出，不计入买入限额
        mock_repo.get_trades_by_account.return_value = [
            MockTrade('SELL', 50000),
            MockTrade('BUY', 10000)
        ]

        guard = TradeGuardService(repo=mock_repo)

        # 应该不抛异常（只有 1 笔买入）
        guard.validate_daily_buy_limits(
            account_name='test',
            trade_amount=10000,
            total_value=100000
        )


class TestSufficientFunds:
    """资金充足性校验测试"""

    def test_validate_sufficient_funds_success(self):
        """资金充足"""
        mock_repo = Mock()
        mock_repo.get_account.return_value = MockAccount('test', cash_available=50000)

        guard = TradeGuardService(repo=mock_repo)

        result = guard.validate_sufficient_funds(
            account_name='test',
            symbol='600000.SH',
            shares=100,
            price=10.0
        )

        assert result['trade_amount'] == 1000.0
        assert result['commission'] >= 5.0
        assert result['total_cost'] > 1000.0

    def test_validate_sufficient_funds_insufficient(self):
        """资金不足"""
        mock_repo = Mock()
        mock_repo.get_account.return_value = MockAccount('test', cash_available=500)

        guard = TradeGuardService(repo=mock_repo)

        with pytest.raises(TradingError) as exc_info:
            guard.validate_sufficient_funds(
                account_name='test',
                symbol='600000.SH',
                shares=100,
                price=10.0
            )

        assert '可用资金不足' in str(exc_info.value)
        assert exc_info.value.status_code == 422

    def test_validate_sufficient_funds_account_not_found(self):
        """账户不存在"""
        mock_repo = Mock()
        mock_repo.get_account.return_value = None

        guard = TradeGuardService(repo=mock_repo)

        with pytest.raises(TradingError) as exc_info:
            guard.validate_sufficient_funds(
                account_name='test',
                symbol='600000.SH',
                shares=100,
                price=10.0
            )

        assert '账户不存在' in str(exc_info.value)
        assert exc_info.value.status_code == 404

    def test_validate_sufficient_funds_commission_calculation(self):
        """佣金计算（最低 5 元）"""
        mock_repo = Mock()
        mock_repo.get_account.return_value = MockAccount('test', cash_available=50000)

        guard = TradeGuardService(repo=mock_repo)

        # 小额交易，佣金应为最低 5 元
        result = guard.validate_sufficient_funds(
            account_name='test',
            symbol='600000.SH',
            shares=100,
            price=0.1  # 仅 10 元交易额
        )

        assert result['commission'] == 5.0  # 最低佣金


class TestSufficientPosition:
    """持仓充足性校验测试"""

    def test_validate_sufficient_position_success(self):
        """持仓充足"""
        mock_repo = Mock()
        mock_repo.get_all_positions.return_value = [
            MockPosition('600000.SH', shares_total=1000, shares_available=1000, avg_cost=10.0)
        ]

        guard = TradeGuardService(repo=mock_repo)

        result = guard.validate_sufficient_position(
            account_name='test',
            symbol='600000.SH',
            shares=500,
            price=12.0
        )

        assert result['trade_amount'] == 6000.0
        assert 'realized_pnl' in result
        assert 'realized_pnl_rate' in result

    def test_validate_sufficient_position_no_position(self):
        """无持仓"""
        mock_repo = Mock()
        mock_repo.get_all_positions.return_value = []

        guard = TradeGuardService(repo=mock_repo)

        with pytest.raises(TradingError) as exc_info:
            guard.validate_sufficient_position(
                account_name='test',
                symbol='600000.SH',
                shares=100,
                price=10.0
            )

        assert '无 600000.SH 持仓' in str(exc_info.value)
        assert exc_info.value.status_code == 422

    def test_validate_sufficient_position_t1_insufficient(self):
        """T+1 可卖数量不足"""
        mock_repo = Mock()
        mock_repo.get_all_positions.return_value = [
            MockPosition('600000.SH', shares_total=1000, shares_available=300, avg_cost=10.0)
        ]

        guard = TradeGuardService(repo=mock_repo)

        with pytest.raises(TradingError) as exc_info:
            guard.validate_sufficient_position(
                account_name='test',
                symbol='600000.SH',
                shares=500,  # 超过可卖数量
                price=12.0
            )

        assert 'T+1 可卖数量不足' in str(exc_info.value)
        assert exc_info.value.status_code == 422
        assert exc_info.value.details['sellable_shares'] == 300

    def test_validate_sufficient_position_pnl_calculation(self):
        """盈亏计算"""
        mock_repo = Mock()
        mock_repo.get_all_positions.return_value = [
            MockPosition('600000.SH', shares_total=1000, shares_available=1000, avg_cost=10.0)
        ]

        guard = TradeGuardService(repo=mock_repo)

        result = guard.validate_sufficient_position(
            account_name='test',
            symbol='600000.SH',
            shares=100,
            price=15.0  # 成本 10，卖价 15
        )

        # 盈利 = 1500 - 1000 - 佣金 - 印花税 - 过户费
        assert result['realized_pnl'] > 0
        assert result['realized_pnl_rate'] > 0


class TestPositionLimits:
    """仓位比例校验测试"""

    def test_validate_position_limits_success(self):
        """正常情况"""
        mock_repo = Mock()
        mock_repo.get_account.return_value = MockAccount('test', cash_available=80000)
        mock_repo.get_all_positions.return_value = [
            MockPosition('600001.SH', shares_total=1000, shares_available=1000,
                        avg_cost=10.0, current_price=10.0, market_value=10000)
        ]

        guard = TradeGuardService(repo=mock_repo)

        # 买入 10000 元，总资产 90000，单票占比 22%，总仓位 22%
        guard.validate_position_limits(
            account_name='test',
            symbol='600000.SH',
            shares=1000,
            price=10.0
        )

    def test_validate_position_limits_single_position_exceeded(self):
        """单票仓位超限"""
        mock_repo = Mock()
        mock_repo.get_account.return_value = MockAccount('test', cash_available=50000)
        mock_repo.get_all_positions.return_value = [
            MockPosition('600000.SH', shares_total=1000, shares_available=1000,
                        avg_cost=10.0, current_price=15.0, market_value=15000)
        ]

        guard = TradeGuardService(repo=mock_repo)

        with pytest.raises(TradingError) as exc_info:
            # 再买 20000，单票总计 35000，占比 35000/70000 = 50% > 30%
            guard.validate_position_limits(
                account_name='test',
                symbol='600000.SH',
                shares=2000,
                price=10.0
            )

        assert '单票仓位超限' in str(exc_info.value)

    def test_validate_position_limits_total_position_exceeded(self):
        """总仓位超限"""
        mock_repo = Mock()
        mock_repo.get_account.return_value = MockAccount('test', cash_available=20000)
        mock_repo.get_all_positions.return_value = [
            MockPosition('600001.SH', shares_total=1000, shares_available=1000,
                        avg_cost=50.0, current_price=50.0, market_value=50000)
        ]

        guard = TradeGuardService(repo=mock_repo)

        with pytest.raises(TradingError) as exc_info:
            # 买入 15000，总仓位 65000/85000 = 76%，再买将超 80%
            guard.validate_position_limits(
                account_name='test',
                symbol='600000.SH',
                shares=2000,
                price=10.0
            )

        assert '总仓位超限' in str(exc_info.value)

    def test_validate_position_limits_max_positions_exceeded(self):
        """持仓数量超限"""
        mock_repo = Mock()
        mock_repo.get_account.return_value = MockAccount('test', cash_available=80000)
        # 已持有 10 只
        mock_repo.get_all_positions.return_value = [
            MockPosition(f'60000{i}.SH', shares_total=100, shares_available=100,
                        avg_cost=10.0, current_price=10.0, market_value=1000)
            for i in range(10)
        ]

        guard = TradeGuardService(repo=mock_repo)

        with pytest.raises(TradingError) as exc_info:
            # 买入新股票，将超过 10 只上限
            guard.validate_position_limits(
                account_name='test',
                symbol='600999.SH',
                shares=100,
                price=10.0,
                max_positions=10
            )

        assert '持仓数量超限' in str(exc_info.value)


class TestCompleteValidation:
    """完整交易校验测试"""

    def test_validate_trade_request_buy_success(self):
        """买入 - 成功"""
        mock_calendar = Mock()
        mock_calendar.is_trading_day.return_value = True
        mock_repo = Mock()
        mock_repo.get_account.return_value = MockAccount('test', cash_available=50000)
        mock_repo.get_all_positions.return_value = []
        mock_repo.get_trades_by_account.return_value = []

        guard = TradeGuardService(
            repo=mock_repo,
            calendar=mock_calendar,
            now_fn=lambda: datetime(2026, 9, 1, 10, 0, 0)
        )

        result = guard.validate_trade_request(
            account_name='test',
            action='BUY',
            symbol='600000.SH',
            shares=100,
            price=10.0
        )

        assert 'total_cost' in result

    def test_validate_trade_request_sell_success(self):
        """卖出 - 成功"""
        mock_calendar = Mock()
        mock_calendar.is_trading_day.return_value = True
        mock_repo = Mock()
        mock_repo.get_account.return_value = MockAccount('test', cash_available=50000)
        mock_repo.get_all_positions.return_value = [
            MockPosition('600000.SH', shares_total=1000, shares_available=1000, avg_cost=10.0)
        ]

        guard = TradeGuardService(
            repo=mock_repo,
            calendar=mock_calendar,
            now_fn=lambda: datetime(2026, 9, 1, 10, 0, 0)
        )

        result = guard.validate_trade_request(
            account_name='test',
            action='SELL',
            symbol='600000.SH',
            shares=100,
            price=12.0
        )

        assert 'realized_pnl' in result

    def test_validate_trade_request_account_archived(self):
        """账户已归档"""
        mock_calendar = Mock()
        mock_calendar.is_trading_day.return_value = True
        mock_repo = Mock()
        mock_repo.get_account.return_value = MockAccount('test', status='archived')

        guard = TradeGuardService(
            repo=mock_repo,
            calendar=mock_calendar,
            now_fn=lambda: datetime(2026, 9, 1, 10, 0, 0)
        )

        with pytest.raises(TradingError) as exc_info:
            guard.validate_trade_request(
                account_name='test',
                action='BUY',
                symbol='600000.SH',
                shares=100,
                price=10.0
            )

        assert '账户已归档' in str(exc_info.value)
        assert exc_info.value.status_code == 409

    def test_validate_trade_request_off_hours_allowed(self):
        """允许盘后交易"""
        mock_calendar = Mock()
        mock_calendar.is_trading_day.return_value = True
        mock_repo = Mock()
        mock_repo.get_account.return_value = MockAccount('test', cash_available=50000)
        mock_repo.get_all_positions.return_value = []
        mock_repo.get_trades_by_account.return_value = []

        guard = TradeGuardService(
            repo=mock_repo,
            calendar=mock_calendar,
            now_fn=lambda: datetime(2026, 9, 1, 16, 0, 0)  # 收盘后
        )

        # allow_off_hours=True 应该不抛异常
        result = guard.validate_trade_request(
            account_name='test',
            action='BUY',
            symbol='600000.SH',
            shares=100,
            price=10.0,
            allow_off_hours=True
        )

        assert 'total_cost' in result
