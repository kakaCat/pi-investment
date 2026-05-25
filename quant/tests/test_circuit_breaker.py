"""
熔断机制单元测试
"""

import unittest
from datetime import datetime, timedelta
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from quantsys.risk import CircuitBreaker, CircuitBreakerConfig
from quantsys.backtest.portfolio import Portfolio


class TestCircuitBreaker(unittest.TestCase):
    """熔断机制测试"""

    def setUp(self):
        """测试前准备"""
        self.config = CircuitBreakerConfig(
            daily_loss_limit=0.05,
            consecutive_loss_limit=3,
            max_drawdown_limit=0.20
        )
        self.breaker = CircuitBreaker(self.config)
        self.portfolio = Portfolio(initial_capital=1000000)

    def test_daily_loss_halt(self):
        """测试单日亏损熔断"""
        # 模拟单日亏损6%
        self.portfolio.cash = 940000
        self.portfolio.total_equity = 940000

        # 添加权益曲线
        from quantsys.backtest.engine import DailyEquity
        self.portfolio.equity_curve = [
            DailyEquity('2024-01-01', 1000000, 0, 1000000, 0, 0),
            DailyEquity('2024-01-02', 940000, 0, 940000, -0.06, 0.06)
        ]

        should_halt, level, reason = self.breaker.check(
            portfolio=self.portfolio,
            current_date='2024-01-02'
        )

        self.assertTrue(should_halt)
        self.assertEqual(level, 'HALT')
        self.assertIn('单日亏损', reason)

    def test_daily_loss_warning(self):
        """测试单日亏损预警"""
        # 模拟单日亏损3.5%（超过预警线3%，但未达熔断线5%）
        self.portfolio.cash = 965000
        self.portfolio.total_equity = 965000

        from quantsys.backtest.engine import DailyEquity
        self.portfolio.equity_curve = [
            DailyEquity('2024-01-01', 1000000, 0, 1000000, 0, 0),
            DailyEquity('2024-01-02', 965000, 0, 965000, -0.035, 0.035)
        ]

        should_halt, level, reason = self.breaker.check(
            portfolio=self.portfolio,
            current_date='2024-01-02'
        )

        self.assertFalse(should_halt)
        self.assertEqual(level, 'WARN')
        self.assertIn('预警', reason)

    def test_consecutive_loss_halt(self):
        """测试连续亏损熔断"""
        trades = [
            {'pnl': -10000, 'strategy_id': 'test'},
            {'pnl': -8000, 'strategy_id': 'test'},
            {'pnl': -5000, 'strategy_id': 'test'},
        ]

        should_halt, level, reason = self.breaker.check(
            portfolio=self.portfolio,
            recent_trades=trades
        )

        self.assertTrue(should_halt)
        self.assertEqual(level, 'HALT')
        self.assertIn('连续亏损', reason)

    def test_consecutive_loss_warning(self):
        """测试连续亏损预警"""
        trades = [
            {'pnl': -10000, 'strategy_id': 'test'},
            {'pnl': -8000, 'strategy_id': 'test'},
        ]

        should_halt, level, reason = self.breaker.check(
            portfolio=self.portfolio,
            recent_trades=trades
        )

        self.assertFalse(should_halt)
        self.assertEqual(level, 'WARN')
        self.assertIn('预警', reason)

    def test_max_drawdown_halt(self):
        """测试最大回撤熔断"""
        # 设置峰值
        self.breaker.peak_equity = 1000000

        # 当前权益下降25%
        self.portfolio.total_equity = 750000

        should_halt, level, reason = self.breaker.check(
            portfolio=self.portfolio
        )

        self.assertTrue(should_halt)
        self.assertEqual(level, 'HALT')
        self.assertIn('回撤', reason)

    def test_strategy_consecutive_failure(self):
        """测试单策略连续失败"""
        trades = [
            {'pnl': -5000, 'strategy_id': 'strategy_a'},
            {'pnl': -5000, 'strategy_id': 'strategy_a'},
            {'pnl': -5000, 'strategy_id': 'strategy_a'},
            {'pnl': -5000, 'strategy_id': 'strategy_a'},
            {'pnl': -5000, 'strategy_id': 'strategy_a'},
        ]

        should_halt, level, reason = self.breaker.check(
            portfolio=self.portfolio,
            recent_trades=trades
        )

        self.assertTrue(should_halt)
        self.assertEqual(level, 'HALT')
        self.assertIn('strategy_a', reason)

    def test_update_trade_result(self):
        """测试交易结果更新"""
        # 连续亏损
        for i in range(3):
            self.breaker.update_trade_result({'pnl': -1000, 'strategy_id': 'test'})

        self.assertEqual(self.breaker.consecutive_losses, 3)
        self.assertEqual(self.breaker.consecutive_wins, 0)

        # 盈利，重置连续亏损
        self.breaker.update_trade_result({'pnl': 2000, 'strategy_id': 'test'})

        self.assertEqual(self.breaker.consecutive_losses, 0)
        self.assertEqual(self.breaker.consecutive_wins, 1)

    def test_halt_and_resume(self):
        """测试熔断和恢复"""
        # 触发熔断
        self.breaker.halt('测试熔断', 'test', 0.1, 0.05)

        self.assertTrue(self.breaker.is_halted)
        self.assertEqual(self.breaker.halt_reason, '测试熔断')
        self.assertIsNotNone(self.breaker.halt_timestamp)

        # 恢复
        self.breaker.resume('测试恢复')

        self.assertFalse(self.breaker.is_halted)
        self.assertIsNone(self.breaker.halt_reason)

    def test_auto_resume(self):
        """测试自动恢复"""
        # 启用自动恢复
        config = CircuitBreakerConfig(
            auto_resume_enabled=True,
            auto_resume_delay_minutes=1  # 1分钟后恢复
        )
        breaker = CircuitBreaker(config)

        # 触发熔断
        breaker.halt('测试', 'test', 0.1, 0.05)

        # 模拟时间流逝
        breaker.halt_timestamp = datetime.now() - timedelta(minutes=2)

        # 检查应该自动恢复
        should_halt, level, reason = breaker.check(self.portfolio)

        self.assertFalse(should_halt)
        self.assertFalse(breaker.is_halted)

    def test_get_status(self):
        """测试获取状态"""
        status = self.breaker.get_status()

        self.assertIn('is_halted', status)
        self.assertIn('consecutive_losses', status)
        self.assertIn('current_drawdown', status)
        self.assertFalse(status['is_halted'])

    def test_get_statistics(self):
        """测试获取统计"""
        # 触发几次熔断
        self.breaker.halt('测试1', 'daily_loss', 0.06, 0.05)
        self.breaker.resume()
        self.breaker.halt('测试2', 'consecutive_loss', 3, 3, 'strategy_a')

        stats = self.breaker.get_statistics()

        self.assertEqual(stats['total_halts'], 2)
        self.assertIn('daily_loss', stats['halt_by_type'])
        self.assertIn('consecutive_loss', stats['halt_by_type'])

    def test_no_halt_on_profit(self):
        """测试盈利时不触发熔断"""
        trades = [
            {'pnl': 10000, 'strategy_id': 'test'},
            {'pnl': 8000, 'strategy_id': 'test'},
            {'pnl': 5000, 'strategy_id': 'test'},
        ]

        should_halt, level, reason = self.breaker.check(
            portfolio=self.portfolio,
            recent_trades=trades
        )

        self.assertFalse(should_halt)
        self.assertIsNone(level)
        self.assertIsNone(reason)

    def test_mixed_trades(self):
        """测试混合盈亏交易"""
        trades = [
            {'pnl': -10000, 'strategy_id': 'test'},
            {'pnl': 5000, 'strategy_id': 'test'},   # 盈利，打断连续亏损
            {'pnl': -8000, 'strategy_id': 'test'},
            {'pnl': -5000, 'strategy_id': 'test'},
        ]

        should_halt, level, reason = self.breaker.check(
            portfolio=self.portfolio,
            recent_trades=trades
        )

        # 只有最后2次连续亏损，不应触发熔断
        self.assertFalse(should_halt)


class TestCircuitBreakerConfig(unittest.TestCase):
    """熔断配置测试"""

    def test_default_config(self):
        """测试默认配置"""
        config = CircuitBreakerConfig()

        self.assertEqual(config.daily_loss_limit, 0.05)
        self.assertEqual(config.consecutive_loss_limit, 3)
        self.assertEqual(config.max_drawdown_limit, 0.20)
        self.assertFalse(config.auto_resume_enabled)

    def test_custom_config(self):
        """测试自定义配置"""
        config = CircuitBreakerConfig(
            daily_loss_limit=0.03,
            consecutive_loss_limit=2,
            auto_resume_enabled=True
        )

        self.assertEqual(config.daily_loss_limit, 0.03)
        self.assertEqual(config.consecutive_loss_limit, 2)
        self.assertTrue(config.auto_resume_enabled)


if __name__ == '__main__':
    unittest.main()
