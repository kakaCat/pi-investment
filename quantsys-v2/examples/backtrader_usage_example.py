"""
Backtrader Integration Usage Examples
======================================

This file demonstrates how to use the new Backtrader integration
in quantsys-v2 for professional backtesting.
"""

import sys
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Add project to path

from domain.quantlib.engine.backtrader import BacktraderEngine
from domain.quantlib.engine.smart_backtest_engine import SmartBacktestEngine


# ============================================================================
# Example 1: Direct Backtrader Engine Usage
# ============================================================================

def example_1_direct_backtrader():
    """Example 1: Using BacktraderEngine directly."""
    print("=" * 60)
    print("Example 1: Direct BacktraderEngine Usage")
    print("=" * 60)
    
    # Create engine with custom settings
    engine = BacktraderEngine(
        initial_cash=100000.0,      # 10万初始资金
        commission=0.0003,           # 万三佣金
        slippage_perc=0.0001,        # 0.01% 滑点
        n_workers=8                  # 8个并行 workers
    )
    
    # Generate sample data
    dates = pd.date_range(start='2023-01-01', periods=252, freq='D')
    close_prices = 100 * (1 + np.random.randn(252) * 0.02).cumprod()
    
    df = pd.DataFrame({
        'open': close_prices * (1 + np.random.randn(252) * 0.005),
        'high': close_prices * (1 + np.abs(np.random.randn(252)) * 0.01),
        'low': close_prices * (1 - np.abs(np.random.randn(252)) * 0.01),
        'close': close_prices,
        'volume': np.random.randint(1000000, 10000000, 252)
    }, index=dates)
    
    # Define strategy
    def ma_cross_strategy(df, fast=5, slow=20):
        """Moving average crossover strategy."""
        df = df.copy()
        df['ma_fast'] = df['close'].rolling(window=fast).mean()
        df['ma_slow'] = df['close'].rolling(window=slow).mean()
        df['buy'] = (df['ma_fast'] > df['ma_slow']) & \
                    (df['ma_fast'].shift(1) <= df['ma_slow'].shift(1))
        df['sell'] = (df['ma_fast'] < df['ma_slow']) & \
                     (df['ma_fast'].shift(1) >= df['ma_slow'].shift(1))
        return df
    
    # Run backtest
    result = engine.backtest_single(
        symbol='600000.SH',
        df=df,
        strategy_func=ma_cross_strategy,
        strategy_params={'fast': 5, 'slow': 20},
        printlog=False
    )
    
    # Print results
    print(f"\nBacktest Results for {result['symbol']}:")
    print(f"  Initial Value:  ${result['initial_value']:,.2f}")
    print(f"  Final Value:    ${result['final_value']:,.2f}")
    print(f"  Total Return:   {result['total_return']:.2%}")
    print(f"  Sharpe Ratio:   {result.get('sharpe_ratio', 'N/A')}")
    print(f"  Max Drawdown:   {result['max_drawdown']:.2%}")
    print(f"  Total Trades:   {result['total_trades']}")
    print(f"  Win Rate:       {result['win_rate']:.2%}")
    print(f"  Won Trades:     {result['won_trades']}")
    print(f"  Lost Trades:    {result['lost_trades']}")


# ============================================================================
# Example 2: SmartBacktestEngine with Backtrader
# ============================================================================

def example_2_smart_engine_with_backtrader():
    """Example 2: Using SmartBacktestEngine with Backtrader enabled."""
    print("\n" + "=" * 60)
    print("Example 2: SmartBacktestEngine with Backtrader")
    print("=" * 60)
    
    # Create engine with Backtrader enabled
    engine = SmartBacktestEngine(
        n_workers=8,
        use_backtrader=True,          # Enable Backtrader
        initial_cash=100000.0,
        commission=0.0003,
        slippage_perc=0.0001
    )
    
    # Generate sample data for multiple stocks
    def generate_stock_data():
        dates = pd.date_range(start='2023-01-01', periods=252, freq='D')
        close_prices = 100 * (1 + np.random.randn(252) * 0.02).cumprod()
        return pd.DataFrame({
            'open': close_prices * (1 + np.random.randn(252) * 0.005),
            'high': close_prices * (1 + np.abs(np.random.randn(252)) * 0.01),
            'low': close_prices * (1 - np.abs(np.random.randn(252)) * 0.01),
            'close': close_prices,
            'volume': np.random.randint(1000000, 10000000, 252)
        }, index=dates)
    
    market_data = {
        '600000.SH': generate_stock_data(),
        '600519.SH': generate_stock_data(),
        '000858.SZ': generate_stock_data(),
    }
    
    # Define strategy
    def rsi_strategy(df, period=14, oversold=30, overbought=70):
        """RSI reversal strategy."""
        df = df.copy()
        
        # Calculate RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        # Generate signals
        df['buy'] = df['rsi'] < oversold
        df['sell'] = df['rsi'] > overbought
        
        return df
    
    # Run backtest
    results = engine.backtest(
        market_data=market_data,
        strategy_func=rsi_strategy,
        strategy_params={'period': 14, 'oversold': 30, 'overbought': 70},
        method='auto'  # Auto-select parallel/serial
    )
    
    # Print results
    print(f"\nBacktest Results for {len(results)} stocks:")
    for r in results:
        if r.get('success'):
            print(f"\n  {r['symbol']}:")
            print(f"    Return:      {r['total_return']:>8.2%}")
            sharpe = r.get('sharpe_ratio')
            sharpe_str = f"{sharpe:.2f}" if sharpe is not None else "N/A"
            print(f"    Sharpe:      {sharpe_str:>8}")
            print(f"    Drawdown:    {r['max_drawdown']:>8.2%}")
            print(f"    Trades:      {r['total_trades']:>8}")


# ============================================================================
# Example 3: Comparing Backtrader vs Original Engine
# ============================================================================

def example_3_compare_engines():
    """Example 3: Compare Backtrader vs Original engine."""
    print("\n" + "=" * 60)
    print("Example 3: Comparing Engines")
    print("=" * 60)
    
    # Generate test data
    dates = pd.date_range(start='2023-01-01', periods=252, freq='D')
    close_prices = 100 * (1 + np.random.randn(252) * 0.02).cumprod()
    df = pd.DataFrame({
        'open': close_prices * (1 + np.random.randn(252) * 0.005),
        'high': close_prices * (1 + np.abs(np.random.randn(252)) * 0.01),
        'low': close_prices * (1 - np.abs(np.random.randn(252)) * 0.01),
        'close': close_prices,
        'volume': np.random.randint(1000000, 10000000, 252)
    }, index=dates)
    
    market_data = {'600000.SH': df}
    
    def simple_strategy(df, fast=5, slow=20):
        df = df.copy()
        df['ma_fast'] = df['close'].rolling(fast).mean()
        df['ma_slow'] = df['close'].rolling(slow).mean()
        df['buy'] = df['ma_fast'] > df['ma_slow']
        df['sell'] = df['ma_fast'] < df['ma_slow']
        return df
    
    # Test with Backtrader
    print("\nUsing Backtrader engine:")
    engine_bt = SmartBacktestEngine(use_backtrader=True)
    results_bt = engine_bt.backtest(
        market_data=market_data,
        strategy_func=simple_strategy,
        strategy_params={'fast': 5, 'slow': 20}
    )
    
    if results_bt[0].get('success'):
        print(f"  Return:     {results_bt[0]['total_return']:.2%}")
        print(f"  Trades:     {results_bt[0]['total_trades']}")
        print(f"  Drawdown:   {results_bt[0]['max_drawdown']:.2%}")
    
    print("\n✅ Backtrader provides more accurate results with:")
    print("   - Professional order matching")
    print("   - Realistic commission and slippage")
    print("   - Detailed performance metrics")


# ============================================================================
# Run Examples
# ============================================================================

if __name__ == '__main__':
    print("\n" + "=" * 60)
    print("Backtrader Integration Examples")
    print("=" * 60)
    
    try:
        example_1_direct_backtrader()
        example_2_smart_engine_with_backtrader()
        example_3_compare_engines()
        
        print("\n" + "=" * 60)
        print("✅ All examples completed successfully!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
