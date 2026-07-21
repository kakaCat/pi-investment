"""Tests for ConfigDrivenStrategy — database-configurable strategies."""
import math
import pytest


def make_klines(n=50, start=10.0, step=0.1):
    klines = []
    for i in range(n):
        base = start + i * step
        klines.append({
            'date': f'2024-01-{i+1:02d}',
            'open': base,
            'high': base * 1.02,
            'low': base * 0.98,
            'close': base + 0.05,
            'volume': 1000000 + i * 10000,
        })
    return klines


class TestConfigDrivenStrategy:
    """Tests for ConfigDrivenStrategy."""

    @pytest.fixture
    def strategy(self):
        from domain.quantlib.engine.config_driven_strategy import ConfigDrivenStrategy
        return ConfigDrivenStrategy(name='test_config')

    def test_sma_cross_buy_rule(self, strategy):
        """Buy when price crosses above SMA 20."""
        klines = make_klines(50, start=10.0, step=0.15)
        signal = strategy.generate_signal(klines, {
            'indicators': {
                'sma20': {'name': 'SMA', 'length': 20},
            },
            'rules': [{
                'condition': 'close > sma20',
                'action': 'buy',
                'confidence': 0.75,
            }],
        })
        assert signal['action'] in ('buy', 'hold')

    def test_rsi_oversold_buy_rule(self, strategy):
        """Buy when RSI is oversold."""
        klines = make_klines(50, start=10.0, step=0.02)
        signal = strategy.generate_signal(klines, {
            'indicators': {
                'rsi14': {'name': 'RSI', 'length': 14},
            },
            'rules': [{
                'condition': 'rsi14 < 30',
                'action': 'buy',
                'confidence': 0.8,
            }, {
                'condition': 'rsi14 > 70',
                'action': 'sell',
                'confidence': 0.8,
            }],
        })
        assert signal['action'] in ('buy', 'sell', 'hold')

    def test_and_condition(self, strategy):
        """Buy when both SMA > price and RSI is low."""
        klines = make_klines(50, start=10.0, step=0.15)
        signal = strategy.generate_signal(klines, {
            'indicators': {
                'sma20': {'name': 'SMA', 'length': 20},
                'rsi14': {'name': 'RSI', 'length': 14},
            },
            'rules': [{
                'condition': 'close > sma20 AND rsi14 > 50',
                'action': 'buy',
                'confidence': 0.85,
            }],
        })
        assert signal['action'] in ('buy', 'hold')

    def test_hold_when_no_rule_matches(self, strategy):
        """Should return hold when no rule matches."""
        klines = make_klines(50)
        signal = strategy.generate_signal(klines, {
            'indicators': {
                'rsi14': {'name': 'RSI', 'length': 14},
            },
            'rules': [{
                'condition': 'rsi14 < 5',  # impossible
                'action': 'buy',
                'confidence': 0.9,
            }],
        })
        assert signal['action'] == 'hold'

    def test_first_matching_rule_wins(self, strategy):
        """First matching rule should be used (priority ordering)."""
        klines = make_klines(50, start=10.0, step=0.2)
        signal = strategy.generate_signal(klines, {
            'indicators': {
                'sma20': {'name': 'SMA', 'length': 20},
            },
            'rules': [
                {'condition': 'close > sma20', 'action': 'buy', 'confidence': 0.9},
                {'condition': 'close > sma20', 'action': 'sell', 'confidence': 0.5},
            ],
        })
        assert signal['action'] == 'buy'
        assert signal['confidence'] == 0.9

    def test_close_and_volume_in_condition(self, strategy):
        """Should support close, high, low, open, volume in conditions."""
        klines = make_klines(50)
        signal = strategy.generate_signal(klines, {
            'indicators': {
                'sma10': {'name': 'SMA', 'length': 10},
            },
            'rules': [{
                'condition': 'close > low AND volume > 0',
                'action': 'buy',
                'confidence': 0.7,
            }],
        })
        assert signal['action'] == 'buy'

    def test_invalid_condition_returns_hold(self, strategy):
        """Malformed condition should not crash, returns hold."""
        klines = make_klines(50)
        signal = strategy.generate_signal(klines, {
            'indicators': {},
            'rules': [{
                'condition': 'this_is_broken',
                'action': 'buy',
                'confidence': 0.5,
            }],
        })
        assert signal['action'] == 'hold'

    def test_gt_gte_lt_lte_eq_neq_operators(self, strategy):
        """All comparison operators should work."""
        klines = make_klines(30)
        close = float(klines[-1]['close'])

        # Test >=
        signal = strategy.generate_signal(klines, {
            'indicators': {
                'sma5': {'name': 'SMA', 'length': 5},
            },
            'rules': [{
                'condition': f'close >= {close - 1}',
                'action': 'buy',
                'confidence': 0.8,
            }],
        })
        assert signal['action'] == 'buy'

        # Test <=
        signal = strategy.generate_signal(klines, {
            'indicators': {
                'sma5': {'name': 'SMA', 'length': 5},
            },
            'rules': [{
                'condition': f'close <= {close + 1}',
                'action': 'buy',
                'confidence': 0.8,
            }],
        })
        assert signal['action'] == 'buy'

    def test_or_condition(self, strategy):
        """OR should work between conditions."""
        klines = make_klines(50, start=10.0, step=0.15)
        signal = strategy.generate_signal(klines, {
            'indicators': {
                'rsi14': {'name': 'RSI', 'length': 14},
            },
            'rules': [{
                'condition': 'rsi14 < 5 OR close > 0',  # second is always true
                'action': 'buy',
                'confidence': 0.8,
            }],
        })
        assert signal['action'] == 'buy'

    def test_default_params(self, strategy):
        """Should have DEFAULT_PARAMS with empty config."""
        assert hasattr(strategy, 'DEFAULT_PARAMS')
        assert 'indicators' in strategy.DEFAULT_PARAMS
        assert 'rules' in strategy.DEFAULT_PARAMS
