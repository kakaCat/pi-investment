"""Tests for strategy mixins."""
import pytest


def make_test_klines(n=50):
    klines = []
    for i in range(n):
        base = 10.0 + i * 0.1
        klines.append({
            'date': f'2024-01-{i+1:02d}',
            'open': base,
            'high': base * 1.02,
            'low': base * 0.98,
            'close': base + 0.05,
            'volume': 1000000 + i * 10000,
        })
    return klines


class TestIndicatorMixin:
    """Tests for IndicatorMixin."""

    @pytest.fixture
    def mixin(self):
        from domain.quantlib.engine.mixins.indicator_mixin import IndicatorMixin
        return IndicatorMixin()

    @pytest.fixture
    def klines(self):
        return make_test_klines(50)

    def test_calculate_indicator_sma(self, mixin, klines):
        result = mixin.calculate_indicator(klines, 'SMA', length=20)
        assert result is not None

    def test_calculate_batch_indicators(self, mixin, klines):
        results = mixin.calculate_batch_indicators(
            klines, ['SMA', 'RSI', 'ADX']
        )
        assert 'SMA' in results
        assert 'RSI' in results
        assert 'ADX' in results

    def test_indicator_manager_is_lazy_and_singleton(self, mixin):
        mgr = mixin.indicator_manager
        assert mgr is mixin.indicator_manager


class TestFactorMixin:
    """Tests for FactorMixin."""

    @pytest.fixture
    def mixin(self):
        from domain.quantlib.engine.mixins.factor_mixin import FactorMixin
        return FactorMixin()

    @pytest.fixture
    def klines(self):
        return make_test_klines(50)

    def test_calculate_factors_default(self, mixin, klines):
        factors = mixin.calculate_factors(klines)
        assert isinstance(factors, dict)
        assert len(factors) > 0

    def test_calculate_factors_subset(self, mixin, klines):
        factors = mixin.calculate_factors(klines, ['ma5', 'ma10', 'rsi14'])
        assert 'ma5' in factors
        assert 'ma10' in factors
        assert 'rsi14' in factors

    def test_get_factor_categories(self, mixin):
        categories = mixin.get_factor_categories()
        assert isinstance(categories, dict)


class TestMLMixin:
    """Tests for MLMixin."""

    @pytest.fixture
    def mixin(self):
        from domain.quantlib.engine.mixins.ml_mixin import MLMixin
        return MLMixin()

    def test_ml_mixin_initial_state(self, mixin):
        assert mixin.is_model_loaded() is False

    def test_predict_precomputed_mode(self, mixin):
        features = {'ml_prediction': {'signal': 'BUY', 'confidence': 0.85}}
        result = mixin.predict_ml(features, use_precomputed=True)
        assert result is not None
        assert result['signal'] == 'BUY'
        assert result['confidence'] == 0.85

    def test_predict_precomputed_none(self, mixin):
        result = mixin.predict_ml({}, use_precomputed=True)
        assert result is None

    def test_predict_without_model_raises(self, mixin):
        with pytest.raises(ValueError, match='Model not loaded'):
            mixin.predict_ml({'feature1': 1.0}, use_precomputed=False)


class TestEnhancedStrategyBase:
    """Tests for EnhancedStrategyBase."""

    @pytest.fixture
    def klines(self):
        return make_test_klines(50)

    def test_enhanced_base_includes_all_mixins(self):
        from domain.quantlib.engine.enhanced_strategy_base import EnhancedStrategyBase
        from domain.quantlib.engine.mixins.indicator_mixin import IndicatorMixin
        from domain.quantlib.engine.mixins.factor_mixin import FactorMixin
        from domain.quantlib.engine.strategy_base import StrategyBase

        assert issubclass(EnhancedStrategyBase, StrategyBase)
        assert issubclass(EnhancedStrategyBase, IndicatorMixin)
        assert issubclass(EnhancedStrategyBase, FactorMixin)

    def test_enhanced_base_requires_generate_signal(self):
        from domain.quantlib.engine.enhanced_strategy_base import EnhancedStrategyBase
        with pytest.raises(TypeError):
            # Cannot instantiate abstract class with abstract generate_signal
            EnhancedStrategyBase(name='test')

    def test_enhanced_base_calculates_indicator(self, klines):
        from domain.quantlib.engine.enhanced_strategy_base import EnhancedStrategyBase

        class TestStrat(EnhancedStrategyBase):
            def generate_signal(self, klines, params=None):
                return {'action': 'hold', 'confidence': 0.5, 'reason': 'test'}

        strat = TestStrat(name='test')
        result = strat.calculate_indicator(klines, 'SMA', length=20)
        assert result is not None
