"""
Integration test with the new backtest engine.

Tests all three strategies using the event-driven BacktestEngine.
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import pandas as pd
from quantsys.data.db import Database
from quantsys.backtest.engine import BacktestEngine
from quantsys.strategies.adapter import StrategyAdapter
from quantsys.strategies.classic.ma_cross import MACrossStrategy
from quantsys.strategies.classic.rsi_reversal import RSIReversalStrategy
from quantsys.strategies.classic.bollinger_breakout import BollingerBreakoutStrategy


def load_data(symbol: str = '000001', start_date: str = '2024-04-01', end_date: str = '2026-05-13') -> pd.DataFrame:
    """Load historical data from database."""
    db_path = '.pi-invest/stock-db/stocks.db'

    try:
        database = Database(db_path)
        try:
            df = database.get_backtest_klines(symbol, start_date=start_date, end_date=end_date)
        finally:
            database.close()

        if df.empty:
            print(f"No data found for {symbol}")
            return pd.DataFrame()

        # Convert date format (handle both YYYYMMDD and YYYY-MM-DD)
        df['date'] = pd.to_datetime(df['timestamp'], format='mixed', errors='coerce').dt.strftime('%Y-%m-%d')
        df['timestamp'] = pd.to_datetime(df['date'], format='mixed', errors='coerce')

        return df

    except Exception as e:
        print(f"Error loading data: {e}")
        return pd.DataFrame()


def test_strategy(strategy_name: str, strategy: any, data: pd.DataFrame):
    """Test a single strategy with the new backtest engine."""
    print(f"\n{'='*60}")
    print(f"Testing {strategy_name}")
    print('='*60)

    # Wrap strategy with adapter
    adapted_strategy = StrategyAdapter(strategy)

    # Create backtest engine
    engine = BacktestEngine(
        initial_capital=100000,
        commission_rate=0.0003,  # 0.03%
        stamp_tax_rate=0.001,    # 0.1%
        slippage_rate=0.001      # 0.1%
    )

    # Run backtest
    result = engine.run(
        strategy=adapted_strategy,
        data=data,
        start_date='2024-04-01',
        end_date='2026-05-13'
    )

    # Print results
    print(f"\nTotal Return: {result.get('total_return', 0)*100:.2f}%")
    print(f"Annual Return: {result.get('annual_return', 0)*100:.2f}%")
    print(f"Max Drawdown: {result.get('max_drawdown', 0)*100:.2f}%")
    print(f"Sharpe Ratio: {result.get('sharpe_ratio', 0):.2f}")
    print(f"\nTotal Trades: {result.get('total_trades', 0)}")
    print(f"Win Rate: {result.get('win_rate', 0)*100:.2f}%")
    print(f"Profit/Loss Ratio: {result.get('profit_loss_ratio', 0):.2f}")
    print(f"Avg Holding Days: {result.get('avg_holding_days', 0):.1f}")

    return result


def main():
    """Run integration tests."""
    print("="*60)
    print("Strategy Integration Test with New Backtest Engine")
    print("="*60)
    print("Period: 2024-04-01 to 2026-05-13")
    print("Initial Capital: $100,000")
    print("Commission: 0.03%, Stamp Tax: 0.1%, Slippage: 0.1%")

    # Load data
    print("\nLoading data...")
    data = load_data('000001', '2024-04-01', '2026-05-13')

    if data.empty:
        print("No data loaded. Exiting.")
        return

    print(f"Loaded {len(data)} bars")

    # Test all strategies
    strategies = [
        ("MA Cross Strategy (5/20)", MACrossStrategy()),
        ("RSI Reversal Strategy (14-period)", RSIReversalStrategy()),
        ("Bollinger Breakout Strategy (20-period, 2σ)", BollingerBreakoutStrategy())
    ]

    results = {}
    for name, strategy in strategies:
        result = test_strategy(name, strategy, data)
        results[name] = result

    # Summary comparison
    print(f"\n{'='*60}")
    print("STRATEGY COMPARISON")
    print('='*60)
    print(f"{'Strategy':<40} {'Return':<12} {'Sharpe':<10} {'Win Rate':<10}")
    print('-'*60)

    for name, result in results.items():
        print(f"{name:<40} {result.get('total_return', 0)*100:>10.2f}% {result.get('sharpe_ratio', 0):>9.2f} {result.get('win_rate', 0)*100:>9.1f}%")

    print('='*60)


if __name__ == '__main__':
    main()
