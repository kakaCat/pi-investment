"""Tests for indicator adapter layer."""
import pytest


def make_test_klines(n=50):
    """Generate synthetic klines for indicator testing."""
    klines = []
    for i in range(n):
        base_price = 10.0 + i * 0.1
        klines.append({
            'date': f'2024-01-{i+1:02d}',
            'open': base_price,
            'high': base_price * 1.02,
            'low': base_price * 0.98,
            'close': base_price + 0.05,
            'volume': 1000000 + i * 10000,
        })
    return klines


class TestIndicatorAdapterABC:
    """Tests for the abstract base class interface."""

    def test_adapter_has_calculate_method(self):
        from domain.quantlib.engine.indicators.base import IndicatorAdapter
        assert hasattr(IndicatorAdapter, 'calculate')
        assert hasattr(IndicatorAdapter, 'is_available')

    def test_adapter_has_list_indicators_method(self):
        from domain.quantlib.engine.indicators.base import IndicatorAdapter
        assert hasattr(IndicatorAdapter, 'list_indicators')


class TestPandasTAAdapter:
    """Tests for pandas-ta adapter."""

    @pytest.fixture
    def adapter(self):
        from domain.quantlib.engine.indicators.pandasta_adapter import PandasTAAdapter
        return PandasTAAdapter()

    @pytest.fixture
    def klines(self):
        return make_test_klines(50)

    def test_is_available(self, adapter):
        assert adapter.is_available() is True

    def test_calculate_sma(self, adapter, klines):
        result = adapter.calculate(klines, 'SMA', length=20)
        assert result is not None
        assert len(result) == len(klines)

    def test_calculate_rsi(self, adapter, klines):
        result = adapter.calculate(klines, 'RSI', length=14)
        assert result is not None
        last_val = result[-1]
        assert 0 <= last_val <= 100

    def test_calculate_adx(self, adapter, klines):
        result = adapter.calculate(klines, 'ADX', length=14)
        assert result is not None

    def test_calculate_cci(self, adapter, klines):
        result = adapter.calculate(klines, 'CCI', length=20)
        assert result is not None

    def test_list_indicators(self, adapter):
        indicators = adapter.list_indicators()
        assert isinstance(indicators, list)
        assert len(indicators) > 10

    def test_unknown_indicator_returns_none(self, adapter, klines):
        result = adapter.calculate(klines, 'NONEXISTENT_INDICATOR')
        assert result is None


class TestTALibAdapter:
    """Tests for TA-Lib adapter (may be skipped if not installed)."""

    @pytest.fixture
    def adapter(self):
        from domain.quantlib.engine.indicators.talib_adapter import TALibAdapter
        return TALibAdapter()

    def test_is_available_returns_bool(self, adapter):
        result = adapter.is_available()
        assert isinstance(result, bool)


class TestIndicatorManager:
    """Tests for unified indicator manager with auto-fallback."""

    @pytest.fixture
    def manager(self):
        from domain.quantlib.engine.indicators.indicator_manager import IndicatorManager
        return IndicatorManager()

    @pytest.fixture
    def klines(self):
        return make_test_klines(50)

    def test_manager_created_with_adapters(self, manager):
        assert len(manager.adapters) >= 1

    def test_calculate_sma_via_manager(self, manager, klines):
        result = manager.calculate(klines, 'SMA', length=20)
        assert result is not None
        assert isinstance(result[-1], float)

    def test_calculate_rsi_via_manager(self, manager, klines):
        result = manager.calculate(klines, 'RSI', length=14)
        assert result is not None

    def test_calculate_batch(self, manager, klines):
        results = manager.calculate_batch(
            klines,
            {'SMA': {'length': 20}, 'RSI': {'length': 14}, 'CCI': {'length': 20}}
        )
        assert 'SMA' in results
        assert 'RSI' in results
        assert 'CCI' in results

    def test_calculate_raises_when_no_adapter_available(self):
        from domain.quantlib.engine.indicators.indicator_manager import IndicatorManager
        mgr = IndicatorManager()
        mgr.adapters = []
        with pytest.raises(RuntimeError, match='No indicator library'):
            mgr.calculate(make_test_klines(10), 'SMA')
