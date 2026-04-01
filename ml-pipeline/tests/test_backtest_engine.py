import unittest

import pandas as pd

from backtesting.engine import BacktestEngine
from backtesting.risk_manager import RiskManager


class TestBacktestEngine(unittest.TestCase):
    def test_risk_manager_calculates_position_size(self):
        manager = RiskManager(max_position=0.3)

        shares = manager.calculate_position_size(capital=100000, price=10.0)

        self.assertEqual(shares, 3000.0)

    def test_run_buys_with_max_position_and_sells_on_last_day(self):
        engine = BacktestEngine(
            initial_capital=100000,
            risk_manager=RiskManager(stop_loss=0.05, take_profit=0.10, max_position=0.3),
        )
        df = pd.DataFrame(
            {
                'date': ['2024-01-01', '2024-01-02', '2024-01-03'],
                'close': [10.0, 11.0, 12.0],
                'volume': [1000, 1100, 1200],
            }
        )
        signals = pd.Series([0, 1, 0])

        result = engine.run(df, signals)

        self.assertEqual(result['initial_capital'], 100000)
        self.assertAlmostEqual(result['final_value'], 102727.27272727272)
        self.assertAlmostEqual(result['return'], 2.7272727272727293)
        self.assertEqual(result['trades'], 2)
        self.assertAlmostEqual(result['win_rate'], 100.0)
        self.assertAlmostEqual(result['max_drawdown'], 0.0)
        self.assertAlmostEqual(result['sharpe_ratio'], 0.0)
        self.assertEqual(engine.trades[0]['action'], 'buy')
        self.assertEqual(engine.trades[1]['action'], 'sell')

    def test_run_sells_on_stop_loss_before_last_day(self):
        engine = BacktestEngine(
            initial_capital=100000,
            risk_manager=RiskManager(stop_loss=0.05, take_profit=0.10, max_position=1.0),
        )
        df = pd.DataFrame(
            {
                'date': ['2024-01-01', '2024-01-02', '2024-01-03'],
                'close': [100.0, 94.0, 95.0],
                'volume': [1000, 1100, 1200],
            }
        )
        signals = pd.Series([1, 0, 0])

        result = engine.run(df, signals)

        self.assertAlmostEqual(result['final_value'], 94000.0)
        self.assertAlmostEqual(result['return'], -6.0)
        self.assertEqual(result['trades'], 2)
        self.assertAlmostEqual(result['win_rate'], 0.0)
        self.assertAlmostEqual(result['max_drawdown'], 6.0)
        self.assertAlmostEqual(result['sharpe_ratio'], 0.0)
        self.assertEqual(engine.trades[1]['action'], 'sell_stop_loss')

    def test_run_sells_on_take_profit_before_last_day(self):
        engine = BacktestEngine(
            initial_capital=100000,
            risk_manager=RiskManager(stop_loss=0.05, take_profit=0.10, max_position=1.0),
        )
        df = pd.DataFrame(
            {
                'date': ['2024-01-01', '2024-01-02', '2024-01-03'],
                'close': [100.0, 111.0, 112.0],
                'volume': [1000, 1100, 1200],
            }
        )
        signals = pd.Series([1, 0, 0])

        result = engine.run(df, signals)

        self.assertAlmostEqual(result['final_value'], 111000.0)
        self.assertAlmostEqual(result['return'], 11.0)
        self.assertEqual(result['trades'], 2)
        self.assertAlmostEqual(result['win_rate'], 100.0)
        self.assertAlmostEqual(result['max_drawdown'], 0.0)
        self.assertAlmostEqual(result['sharpe_ratio'], 0.0)
        self.assertEqual(engine.trades[1]['action'], 'sell_take_profit')

    def test_run_calculates_sharpe_ratio_from_multiple_completed_trades(self):
        engine = BacktestEngine(
            initial_capital=100000,
            risk_manager=RiskManager(stop_loss=0.05, take_profit=0.10, max_position=1.0),
        )
        df = pd.DataFrame(
            {
                'date': ['2024-01-01', '2024-01-02', '2024-01-03', '2024-01-04'],
                'close': [100.0, 111.0, 90.0, 108.0],
                'volume': [1000, 1100, 1200, 1300],
            }
        )
        signals = pd.Series([1, 0, 1, 0])

        result = engine.run(df, signals)

        self.assertAlmostEqual(result['final_value'], 133200.0)
        self.assertAlmostEqual(result['return'], 33.2)
        self.assertEqual(result['trades'], 4)
        self.assertAlmostEqual(result['win_rate'], 100.0)
        self.assertAlmostEqual(result['max_drawdown'], 0.0)
        self.assertAlmostEqual(result['sharpe_ratio'], 3.444444444444444)

    def test_run_raises_when_required_columns_are_missing(self):
        engine = BacktestEngine()
        df = pd.DataFrame(
            {
                'date': ['2024-01-01', '2024-01-02'],
                'close': [10.0, 11.0],
            }
        )
        signals = pd.Series([0, 1])

        with self.assertRaisesRegex(ValueError, 'volume'):
            engine.run(df, signals)

    def test_run_aligns_signals_by_date_index(self):
        engine = BacktestEngine(
            initial_capital=100000,
            risk_manager=RiskManager(stop_loss=0.05, take_profit=0.50, max_position=0.3),
        )
        df = pd.DataFrame(
            {
                'date': ['2024-01-01', '2024-01-02', '2024-01-03'],
                'close': [9.0, 10.0, 11.0],
                'volume': [1000, 1100, 1200],
            }
        )
        signals = pd.Series(
            [1, 0],
            index=pd.Index(['2024-01-02', '2024-01-03'], name='date'),
        )

        result = engine.run(df, signals)

        self.assertEqual(result['trades'], 2)
        self.assertAlmostEqual(result['final_value'], 103000.0)
        self.assertEqual(engine.trades[0]['date'], pd.Timestamp('2024-01-02'))
        self.assertEqual(engine.trades[1]['date'], pd.Timestamp('2024-01-03'))
