"""End-to-end integration test for unified data provider architecture."""
import pytest
from adapters.outbound.datasources import get_data_provider_manager
from application.services.stock_data_service import StockDataService
from application.services.realtime_quote_service import RealtimeQuoteService


def test_e2e_provider_manager_singleton():
    """Test that all services use the same DataProviderManager instance"""
    manager1 = get_data_provider_manager()
    manager2 = get_data_provider_manager()

    stock_service = StockDataService()
    quote_service = RealtimeQuoteService()

    # All should reference the same singleton
    assert manager1 is manager2
    assert stock_service.provider_manager is manager1
    assert quote_service.provider_manager is manager1


def test_e2e_stock_data_service_integration():
    """Test StockDataService uses DataProviderManager correctly"""
    service = StockDataService()

    # Test get_announcements (uses provider_manager internally)
    result = service.get_announcements('600519.SH')

    # Should return a dict with success key
    assert isinstance(result, dict)
    assert 'success' in result

    if result['success']:
        # If successful, should have source tracking
        assert 'data' in result
        assert 'source' in result['data']
        assert result['data']['source'] == 'akshare'


def test_e2e_realtime_quote_service_integration():
    """Test RealtimeQuoteService delegates to DataProviderManager"""
    service = RealtimeQuoteService()

    # Test get_realtime_quote
    quote = service.get_realtime_quote('600519.SH')

    # May succeed or fail depending on network, but should not raise
    if quote:
        assert hasattr(quote, 'symbol')
        assert hasattr(quote, 'price')
        assert hasattr(quote, 'source')
        assert quote.source in ['sina', 'eastmoney', 'akshare', 'tencent', 'netease']


def test_e2e_provider_health_tracking():
    """Test that provider health stats are tracked across services"""
    manager = get_data_provider_manager()

    # Clear stats
    for provider_name in manager.provider_stats:
        manager.provider_stats[provider_name] = {'success': 0, 'failure': 0}

    # Make a request through StockDataService
    service = StockDataService()
    service.get_announcements('600519.SH')

    # Check that stats were updated
    health = manager.get_provider_health()

    # At least one provider should have been tried
    total_attempts = sum(
        stats['success'] + stats['failure']
        for stats in health.values()
    )
    assert total_attempts > 0


def test_e2e_architecture_summary():
    """Summary test showing the complete architecture works"""
    manager = get_data_provider_manager()

    # Verify all provider types are initialized
    assert len(manager.quote_providers) == 5
    assert len(manager.stock_providers) == 1
    assert len(manager.dividend_providers) == 1
    assert len(manager.market_providers) == 1

    # Verify provider names
    quote_names = [p.name for p in manager.quote_providers]
    assert 'sina' in quote_names
    assert 'eastmoney' in quote_names
    assert 'akshare' in quote_names

    # Verify services can be instantiated
    stock_service = StockDataService()
    quote_service = RealtimeQuoteService()

    assert stock_service.provider_manager is manager
    assert quote_service.provider_manager is manager

    print("\n✅ Unified Data Provider Architecture E2E Test PASSED")
    print(f"   - {len(manager.quote_providers)} quote providers")
    print(f"   - {len(manager.stock_providers)} stock providers")
    print(f"   - {len(manager.dividend_providers)} dividend providers")
    print(f"   - {len(manager.market_providers)} market providers")
    print(f"   - 2 services integrated")
