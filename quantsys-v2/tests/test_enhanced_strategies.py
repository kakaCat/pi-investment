"""Tests for the 5 new strategies."""
import math
import pytest


def make_uptrend_klines(n=60):
    klines = []
    for i in range(n):
        close = 10.0 + i * 0.2
        klines.append({
            'date': f'2024-01-{i+1:02d}',
            'open': close - 0.05,
            'high': close * 1.02,
            'low': close * 0.98,
            'close': close,
            'volume': 1000000 + i * 10000,
        })
    return klines


def make_downtrend_klines(n=60):
    klines = []
    for i in range(n):
        close = 20.0 - i * 0.2
        klines.append({
            'date': f'2024-01-{i+1:02d}',
            'open': close + 0.05,
            'high': close * 1.02,
            'low': close * 0.98,
            'close': close,
            'volume': 1000000 + i * 10000,
        })
    return klines


def make_sideways_klines(n=60):
    klines = []
    for i in range(n):
        close = 10.0 + 0.5 * math.sin(2 * math.pi * i / 10)
        klines.append({
            'date': f'2024-01-{i+1:02d}',
            'open': close - 0.02,
            'high': close * 1.02,
            'low': close * 0.98,
            'close': close,
            'volume': 1000000,
        })
    return klines


# ==================== MultiFactorStrategy ====================

class TestMultiFactorStrategy:
    """Tests for MultiFactorStrategy."""

    @pytest.fixture
    def strategy(self):
        from domain.quantlib.engine.multi_factor_strategy import MultiFactorStrategy
        return MultiFactorStrategy(name='test_mf')

    def test_signal_in_uptrend(self, strategy):
        klines = make_uptrend_klines(60)
        signal = strategy.generate_signal(klines)
        assert signal['action'] in ('buy', 'sell', 'hold')
        assert 0 <= signal['confidence'] <= 1
        assert signal['reason']

    def test_signal_in_downtrend(self, strategy):
        klines = make_downtrend_klines(60)
        signal = strategy.generate_signal(klines)
        assert signal['action'] in ('buy', 'sell', 'hold')

    def test_custom_factor_groups(self, strategy):
        klines = make_uptrend_klines(60)
        signal = strategy.generate_signal(klines, {
            'factor_groups': {'trend': ['ma5', 'ma10'], 'momentum': ['rsi14']},
            'group_weights': [0.5, 0.5],
        })
        assert signal['action'] in ('buy', 'sell', 'hold')

    def test_default_params(self, strategy):
        assert hasattr(strategy, 'DEFAULT_PARAMS')
        assert 'factor_groups' in strategy.DEFAULT_PARAMS

    def test_param_schema(self, strategy):
        assert hasattr(strategy, 'PARAM_SCHEMA')
        assert 'buy_threshold' in strategy.PARAM_SCHEMA


# ==================== ADXTrendStrategy ====================

class TestADXTrendStrategy:
    """Tests for ADXTrendStrategy."""

    @pytest.fixture
    def strategy(self):
        from domain.quantlib.engine.adx_trend_strategy import ADXTrendStrategy
        return ADXTrendStrategy(name='test_adx')

    def test_signal_structure(self, strategy):
        klines = make_uptrend_klines(90)
        signal = strategy.generate_signal(klines)
        assert signal['action'] in ('buy', 'sell', 'hold')
        assert 0 <= signal['confidence'] <= 1

    def test_uses_adx(self, strategy):
        klines = make_uptrend_klines(90)
        signal = strategy.generate_signal(klines)
        assert 'ADX' in signal['reason']

    def test_custom_adx_threshold(self, strategy):
        klines = make_uptrend_klines(90)
        signal = strategy.generate_signal(klines, {'adx_threshold': 40})
        assert signal['action'] in ('buy', 'sell', 'hold')

    def test_default_params(self, strategy):
        assert hasattr(strategy, 'DEFAULT_PARAMS')
        assert 'adx_threshold' in strategy.DEFAULT_PARAMS


# ==================== CCIReversalStrategy ====================

class TestCCIReversalStrategy:
    """Tests for CCIReversalStrategy."""

    @pytest.fixture
    def strategy(self):
        from domain.quantlib.engine.cci_reversal_strategy import CCIReversalStrategy
        return CCIReversalStrategy(name='test_cci')

    def test_signal_structure(self, strategy):
        klines = make_sideways_klines(80)
        signal = strategy.generate_signal(klines)
        assert signal['action'] in ('buy', 'sell', 'hold')
        assert 0 <= signal['confidence'] <= 1

    def test_custom_thresholds(self, strategy):
        klines = make_sideways_klines(80)
        signal = strategy.generate_signal(klines, {
            'overbought': 150, 'oversold': -150,
        })
        assert signal['action'] in ('buy', 'sell', 'hold')

    def test_default_params(self, strategy):
        assert hasattr(strategy, 'DEFAULT_PARAMS')
        assert 'overbought' in strategy.DEFAULT_PARAMS


# ==================== GridTradingStrategy ====================

class TestGridTradingStrategy:
    """Tests for GridTradingStrategy."""

    @pytest.fixture
    def strategy(self):
        from domain.quantlib.engine.grid_trading_strategy import GridTradingStrategy
        return GridTradingStrategy(name='test_grid')

    def test_signal_structure(self, strategy):
        klines = make_sideways_klines(60)
        signal = strategy.generate_signal(klines)
        assert signal['action'] in ('buy', 'sell', 'hold')
        assert 0 <= signal['confidence'] <= 1

    def test_auto_price_range(self, strategy):
        klines = make_sideways_klines(60)
        signal = strategy.generate_signal(klines, {'price_range': 'auto'})
        assert signal['action'] in ('buy', 'sell', 'hold')

    def test_fixed_price_range(self, strategy):
        klines = make_sideways_klines(60)
        signal = strategy.generate_signal(klines, {
            'price_range': [9.0, 11.0], 'grid_count': 5,
        })
        assert 'Grid' in signal['reason']

    def test_default_params(self, strategy):
        assert hasattr(strategy, 'DEFAULT_PARAMS')
        assert 'grid_count' in strategy.DEFAULT_PARAMS


# ==================== MLPredictionStrategy ====================

class TestMLPredictionStrategy:
    """Tests for MLPredictionStrategy."""

    @pytest.fixture
    def strategy(self):
        from domain.quantlib.engine.ml_prediction_strategy import MLPredictionStrategy
        return MLPredictionStrategy(name='test_ml')

    def test_precomputed_buy(self, strategy):
        klines = make_uptrend_klines(60)
        signal = strategy.generate_signal(klines, {
            'use_precomputed': True,
            'ml_prediction': {'signal': 'BUY', 'confidence': 0.85},
        })
        assert signal['action'] == 'BUY'
        assert signal['confidence'] == 0.85

    def test_precomputed_low_confidence(self, strategy):
        klines = make_uptrend_klines(60)
        signal = strategy.generate_signal(klines, {
            'use_precomputed': True,
            'ml_prediction': {'signal': 'BUY', 'confidence': 0.55},
        })
        assert signal['action'] == 'hold'

    def test_no_precomputed_data(self, strategy):
        klines = make_uptrend_klines(60)
        signal = strategy.generate_signal(klines, {'use_precomputed': True})
        assert signal['action'] == 'hold'

    def test_custom_confidence_threshold(self, strategy):
        klines = make_uptrend_klines(60)
        signal = strategy.generate_signal(klines, {
            'use_precomputed': True,
            'ml_prediction': {'signal': 'BUY', 'confidence': 0.65},
            'confidence_threshold': 0.6,
        })
        assert signal['action'] == 'BUY'

    def test_default_params(self, strategy):
        assert hasattr(strategy, 'DEFAULT_PARAMS')
