"""Cache layer for data sources.

Provides TTL-based caching to avoid redundant API calls.
"""

import time
import json
import hashlib
import logging
from typing import Any, Optional, Dict

from domain.ports.datasource_ports import ICacheService

logger = logging.getLogger(__name__)

# Type alias for cached responses
DataSourceResponse = Any


class DataSourceCache(ICacheService):
    """TTL-based cache for data source responses.

    实现 ICacheService 接口

    Caches successful responses to reduce API calls and improve performance.

    Example:
        cache = DataSourceCache(ttl=60)

        key = cache.make_key('get_stock_info', symbol='600000.SH')
        cached = cache.get(key)
        if cached:
            return cached

        result = data_source.get_stock_info('600000.SH')
        cache.set(key, result)
    """

    def __init__(self, ttl: int = 60, max_size: int = 1000):
        """Initialize cache.

        Args:
            ttl: Time to live in seconds
            max_size: Maximum number of cached items
        """
        self.ttl = ttl
        self.max_size = max_size
        self._cache: Dict[str, tuple[DataSourceResponse, float]] = {}
        self._access_times: Dict[str, float] = {}

    def get(self, key: str) -> Optional[DataSourceResponse]:
        """Get cached response if not expired.

        Args:
            key: Cache key

        Returns:
            Cached DataSourceResponse or None if not found/expired
        """
        if key not in self._cache:
            return None

        response, timestamp = self._cache[key]

        # Check if expired
        if time.time() - timestamp >= self.ttl:
            logger.debug(f"Cache expired for key: {key[:50]}...")
            del self._cache[key]
            if key in self._access_times:
                del self._access_times[key]
            return None

        # Update access time for LRU
        self._access_times[key] = time.time()
        logger.debug(f"Cache hit for key: {key[:50]}...")
        return response

    def set(self, key: str, response: DataSourceResponse):
        """Cache a response.

        Args:
            key: Cache key
            response: DataSourceResponse to cache
        """
        # Only cache successful responses
        if not response.success:
            return

        # Evict oldest items if cache is full
        if len(self._cache) >= self.max_size:
            self._evict_oldest()

        self._cache[key] = (response, time.time())
        self._access_times[key] = time.time()
        logger.debug(f"Cached response for key: {key[:50]}...")

    def make_key(self, method: str, *args, **kwargs) -> str:
        """Generate cache key from method name and parameters.

        Args:
            method: Method name (e.g., 'get_stock_info')
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Cache key string
        """
        # Combine args and kwargs for consistent keys
        all_params = {'args': args, 'kwargs': kwargs}
        params_str = json.dumps(all_params, sort_keys=True, default=str)
        # Use hash for shorter keys
        params_hash = hashlib.md5(params_str.encode()).hexdigest()
        return f"{method}:{params_hash}"

    def invalidate(self, key: str):
        """Invalidate a specific cache entry.

        Args:
            key: Cache key to invalidate
        """
        if key in self._cache:
            del self._cache[key]
            logger.debug(f"Invalidated cache key: {key[:50]}...")
        if key in self._access_times:
            del self._access_times[key]

    def clear(self):
        """Clear all cached entries."""
        count = len(self._cache)
        self._cache.clear()
        self._access_times.clear()
        logger.info(f"Cleared {count} cache entries")

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dict with cache statistics
        """
        return {
            'size': len(self._cache),
            'max_size': self.max_size,
            'ttl': self.ttl,
            'utilization': len(self._cache) / self.max_size if self.max_size > 0 else 0
        }

    def _evict_oldest(self):
        """Evict the least recently accessed item."""
        if not self._access_times:
            return

        # Find oldest access time
        oldest_key = min(self._access_times, key=self._access_times.get)

        # Remove from both caches
        if oldest_key in self._cache:
            del self._cache[oldest_key]
        del self._access_times[oldest_key]

        logger.debug(f"Evicted oldest cache entry: {oldest_key[:50]}...")

    def cleanup_expired(self):
        """Remove all expired entries.

        Should be called periodically to prevent memory buildup.
        """
        now = time.time()
        expired_keys = [
            key for key, (_, timestamp) in self._cache.items()
            if now - timestamp >= self.ttl
        ]

        for key in expired_keys:
            del self._cache[key]
            if key in self._access_times:
                del self._access_times[key]

        if expired_keys:
            logger.info(f"Cleaned up {len(expired_keys)} expired cache entries")
