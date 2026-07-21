"""
Unit tests for Backtrader engine and adapters.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from domain.quantlib.engine.backtrader.data_feed import PandasDataFeed, validate_dataframe
from domain.quantlib.engine.backtrader.backtrader_engine import BacktraderEngine


# ============================================================================
# Test Data Generation
# ============================================================================

def generate_test_data(n_days=252, start_price=100):
    """Generate synthetic OHLCV data for testing."""
    dates = pd.date_range(start='2023-01-01', periods=n_days, freq='D')
    
    # Generate random walk
    returns = np.random.randn(n_days) * 0.02
    close_prices = start_price * (1 + returns).cumprod()
    
    df = pd.DataFrame({
        'open': close_prices * (1 + np.random.randn(n_days) * 0.005),
        'high': close_prices * (1 + np.abs(np.random.randn(n_days)) * 0.01),
        'low': close_prices * (1 - np.abs(np.random.randn(n_days)) * 0.01),
        'close': close_prices,
        'volume': np.random.randint(1000000, 10000000, n_days)
    }, index=dates)
    
    return df


def simple_ma_strategy(df, fast=5, slow=20):
    """Simple moving average crossover strategy."""
    df = df.copy()
    
    df['ma_fast'] = df['close'].rolling(window=fast).mean()
    df['ma_slow'] = df['close'].rolling(window=slow).mean()
    
    df['buy'] = (df['ma_fast'] > df['ma_slow']) & (df['ma_fast'].shift(1) <= df['ma_slow'].shift(1))
    df['sell'] = (df['ma_fast'] < df['ma_slow']) & (df['ma_fast'].shift(1) >= df['ma_slow'].shift(1))
    
    return df


# ============================================================================
# Test PandasDataFeed
# ============================================================================

def test_pandas_data_feed_from_dataframe():
    """Test creating data feed from DataFrame."""
    df = generate_test_data(100)
    
    data_feed = PandasDataFeed.from_dataframe(df, '600000.SH')
    
    assert data_feed is not None
    assert data_feed._name == '600000.SH'


def test_pandas_data_feed_with_trade_date_column():
    """Test data feed with trade_date column instead of index."""
    df = generate_test_data(100)
    df = df.reset_index()
    df.rename(columns={'index': 'trade_date'}, inplace=True)
    
    data_feed = PandasDataFeed.from_dataframe(df, '600519.SH')
    
    assert data_feed is not None


def test_pandas_data_feed_missing_columns():
    """Test data feed with missing required columns."""
    df = pd.DataFrame({
        'open': [100, 101],
        'close': [100, 101],
        # Missing high, low, volume
    })
    
    with pytest.raises(ValueError, match="Missing required columns"):
        PandasDataFeed.from_dataframe(df)


def test_validate_dataframe_valid():
    """Test DataFrame validation with valid data."""
    df = generate_test_data(50)
    
    is_valid, error_msg = validate_dataframe(df)
    
    assert is_valid
    assert error_msg == ""


def test_validate_dataframe_empty():
    """Test DataFrame validation with empty DataFrame."""
    df = pd.DataFrame()
    
    is_valid, error_msg = validate_dataframe(df)
    
    assert not is_valid
    assert "empty" in error_msg.lower()


def test_validate_dataframe_missing_columns():
    """Test DataFrame validation with missing columns."""
    df = pd.DataFrame({
        'open': [100],
        'close': [101]
    })
    
    is_valid, error_msg = validate_dataframe(df)
    
    assert not is_valid
    assert "Missing columns" in error_msg


# ============================================================================
# Test BacktraderEngine
# ============================================================================

def test_backtrader_engine_initialization():
    """Test BacktraderEngine initialization."""
    engine = BacktraderEngine(
        initial_cash=100000,
        commission=0.0003,
        slippage_perc=0.0001
    )
    
    assert engine.initial_cash == 100000
    assert engine.commission == 0.0003
    assert engine.slippage_perc == 0.0001


def test_backtrader_engine_single_backtest():
    """Test single stock backtest."""
    engine = BacktraderEngine(initial_cash=100000)
    
    df = generate_test_data(252)
    
    result = engine.backtest_single(
        symbol='600000.SH',
        df=df,
        strategy_func=simple_ma_strategy,
        strategy_params={'fast': 5, 'slow': 20}
    )
    
    # Verify result structure
    assert result['success'] is True
    assert result['symbol'] == '600000.SH'
    assert 'total_return' in result
    assert 'sharpe_ratio' in result
    assert 'max_drawdown' in result
    assert 'total_trades' in result
    assert 'win_rate' in result
    
    # Verify types
    assert isinstance(result['total_return'], (int, float))
    assert isinstance(result['total_trades'], int)
    assert 0 <= result['win_rate'] <= 1


def test_backtrader_engine_multiple_backtest_serial():
    """Test multiple stocks backtest (serial mode)."""
    engine = BacktraderEngine(initial_cash=100000)
    
    market_data = {
        '600000.SH': generate_test_data(252),
        '600519.SH': generate_test_data(252),
        '000858.SZ': generate_test_data(252),
    }
    
    results = engine.backtest_multiple(
        market_data=market_data,
        strategy_func=simple_ma_strategy,
        strategy_params={'fast': 5, 'slow': 20},
        parallel=False  # Force serial mode
    )
    
    assert len(results) == 3
    assert all(r['success'] for r in results)
    assert {r['symbol'] for r in results} == {'600000.SH', '600519.SH', '000858.SZ'}


def test_backtrader_engine_with_different_parameters():
    """Test backtest with different strategy parameters."""
    engine = BacktraderEngine(initial_cash=100000)
    
    df = generate_test_data(252)
    
    # Test with different MA periods
    result1 = engine.backtest_single(
        symbol='600000.SH',
        df=df,
        strategy_func=simple_ma_strategy,
        strategy_params={'fast': 5, 'slow': 20}
    )
    
    result2 = engine.backtest_single(
        symbol='600000.SH',
        df=df,
        strategy_func=simple_ma_strategy,
        strategy_params={'fast': 10, 'slow': 50}
    )
    
    assert result1['success']
    assert result2['success']
    # Different parameters may produce different results
    # (not guaranteed, but likely with sufficient data)


def test_backtrader_engine_invalid_data():
    """Test backtest with invalid data."""
    engine = BacktraderEngine(initial_cash=100000)
    
    # Empty DataFrame
    df_empty = pd.DataFrame()
    
    result = engine.backtest_single(
        symbol='TEST.SH',
        df=df_empty,
        strategy_func=simple_ma_strategy,
        strategy_params={'fast': 5, 'slow': 20}
    )
    
    assert result['success'] is False
    assert 'error' in result


def test_backtrader_engine_commission_impact():
    """Test that commission affects returns."""
    df = generate_test_data(252)
    
    # No commission
    engine_no_comm = BacktraderEngine(initial_cash=100000, commission=0.0)
    result_no_comm = engine_no_comm.backtest_single(
        symbol='600000.SH',
        df=df,
        strategy_func=simple_ma_strategy,
        strategy_params={'fast': 5, 'slow': 20}
    )
    
    # With commission
    engine_with_comm = BacktraderEngine(initial_cash=100000, commission=0.001)
    result_with_comm = engine_with_comm.backtest_single(
        symbol='600000.SH',
        df=df,
        strategy_func=simple_ma_strategy,
        strategy_params={'fast': 5, 'slow': 20}
    )
    
    # Commission should reduce returns (if there are trades)
    if result_no_comm['total_trades'] > 0:
        assert result_with_comm['total_return'] <= result_no_comm['total_return']


# ============================================================================
# Run tests
# ============================================================================

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
