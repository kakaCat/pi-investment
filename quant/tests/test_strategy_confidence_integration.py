"""
Integration test: Generate sample signals and verify confidence calibration.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from quantsys.strategies.classic.rsi_reversal import RSIReversalStrategy
from quantsys.strategies.classic.ma_cross import MACrossStrategy
from quantsys.strategies.classic.bollinger_breakout import BollingerBreakoutStrategy


def generate_sample_data(symbol='TEST', days=30):
    """Generate sample OHLCV data for testing."""
    dates = [datetime.now() - timedelta(days=i) for i in range(days, 0, -1)]

    # Generate realistic price data
    base_price = 100
    prices = []
    for i in range(days):
        # Add some volatility
        change = np.random.randn() * 2
        base_price = max(base_price + change, 50)
        prices.append(base_price)

    data = pd.DataFrame({
        'timestamp': dates,
        'symbol': symbol,
        'open': prices,
        'high': [p * 1.02 for p in prices],
        'low': [p * 0.98 for p in prices],
        'close': prices,
        'volume': [np.random.randint(1000000, 5000000) for _ in range(days)]
    })

    return data


def test_rsi_strategy():
    """Test RSI strategy confidence calibration."""
    print("=" * 60)
    print("Testing RSI Strategy Confidence")
    print("=" * 60)

    strategy = RSIReversalStrategy()

    # Generate data with oversold condition
    data = generate_sample_data(days=30)

    # Force RSI to be oversold by manipulating prices
    data.loc[data.index[-5:], 'close'] = data.loc[data.index[-5:], 'close'] * 0.85

    signals = strategy.calculate_signals(data)

    print(f"Generated {len(signals)} signals")
    for signal in signals:
        print(f"  {signal.action.upper():4s} @ {signal.price:.2f} | "
              f"confidence={signal.confidence:.4f} | reason={signal.reason}")
        assert signal.confidence <= 0.85, f"Confidence {signal.confidence} exceeds 0.85"
        assert signal.confidence < 1.0, f"Confidence should not be 100%"

    print("✅ RSI strategy confidence properly calibrated\n")


def test_ma_cross_strategy():
    """Test MA Cross strategy confidence calibration."""
    print("=" * 60)
    print("Testing MA Cross Strategy Confidence")
    print("=" * 60)

    strategy = MACrossStrategy()

    # Generate data with uptrend
    data = generate_sample_data(days=30)

    # Force golden cross by creating uptrend
    for i in range(len(data)):
        data.loc[data.index[i], 'close'] = 100 + i * 2

    signals = strategy.calculate_signals(data)

    print(f"Generated {len(signals)} signals")
    for signal in signals:
        print(f"  {signal.action.upper():4s} @ {signal.price:.2f} | "
              f"confidence={signal.confidence:.4f} | reason={signal.reason}")
        assert signal.confidence <= 0.85, f"Confidence {signal.confidence} exceeds 0.85"
        assert signal.confidence < 1.0, f"Confidence should not be 100%"

    print("✅ MA Cross strategy confidence properly calibrated\n")


def test_bollinger_strategy():
    """Test Bollinger Bands strategy confidence calibration."""
    print("=" * 60)
    print("Testing Bollinger Bands Strategy Confidence")
    print("=" * 60)

    strategy = BollingerBreakoutStrategy()

    # Generate data
    data = generate_sample_data(days=30)

    # Force price to touch lower band
    data.loc[data.index[-1], 'close'] = data['close'].mean() - 2 * data['close'].std()

    signals = strategy.calculate_signals(data)

    print(f"Generated {len(signals)} signals")
    for signal in signals:
        print(f"  {signal.action.upper():4s} @ {signal.price:.2f} | "
              f"confidence={signal.confidence:.4f} | reason={signal.reason}")
        assert signal.confidence <= 0.85, f"Confidence {signal.confidence} exceeds 0.85"
        assert signal.confidence < 1.0, f"Confidence should not be 100%"

    print("✅ Bollinger strategy confidence properly calibrated\n")


def test_stop_loss_take_profit():
    """Test stop-loss and take-profit confidence calibration."""
    print("=" * 60)
    print("Testing Stop-Loss/Take-Profit Confidence")
    print("=" * 60)

    strategy = RSIReversalStrategy()

    # Generate data and create a position
    data = generate_sample_data(days=30)

    # Simulate buying
    from quantsys.strategies.base import Position
    strategy.positions['TEST'] = Position(
        symbol='TEST',
        quantity=100,
        entry_price=100.0,
        entry_time=datetime.now(),
        current_price=100.0,
        stop_loss=95.0,  # 5% stop loss
        take_profit=115.0  # 15% take profit
    )

    # Test stop loss trigger
    bar_sl = {
        'timestamp': datetime.now(),
        'symbol': 'TEST',
        'close': 94.0,  # Below stop loss
        'open': 95.0,
        'high': 95.5,
        'low': 93.5,
        'volume': 1000000
    }

    signal_sl = strategy.on_bar(bar_sl)
    if signal_sl:
        print(f"Stop-Loss Signal: confidence={signal_sl.confidence:.4f}")
        assert signal_sl.confidence <= 0.75, f"Stop-loss confidence {signal_sl.confidence} exceeds 0.75"
        assert signal_sl.confidence < 1.0, f"Stop-loss confidence should not be 100%"

    # Reset position for take profit test
    strategy.positions['TEST'] = Position(
        symbol='TEST',
        quantity=100,
        entry_price=100.0,
        entry_time=datetime.now(),
        current_price=100.0,
        stop_loss=95.0,
        take_profit=115.0
    )

    # Test take profit trigger
    bar_tp = {
        'timestamp': datetime.now(),
        'symbol': 'TEST',
        'close': 116.0,  # Above take profit
        'open': 115.0,
        'high': 117.0,
        'low': 114.5,
        'volume': 1000000
    }

    signal_tp = strategy.on_bar(bar_tp)
    if signal_tp:
        print(f"Take-Profit Signal: confidence={signal_tp.confidence:.4f}")
        assert signal_tp.confidence <= 0.75, f"Take-profit confidence {signal_tp.confidence} exceeds 0.75"
        assert signal_tp.confidence < 1.0, f"Take-profit confidence should not be 100%"

    print("✅ Stop-loss/take-profit confidence properly calibrated\n")


if __name__ == '__main__':
    print("\n" + "=" * 60)
    print("STRATEGY INTEGRATION TEST - CONFIDENCE CALIBRATION")
    print("=" * 60 + "\n")

    test_rsi_strategy()
    test_ma_cross_strategy()
    test_bollinger_strategy()
    test_stop_loss_take_profit()

    print("=" * 60)
    print("ALL INTEGRATION TESTS PASSED ✅")
    print("=" * 60)
    print("\nConfidence calibration is working correctly:")
    print("  • All signals have confidence <= 0.85 (85%)")
    print("  • Stop-loss/take-profit signals <= 0.75 (75%)")
    print("  • No signals reach 100% confidence")
    print()
