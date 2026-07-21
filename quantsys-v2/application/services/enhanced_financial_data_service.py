"""Enhanced Financial Data Service with caching and circuit breaker.

Wrapper around FinancialDataService that adds:
- Cache (5 min TTL by default)
- Circuit breaker (per provider)
- source parameter (auto/fresh/cache_only)
- Statistics tracking
"""

import structlog
from typing import Optional, Dict, Any
from application.services.financial_data_service import FinancialDataService
from application.services.financial_providers import FinancialData
from adapters.outbound.datasources.cache import DataSourceCache
from adapters.outbound.datasources.circuit_breaker import CircuitBreaker

logger = structlog.get_logger(__name__)


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

            # Update cache — wrap in minimal entry compatible with cache layer
            # (DataSourceResponse was removed; cache.set() expects .success attribute)
            class _CacheEntry:
                __slots__ = ('success', 'data')
                def __init__(self, d):
                    self.success = True
                    self.data = d
            self.cache.set(cache_key, _CacheEntry(data))
            logger.debug(f"Cached response: {cache_key}")

            return data
        except Exception as e:
            self.stats['failure_count'] += 1
            raise
    
    def was_cache_hit(self) -> bool:
        """Check if last request was a cache hit."""
        return self._last_cache_hit
    
    def get_stats(self) -> Dict[str, Any]:
        """Get service statistics."""
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
        """Reset statistics counters."""
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
    """Get global EnhancedFinancialDataService instance."""
    global _enhanced_service
    if _enhanced_service is None:
        _enhanced_service = EnhancedFinancialDataService()
    return _enhanced_service
