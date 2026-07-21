"""Tests for StrategyFactory."""
import pytest


class TestStrategyFactory:
    """Tests for StrategyFactory auto-discovery and registration."""

    @pytest.fixture(autouse=True)
    def clean_registry(self):
        from domain.quantlib.engine.strategy_factory import StrategyFactory
        StrategyFactory._registry = {}
        StrategyFactory._metadata = {}
        yield
        StrategyFactory._registry = {}
        StrategyFactory._metadata = {}

    def test_auto_discover_finds_strategies(self):
        from domain.quantlib.engine.strategy_factory import StrategyFactory
        StrategyFactory.auto_discover()
        registered = StrategyFactory.list_all()
        assert len(registered) >= 15

    def test_auto_discover_includes_new_strategies(self):
        from domain.quantlib.engine.strategy_factory import StrategyFactory
        StrategyFactory.auto_discover()
        registered = StrategyFactory.list_all()
        for name in ('multi_factor', 'adx_trend', 'cci_reversal',
                      'grid_trading', 'ml_prediction'):
            assert name in registered, f"Missing: {name}"

    def test_create_strategy(self):
        from domain.quantlib.engine.strategy_factory import StrategyFactory
        from domain.quantlib.engine.enhanced_strategy_base import EnhancedStrategyBase
        StrategyFactory.auto_discover()
        strat = StrategyFactory.create('multi_factor', name='test')
        assert isinstance(strat, EnhancedStrategyBase)
        assert strat.name == 'test'

    def test_create_unknown_strategy_raises(self):
        from domain.quantlib.engine.strategy_factory import StrategyFactory
        with pytest.raises(ValueError, match='Unknown'):
            StrategyFactory.create('nonexistent')

    def test_get_info(self):
        from domain.quantlib.engine.strategy_factory import StrategyFactory
        StrategyFactory.auto_discover()
        info = StrategyFactory.get_info('multi_factor')
        assert info is not None
        assert info['class_name'] == 'MultiFactorStrategy'

    def test_class_name_to_type(self):
        from domain.quantlib.engine.strategy_factory import StrategyFactory
        assert StrategyFactory.class_name_to_type('MACrossStrategy') == 'ma_cross'
        assert StrategyFactory.class_name_to_type('ADXTrendStrategy') == 'adx_trend'
        assert StrategyFactory.class_name_to_type('MLPredictionStrategy') == 'ml_prediction'
        assert StrategyFactory.class_name_to_type('RSIReversalStrategy') == 'rsi_reversal'
