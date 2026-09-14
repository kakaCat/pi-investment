"""
AccountTradingService.execute_trade 集成测试

测试覆盖：
- 买入成功
- 卖出成功
- 交易护栏校验
- 锁内复核
- 事务回滚
"""

import pytest
from datetime import datetime, time as dt_time
from unittest.mock import Mock, MagicMock, patch

from application.services.account_trading_service import AccountTradingService, TradingError


class MockAccount:
    """Mock 账户"""
    def __init__(self, name, cash_available=100000, cash_frozen=0, status='active',
                 position_value=0, total_value=None, initial_capital=100000,
                 peak_value=100000, cumulative_return=0):
        self.account_name = name
        self.cash_available = cash_available
        self.cash_frozen = cash_frozen
        self.status = status
        self.position_value = position_value
        self.total_value = total_value or (cash_available + cash_frozen + position_value)
        self.initial_capital = initial_capital
        self.peak_value = peak_value
        self.cumulative_return = cumulative_return


class MockPosition:
    """Mock 持仓"""
    def __init__(self, symbol, shares_total, shares_available, avg_cost,
                 current_price=None, market_value=None):
        self.symbol = symbol
        self.shares_total = shares_total
        self.shares_available = shares_available
        self.avg_cost = avg_cost
        self.current_price = current_price or avg_cost
        self.market_value = market_value or (shares_total * (current_price or avg_cost))


class MockOrder:
    """Mock 订单"""
    def __init__(self, order_id):
        self.id = order_id
        self.status = 'pending'
        self.filled_shares = 0
        self.avg_filled_price = 0


class TestExecuteTradeV2Buy:
    """买入测试"""

    def test_buy_success(self):
        """买入成功"""
        # Mock 仓储
        mock_repo = Mock()
        mock_repo.get_account.return_value = MockAccount('test', cash_available=50000)
        mock_repo.get_account_for_update.return_value = MockAccount('test', cash_available=50000)
        mock_repo.get_all_positions.return_value = []
        mock_repo.get_trades_by_account.return_value = []

        mock_order = MockOrder(1)
        mock_repo.create_order.return_value = mock_order
        mock_repo.add_trade.return_value = 1
        mock_repo.upsert_position.return_value = True
        mock_repo.upsert_equity_snapshot.return_value = True

        mock_session = Mock()
        mock_repo.session = mock_session

        # Mock 日历
        mock_calendar = Mock()
        mock_calendar.is_trading_day.return_value = True

        # Mock 时间（周一 10:00）
        now_fn = lambda: datetime(2026, 9, 1, 10, 0, 0)

        # Mock 行情
        with patch('application.services.realtime_quote_service.RealtimeQuoteService') as mock_quote_service:
            mock_quote = Mock()
            mock_quote.price = 10.0
            mock_quote_service.return_value.get_realtime_quote.return_value = mock_quote

            service = AccountTradingService(
                repo=mock_repo,
                calendar=mock_calendar,
                now_fn=now_fn
            )

            # 执行买入
            result = service.execute_trade(
                account_name='test',
                action='buy',
                symbol='600000.SH',
                shares=1000,
                reason='测试买入理由至少十个字'
            )

        # 验证结果
        assert result['action'] == 'buy'
        assert result['shares'] == 1000
        assert result['price'] == 10.0
        assert result['amount'] == 10000.0
        assert result['commission'] >= 5.0
        assert result['trade_id'] == 1

        # 验证调用
        mock_repo.get_account_for_update.assert_called_once_with('test')
        mock_repo.create_order.assert_called_once()
        mock_repo.add_trade.assert_called_once()
        mock_repo.upsert_position.assert_called_once()
        mock_session.commit.assert_called_once()

    def test_buy_insufficient_funds_lock_check(self):
        """买入 - 锁内复核资金不足"""
        mock_repo = Mock()
        # 锁外检查通过
        mock_repo.get_account.return_value = MockAccount('test', cash_available=50000)

        # 锁内检查失败（资金被其他事务扣减）
        mock_repo.get_account_for_update.return_value = MockAccount('test', cash_available=500)

        mock_repo.get_all_positions.return_value = []
        mock_repo.get_trades_by_account.return_value = []

        mock_session = Mock()
        mock_repo.session = mock_session

        mock_calendar = Mock()
        mock_calendar.is_trading_day.return_value = True
        now_fn = lambda: datetime(2026, 9, 1, 10, 0, 0)

        with patch('application.services.realtime_quote_service.RealtimeQuoteService') as mock_quote_service:
            mock_quote = Mock()
            mock_quote.price = 10.0
            mock_quote_service.return_value.get_realtime_quote.return_value = mock_quote

            service = AccountTradingService(
                repo=mock_repo,
                calendar=mock_calendar,
                now_fn=now_fn
            )

            # 应该在锁内复核时失败
            with pytest.raises(TradingError) as exc_info:
                service.execute_trade(
                    account_name='test',
                    action='buy',
                    symbol='600000.SH',
                    shares=1000,
                    reason='测试买入理由至少十个字'
                )

            assert '锁内复核' in str(exc_info.value)
            mock_session.rollback.assert_called_once()

    def test_buy_exceeds_position_limit(self):
        """买入 - 超过仓位限制"""
        mock_repo = Mock()
        # 已有大量持仓
        existing_positions = [
            MockPosition(f'60000{i}.SH', 10000, 10000, 10.0)
            for i in range(5)
        ]

        mock_repo.get_account.return_value = MockAccount(
            'test',
            cash_available=50000,
            position_value=500000  # 大量持仓
        )
        mock_repo.get_all_positions.return_value = existing_positions
        mock_repo.get_trades_by_account.return_value = []

        mock_calendar = Mock()
        mock_calendar.is_trading_day.return_value = True
        now_fn = lambda: datetime(2026, 9, 1, 10, 0, 0)

        with patch('application.services.realtime_quote_service.RealtimeQuoteService') as mock_quote_service:
            mock_quote = Mock()
            mock_quote.price = 10.0
            mock_quote_service.return_value.get_realtime_quote.return_value = mock_quote

            service = AccountTradingService(
                repo=mock_repo,
                calendar=mock_calendar,
                now_fn=now_fn
            )

            # 应该被 TradeGuardService 拒绝
            with pytest.raises(TradingError) as exc_info:
                service.execute_trade(
                    account_name='test',
                    action='buy',
                    symbol='600000.SH',
                    shares=5000,  # 大额买入
                    reason='测试买入理由至少十个字'
                )

            # 可能是总仓位超限或单票仓位超限
            assert '仓位超限' in str(exc_info.value)


class TestExecuteTradeV2Sell:
    """卖出测试"""

    def test_sell_success(self):
        """卖出成功"""
        mock_repo = Mock()
        mock_repo.get_account.return_value = MockAccount('test', cash_available=50000)
        mock_repo.get_account_for_update.return_value = MockAccount('test', cash_available=50000)

        # 有持仓
        position = MockPosition('600000.SH', 1000, 1000, 10.0, current_price=12.0)
        mock_repo.get_all_positions.return_value = [position]

        mock_order = MockOrder(1)
        mock_repo.create_order.return_value = mock_order
        mock_repo.add_trade.return_value = 1
        mock_repo.upsert_position.return_value = True
        mock_repo.upsert_equity_snapshot.return_value = True

        mock_session = Mock()
        mock_repo.session = mock_session

        mock_calendar = Mock()
        mock_calendar.is_trading_day.return_value = True
        now_fn = lambda: datetime(2026, 9, 1, 10, 0, 0)

        with patch('application.services.realtime_quote_service.RealtimeQuoteService') as mock_quote_service:
            mock_quote = Mock()
            mock_quote.price = 12.0
            mock_quote_service.return_value.get_realtime_quote.return_value = mock_quote

            service = AccountTradingService(
                repo=mock_repo,
                calendar=mock_calendar,
                now_fn=now_fn
            )

            result = service.execute_trade(
                account_name='test',
                action='sell',
                symbol='600000.SH',
                shares=500,
                reason='测试卖出理由至少十个字'
            )

        # 验证结果
        assert result['action'] == 'sell'
        assert result['shares'] == 500
        assert result['price'] == 12.0
        assert result['realized_pnl'] is not None  # 应该有盈亏

        mock_session.commit.assert_called_once()

    def test_sell_insufficient_position_lock_check(self):
        """卖出 - 锁内复核持仓不足"""
        mock_repo = Mock()
        mock_repo.get_account.return_value = MockAccount('test', cash_available=50000)
        mock_repo.get_account_for_update.return_value = MockAccount('test', cash_available=50000)

        # 锁外检查：有持仓
        position_outside = MockPosition('600000.SH', 1000, 1000, 10.0)
        mock_repo.get_all_positions.side_effect = [
            [position_outside],  # 第一次调用（TradeGuardService）
            []  # 第二次调用（锁内重读，持仓已被卖出）
        ]

        mock_session = Mock()
        mock_repo.session = mock_session

        mock_calendar = Mock()
        mock_calendar.is_trading_day.return_value = True
        now_fn = lambda: datetime(2026, 9, 1, 10, 0, 0)

        with patch('application.services.realtime_quote_service.RealtimeQuoteService') as mock_quote_service:
            mock_quote = Mock()
            mock_quote.price = 12.0
            mock_quote_service.return_value.get_realtime_quote.return_value = mock_quote

            service = AccountTradingService(
                repo=mock_repo,
                calendar=mock_calendar,
                now_fn=now_fn
            )

            # 应该在锁内复核时失败
            with pytest.raises(TradingError) as exc_info:
                service.execute_trade(
                    account_name='test',
                    action='sell',
                    symbol='600000.SH',
                    shares=500,
                    reason='测试卖出理由至少十个字'
                )

            assert '无 600000.SH 持仓' in str(exc_info.value)
            mock_session.rollback.assert_called_once()


class TestExecuteTradeV2Validation:
    """参数校验测试"""

    def test_invalid_reason(self):
        """理由太短"""
        service = AccountTradingService(repo=Mock())

        with pytest.raises(TradingError) as exc_info:
            service.execute_trade(
                account_name='test',
                action='buy',
                symbol='600000.SH',
                shares=100,
                reason='短'  # 少于10字
            )

        assert '至少10字' in str(exc_info.value)
        assert exc_info.value.status_code == 400

    def test_invalid_action(self):
        """无效的 action"""
        mock_repo = Mock()
        service = AccountTradingService(repo=mock_repo)

        with pytest.raises(TradingError) as exc_info:
            service.execute_trade(
                account_name='test',
                action='invalid',
                symbol='600000.SH',
                shares=100,
                reason='测试理由至少十个字'
            )

        # action 验证在 reason 之后
        assert exc_info.value.status_code == 400

    def test_shares_not_multiple_of_100(self):
        """股数不是100的整数倍"""
        mock_repo = Mock()
        mock_repo.get_account.return_value = MockAccount('test', cash_available=50000)
        mock_repo.get_all_positions.return_value = []
        mock_repo.get_trades_by_account.return_value = []

        mock_calendar = Mock()
        mock_calendar.is_trading_day.return_value = True
        now_fn = lambda: datetime(2026, 9, 1, 10, 0, 0)

        with patch('application.services.realtime_quote_service.RealtimeQuoteService') as mock_quote_service:
            mock_quote = Mock()
            mock_quote.price = 10.0
            mock_quote_service.return_value.get_realtime_quote.return_value = mock_quote

            service = AccountTradingService(
                repo=mock_repo,
                calendar=mock_calendar,
                now_fn=now_fn
            )

            with pytest.raises(TradingError) as exc_info:
                service.execute_trade(
                    account_name='test',
                    action='buy',
                    symbol='600000.SH',
                    shares=150,  # 不是100的整数倍
                    reason='测试理由至少十个字啊啊啊啊'
                )

            assert '100 的整数倍' in str(exc_info.value)


class TestExecuteTradeV2PendingOrder:
    """挂单测试"""

    def test_pending_order_after_hours(self):
        """盘后挂单"""
        mock_repo = Mock()
        mock_repo.get_account.return_value = MockAccount('test', status='active')
        mock_repo.get_pending_orders.return_value = []  # 无既有挂单 → 查重放行（2026-09-03）

        mock_pending = Mock()
        mock_pending.id = 1
        mock_repo.create_pending_order.return_value = mock_pending

        mock_calendar = Mock()
        mock_calendar.is_trading_day.return_value = True

        # 盘后时间（16:00）
        now_fn = lambda: datetime(2026, 9, 1, 16, 0, 0)

        service = AccountTradingService(
            repo=mock_repo,
            calendar=mock_calendar,
            now_fn=now_fn
        )

        result = service.execute_trade(
            account_name='test',
            action='buy',
            symbol='600000.SH',
            shares=100,
            reason='测试挂单理由至少十个字',
            execute_at='market_open'
        )

        # 验证挂单结果
        assert result['status'] == 'pending'
        assert result['pending_order_id'] == 1
        assert '挂单' in result['message']

        mock_repo.create_pending_order.assert_called_once()

    def test_pending_order_records_decision_price(self):
        """挂单必须把「决策时价 + 来源」写进挂单表（M5 执行质量闭环）。

        回归锚点（2026-09-14 w-2129d492）：原有用例只断言 create_pending_order 被调用，
        Mock 不校验参数 → 该路径把 decision_price 传给一个**没有该列的模型**时
        （构造即 TypeError），测试照样是绿的。
        """
        mock_repo = Mock()
        mock_repo.get_account.return_value = MockAccount('test', status='active')
        mock_repo.get_pending_orders.return_value = []
        mock_pending = Mock()
        mock_pending.id = 7
        mock_repo.create_pending_order.return_value = mock_pending

        mock_calendar = Mock()
        mock_calendar.is_trading_day.return_value = True

        service = AccountTradingService(
            repo=mock_repo,
            calendar=mock_calendar,
            now_fn=lambda: datetime(2026, 9, 1, 16, 0, 0),   # 盘后 → 走挂单
        )
        service._get_price = Mock(return_value=12.34)

        result = service.execute_trade(
            account_name='test', action='buy', symbol='600000.SH', shares=100,
            reason='测试挂单决策价理由至少十个字', execute_at='market_open',
        )

        assert result['status'] == 'pending'
        kwargs = mock_repo.create_pending_order.call_args.kwargs
        assert kwargs['decision_price'] == 12.34, '挂单必须记录决策时价（滑点基准）'
        assert kwargs['price_source'], '决策价来源必须可追溯（R-013）'

    def test_execute_pending_orders_records_slippage(self):
        """撮合后必须回填 fill_price 与方向归一后的 slippage_bps。

        正数 = 买贵/卖便宜 = 成本；缺决策价时留 None，绝不拿成交价自比冒充 0 滑点。
        """
        po = Mock()
        po.id = 11
        po.account_name = 'test'
        po.action = 'BUY'
        po.symbol = '600000.SH'
        po.shares = 100
        po.amount = None
        po.price_limit = None
        po.reason = '测试撮合理由至少十个字'
        po.decision_price = 10.0

        mock_repo = Mock()
        mock_repo.get_pending_orders.return_value = [po]

        service = AccountTradingService(
            repo=mock_repo,
            calendar=Mock(is_trading_day=Mock(return_value=True)),
            now_fn=lambda: datetime(2026, 9, 1, 9, 31, 0),
        )
        service.execute_trade = Mock(return_value={'price': 10.05, 'trade_id': 99})

        out = service.execute_pending_orders()

        assert out['executed'] == 1
        call = mock_repo.update_pending_order_status.call_args
        assert call.args[0] == 11, '回填必须落在该挂单行上'
        assert call.args[1] == 'executed'
        assert call.kwargs['fill_price'] == 10.05
        assert call.kwargs['slippage_bps'] == 50.0, '买入成交价高于决策价 → 正滑点（成本）'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
