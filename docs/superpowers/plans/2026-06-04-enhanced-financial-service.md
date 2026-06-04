# Enhanced Financial Data Service Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add caching, circuit breaker, and source parameter to financial data service using wrapper pattern.

**Architecture:** Create `EnhancedFinancialDataService` wrapper around existing `FinancialDataService`. Integrate `DataSourceCache` (300s TTL) and `CircuitBreaker` (per provider). Add V2 API endpoints. Update TypeScript client and tool layer.

**Tech Stack:** Python (Flask), TypeScript, pytest, DataSourceCache, CircuitBreaker

---

## File Structure

### New Files
- `quantsys-v2/services/enhanced_financial_data_service.py` — Enhanced service with cache/circuit breaker
- `quantsys-v2/api/routes/financials_v2.py` — V2 API endpoints
- `quantsys-v2/tests/services/test_enhanced_financial_data_service.py` — Service unit tests
- `quantsys-v2/tests/api/test_financials_v2_routes.py` — API integration tests

### Modified Files
- `quantsys-v2/api/server.py` — Register financials_v2_bp blueprint
- `src/infrastructure/adapters/quant/quant-v2-client.ts` — Add source parameter
- `src/infrastructure/adapters/quant/types.ts` — Add source type
- `src/infrastructure/tools/data/fetch-financial-tool.ts` — Expose source parameter

---

## Task 1: Core Enhanced Service

**Files:**
- Create: `quantsys-v2/services/enhanced_financial_data_service.py`
- Test: `quantsys-v2/tests/services/test_enhanced_financial_data_service.py`

- [ ] **Step 1: Write failing test for basic initialization**

Create `quantsys-v2/tests/services/test_enhanced_financial_data_service.py`:

```python
import pytest
from services.enhanced_financial_data_service import EnhancedFinancialDataService
from services.financial_data_service import FinancialDataService


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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd quantsys-v2
python -m pytest tests/services/test_enhanced_financial_data_service.py::TestEnhancedFinancialDataServiceInit -v
```

Expected: `ModuleNotFoundError: No module named 'services.enhanced_financial_data_service'`

- [ ] **Step 3: Create enhanced service class with initialization**

Create `quantsys-v2/services/enhanced_financial_data_service.py`:

```python
"""Enhanced Financial Data Service with caching and circuit breaker.

Wrapper around FinancialDataService that adds:
- Cache (5 min TTL by default)
- Circuit breaker (per provider)
- source parameter (auto/fresh/cache_only)
- Statistics tracking
"""

import logging
from typing import Optional, Dict, Any
from services.financial_data_service import FinancialDataService
from services.financial_providers import FinancialData
from data_sources.cache import DataSourceCache
from data_sources.circuit_breaker import CircuitBreaker

logger = logging.getLogger(__name__)


class EnhancedFinancialDataService:
    """Enhanced financial data service with caching and circuit breaker.
    
    Features:
    - Cache (configurable TTL, default 300s)
    - Circuit breaker (per provider, failure_threshold=3, timeout=60s)
    - source parameter (auto/fresh/cache_only)
    - Statistics tracking
    """
    
    def __init__(
        self,
        base_service: Optional[FinancialDataService] = None,
        cache_ttl: int = 300,
        circuit_breaker_cooldown: int = 60
    ):
        """Initialize enhanced service.
        
        Args:
            base_service: Base financial data service (creates new if None)
            cache_ttl: Cache time-to-live in seconds (default: 300)
            circuit_breaker_cooldown: Circuit breaker timeout in seconds (default: 60)
        """
        self.base_service = base_service or FinancialDataService()
        self.cache = DataSourceCache(ttl=cache_ttl, max_size=1000)
        
        # Create circuit breaker for each provider
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        for provider in self.base_service.providers:
            self.circuit_breakers[provider.name] = CircuitBreaker(
                failure_threshold=3,
                timeout=circuit_breaker_cooldown
            )
        
        # Statistics
        self.stats = {
            'total_requests': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'success_count': 0,
            'failure_count': 0,
            'provider_stats': {
                provider.name: {'success': 0, 'failure': 0, 'skipped': 0}
                for provider in self.base_service.providers
            }
        }
        
        self._last_cache_hit = False
        
        logger.info(
            f"EnhancedFinancialDataService initialized: "
            f"cache_ttl={cache_ttl}s, "
            f"circuit_breaker_timeout={circuit_breaker_cooldown}s, "
            f"providers={[p.name for p in self.base_service.providers]}"
        )
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd quantsys-v2
python -m pytest tests/services/test_enhanced_financial_data_service.py::TestEnhancedFinancialDataServiceInit -v
```

Expected: All 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add quantsys-v2/services/enhanced_financial_data_service.py quantsys-v2/tests/services/test_enhanced_financial_data_service.py
git commit -m "feat(financial): add EnhancedFinancialDataService initialization

- Wrapper around FinancialDataService
- Integrates DataSourceCache (300s TTL)
- Creates CircuitBreaker per provider
- Initializes statistics tracking"
```

---

## Task 2: Cache Key Generation

**Files:**
- Modify: `quantsys-v2/services/enhanced_financial_data_service.py`
- Modify: `quantsys-v2/tests/services/test_enhanced_financial_data_service.py`

- [ ] **Step 1: Write failing test for cache key generation**

Append to `quantsys-v2/tests/services/test_enhanced_financial_data_service.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd quantsys-v2
python -m pytest tests/services/test_enhanced_financial_data_service.py::TestCacheKeyGeneration -v
```

Expected: `AttributeError: 'EnhancedFinancialDataService' object has no attribute '_make_cache_key'`

- [ ] **Step 3: Implement cache key generation**

Add to `quantsys-v2/services/enhanced_financial_data_service.py` after `__init__`:

```python
    def _make_cache_key(self, symbol: str, statement_type: str, periods: int) -> str:
        """Generate cache key.
        
        Format: financial:{symbol}:{statement_type}:{periods}
        
        Args:
            symbol: Stock symbol
            statement_type: Statement type (income/balance/cash_flow/all)
            periods: Number of periods
            
        Returns:
            Cache key string
            
        Example:
            >>> service._make_cache_key("600519", "all", 4)
            'financial:600519:all:4'
        """
        return f"financial:{symbol}:{statement_type}:{periods}"
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd quantsys-v2
python -m pytest tests/services/test_enhanced_financial_data_service.py::TestCacheKeyGeneration -v
```

Expected: All 2 tests PASS

- [ ] **Step 5: Commit**

```bash
git add quantsys-v2/services/enhanced_financial_data_service.py quantsys-v2/tests/services/test_enhanced_financial_data_service.py
git commit -m "feat(financial): add cache key generation

- Format: financial:{symbol}:{statement_type}:{periods}
- Unique key per parameter combination"
```

---

(继续在下一条消息...)

## Task 3: Circuit Breaker Integration

**Files:**
- Modify: `quantsys-v2/services/enhanced_financial_data_service.py`
- Modify: `quantsys-v2/tests/services/test_enhanced_financial_data_service.py`

- [ ] **Step 1: Write failing test for circuit breaker data fetching**

Append to `quantsys-v2/tests/services/test_enhanced_financial_data_service.py`:

```python
from unittest.mock import Mock, patch
from services.financial_providers import FinancialData


class TestCircuitBreakerIntegration:
    def test_fetches_from_first_available_provider(self):
        """Should fetch from first provider with closed circuit breaker."""
        service = EnhancedFinancialDataService()
        
        # Mock successful provider call
        mock_data = FinancialData(
            symbol="600519",
            statement_type="all",
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
    
    def test_skips_provider_with_open_circuit_breaker(self):
        """Should skip providers with open circuit breakers."""
        service = EnhancedFinancialDataService()
        
        # Open first provider's circuit breaker
        first_provider = service.base_service.providers[0]
        service.circuit_breakers[first_provider.name].failure_count = 3
        service.circuit_breakers[first_provider.name].state = service.circuit_breakers[first_provider.name].state.OPEN
        
        mock_data = FinancialData(
            symbol="600519",
            statement_type="all",
            income_statement=[{"revenue": 100}],
            balance_sheet=None,
            cash_flow=None,
            source=service.base_service.providers[1].name
        )
        
        with patch.object(service.base_service.providers[1], 'get_financial_data', return_value=mock_data):
            with patch.object(service.base_service, '_is_valid_financial_data', return_value=True):
                result = service._get_data_with_circuit_breaker("600519", "all", 4)
        
        assert result.source == service.base_service.providers[1].name
        assert service.stats['provider_stats'][first_provider.name]['skipped'] == 1
    
    def test_records_failure_on_exception(self):
        """Should record failure when provider raises exception."""
        service = EnhancedFinancialDataService()
        first_provider = service.base_service.providers[0]
        
        with patch.object(first_provider, 'get_financial_data', side_effect=Exception("API Error")):
            with pytest.raises(Exception):
                service._get_data_with_circuit_breaker("600519", "all", 4)
        
        assert service.circuit_breakers[first_provider.name].failure_count > 0
        assert service.stats['provider_stats'][first_provider.name]['failure'] > 0
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd quantsys-v2
python -m pytest tests/services/test_enhanced_financial_data_service.py::TestCircuitBreakerIntegration -v
```

Expected: `AttributeError: 'EnhancedFinancialDataService' object has no attribute '_get_data_with_circuit_breaker'`

- [ ] **Step 3: Implement circuit breaker data fetching**

Add to `quantsys-v2/services/enhanced_financial_data_service.py` after `_make_cache_key`:

```python
    def _get_data_with_circuit_breaker(
        self,
        symbol: str,
        statement_type: str,
        periods: int
    ) -> FinancialData:
        """Fetch data with circuit breaker protection.
        
        Args:
            symbol: Stock symbol
            statement_type: Statement type
            periods: Number of periods
            
        Returns:
            FinancialData object
            
        Raises:
            Exception: If all providers fail
        """
        # Get available providers (circuit breaker not open)
        available_providers = []
        for provider in self.base_service.providers:
            if self.circuit_breakers[provider.name].is_available():
                available_providers.append(provider)
            else:
                self.stats['provider_stats'][provider.name]['skipped'] += 1
                logger.debug(f"Skipping {provider.name} (circuit breaker open)")
        
        if not available_providers:
            error_msg = "所有数据源熔断器都已打开"
            logger.error(error_msg)
            raise Exception(error_msg)
        
        # Try each available provider
        errors = []
        for provider in available_providers:
            try:
                logger.debug(f"Trying provider {provider.name} for {symbol}")
                data = provider.get_financial_data(symbol, statement_type, periods)
                
                # Validate data
                if self.base_service._is_valid_financial_data(data):
                    # Success - record it
                    self.circuit_breakers[provider.name].record_success()
                    self.stats['provider_stats'][provider.name]['success'] += 1
                    logger.info(f"Successfully fetched from {provider.name}")
                    return data
                else:
                    # Invalid data - treat as failure
                    self.circuit_breakers[provider.name].record_failure()
                    self.stats['provider_stats'][provider.name]['failure'] += 1
                    errors.append(f"{provider.name}: invalid data")
                    logger.warning(f"Invalid data from {provider.name}")
                    
            except Exception as e:
                # Exception - record failure
                self.circuit_breakers[provider.name].record_failure()
                self.stats['provider_stats'][provider.name]['failure'] += 1
                errors.append(f"{provider.name}: {str(e)}")
                logger.warning(f"Provider {provider.name} failed: {e}")
        
        # All providers failed
        error_msg = f"所有数据源都失败: {'; '.join(errors)}"
        logger.error(error_msg)
        raise Exception(error_msg)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd quantsys-v2
python -m pytest tests/services/test_enhanced_financial_data_service.py::TestCircuitBreakerIntegration -v
```

Expected: All 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add quantsys-v2/services/enhanced_financial_data_service.py quantsys-v2/tests/services/test_enhanced_financial_data_service.py
git commit -m "feat(financial): add circuit breaker protected data fetching

- Skip providers with open circuit breakers
- Record success/failure for each provider
- Track provider statistics"
```

---

## Task 4: Main get_financial_data Method with source Parameter

**Files:**
- Modify: `quantsys-v2/services/enhanced_financial_data_service.py`
- Modify: `quantsys-v2/tests/services/test_enhanced_financial_data_service.py`

- [ ] **Step 1: Write failing tests for source parameter behavior**

Append to `quantsys-v2/tests/services/test_enhanced_financial_data_service.py`:

```python
class TestGetFinancialData:
    def test_auto_mode_uses_cache_on_second_request(self):
        """auto mode should return cached data on second request."""
        service = EnhancedFinancialDataService()
        
        mock_data = FinancialData(
            symbol="600519",
            statement_type="all",
            income_statement=[{"revenue": 100}],
            balance_sheet=None,
            cash_flow=None,
            source="test"
        )
        
        with patch.object(service, '_get_data_with_circuit_breaker', return_value=mock_data):
            # First request - miss cache
            result1 = service.get_financial_data("600519", "all", 4, source="auto")
            # Second request - hit cache
            result2 = service.get_financial_data("600519", "all", 4, source="auto")
        
        assert service.stats['total_requests'] == 2
        assert service.stats['cache_hits'] == 1
        assert service.stats['cache_misses'] == 1
    
    def test_fresh_mode_bypasses_cache(self):
        """fresh mode should always call data source."""
        service = EnhancedFinancialDataService()
        
        mock_data = FinancialData(
            symbol="600519",
            statement_type="all",
            income_statement=[{"revenue": 100}],
            balance_sheet=None,
            cash_flow=None,
            source="test"
        )
        
        with patch.object(service, '_get_data_with_circuit_breaker', return_value=mock_data) as mock_fetch:
            service.get_financial_data("600519", "all", 4, source="fresh")
            service.get_financial_data("600519", "all", 4, source="fresh")
        
        assert mock_fetch.call_count == 2  # Called both times
        assert service.stats['cache_hits'] == 0
    
    def test_cache_only_mode_fails_on_miss(self):
        """cache_only mode should raise error if cache miss."""
        service = EnhancedFinancialDataService()
        
        with pytest.raises(Exception, match="缓存未命中"):
            service.get_financial_data("600519", "all", 4, source="cache_only")
    
    def test_cache_only_mode_succeeds_on_hit(self):
        """cache_only mode should return cached data if available."""
        service = EnhancedFinancialDataService()
        
        mock_data = FinancialData(
            symbol="600519",
            statement_type="all",
            income_statement=[{"revenue": 100}],
            balance_sheet=None,
            cash_flow=None,
            source="test"
        )
        
        with patch.object(service, '_get_data_with_circuit_breaker', return_value=mock_data):
            # First request to populate cache
            service.get_financial_data("600519", "all", 4, source="auto")
            
            # Second request with cache_only
            result = service.get_financial_data("600519", "all", 4, source="cache_only")
        
        assert result == mock_data
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd quantsys-v2
python -m pytest tests/services/test_enhanced_financial_data_service.py::TestGetFinancialData -v
```

Expected: `AttributeError: 'EnhancedFinancialDataService' object has no attribute 'get_financial_data'`

- [ ] **Step 3: Implement get_financial_data method**

Add to `quantsys-v2/services/enhanced_financial_data_service.py` after `_get_data_with_circuit_breaker`:

```python
    def get_financial_data(
        self,
        symbol: str,
        statement_type: str = 'all',
        periods: int = 4,
        source: str = 'auto'
    ) -> FinancialData:
        """Get financial data with caching and circuit breaker.
        
        Args:
            symbol: Stock symbol
            statement_type: Statement type (income/balance/cash_flow/all)
            periods: Number of periods
            source: Data source strategy
                - 'auto' (default): Cache first, then data source on miss
                - 'fresh': Skip cache, always fetch from data source
                - 'cache_only': Only return cached data, error on miss
                
        Returns:
            FinancialData object
            
        Raises:
            Exception: If data unavailable (cache_only miss or all providers fail)
        """
        self.stats['total_requests'] += 1
        cache_key = self._make_cache_key(symbol, statement_type, periods)
        
        # cache_only mode - only check cache
        if source == 'cache_only':
            cached = self.cache.get(cache_key)
            if cached:
                self.stats['cache_hits'] += 1
                self._last_cache_hit = True
                logger.debug(f"Cache hit (cache_only): {cache_key}")
                return cached.data if hasattr(cached, 'data') else cached
            else:
                self.stats['cache_misses'] += 1
                self._last_cache_hit = False
                raise Exception(
                    f"缓存未命中: {symbol} ({statement_type}). "
                    "使用 source='auto' 或 'fresh' 以调用数据源"
                )
        
        # auto mode - check cache first
        if source == 'auto':
            cached = self.cache.get(cache_key)
            if cached:
                self.stats['cache_hits'] += 1
                self._last_cache_hit = True
                logger.debug(f"Cache hit: {cache_key}")
                return cached.data if hasattr(cached, 'data') else cached
            self.stats['cache_misses'] += 1
            logger.debug(f"Cache miss: {cache_key}")
        
        # fresh mode or auto cache miss - fetch from data source
        self._last_cache_hit = False
        try:
            data = self._get_data_with_circuit_breaker(symbol, statement_type, periods)
            self.stats['success_count'] += 1
            
            # Update cache
            from data_sources.base import DataSourceResponse
            cache_value = DataSourceResponse.success_response(data)
            self.cache.set(cache_key, cache_value)
            logger.debug(f"Cached response: {cache_key}")
            
            return data
        except Exception as e:
            self.stats['failure_count'] += 1
            raise
    
    def was_cache_hit(self) -> bool:
        """Check if last request was a cache hit.
        
        Returns:
            True if last request hit cache, False otherwise
        """
        return self._last_cache_hit
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd quantsys-v2
python -m pytest tests/services/test_enhanced_financial_data_service.py::TestGetFinancialData -v
```

Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add quantsys-v2/services/enhanced_financial_data_service.py quantsys-v2/tests/services/test_enhanced_financial_data_service.py
git commit -m "feat(financial): implement get_financial_data with source parameter

- auto mode: cache first, fetch on miss
- fresh mode: always fetch, update cache
- cache_only mode: return cache or error
- Track cache hits/misses"
```

---


## Task 5: Statistics and Management Methods

**Files:**
- Modify: `quantsys-v2/services/enhanced_financial_data_service.py`
- Modify: `quantsys-v2/tests/services/test_enhanced_financial_data_service.py`

- [ ] **Step 1: Write failing tests for statistics methods**

Append to `quantsys-v2/tests/services/test_enhanced_financial_data_service.py`:

```python
class TestStatisticsAndManagement:
    def test_get_stats_returns_complete_stats(self):
        """Should return all statistics including cache and circuit breaker status."""
        service = EnhancedFinancialDataService()
        
        stats = service.get_stats()
        
        assert 'total_requests' in stats
        assert 'cache_hits' in stats
        assert 'cache_hit_rate' in stats
        assert 'success_count' in stats
        assert 'provider_stats' in stats
        assert 'circuit_breaker_status' in stats
        assert 'cache_stats' in stats
    
    def test_clear_cache_empties_cache(self):
        """Should clear all cached entries."""
        service = EnhancedFinancialDataService()
        
        # Populate cache
        mock_data = FinancialData(symbol="600519", statement_type="all", 
                                   income_statement=[{"revenue": 100}],
                                   balance_sheet=None, cash_flow=None, source="test")
        with patch.object(service, '_get_data_with_circuit_breaker', return_value=mock_data):
            service.get_financial_data("600519", "all", 4)
        
        assert service.stats['cache_hits'] + service.stats['cache_misses'] > 0
        
        service.clear_cache()
        
        # Cache should be empty now
        stats = service.get_stats()
        assert stats['cache_stats']['size'] == 0
    
    def test_reset_stats_clears_counters(self):
        """Should reset all statistics counters."""
        service = EnhancedFinancialDataService()
        
        # Generate some stats
        mock_data = FinancialData(symbol="600519", statement_type="all",
                                   income_statement=[{"revenue": 100}],
                                   balance_sheet=None, cash_flow=None, source="test")
        with patch.object(service, '_get_data_with_circuit_breaker', return_value=mock_data):
            service.get_financial_data("600519", "all", 4)
        
        assert service.stats['total_requests'] > 0
        
        service.reset_stats()
        
        assert service.stats['total_requests'] == 0
        assert service.stats['cache_hits'] == 0
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd quantsys-v2
python -m pytest tests/services/test_enhanced_financial_data_service.py::TestStatisticsAndManagement -v
```

Expected: `AttributeError: 'EnhancedFinancialDataService' object has no attribute 'get_stats'`

- [ ] **Step 3: Implement statistics and management methods**

Add to `quantsys-v2/services/enhanced_financial_data_service.py` after `was_cache_hit`:

```python
    def get_stats(self) -> Dict[str, Any]:
        """Get service statistics.
        
        Returns:
            Dict with statistics including:
                - total_requests, cache_hits, cache_misses, cache_hit_rate
                - success_count, failure_count, success_rate
                - provider_stats (per provider)
                - circuit_breaker_status
                - cache_stats
        """
        total = self.stats['total_requests']
        cache_hit_rate = (
            self.stats['cache_hits'] / total * 100
            if total > 0
            else 0.0
        )
        success_rate = (
            self.stats['success_count'] / total * 100
            if total > 0
            else 0.0
        )
        
        return {
            'total_requests': self.stats['total_requests'],
            'cache_hits': self.stats['cache_hits'],
            'cache_misses': self.stats['cache_misses'],
            'cache_hit_rate': f"{cache_hit_rate:.2f}%",
            'success_count': self.stats['success_count'],
            'failure_count': self.stats['failure_count'],
            'success_rate': f"{success_rate:.2f}%",
            'provider_stats': self.stats['provider_stats'],
            'circuit_breaker_status': {
                name: breaker.get_state()
                for name, breaker in self.circuit_breakers.items()
            },
            'cache_stats': self.cache.get_stats()
        }
    
    def clear_cache(self):
        """Clear all cached entries."""
        self.cache.clear()
        logger.info("Cache cleared")
    
    def reset_stats(self):
        """Reset statistics counters.
        
        Note: Does not reset cache or circuit breaker state.
        """
        self.stats['total_requests'] = 0
        self.stats['cache_hits'] = 0
        self.stats['cache_misses'] = 0
        self.stats['success_count'] = 0
        self.stats['failure_count'] = 0
        
        for provider_name in self.stats['provider_stats']:
            self.stats['provider_stats'][provider_name] = {
                'success': 0,
                'failure': 0,
                'skipped': 0
            }
        
        logger.info("Statistics reset")
    
    def reset_circuit_breakers(self):
        """Manually reset all circuit breakers to CLOSED state."""
        for breaker in self.circuit_breakers.values():
            breaker.reset()
        logger.info("All circuit breakers reset")


# Global instance
_enhanced_service: Optional[EnhancedFinancialDataService] = None


def get_enhanced_financial_service() -> EnhancedFinancialDataService:
    """Get global EnhancedFinancialDataService instance.
    
    Returns:
        EnhancedFinancialDataService singleton
    """
    global _enhanced_service
    if _enhanced_service is None:
        _enhanced_service = EnhancedFinancialDataService()
    return _enhanced_service
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd quantsys-v2
python -m pytest tests/services/test_enhanced_financial_data_service.py::TestStatisticsAndManagement -v
```

Expected: All 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add quantsys-v2/services/enhanced_financial_data_service.py quantsys-v2/tests/services/test_enhanced_financial_data_service.py
git commit -m "feat(financial): add statistics and management methods

- get_stats(): return complete statistics
- clear_cache(): empty all cached entries
- reset_stats(): reset counters
- reset_circuit_breakers(): manually reset breakers
- get_enhanced_financial_service(): global singleton"
```

---

## Task 6: V2 API Routes

**Files:**
- Create: `quantsys-v2/api/routes/financials_v2.py`
- Test: `quantsys-v2/tests/api/test_financials_v2_routes.py`

- [ ] **Step 1: Write failing test for main endpoint**

Create `quantsys-v2/tests/api/test_financials_v2_routes.py`:

```python
import pytest
from flask import Flask
from api.routes.financials_v2 import financials_v2_bp
from unittest.mock import patch, Mock
from services.financial_providers import FinancialData


@pytest.fixture
def client():
    """Create test client."""
    app = Flask(__name__)
    app.register_blueprint(financials_v2_bp)
    app.config['TESTING'] = True
    return app.test_client()


class TestFinancialsV2Routes:
    def test_get_financial_data_auto_mode(self, client):
        """Should return financial data with auto mode (default)."""
        mock_data = FinancialData(
            symbol="600519",
            statement_type="all",
            income_statement=[{"revenue": 100}],
            balance_sheet=None,
            cash_flow=None,
            source="test"
        )
        
        with patch('api.routes.financials_v2.get_enhanced_financial_service') as mock_get_service:
            mock_service = Mock()
            mock_service.get_financial_data.return_value = mock_data
            mock_service.was_cache_hit.return_value = False
            mock_get_service.return_value = mock_service
            
            response = client.get('/api/v2/stock/600519/financials')
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert 'data' in data
        assert data['cached'] is False
    
    def test_get_financial_data_with_source_parameter(self, client):
        """Should respect source parameter."""
        mock_data = FinancialData(
            symbol="600519",
            statement_type="all",
            income_statement=[{"revenue": 100}],
            balance_sheet=None,
            cash_flow=None,
            source="test"
        )
        
        with patch('api.routes.financials_v2.get_enhanced_financial_service') as mock_get_service:
            mock_service = Mock()
            mock_service.get_financial_data.return_value = mock_data
            mock_service.was_cache_hit.return_value = False
            mock_get_service.return_value = mock_service
            
            response = client.get('/api/v2/stock/600519/financials?source=fresh')
        
        mock_service.get_financial_data.assert_called_once_with('600519', 'all', 4, 'fresh')
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd quantsys-v2
python -m pytest tests/api/test_financials_v2_routes.py::TestFinancialsV2Routes -v
```

Expected: `ModuleNotFoundError: No module named 'api.routes.financials_v2'`

- [ ] **Step 3: Create V2 API routes**

Create `quantsys-v2/api/routes/financials_v2.py`:

```python
"""Financial Data V2 API Routes.

Enhanced financial data endpoints with caching and circuit breaker.
"""

import logging
from flask import Blueprint, jsonify, request
from api.shared import api_response, handle_api_error
from services.enhanced_financial_data_service import get_enhanced_financial_service

logger = logging.getLogger(__name__)

financials_v2_bp = Blueprint('financials_v2', __name__)


@financials_v2_bp.route('/api/v2/stock/<symbol>/financials', methods=['GET'])
@handle_api_error
def get_financial_data_v2(symbol):
    """Get financial data V2 with caching and circuit breaker.
    
    Query Parameters:
        statement_type: income/balance/cash_flow/all (default: all)
        periods: number of periods (default: 4)
        source: auto/fresh/cache_only (default: auto)
    
    Response:
        {
            "success": true,
            "data": {...},
            "cached": true,
            "source": "sina_web"
        }
    """
    statement_type = request.args.get('statement_type', 'all')
    periods = int(request.args.get('periods', 4))
    source = request.args.get('source', 'auto')
    
    # Validate source parameter
    if source not in ('auto', 'fresh', 'cache_only'):
        return jsonify({
            'success': False,
            'error': f"Invalid source parameter: {source}. Must be auto/fresh/cache_only"
        }), 400
    
    service = get_enhanced_financial_service()
    data = service.get_financial_data(symbol, statement_type, periods, source)
    
    return api_response({
        'data': data.to_dict() if hasattr(data, 'to_dict') else data.__dict__,
        'cached': service.was_cache_hit(),
        'source': data.source if hasattr(data, 'source') else 'unknown'
    })


@financials_v2_bp.route('/api/v2/financials/stats', methods=['GET'])
@handle_api_error
def get_stats():
    """Get service statistics.
    
    Response:
        {
            "success": true,
            "stats": {
                "total_requests": 100,
                "cache_hits": 70,
                "cache_hit_rate": "70.0%",
                ...
            }
        }
    """
    service = get_enhanced_financial_service()
    stats = service.get_stats()
    
    return api_response({'stats': stats})


@financials_v2_bp.route('/api/v2/financials/cache/clear', methods=['POST'])
@handle_api_error
def clear_cache():
    """Clear cache.
    
    Response:
        {
            "success": true,
            "message": "缓存已清空"
        }
    """
    service = get_enhanced_financial_service()
    service.clear_cache()
    
    return api_response({'message': '缓存已清空'})


@financials_v2_bp.route('/api/v2/financials/stats/reset', methods=['POST'])
@handle_api_error
def reset_stats():
    """Reset statistics (keep cache and circuit breaker state).
    
    Response:
        {
            "success": true,
            "message": "统计信息已重置"
        }
    """
    service = get_enhanced_financial_service()
    service.reset_stats()
    
    return api_response({'message': '统计信息已重置'})
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd quantsys-v2
python -m pytest tests/api/test_financials_v2_routes.py::TestFinancialsV2Routes -v
```

Expected: All 2 tests PASS

- [ ] **Step 5: Commit**

```bash
git add quantsys-v2/api/routes/financials_v2.py quantsys-v2/tests/api/test_financials_v2_routes.py
git commit -m "feat(financial): add V2 API routes

- GET /api/v2/stock/<symbol>/financials
- GET /api/v2/financials/stats
- POST /api/v2/financials/cache/clear
- POST /api/v2/financials/stats/reset"
```

---


## Task 7: Register V2 Blueprint in Server

**Files:**
- Modify: `quantsys-v2/api/server.py`

- [ ] **Step 1: Locate blueprint registration section**

```bash
cd quantsys-v2
grep -n "register_blueprint" api/server.py | head -5
```

Expected: See existing blueprint registrations

- [ ] **Step 2: Add financials_v2_bp import and registration**

Edit `quantsys-v2/api/server.py`, add import after existing route imports:

```python
from api.routes.financials_v2 import financials_v2_bp
```

Add registration after existing blueprint registrations:

```python
app.register_blueprint(financials_v2_bp)
```

- [ ] **Step 3: Verify server starts successfully**

```bash
cd quantsys-v2
python api/server.py &
sleep 3
curl http://127.0.0.1:5001/api/v2/financials/stats
pkill -f "python api/server.py"
```

Expected: Server starts, stats endpoint returns JSON, server stops cleanly

- [ ] **Step 4: Commit**

```bash
git add quantsys-v2/api/server.py
git commit -m "feat(financial): register financials_v2_bp in server

- Import financials_v2_bp
- Register blueprint with Flask app"
```

---

## Task 8: TypeScript Client Integration

**Files:**
- Modify: `src/infrastructure/adapters/quant/quant-v2-client.ts`
- Modify: `src/infrastructure/adapters/quant/types.ts`

- [ ] **Step 1: Add source type to types.ts**

Edit `src/infrastructure/adapters/quant/types.ts`, add after existing type definitions:

```typescript
/**
 * Data source strategy for financial data queries
 */
export type FinancialDataSource = 'auto' | 'fresh' | 'cache_only';
```

- [ ] **Step 2: Update getFinancials signature in quant-v2-client.ts**

Find the `getFinancials` function in `src/infrastructure/adapters/quant/quant-v2-client.ts` and replace it:

```typescript
/**
 * Get financial statements data from quantsys-v2 API (V2 endpoint with caching)
 */
export async function getFinancials(
  symbol: string,
  reportType?: 'income' | 'balance' | 'cash_flow' | 'all',
  periods: number = 4,
  source: FinancialDataSource = 'auto'
): Promise<FinancialData> {
  const url = `${V2_API_BASE}/api/v2/stock/${symbol}/financials`;
  const params = new URLSearchParams({
    statement_type: reportType || 'all',
    periods: periods.toString(),
    source
  });

  const response = await fetch(`${url}?${params}`, {
    signal: AbortSignal.timeout(V2_TIMEOUT_MS)
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new QuantV2Error(
      `财务数据查询失败 (${response.status}): ${errorText}`,
      response.status
    );
  }

  const result = await response.json();
  
  if (!result.success) {
    throw new QuantV2Error(result.error || '财务数据查询失败');
  }
  
  return result.data;
}
```

- [ ] **Step 3: Update V2_ROUTES mapping**

In the same file, update the financial route mapping comment:

```typescript
  // ── financial ──
  "financial.statements":   { path: "/api/v2/stock/{symbol}/financials", method: "GET" },  // V2 enhanced
  "financial.indicators":   { path: "/api/stock/{symbol}/financial-indicators", method: "GET" },
  "financial.valuation":    { path: "/api/stock/{symbol}/valuation", method: "GET" },
  "financial.pe_percentile":{ path: "/api/stock/{symbol}/pe-percentile", method: "GET" },
```

- [ ] **Step 4: Build TypeScript to verify no errors**

```bash
npm run build
```

Expected: Build succeeds with no TypeScript errors

- [ ] **Step 5: Commit**

```bash
git add src/infrastructure/adapters/quant/quant-v2-client.ts src/infrastructure/adapters/quant/types.ts
git commit -m "feat(financial): update TypeScript client for V2 API

- Add FinancialDataSource type
- Update getFinancials() to call V2 endpoint
- Add source parameter support (auto/fresh/cache_only)
- Update route mapping"
```

---

## Task 9: Tool Layer Integration

**Files:**
- Modify: `src/infrastructure/tools/data/fetch-financial-tool.ts`

- [ ] **Step 1: Add source parameter to tool definition**

Edit `src/infrastructure/tools/data/fetch-financial-tool.ts`, update parameters object:

```typescript
parameters: Type.Object({
  symbol: Type.String({
    description: "股票代码：A股6位数字（如 600519）"
  }),
  dataType: Type.Optional(Type.Union([
    Type.Literal("statements"),
    Type.Literal("indicators"),
    Type.Literal("valuation"),
    Type.Literal("pe_percentile"),
    Type.Literal("all")
  ], {
    description: "数据类型：statements=财务报表, indicators=财务指标, valuation=估值指标, pe_percentile=PE分位数, all=全部数据。默认: statements"
  })),
  reportType: Type.Optional(Type.Union([
    Type.Literal("income"),
    Type.Literal("balance"),
    Type.Literal("cashflow"),
    Type.Literal("all")
  ], {
    description: "报表类型（仅dataType=statements时生效）：income=利润表, balance=资产负债表, cashflow=现金流量表, all=全部。默认: all"
  })),
  periods: Type.Optional(Type.Integer({
    description: "报表期数（默认4期）",
    minimum: 1,
    maximum: 20
  })),
  years: Type.Optional(Type.Integer({
    description: "PE分位数年限（默认3年）",
    minimum: 1,
    maximum: 10
  })),
  source: Type.Optional(Type.Union([
    Type.Literal("auto"),
    Type.Literal("fresh"),
    Type.Literal("cache_only")
  ], {
    description: "数据源策略：auto=缓存优先（默认），fresh=强制刷新，cache_only=仅缓存"
  }))
}),
```

- [ ] **Step 2: Update execute function to pass source parameter**

Update the execute function in the same file:

```typescript
execute: async (_toolCallId, params: {
  symbol: string;
  dataType?: string;
  reportType?: string;
  periods?: number;
  years?: number;
  source?: 'auto' | 'fresh' | 'cache_only';
}) => {
  const { symbol, dataType = 'statements', reportType = 'all', periods = 4, years = 3, source = 'auto' } = params;

  // 验证A股代码
  const validationError = requireAshare(symbol);
  if (validationError) {
    return {
      content: [{
        type: "text" as const,
        text: validationError
      }],
      details: undefined
    };
  }

  try {
    const results: string[] = [];
    let hasError = false;

    // 1. 财务报表数据
    if (dataType === 'statements' || dataType === 'all') {
      try {
        const mappedReportType = reportType === 'cashflow' ? 'cash_flow' : reportType;
        const data = await getFinancials(
          symbol,
          mappedReportType as 'income' | 'balance' | 'cash_flow' | 'all' | undefined,
          periods,
          source  // Pass source parameter
        );
        results.push(formatFinancialData(data));
      } catch (error) {
        hasError = true;
        results.push(`【财务报表】\n⚠️ 暂时不可用: ${error instanceof Error ? error.message : String(error)}`);
      }
    }

    // Rest of the function remains the same...
    // (indicators, valuation, pe_percentile sections don't use source parameter yet)
```

- [ ] **Step 3: Update tool description**

Update the description at the top of the file:

```typescript
description:
  "L1 数据管道工具：统一的财务数据查询入口。" +
  "支持获取：(1) 原始财务报表（利润表、资产负债表、现金流量表）" +
  "(2) 财务指标（ROE、净利润等）" +
  "(3) 估值指标（PE、PB等）" +
  "(4) PE历史分位数。" +
  "智能容错：某个数据源失败时不影响其他数据。" +
  "缓存控制：通过source参数控制缓存策略（auto=缓存优先，fresh=强制刷新，cache_only=仅缓存）。" +
  "仅支持A股（6位数字代码）。",
```

- [ ] **Step 4: Build TypeScript to verify**

```bash
npm run build
```

Expected: Build succeeds

- [ ] **Step 5: Commit**

```bash
git add src/infrastructure/tools/data/fetch-financial-tool.ts
git commit -m "feat(financial): expose source parameter in tool layer

- Add source parameter to data_fetch_financial tool
- Pass source to getFinancials() client call
- Update tool description with caching info"
```

---

## Task 10: Integration Test and Validation

**Files:**
- Create: `docs/testing/enhanced-financial-data-e2e-test.md`

- [ ] **Step 1: Create E2E test documentation**

Create `docs/testing/enhanced-financial-data-e2e-test.md`:

```markdown
# Enhanced Financial Data Service E2E Test

## Test Environment

- quantsys-v2 server running on http://127.0.0.1:5001
- TypeScript agent with updated client
- Test stock: 600519 (贵州茅台)

## Test Scenario 1: Basic V2 API Flow

### 1.1 Start quantsys-v2 server

```bash
cd quantsys-v2
python start_all.py &
sleep 5
```

### 1.2 Test auto mode (cache miss then hit)

```bash
# First request - cache miss
curl -X GET "http://127.0.0.1:5001/api/v2/stock/600519/financials?source=auto" | jq '.cached'
# Expected: false

# Second request - cache hit
curl -X GET "http://127.0.0.1:5001/api/v2/stock/600519/financials?source=auto" | jq '.cached'
# Expected: true
```

### 1.3 Test fresh mode (bypass cache)

```bash
curl -X GET "http://127.0.0.1:5001/api/v2/stock/600519/financials?source=fresh" | jq '.cached'
# Expected: false (always)
```

### 1.4 Test cache_only mode

```bash
# With warm cache - should succeed
curl -X GET "http://127.0.0.1:5001/api/v2/stock/600519/financials?source=cache_only"
# Expected: 200 OK

# Clear cache
curl -X POST "http://127.0.0.1:5001/api/v2/financials/cache/clear"

# With cold cache - should fail
curl -X GET "http://127.0.0.1:5001/api/v2/stock/600519/financials?source=cache_only"
# Expected: 500 error with "缓存未命中"
```

### 1.5 Check statistics

```bash
curl -X GET "http://127.0.0.1:5001/api/v2/financials/stats" | jq '.stats'
# Expected: total_requests, cache_hits, cache_hit_rate, provider_stats, etc.
```

## Test Scenario 2: TypeScript Agent Integration

### 2.1 Test via Agent tool

Start TypeScript agent:
```bash
npm run dev
```

Use tool:
```typescript
data_fetch_financial({
  symbol: "600519",
  dataType: "statements",
  source: "auto"
})
```

Expected: Returns financial data, second call hits cache

### 2.2 Test fresh mode

```typescript
data_fetch_financial({
  symbol: "600519",
  dataType: "statements",
  source: "fresh"
})
```

Expected: Always fetches fresh data

## Test Scenario 3: Circuit Breaker Behavior

### 3.1 Simulate provider failures

Stop quantsys-v2 temporarily:
```bash
pkill -f "python api/server.py"
```

Make requests:
```bash
for i in {1..5}; do
  curl -X GET "http://127.0.0.1:5001/api/v2/stock/600519/financials"
  sleep 1
done
```

Expected: Circuit breakers open after 3 failures

### 3.2 Restart and verify recovery

```bash
cd quantsys-v2
python api/server.py &
sleep 65  # Wait for circuit breaker timeout (60s)

curl -X GET "http://127.0.0.1:5001/api/v2/stock/600519/financials"
```

Expected: Circuit breaker half-open, request succeeds, breaker closes

## Success Criteria

✅ V2 API endpoints respond correctly
✅ Cache hit on second request with auto mode
✅ Fresh mode bypasses cache
✅ cache_only mode works as expected
✅ Statistics tracking is accurate
✅ TypeScript agent can use source parameter
✅ Circuit breaker opens after failures and recovers
✅ No regressions in existing functionality
```

- [ ] **Step 2: Run manual E2E test**

Follow the test document step by step and verify all scenarios pass.

- [ ] **Step 3: Document test results**

Append results to the E2E test document:

```markdown
## Test Results (YYYY-MM-DD)

- Scenario 1: ✅ All tests passed
- Scenario 2: ✅ TypeScript integration works
- Scenario 3: ✅ Circuit breaker behavior correct

Notes: [any observations]
```

- [ ] **Step 4: Commit E2E test documentation**

```bash
git add docs/testing/enhanced-financial-data-e2e-test.md
git commit -m "docs: add E2E test documentation for enhanced financial service

- Test scenarios for V2 API
- TypeScript agent integration tests
- Circuit breaker behavior tests"
```

---

## Self-Review Checklist

- [x] **Spec coverage check:**
  - ✅ EnhancedFinancialDataService with cache/circuit breaker (Tasks 1-5)
  - ✅ V2 API endpoints (Task 6-7)
  - ✅ TypeScript client integration (Task 8)
  - ✅ Tool layer integration (Task 9)
  - ✅ Testing and validation (Task 10)

- [x] **Placeholder scan:**
  - No TBD, TODO, or "fill in details"
  - All code blocks contain actual implementation
  - All commands have expected output

- [x] **Type consistency:**
  - FinancialData type used consistently
  - source parameter: 'auto' | 'fresh' | 'cache_only' everywhere
  - Cache key format consistent: "financial:{symbol}:{statement_type}:{periods}"

- [x] **No gaps:**
  - All methods in design spec are implemented
  - All test categories covered (unit, integration, E2E)
  - All files in "File Changes" section have corresponding tasks

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-06-04-enhanced-financial-service.md`. 

Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
