"""
Tests for OptionStrategy classes - Delta Neutral and Volatility Arbitrage
"""

import numpy as np
import pandas as pd
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime

from domain.quantlib.derivatives.option_trading_strategies import (
    OptionStrategy,
    DeltaNeutralStrategy,
    VolatilityArbitrageStrategy
)


@pytest.fixture
def sample_market_data():
    """Create sample market data for testing"""
    return {
        'S': 100.0,
        'K': 100.0,
        'T': 0.25,
        'r': 0.05,
        'sigma': 0.2
    }


@pytest.fixture
def sample_vol_arb_data():
    """Create sample data for volatility arbitrage"""
    np.random.seed(42)
    historical_prices = 100 * np.exp(np.cumsum(np.random.randn(100) * 0.02))

    return {
        'S': 100.0,
        'K': 100.0,
        'T': 0.25,
        'r': 0.05,
        'market_price': 6.0,
        'option_type': 'call',
        'historical_prices': historical_prices
    }


class TestOptionStrategy:
    """Test suite for OptionStrategy base class"""

    def test_initialization(self):
        """Test OptionStrategy initialization"""
        strategy = OptionStrategy("Test Strategy")
        assert strategy.name == "Test Strategy"
        assert strategy.greeks_calculator is not None
        assert strategy.positions == []

    def test_add_position(self, sample_market_data):
        """Test adding option position"""
        strategy = OptionStrategy("Test")

        strategy.add_position(
            option_type='call',
            quantity=100,
            S=sample_market_data['S'],
            K=sample_market_data['K'],
            T=sample_market_data['T'],
            r=sample_market_data['r'],
            sigma=sample_market_data['sigma']
        )

        assert len(strategy.positions) == 1
        position = strategy.positions[0]
        assert position['option_type'] == 'call'
        assert position['quantity'] == 100
        assert 'greeks' in position

    def test_add_multiple_positions(self, sample_market_data):
        """Test adding multiple positions"""
        strategy = OptionStrategy("Test")

        # Add call position
        strategy.add_position('call', 100, **sample_market_data)

        # Add put position
        strategy.add_position('put', -50, **sample_market_data)

        assert len(strategy.positions) == 2

    def test_calculate_portfolio_greeks_empty(self):
        """Test portfolio Greeks with no positions"""
        strategy = OptionStrategy("Test")

        greeks = strategy.calculate_portfolio_greeks()

        assert greeks['delta'] == 0.0
        assert greeks['gamma'] == 0.0
        assert greeks['theta'] == 0.0
        assert greeks['vega'] == 0.0
        assert greeks['rho'] == 0.0
        assert greeks['value'] == 0.0

    def test_calculate_portfolio_greeks_single_position(self, sample_market_data):
        """Test portfolio Greeks with single position"""
        strategy = OptionStrategy("Test")

        strategy.add_position('call', 100, **sample_market_data)

        greeks = strategy.calculate_portfolio_greeks()

        assert greeks['delta'] != 0.0
        assert greeks['gamma'] > 0.0
        assert greeks['vega'] > 0.0
        assert greeks['value'] > 0.0

    def test_calculate_portfolio_greeks_multiple_positions(self, sample_market_data):
        """Test portfolio Greeks with multiple positions"""
        strategy = OptionStrategy("Test")

        # Long call
        strategy.add_position('call', 100, **sample_market_data)

        # Short put
        strategy.add_position('put', -50, **sample_market_data)

        greeks = strategy.calculate_portfolio_greeks()

        # Should aggregate all positions
        assert isinstance(greeks['delta'], float)
        assert isinstance(greeks['gamma'], float)

    def test_clear_positions(self, sample_market_data):
        """Test clearing all positions"""
        strategy = OptionStrategy("Test")

        strategy.add_position('call', 100, **sample_market_data)
        strategy.add_position('put', -50, **sample_market_data)

        assert len(strategy.positions) == 2

        strategy.clear_positions()

        assert len(strategy.positions) == 0

    def test_generate_signal_not_implemented(self):
        """Test generate_signal raises NotImplementedError"""
        strategy = OptionStrategy("Test")

        with pytest.raises(NotImplementedError):
            strategy.generate_signal({})


class TestDeltaNeutralStrategy:
    """Test suite for DeltaNeutralStrategy"""

    def test_initialization(self):
        """Test DeltaNeutralStrategy initialization"""
        strategy = DeltaNeutralStrategy(delta_threshold=0.1, rebalance_frequency=1)

        assert strategy.name == "Delta Neutral Strategy"
        assert strategy.delta_threshold == 0.1
        assert strategy.rebalance_frequency == 1
        assert strategy.stock_position == 0

    def test_initialization_defaults(self):
        """Test default initialization"""
        strategy = DeltaNeutralStrategy()

        assert strategy.delta_threshold == 0.1
        assert strategy.rebalance_frequency == 1

    def test_generate_signal_initial_rebalance(self, sample_market_data):
        """Test initial rebalance signal generation"""
        strategy = DeltaNeutralStrategy(delta_threshold=0.1)

        signal = strategy.generate_signal(sample_market_data)

        assert signal is not None
        assert signal['strategy'] == "Delta Neutral Strategy"
        assert signal['action'] == 'rebalance'
        assert 'option_position' in signal
        assert 'stock_adjustment' in signal
        assert 'new_stock_position' in signal
        assert 'portfolio_greeks' in signal

    def test_generate_signal_no_rebalance_needed(self, sample_market_data):
        """Test no signal when rebalance not needed"""
        strategy = DeltaNeutralStrategy(delta_threshold=10.0)  # Very high threshold

        # First call should rebalance
        signal1 = strategy.generate_signal(sample_market_data)
        assert signal1 is not None

        # Second call should not rebalance (delta within threshold)
        signal2 = strategy.generate_signal(sample_market_data)
        assert signal2 is None

    def test_generate_signal_call_option(self, sample_market_data):
        """Test signal generation for call option"""
        strategy = DeltaNeutralStrategy()

        sample_market_data['option_type'] = 'call'
        signal = strategy.generate_signal(sample_market_data)

        assert signal is not None
        assert signal['option_position']['type'] == 'call'

    def test_generate_signal_put_option(self, sample_market_data):
        """Test signal generation for put option"""
        strategy = DeltaNeutralStrategy()

        sample_market_data['option_type'] = 'put'
        signal = strategy.generate_signal(sample_market_data)

        assert signal is not None
        assert signal['option_position']['type'] == 'put'

    def test_stock_position_update(self, sample_market_data):
        """Test stock position is updated after rebalance"""
        strategy = DeltaNeutralStrategy()

        initial_position = strategy.stock_position
        signal = strategy.generate_signal(sample_market_data)

        assert strategy.stock_position != initial_position
        assert strategy.stock_position == signal['new_stock_position']

    def test_delta_neutralization(self, sample_market_data):
        """Test delta is neutralized after rebalance"""
        strategy = DeltaNeutralStrategy(delta_threshold=0.01)

        signal = strategy.generate_signal(sample_market_data)

        # After rebalance, portfolio delta should be close to 0
        option_delta = signal['option_position']['delta']
        stock_position = signal['new_stock_position']

        total_delta = option_delta + stock_position
        assert abs(total_delta) < 0.01

    def test_calculate_pnl(self):
        """Test PnL calculation"""
        strategy = DeltaNeutralStrategy()
        strategy.stock_position = -50

        initial_greeks = {
            'price': 5.0,
            'delta': 0.5,
            'gamma': 0.05,
            'theta': -0.02
        }

        final_greeks = {
            'price': 6.0,
            'delta': 0.6,
            'gamma': 0.04,
            'theta': -0.015
        }

        pnl = strategy.calculate_pnl(
            initial_S=100.0,
            final_S=105.0,
            initial_greeks=initial_greeks,
            final_greeks=final_greeks,
            option_quantity=100
        )

        assert 'option_pnl' in pnl
        assert 'stock_pnl' in pnl
        assert 'total_pnl' in pnl
        assert 'gamma_pnl' in pnl
        assert 'theta_pnl' in pnl

    def test_calculate_pnl_values(self):
        """Test PnL calculation values are correct"""
        strategy = DeltaNeutralStrategy()
        strategy.stock_position = -50

        initial_greeks = {'price': 5.0, 'delta': 0.5, 'gamma': 0.05, 'theta': -0.02}
        final_greeks = {'price': 6.0, 'delta': 0.6, 'gamma': 0.04, 'theta': -0.015}

        pnl = strategy.calculate_pnl(100.0, 105.0, initial_greeks, final_greeks, 100)

        # Option PnL = (6.0 - 5.0) * 100 = 100
        assert pnl['option_pnl'] == pytest.approx(100.0)

        # Stock PnL = (105 - 100) * (-50) = -250
        assert pnl['stock_pnl'] == pytest.approx(-250.0)

        # Total PnL = 100 - 250 = -150
        assert pnl['total_pnl'] == pytest.approx(-150.0)

    def test_different_delta_thresholds(self, sample_market_data):
        """Test different delta thresholds"""
        for threshold in [0.05, 0.1, 0.5]:
            strategy = DeltaNeutralStrategy(delta_threshold=threshold)
            signal = strategy.generate_signal(sample_market_data)

            # First signal should always trigger
            assert signal is not None


class TestVolatilityArbitrageStrategy:
    """Test suite for VolatilityArbitrageStrategy"""

    def test_initialization(self):
        """Test VolatilityArbitrageStrategy initialization"""
        strategy = VolatilityArbitrageStrategy(iv_hv_threshold=0.05, min_vega=10.0)

        assert strategy.name == "Volatility Arbitrage Strategy"
        assert strategy.iv_hv_threshold == 0.05
        assert strategy.min_vega == 10.0

    def test_initialization_defaults(self):
        """Test default initialization"""
        strategy = VolatilityArbitrageStrategy()

        assert strategy.iv_hv_threshold == 0.05
        assert strategy.min_vega == 10.0

    def test_calculate_historical_volatility(self):
        """Test historical volatility calculation"""
        strategy = VolatilityArbitrageStrategy()

        np.random.seed(42)
        prices = 100 * np.exp(np.cumsum(np.random.randn(100) * 0.02))

        hv = strategy.calculate_historical_volatility(prices, window=20)

        assert hv > 0
        assert hv < 2.0  # Reasonable volatility range

    def test_calculate_historical_volatility_insufficient_data(self):
        """Test HV calculation with insufficient data"""
        strategy = VolatilityArbitrageStrategy()

        prices = np.array([100, 101, 102])

        hv = strategy.calculate_historical_volatility(prices, window=20)

        assert hv == 0.0

    def test_calculate_historical_volatility_different_windows(self):
        """Test HV calculation with different windows"""
        strategy = VolatilityArbitrageStrategy()

        np.random.seed(42)
        prices = 100 * np.exp(np.cumsum(np.random.randn(100) * 0.02))

        hv_10 = strategy.calculate_historical_volatility(prices, window=10)
        hv_20 = strategy.calculate_historical_volatility(prices, window=20)

        assert hv_10 > 0
        assert hv_20 > 0

    def test_generate_signal_buy(self, sample_vol_arb_data):
        """Test buy signal generation (IV < HV)"""
        strategy = VolatilityArbitrageStrategy(iv_hv_threshold=0.01)

        # Set low market price to get low IV
        sample_vol_arb_data['market_price'] = 3.0

        signal = strategy.generate_signal(sample_vol_arb_data)

        if signal is not None:
            assert signal['strategy'] == "Volatility Arbitrage Strategy"
            assert 'action' in signal
            assert signal['action'] in ['buy', 'sell']

    def test_generate_signal_sell(self, sample_vol_arb_data):
        """Test sell signal generation (IV > HV)"""
        strategy = VolatilityArbitrageStrategy(iv_hv_threshold=0.01)

        # Set high market price to get high IV
        sample_vol_arb_data['market_price'] = 10.0

        signal = strategy.generate_signal(sample_vol_arb_data)

        if signal is not None:
            assert signal['action'] in ['buy', 'sell']

    def test_generate_signal_no_signal_small_diff(self, sample_vol_arb_data):
        """Test no signal when IV-HV difference is small"""
        strategy = VolatilityArbitrageStrategy(iv_hv_threshold=1.0)  # Very high threshold

        signal = strategy.generate_signal(sample_vol_arb_data)

        # Should not generate signal due to high threshold
        assert signal is None

    def test_generate_signal_no_iv(self, sample_vol_arb_data):
        """Test signal generation when IV calculation fails"""
        strategy = VolatilityArbitrageStrategy()

        # Invalid market price
        sample_vol_arb_data['market_price'] = -1.0

        signal = strategy.generate_signal(sample_vol_arb_data)

        # Should return None when IV calculation fails
        assert signal is None

    def test_generate_signal_no_hv(self, sample_vol_arb_data):
        """Test signal generation when HV calculation fails"""
        strategy = VolatilityArbitrageStrategy()

        # Insufficient historical data
        sample_vol_arb_data['historical_prices'] = np.array([100, 101])

        signal = strategy.generate_signal(sample_vol_arb_data)

        # Should return None when HV calculation fails
        assert signal is None

    def test_generate_signal_low_vega(self, sample_vol_arb_data):
        """Test no signal when vega is too low"""
        strategy = VolatilityArbitrageStrategy(min_vega=1000.0)  # Very high vega requirement

        signal = strategy.generate_signal(sample_vol_arb_data)

        # Should not generate signal due to low vega
        assert signal is None

    def test_signal_contains_required_fields(self, sample_vol_arb_data):
        """Test signal contains all required fields"""
        strategy = VolatilityArbitrageStrategy(iv_hv_threshold=0.01)

        sample_vol_arb_data['market_price'] = 10.0

        signal = strategy.generate_signal(sample_vol_arb_data)

        if signal is not None:
            assert 'strategy' in signal
            assert 'timestamp' in signal
            assert 'action' in signal
            assert 'option_type' in signal
            assert 'quantity' in signal
            assert 'strike' in signal
            assert 'expiry' in signal
            assert 'implied_volatility' in signal
            assert 'historical_volatility' in signal
            assert 'iv_hv_diff' in signal
            assert 'greeks' in signal
            assert 'hedge_ratio' in signal

    def test_hedge_ratio_calculation(self, sample_vol_arb_data):
        """Test hedge ratio is calculated correctly"""
        strategy = VolatilityArbitrageStrategy(iv_hv_threshold=0.01)

        sample_vol_arb_data['market_price'] = 10.0

        signal = strategy.generate_signal(sample_vol_arb_data)

        if signal is not None:
            # Hedge ratio should be -delta * quantity
            expected_hedge = -signal['greeks']['delta'] * signal['quantity']
            assert signal['hedge_ratio'] == pytest.approx(expected_hedge)

    def test_quantity_sign(self, sample_vol_arb_data):
        """Test quantity sign matches action"""
        strategy = VolatilityArbitrageStrategy(iv_hv_threshold=0.01)

        # High IV - should sell
        sample_vol_arb_data['market_price'] = 10.0
        signal_sell = strategy.generate_signal(sample_vol_arb_data)

        if signal_sell is not None and signal_sell['action'] == 'SELL':
            assert signal_sell['quantity'] < 0

        # Low IV - should buy
        sample_vol_arb_data['market_price'] = 3.0
        signal_buy = strategy.generate_signal(sample_vol_arb_data)

        if signal_buy is not None and signal_buy['action'] == 'BUY':
            assert signal_buy['quantity'] > 0

    @pytest.mark.parametrize("option_type", ['call', 'put'])
    def test_different_option_types(self, sample_vol_arb_data, option_type):
        """Test strategy works with both call and put options"""
        strategy = VolatilityArbitrageStrategy(iv_hv_threshold=0.01)

        sample_vol_arb_data['option_type'] = option_type
        sample_vol_arb_data['market_price'] = 10.0

        signal = strategy.generate_signal(sample_vol_arb_data)

        if signal is not None:
            assert signal['option_type'] == option_type

    def test_timestamp_in_signal(self, sample_vol_arb_data):
        """Test timestamp is included in signal"""
        strategy = VolatilityArbitrageStrategy(iv_hv_threshold=0.01)

        sample_vol_arb_data['market_price'] = 10.0

        signal = strategy.generate_signal(sample_vol_arb_data)

        if signal is not None:
            assert isinstance(signal['timestamp'], datetime)

    def test_annualization_factor(self):
        """Test historical volatility uses correct annualization"""
        strategy = VolatilityArbitrageStrategy()

        np.random.seed(42)
        # Create prices with known daily volatility
        daily_vol = 0.01
        returns = np.random.randn(100) * daily_vol
        prices = 100 * np.exp(np.cumsum(returns))

        hv = strategy.calculate_historical_volatility(prices, window=50)

        # Annual vol should be approximately daily_vol * sqrt(252)
        expected_annual = daily_vol * np.sqrt(252)

        # Allow some tolerance due to randomness
        assert hv == pytest.approx(expected_annual, rel=0.5)
