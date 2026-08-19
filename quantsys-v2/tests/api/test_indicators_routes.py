"""
Tests for backtest summary calculation function.
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import patch
import sys
from pathlib import Path
from adapters.inbound.fastapi_app.routes.indicators_async import calculate_backtest_summary

# Add quantsys-v2 to path
v2_root = Path(__file__).resolve().parents[2]
if str(v2_root) not in sys.path:
    sys.path.insert(0, str(v2_root))


class TestCalculateBacktestSummary:
    """测试回测摘要计算函数"""

    def test_calculate_backtest_summary_empty(self):
        """测试空数据 - 规格要求的测试名称"""
        result = calculate_backtest_summary([], [], datetime.now(), datetime.now())
        assert result == {}

    def test_calculate_backtest_summary(self):
        """测试正常计算 - 规格要求的测试名称（综合测试）"""
        start_date = datetime(2024, 1, 1)
        end_date = datetime(2024, 12, 31)

        equity_curve = [
            {'date': '2024-01-01', 'equity': 1000000},
            {'date': '2024-03-01', 'equity': 1050000},
            {'date': '2024-06-01', 'equity': 1030000},
            {'date': '2024-09-01', 'equity': 1080000},
            {'date': '2024-12-31', 'equity': 1100000}
        ]

        trades = [
            {'date': '2024-03-01', 'action': 'sell', 'pnl': 50000},
            {'date': '2024-06-01', 'action': 'sell', 'pnl': -20000},
            {'date': '2024-09-01', 'action': 'sell', 'pnl': 50000},
            {'date': '2024-12-31', 'action': 'sell', 'pnl': 20000}
        ]

        result = calculate_backtest_summary(equity_curve, trades, start_date, end_date)

        # 验证所有 11 个指标都存在
        assert 'total_return' in result
        assert 'annual_return' in result
        assert 'max_drawdown' in result
        assert 'sharpe_ratio' in result
        assert 'win_rate' in result
        assert 'total_trades' in result
        assert 'winning_trades' in result
        assert 'losing_trades' in result
        assert 'avg_win' in result
        assert 'avg_loss' in result
        assert 'profit_factor' in result

        # 验证关键指标值
        assert result['total_return'] == 0.1
        assert result['total_trades'] == 4
        assert result['winning_trades'] == 3
        assert result['losing_trades'] == 1
        assert result['win_rate'] == 0.75
        assert result['avg_win'] == 40000
        assert result['avg_loss'] == -20000
        assert result['profit_factor'] == 6.0

    def test_single_trade_profit(self):
        """单笔盈利交易"""
        start_date = datetime(2024, 1, 1)
        end_date = datetime(2024, 12, 31)

        equity_curve = [
            {'date': '2024-01-01', 'equity': 1000000},
            {'date': '2024-12-31', 'equity': 1100000}
        ]

        trades = [
            {'date': '2024-06-01', 'action': 'sell', 'pnl': 100000}
        ]

        result = calculate_backtest_summary(equity_curve, trades, start_date, end_date)

        assert result['total_return'] == 0.1
        assert result['total_trades'] == 1
        assert result['winning_trades'] == 1
        assert result['losing_trades'] == 0
        assert result['win_rate'] == 1.0
        assert result['avg_win'] == 100000
        assert result['avg_loss'] == 0

    def test_multiple_trades_mixed(self):
        """多笔交易混合盈亏"""
        start_date = datetime(2024, 1, 1)
        end_date = datetime(2024, 12, 31)

        equity_curve = [
            {'date': '2024-01-01', 'equity': 1000000},
            {'date': '2024-03-01', 'equity': 1050000},
            {'date': '2024-06-01', 'equity': 1030000},
            {'date': '2024-09-01', 'equity': 1080000},
            {'date': '2024-12-31', 'equity': 1100000}
        ]

        trades = [
            {'date': '2024-03-01', 'action': 'sell', 'pnl': 50000},
            {'date': '2024-06-01', 'action': 'sell', 'pnl': -20000},
            {'date': '2024-09-01', 'action': 'sell', 'pnl': 50000},
            {'date': '2024-12-31', 'action': 'sell', 'pnl': 20000}
        ]

        result = calculate_backtest_summary(equity_curve, trades, start_date, end_date)

        assert result['total_return'] == 0.1
        assert result['total_trades'] == 4
        assert result['winning_trades'] == 3
        assert result['losing_trades'] == 1
        assert result['win_rate'] == 0.75
        assert result['avg_win'] == 40000
        assert result['avg_loss'] == -20000
        assert result['profit_factor'] == 6.0

    def test_max_drawdown_calculation(self):
        """最大回撤计算"""
        start_date = datetime(2024, 1, 1)
        end_date = datetime(2024, 12, 31)

        equity_curve = [
            {'date': '2024-01-01', 'equity': 1000000},
            {'date': '2024-03-01', 'equity': 1200000},  # 峰值
            {'date': '2024-06-01', 'equity': 900000},   # 回撤 25%
            {'date': '2024-09-01', 'equity': 1100000},
            {'date': '2024-12-31', 'equity': 1150000}
        ]

        trades = [
            {'date': '2024-06-01', 'action': 'sell', 'pnl': -300000},
            {'date': '2024-09-01', 'action': 'sell', 'pnl': 200000}
        ]

        result = calculate_backtest_summary(equity_curve, trades, start_date, end_date)

        assert result['max_drawdown'] == -0.25

    def test_sharpe_ratio_calculation(self):
        """夏普比率计算"""
        start_date = datetime(2024, 1, 1)
        end_date = datetime(2024, 12, 31)

        # 稳定增长的权益曲线
        equity_curve = [
            {'date': '2024-01-01', 'equity': 1000000},
            {'date': '2024-03-01', 'equity': 1025000},
            {'date': '2024-06-01', 'equity': 1050000},
            {'date': '2024-09-01', 'equity': 1075000},
            {'date': '2024-12-31', 'equity': 1100000}
        ]

        trades = [
            {'date': '2024-03-01', 'action': 'sell', 'pnl': 25000},
            {'date': '2024-06-01', 'action': 'sell', 'pnl': 25000},
            {'date': '2024-09-01', 'action': 'sell', 'pnl': 25000},
            {'date': '2024-12-31', 'action': 'sell', 'pnl': 25000}
        ]

        result = calculate_backtest_summary(equity_curve, trades, start_date, end_date)

        # 夏普比率应该为正数（收益率 > 无风险利率）
        assert result['sharpe_ratio'] > 0

