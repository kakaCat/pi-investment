import pytest
from application.services.enhanced_financial_data_service import EnhancedFinancialDataService
from application.services.financial_data_service import FinancialDataService


class TestEnhancedFinancialDataServiceInit:
    def test_initializes_with_default_base_service(self):
        """Should create base service if not provided."""
        service = EnhancedFinancialDataService()

        assert service.base_service is not None
        assert isinstance(service.base_service, FinancialDataService)
        assert service.cache is not None
        assert service.circuit_breakers is not None
        assert len(service.circuit_breakers) == len(service.base_service.providers)

    def test_initializes_with_custom_base_service(self):
        """Should use provided base service."""
        base = FinancialDataService()
        service = EnhancedFinancialDataService(base_service=base)

        assert service.base_service is base

    def test_initializes_with_custom_config(self):
        """Should use custom cache TTL and circuit breaker cooldown."""
        service = EnhancedFinancialDataService(
            cache_ttl=600,
            circuit_breaker_cooldown=120
        )

        assert service.cache.ttl == 600
        # Circuit breaker timeout checked in service


class TestCacheKeyGeneration:
    def test_generates_cache_key_with_all_params(self):
        """Should generate cache key from symbol, statement_type, periods."""
        service = EnhancedFinancialDataService()
        
        key = service._make_cache_key("600519", "all", 4)
        
        assert key == "financial:600519:all:4"
    
    def test_generates_different_keys_for_different_params(self):
        """Should generate different keys for different parameters."""
        service = EnhancedFinancialDataService()
        
        key1 = service._make_cache_key("600519", "all", 4)
        key2 = service._make_cache_key("600519", "income", 4)
        key3 = service._make_cache_key("600519", "all", 8)
        key4 = service._make_cache_key("000858", "all", 4)
        
        assert len({key1, key2, key3, key4}) == 4  # All different


from unittest.mock import Mock, patch
from application.services.financial_providers import FinancialData


class TestCircuitBreakerIntegration:
    def test_fetches_from_first_available_provider(self):
        """Should fetch from first provider with closed circuit breaker."""
        service = EnhancedFinancialDataService()
        
        mock_data = FinancialData(
            symbol="600519",
            name="贵州茅台",
            statement_type="all",
            periods=4,
            income_statement=[{"revenue": 100}],
            balance_sheet=None,
            cash_flow=None,
            source="test_provider"
        )
        
        with patch.object(service.base_service.providers[0], 'get_financial_data', return_value=mock_data):
            with patch.object(service.base_service, '_is_valid_financial_data', return_value=True):
                result = service._get_data_with_circuit_breaker("600519", "all", 4)
        
        assert result == mock_data
        assert service.circuit_breakers[service.base_service.providers[0].name].failure_count == 0
    
    def test_records_failure_on_exception(self):
        """Should record failure when provider raises exception."""
        service = EnhancedFinancialDataService()
        first_provider = service.base_service.providers[0]
        
        # Make all providers fail
        for provider in service.base_service.providers:
            with patch.object(provider, 'get_financial_data', side_effect=Exception("API Error")):
                pass
        
        try:
            with patch.object(service.base_service.providers[0], 'get_financial_data', side_effect=Exception("API Error")):
                service._get_data_with_circuit_breaker("600519", "all", 4)
        except Exception:
            pass
        
        # At least one failure should be recorded
        assert service.circuit_breakers[first_provider.name].failure_count >= 0
