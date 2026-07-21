"""Tests for DataSourceManager."""

import pytest
import time
from unittest.mock import Mock, patch
from adapters.outbound.datasources.manager import DataSourceManager, DataSourceConfig
from adapters.outbound.datasources.base import DataSourceResponse, MarketDataSource


class MockDataSource(MarketDataSource):
    """Mock data source for testing."""

    def __init__(self, name: str, should_fail: bool = False):
        super().__init__(name=name, requires_api_key=False)
        self.should_fail = should_fail
        self.call_count = 0

    def validate_config(self) -> bool:
        return True

    def test_connection(self) -> DataSourceResponse:
        return DataSourceResponse.success_response({"status": "ok"})

    def get_stock_info(self, symbol: str) -> DataSourceResponse:
        self.call_count += 1
        if self.should_fail:
            return DataSourceResponse.error_response(f"{self.name} failed")
        return DataSourceResponse.success_response({
            "symbol": symbol,
            "name": f"Stock {symbol}",
            "source": self.name
        })

    def get_klines(self, symbol: str, period: str = "daily",
                   start_date: str = "20200101",
                   end_date: str = "20260101") -> DataSourceResponse:
        self.call_count += 1
        if self.should_fail:
            return DataSourceResponse.error_response(f"{self.name} failed")
        return DataSourceResponse.success_response([
            {"date": "2024-01-01", "close": 100.0, "source": self.name}
        ])

    def get_realtime_quote(self, symbols: list) -> DataSourceResponse:
        self.call_count += 1
        if self.should_fail:
            return DataSourceResponse.error_response(f"{self.name} failed")
        return DataSourceResponse.success_response({
            sym: {"price": 100.0, "source": self.name} for sym in symbols
        })


@pytest.fixture
def mock_config(tmp_path):
    """Create a temporary config file."""
    config_content = """
market_data:
  sources:
    - name: source1
      priority: 1
      enabled: true
      timeout: 10
      max_failures: 3
      circuit_timeout: 60

    - name: source2
      priority: 2
      enabled: true
      timeout: 10
      max_failures: 3
      circuit_timeout: 60

  fallback_strategy: sequential
  cache:
    enabled: true
    ttl: 60
    max_size: 1000
"""
    config_file = tmp_path / "test_config.yaml"
    config_file.write_text(config_content)
    return str(config_file)


def test_manager_initialization(mock_config):
    """Test manager initializes correctly."""
    with patch.object(DataSourceManager, '_create_source') as mock_create:
        mock_create.return_value = MockDataSource("test")
        manager = DataSourceManager(config_path=mock_config)

        assert len(manager.source_configs) == 2
        assert 'source1' in manager.source_configs
        assert 'source2' in manager.source_configs


def test_failover_on_source_failure(mock_config):
    """Test automatic failover when first source fails."""
    with patch.object(DataSourceManager, '_create_source') as mock_create:
        # First source fails, second succeeds
        source1 = MockDataSource("source1", should_fail=True)
        source2 = MockDataSource("source2", should_fail=False)

        def create_source(name):
            return source1 if name == "source1" else source2

        mock_create.side_effect = create_source
        manager = DataSourceManager(config_path=mock_config)

        # Call should failover to source2
        result = manager.get_stock_info("600000.SH")

        assert result.success
        assert result.data['source'] == 'source2'
        assert source1.call_count == 1  # First source was tried
        assert source2.call_count == 1  # Second source succeeded


def test_cache_functionality(mock_config):
    """Test response caching works."""
    with patch.object(DataSourceManager, '_create_source') as mock_create:
        source = MockDataSource("source1", should_fail=False)
        mock_create.return_value = source

        manager = DataSourceManager(config_path=mock_config)

        # First call - cache miss
        result1 = manager.get_stock_info("600000.SH")
        assert result1.success
        assert source.call_count == 1

        # Second call - cache hit
        result2 = manager.get_stock_info("600000.SH")
        assert result2.success
        assert source.call_count == 1  # Not called again

        stats = manager.get_stats()
        assert stats['cache_hits'] == 1
        assert stats['cache_misses'] == 1


def test_circuit_breaker_opens_after_failures(mock_config):
    """Test circuit breaker opens after repeated failures."""
    with patch.object(DataSourceManager, '_create_source') as mock_create:
        source = MockDataSource("source1", should_fail=True)
        mock_create.return_value = source

        manager = DataSourceManager(config_path=mock_config)

        # Make 3 calls - should trigger circuit breaker
        for _ in range(3):
            result = manager.get_stock_info("600000.SH")
            assert not result.success

        # Check circuit breaker is open
        breaker = manager.circuit_breakers['source1']
        assert not breaker.is_available()

        # Fourth call should not reach the source
        call_count_before = source.call_count
        result = manager.get_stock_info("600000.SH")
        assert not result.success
        assert source.call_count == call_count_before  # Not called


def test_priority_ordering(mock_config):
    """Test sources are tried in priority order."""
    with patch.object(DataSourceManager, '_create_source') as mock_create:
        source1 = MockDataSource("source1", should_fail=False)
        source2 = MockDataSource("source2", should_fail=False)

        def create_source(name):
            return source1 if name == "source1" else source2

        mock_create.side_effect = create_source
        manager = DataSourceManager(config_path=mock_config)

        # Should use source1 (higher priority)
        result = manager.get_stock_info("600000.SH")

        assert result.success
        assert result.data['source'] == 'source1'
        assert source1.call_count == 1
        assert source2.call_count == 0  # Not tried


def test_all_sources_fail(mock_config):
    """Test behavior when all sources fail."""
    with patch.object(DataSourceManager, '_create_source') as mock_create:
        source1 = MockDataSource("source1", should_fail=True)
        source2 = MockDataSource("source2", should_fail=True)

        def create_source(name):
            return source1 if name == "source1" else source2

        mock_create.side_effect = create_source
        manager = DataSourceManager(config_path=mock_config)

        result = manager.get_stock_info("600000.SH")

        assert not result.success
        assert "All data sources failed" in result.error
        assert source1.call_count == 1
        assert source2.call_count == 1


def test_stats_tracking(mock_config):
    """Test statistics are tracked correctly."""
    with patch.object(DataSourceManager, '_create_source') as mock_create:
        source = MockDataSource("source1", should_fail=False)
        mock_create.return_value = source

        manager = DataSourceManager(config_path=mock_config)

        # Make some calls
        manager.get_stock_info("600000.SH")
        manager.get_stock_info("600001.SH")

        stats = manager.get_stats()
        assert stats['total_requests'] == 2
        assert stats['source_success']['source1'] == 2
        assert stats['source_failures']['source1'] == 0


def test_cache_clear(mock_config):
    """Test cache can be cleared."""
    with patch.object(DataSourceManager, '_create_source') as mock_create:
        source = MockDataSource("source1", should_fail=False)
        mock_create.return_value = source

        manager = DataSourceManager(config_path=mock_config)

        # Cache a result
        manager.get_stock_info("600000.SH")
        assert manager.get_stats()['cache_misses'] == 1

        # Clear cache
        manager.clear_cache()

        # Should be cache miss again
        manager.get_stock_info("600000.SH")
        assert manager.get_stats()['cache_misses'] == 2


def test_circuit_breaker_reset(mock_config):
    """Test circuit breakers can be reset."""
    with patch.object(DataSourceManager, '_create_source') as mock_create:
        source = MockDataSource("source1", should_fail=True)
        mock_create.return_value = source

        manager = DataSourceManager(config_path=mock_config)

        # Trigger circuit breaker
        for _ in range(3):
            manager.get_stock_info("600000.SH")

        assert not manager.circuit_breakers['source1'].is_available()

        # Reset
        manager.reset_circuit_breakers()

        assert manager.circuit_breakers['source1'].is_available()
