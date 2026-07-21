"""Tests for quote providers integration."""
import pytest
from adapters.outbound.datasources import get_data_provider_manager


def test_quote_providers_registered():
    """Test quote providers are registered in manager"""
    manager = get_data_provider_manager()
    assert len(manager.quote_providers) == 5
    provider_names = [p.name for p in manager.quote_providers]
    assert 'sina' in provider_names
    assert 'eastmoney' in provider_names
    assert 'akshare' in provider_names
    assert 'tencent' in provider_names
    assert 'netease' in provider_names


def test_quote_provider_priority():
    """Test quote providers are in correct priority order"""
    manager = get_data_provider_manager()
    provider_names = [p.name for p in manager.quote_providers]
    # Expected priority: sina, eastmoney, akshare, tencent, netease
    assert provider_names[0] == 'sina'
    assert provider_names[1] == 'eastmoney'
    assert provider_names[2] == 'akshare'


def test_get_quote_returns_structure():
    """Test get_quote returns correct structure"""
    manager = get_data_provider_manager()

    # Test with a valid symbol (may succeed or fail depending on network)
    result = manager.get_quote('600519.SH')

    # Should always return a dict with 'success' key
    assert isinstance(result, dict)
    assert 'success' in result

    if result['success']:
        # If successful, should have data and source
        assert 'data' in result
        assert 'source' in result
        assert result['data'].symbol == '600519.SH'
        assert result['source'] in ['sina', 'eastmoney', 'akshare', 'tencent', 'netease']
    else:
        # If failed, should have error and attempted_sources
        assert 'error' in result
        assert 'attempted_sources' in result


@pytest.mark.slow
def test_get_quote_failover():
    """Test get_quote uses failover mechanism (slow test, requires network)"""
    manager = get_data_provider_manager()

    # Try to get a quote
    result = manager.get_quote('600519.SH')

    # Check provider stats were updated
    stats = manager.get_provider_health()

    # At least one provider should have been tried
    total_attempts = sum(
        stats.get(p.name, {}).get('success', 0) + stats.get(p.name, {}).get('failure', 0)
        for p in manager.quote_providers
    )
    assert total_attempts > 0
