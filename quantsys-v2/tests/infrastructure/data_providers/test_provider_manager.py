"""Tests for DataProviderManager."""
import pytest
from adapters.outbound.datasources.manager import DataProviderManager, get_data_provider_manager


def test_manager_initialization():
    """Test manager initializes with hardcoded providers"""
    manager = DataProviderManager()
    # Initially empty until Phase 2 when we migrate providers
    assert isinstance(manager.quote_providers, list)
    assert isinstance(manager.financial_providers, list)
    assert isinstance(manager.dividend_providers, list)
    assert isinstance(manager.market_providers, list)
    assert isinstance(manager.stock_providers, list)
    assert isinstance(manager.provider_stats, dict)


def test_manager_singleton():
    """Test get_data_provider_manager returns singleton"""
    m1 = get_data_provider_manager()
    m2 = get_data_provider_manager()
    assert m1 is m2


def test_manager_health_stats():
    """Test provider health stats tracking"""
    manager = DataProviderManager()
    stats = manager.get_provider_health()
    assert isinstance(stats, dict)


def test_manager_record_success():
    """Test recording success"""
    manager = DataProviderManager()
    manager.provider_stats['test_provider'] = {'success': 0, 'failure': 0}

    manager._record_success('test_provider')
    assert manager.provider_stats['test_provider']['success'] == 1
    assert manager.provider_stats['test_provider']['failure'] == 0


def test_manager_record_failure():
    """Test recording failure"""
    manager = DataProviderManager()
    manager.provider_stats['test_provider'] = {'success': 0, 'failure': 0}

    manager._record_failure('test_provider')
    assert manager.provider_stats['test_provider']['success'] == 0
    assert manager.provider_stats['test_provider']['failure'] == 1


def test_manager_is_valid():
    """Test data validation"""
    from adapters.outbound.datasources.models import QuoteData

    manager = DataProviderManager()

    # Valid data with source and timestamp
    valid_data = QuoteData(
        symbol='600519',
        name='茅台',
        price=100,
        source='test',
        timestamp='2026-06-07T14:30:00'
    )
    assert manager._is_valid(valid_data) is True

    # Invalid data without source
    invalid_data = QuoteData(
        symbol='600519',
        name='茅台',
        price=100,
        source='',
        timestamp='2026-06-07T14:30:00'
    )
    assert manager._is_valid(invalid_data) is False
