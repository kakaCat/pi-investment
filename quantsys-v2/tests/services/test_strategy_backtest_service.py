"""
策略回测服务单元测试
"""

import pytest
import pandas as pd
from application.services.strategy_backtest_service import StrategyBacktestService


class TestStrategyBacktestService:
    """测试策略回测服务"""

    def setup_method(self):
        """每个测试方法前执行"""
        self.service = StrategyBacktestService()

    def test_calculate_max_drawdown(self):
        """测试最大回撤计算"""
        # 权益曲线: 100 -> 120 -> 90 -> 110
        equities = [100, 120, 90, 110]

        max_dd = self.service.calculate_max_drawdown(equities)

        # 最大回撤应该是从120跌到90，即 (90-120)/120 = -0.25
        assert abs(max_dd - (-0.25)) < 0.001

    def test_calculate_max_drawdown_no_drawdown(self):
        """测试无回撤情况"""
        equities = [100, 110, 120, 130]

        max_dd = self.service.calculate_max_drawdown(equities)

        assert max_dd == 0.0

    def test_calculate_max_drawdown_empty(self):
        """测试空权益曲线"""
        equities = []

        max_dd = self.service.calculate_max_drawdown(equities)

        assert max_dd == 0.0

    def test_calculate_win_rate(self):
        """测试胜率计算"""
        trades = [
            {'pnl': 100},   # 盈利
            {'pnl': -50},   # 亏损
            {'pnl': 200},   # 盈利
            {'pnl': 150},   # 盈利
        ]

        win_rate = self.service.calculate_win_rate(trades)

        # 3盈1亏，胜率 = 3/4 = 0.75
        assert win_rate == 0.75

    def test_calculate_win_rate_empty(self):
        """测试空交易列表"""
        trades = []

        win_rate = self.service.calculate_win_rate(trades)

        assert win_rate == 0.0

    def test_calculate_profit_loss_ratio(self):
        """测试盈亏比计算"""
        trades = [
            {'pnl': 100},   # 盈利
            {'pnl': 200},   # 盈利
            {'pnl': -50},   # 亏损
            {'pnl': -100},  # 亏损
        ]

        ratio = self.service.calculate_profit_loss_ratio(trades)

        # 平均盈利 = (100+200)/2 = 150
        # 平均亏损 = (50+100)/2 = 75
        # 盈亏比 = 150/75 = 2.0
        assert ratio == 2.0

    def test_calculate_consecutive_wins_losses(self):
        """测试最大连续盈亏"""
        trades = [
            {'pnl': 100},   # 盈1
            {'pnl': 50},    # 盈2
            {'pnl': 80},    # 盈3
            {'pnl': -30},   # 亏1
            {'pnl': 100},   # 盈1
            {'pnl': -50},   # 亏1
            {'pnl': -20},   # 亏2
        ]

        max_wins, max_losses = self.service.calculate_consecutive_wins_losses(trades)

        assert max_wins == 3
        assert max_losses == 2

    def test_calculate_profit_factor(self):
        """测试盈利因子"""
        trades = [
            {'pnl': 100},
            {'pnl': 200},
            {'pnl': -50},
            {'pnl': -50},
        ]

        profit_factor = self.service.calculate_profit_factor(trades)

        # 总盈利 = 300, 总亏损 = 100
        # 盈利因子 = 300/100 = 3.0
        assert profit_factor == 3.0

    def test_run_backtest_from_signals_simple(self):
        """测试从信号运行回测（简单场景）"""
        # 创建简单的信号DataFrame
        signals_data = {
            'trade_date': ['2025-01-01', '2025-01-02', '2025-01-03', '2025-01-04'],
            'close': [10.0, 11.0, 10.5, 12.0],
            'buy': [True, False, False, False],
            'sell': [False, False, True, False],
        }
        signals_df = pd.DataFrame(signals_data)

        result = self.service.run_backtest_from_signals(
            signals_df=signals_df,
            initial_cash=100000,
            period=None
        )

        # 验证返回的指标
        assert 'total_return' in result
        assert 'sharpe_ratio' in result
        assert 'max_drawdown' in result
        assert 'win_rate' in result
        assert 'total_trades' in result
        assert 'trades' in result
        assert 'equity_curve' in result

    def test_run_backtest_from_signals_with_t1_constraint(self):
        """测试带T+1约束的回测"""
        signals_data = {
            'trade_date': ['2025-01-01 09:30', '2025-01-01 10:00', '2025-01-01 14:00'],
            'close': [10.0, 10.5, 10.8],
            'buy': [True, False, False],
            'sell': [False, True, False],  # 当天买入不能卖出
        }
        signals_df = pd.DataFrame(signals_data)

        result = self.service.run_backtest_from_signals(
            signals_df=signals_df,
            initial_cash=100000,
            period='5min'  # 分钟线启用T+1
        )

        # T+1约束下，当天买入不能卖出，所以交易数应该为0
        assert result['total_trades'] == 0
        assert len(result['trade_records']) == 1
        assert result['trade_records'][0]['action'] == 'buy'

    def test_run_backtest_records_unclosed_buy_execution(self):
        """测试未平仓买入也会返回交易执行流水"""
        signals_data = {
            'trade_date': ['2025-01-01', '2025-01-02', '2025-01-03'],
            'close': [10.0, 11.0, 12.0],
            'buy': [True, False, False],
            'sell': [False, False, False],
        }
        signals_df = pd.DataFrame(signals_data)

        result = self.service.run_backtest_from_signals(
            signals_df=signals_df,
            initial_cash=100000,
            period=None
        )

        assert result['total_trades'] == 0
        assert result['trades'] == []
        assert result['trade_records'] == [
            {
                'date': '2025-01-01',
                'action': 'buy',
                'type': 'BUY',
                'tier': 1,
                'price': 10.0,
                'shares': 10000,
                'quantity': 10000,
                'amount': 100000.0,
                'cash': 0.0,
                'position_shares': 10000
            }
        ]

    def test_calculate_metrics_from_trades_empty(self):
        """测试空交易记录的指标计算"""
        result = self.service.calculate_metrics_from_trades(
            trades=[],
            equity_curve=[],
            initial_cash=100000
        )

        # 应该返回全零指标
        assert result['total_return'] == 0
        assert result['sharpe_ratio'] == 0
        assert result['win_rate'] == 0
        assert result['total_trades'] == 0

    def test_empty_metrics(self):
        """测试空指标返回"""
        result = self.service._empty_metrics()

        assert isinstance(result, dict)
        assert result['total_return'] == 0
        assert result['total_trades'] == 0
        assert result['trades'] == []
        assert result['equity_curve'] == []
