"""
风控系统测试
"""

import unittest
from datetime import datetime, timedelta
from risk import PreTradeRiskCheck, RiskConfig, PositionManager, PositionSizeConfig, StopLossManager, StopLossConfig


class MockOrder:
    """模拟订单"""
    def __init__(self, symbol, action, price, shares, date):
        self.symbol = symbol
        self.action = action
        self.price = price
        self.shares = shares
        self.date = date


class MockPortfolio:
    """模拟投资组合"""
    def __init__(self, total_equity=1000000, cash=500000):
        self.total_equity = total_equity
        self.cash = cash
        self.positions = {}
        self.current_drawdown = 0.0


class TestPreTradeRiskCheck(unittest.TestCase):
    """预交易风控测试"""

    def setUp(self):
        self.config = RiskConfig(
            max_position_pct=0.10,
            max_sector_pct=0.30,
            max_drawdown=0.20,
            max_daily_trades=10,
            blacklist=['000001'],
            allow_st_stocks=False
        )
        self.risk_check = PreTradeRiskCheck(self.config)
        self.portfolio = MockPortfolio()

    def test_blacklist_check(self):
        """测试黑名单检查"""
        order = MockOrder('000001', 'buy', 10.0, 1000, '2024-01-01')
        is_valid, error = self.risk_check.check(order, self.portfolio)
        self.assertFalse(is_valid)
        self.assertIn('黑名单', error)

    def test_st_stock_check(self):
        """测试ST股票检查"""
        order = MockOrder('ST000002', 'buy', 5.0, 1000, '2024-01-01')
        is_valid, error = self.risk_check.check(order, self.portfolio)
        self.assertFalse(is_valid)
        self.assertIn('ST', error)

    def test_position_limit(self):
        """测试仓位限制"""
        # 买入超过10%仓位
        order = MockOrder('000002', 'buy', 10.0, 15000, '2024-01-01')  # 150000元 > 10%
        is_valid, error = self.risk_check.check(order, self.portfolio)
        self.assertFalse(is_valid)
        self.assertIn('仓位限制', error)

    def test_drawdown_limit(self):
        """测试回撤限制"""
        self.portfolio.current_drawdown = 0.25  # 25%回撤
        order = MockOrder('000002', 'buy', 10.0, 1000, '2024-01-01')
        is_valid, error = self.risk_check.check(order, self.portfolio)
        self.assertFalse(is_valid)
        self.assertIn('回撤', error)

    def test_daily_trade_limit(self):
        """测试单日交易次数限制"""
        order = MockOrder('000002', 'buy', 10.0, 1000, '2024-01-01')

        # 前10次应该通过
        for i in range(10):
            is_valid, _ = self.risk_check.check(order, self.portfolio)
            self.assertTrue(is_valid)

        # 第11次应该被拒绝
        is_valid, error = self.risk_check.check(order, self.portfolio)
        self.assertFalse(is_valid)
        self.assertIn('交易次数', error)

    def test_valid_order(self):
        """测试正常订单"""
        order = MockOrder('000002', 'buy', 10.0, 5000, '2024-01-01')  # 50000元 = 5%
        is_valid, error = self.risk_check.check(order, self.portfolio)
        self.assertTrue(is_valid)
        self.assertIsNone(error)


class TestStopLossManager(unittest.TestCase):
    """止损管理测试"""

    def setUp(self):
        self.config = StopLossConfig(
            method='fixed',
            fixed_pct=0.05,
            trailing_pct=0.10,
            max_holding_days=60
        )
        self.stop_mgr = StopLossManager(self.config)

    def test_fixed_stop_loss(self):
        """测试固定止损"""
        entry_price = 10.0
        current_price = 9.0  # 下跌10%

        should_stop, reason = self.stop_mgr.should_stop_loss(
            symbol='000001',
            entry_price=entry_price,
            current_price=current_price,
            highest_price=10.0,
            entry_date='2024-01-01',
            current_date='2024-01-10'
        )

        self.assertTrue(should_stop)
        self.assertIn('固定止损', reason)

    def test_trailing_stop_loss(self):
        """测试移动止损"""
        self.stop_mgr.config.method = 'trailing'

        entry_price = 10.0
        highest_price = 12.0  # 曾涨到12
        current_price = 10.5  # 从12回落到10.5 (回撤12.5%)

        should_stop, reason = self.stop_mgr.should_stop_loss(
            symbol='000001',
            entry_price=entry_price,
            current_price=current_price,
            highest_price=highest_price,
            entry_date='2024-01-01',
            current_date='2024-01-10'
        )

        self.assertTrue(should_stop)
        self.assertIn('移动止损', reason)

    def test_time_stop_loss(self):
        """测试时间止损"""
        should_stop, reason = self.stop_mgr.should_stop_loss(
            symbol='000001',
            entry_price=10.0,
            current_price=10.5,
            highest_price=11.0,
            entry_date='2024-01-01',
            current_date='2024-03-15'  # 持仓超过60天
        )

        self.assertTrue(should_stop)
        self.assertIn('时间止损', reason)

    def test_no_stop_loss(self):
        """测试不触发止损"""
        should_stop, reason = self.stop_mgr.should_stop_loss(
            symbol='000001',
            entry_price=10.0,
            current_price=10.2,  # 小幅上涨
            highest_price=10.5,
            entry_date='2024-01-01',
            current_date='2024-01-10'
        )

        self.assertFalse(should_stop)
        self.assertIsNone(reason)

    def test_batch_check_stops(self):
        """测试批量止损检查"""
        positions = {
            '000001': {
                'entry_price': 10.0,
                'entry_date': '2024-01-01',
                'highest_price': 10.5,
                'shares': 1000
            },
            '000002': {
                'entry_price': 20.0,
                'entry_date': '2024-01-01',
                'highest_price': 22.0,
                'shares': 500
            }
        }

        current_prices = {
            '000001': 9.0,   # 触发止损
            '000002': 21.0   # 不触发
        }

        stops = self.stop_mgr.batch_check_stops(
            positions, current_prices, '2024-01-10'
        )

        self.assertEqual(len(stops), 1)
        self.assertEqual(stops[0]['symbol'], '000001')


class TestPositionManager(unittest.TestCase):
    """仓位管理测试"""

    def setUp(self):
        self.config = PositionSizeConfig(
            method='fixed',
            fixed_pct=0.10,
            max_position_pct=0.20,
            min_position_pct=0.02
        )
        self.pos_mgr = PositionManager(self.config)

    def test_fixed_position(self):
        """测试固定仓位"""
        shares = self.pos_mgr.calculate_position_size(
            symbol='000001',
            price=10.0,
            total_equity=1000000,
            signal_strength=1.0
        )

        # 10% * 1000000 / 10 = 10000股
        self.assertEqual(shares, 10000)

    def test_signal_strength_adjustment(self):
        """测试信号强度调整"""
        # 信号强度50%
        shares = self.pos_mgr.calculate_position_size(
            symbol='000001',
            price=10.0,
            total_equity=1000000,
            signal_strength=0.5
        )

        # 10% * 0.5 * 1000000 / 10 = 5000股
        self.assertEqual(shares, 5000)

    def test_max_position_limit(self):
        """测试最大仓位限制"""
        # 尝试买入超过最大仓位
        shares = self.pos_mgr.calculate_position_size(
            symbol='000001',
            price=10.0,
            total_equity=1000000,
            signal_strength=3.0  # 信号强度300%
        )

        # 应该被限制在20%
        max_shares = int(1000000 * 0.20 / 10 / 100) * 100
        self.assertEqual(shares, max_shares)

    def test_min_position_limit(self):
        """测试最小仓位限制"""
        # 信号强度很弱
        shares = self.pos_mgr.calculate_position_size(
            symbol='000001',
            price=10.0,
            total_equity=1000000,
            signal_strength=0.01  # 信号强度1%
        )

        # 应该被限制在2%
        min_shares = int(1000000 * 0.02 / 10 / 100) * 100
        self.assertEqual(shares, min_shares)

    def test_kelly_position(self):
        """测试Kelly公式仓位"""
        self.pos_mgr.config.method = 'kelly'

        market_data = {
            'win_rate': 0.6,
            'profit_loss_ratio': 2.0
        }

        shares = self.pos_mgr.calculate_position_size(
            symbol='000001',
            price=10.0,
            total_equity=1000000,
            market_data=market_data
        )

        # Kelly = (0.6 * 2 - 0.4) / 2 = 0.4
        # 保守系数0.25: 0.4 * 0.25 = 0.1 = 10%
        self.assertGreater(shares, 0)

    def test_get_max_shares(self):
        """测试最大股数计算"""
        max_shares = self.pos_mgr.get_max_shares(
            price=10.0,
            total_equity=1000000
        )

        # 20% * 1000000 / 10 = 20000股
        self.assertEqual(max_shares, 20000)


if __name__ == '__main__':
    unittest.main()
