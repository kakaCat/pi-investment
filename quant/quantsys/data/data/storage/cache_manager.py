"""Cache manager for stock data.

This module provides in-memory caching for frequently accessed stock data
to reduce database queries and improve performance.
"""

from __future__ import annotations

import time
from typing import Any, Optional

import pandas as pd


class CacheManager:
    """Manage in-memory cache for stock data.

    Uses a simple LRU-like cache with TTL (time-to-live) for each entry.
    """

    def __init__(
        self,
        max_size: int = 1000,
        default_ttl: int = 300,
    ):
        """Initialize cache manager.

        Args:
            max_size: Maximum number of cache entries
            default_ttl: Default time-to-live in seconds
        """
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._cache: dict[str, dict] = {}
        self._access_times: dict[str, float] = {}

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value, or None if not found or expired
        """
        if key not in self._cache:
            return None

        entry = self._cache[key]
        now = time.time()

        # Check if expired
        if now - entry["timestamp"] > entry["ttl"]:
            self._remove(key)
            return None

        # Update access time
        self._access_times[key] = now
        return entry["value"]

    def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
    ) -> None:
        """Set value in cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live in seconds (uses default if None)
        """
        # Evict if cache is full
        if len(self._cache) >= self.max_size and key not in self._cache:
            self._evict_lru()

        now = time.time()
        self._cache[key] = {
            "value": value,
            "timestamp": now,
            "ttl": ttl if ttl is not None else self.default_ttl,
        }
        self._access_times[key] = now

    def delete(self, key: str) -> bool:
        """Delete entry from cache.

        Args:
            key: Cache key

        Returns:
            True if deleted, False if not found
        """
        if key in self._cache:
            self._remove(key)
            return True
        return False

    def clear(self) -> None:
        """Clear all cache entries."""
        self._cache.clear()
        self._access_times.clear()

    def get_klines(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Optional[pd.DataFrame]:
        """Get K-line data from cache.

        Args:
            symbol: Stock symbol
            start_date: Start date
            end_date: End date

        Returns:
            DataFrame if found in cache, None otherwise
        """
        key = self._make_klines_key(symbol, start_date, end_date)
        return self.get(key)

    def set_klines(
        self,
        symbol: str,
        df: pd.DataFrame,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        ttl: Optional[int] = None,
    ) -> None:
        """Cache K-line data.

        Args:
            symbol: Stock symbol
            df: K-line DataFrame
            start_date: Start date
            end_date: End date
            ttl: Time-to-live in seconds
        """
        key = self._make_klines_key(symbol, start_date, end_date)
        self.set(key, df.copy(), ttl)

    def invalidate_symbol(self, symbol: str) -> int:
        """Invalidate all cache entries for a symbol.

        Args:
            symbol: Stock symbol

        Returns:
            Number of entries invalidated
        """
        keys_to_remove = [
            key for key in self._cache.keys()
            if key.startswith(f"klines:{symbol}:")
        ]

        for key in keys_to_remove:
            self._remove(key)

        return len(keys_to_remove)

    def get_stats(self) -> dict:
        """Get cache statistics.

        Returns:
            Dict with cache statistics
        """
        now = time.time()
        expired_count = 0

        for key, entry in self._cache.items():
            if now - entry["timestamp"] > entry["ttl"]:
                expired_count += 1

        return {
            "size": len(self._cache),
            "max_size": self.max_size,
            "expired_count": expired_count,
            "utilization": len(self._cache) / self.max_size if self.max_size > 0 else 0,
        }

    def cleanup_expired(self) -> int:
        """Remove expired entries from cache.

        Returns:
            Number of entries removed
        """
        now = time.time()
        keys_to_remove = []

        for key, entry in self._cache.items():
            if now - entry["timestamp"] > entry["ttl"]:
                keys_to_remove.append(key)

        for key in keys_to_remove:
            self._remove(key)

        return len(keys_to_remove)

    def _make_klines_key(
        self,
        symbol: str,
        start_date: Optional[str],
        end_date: Optional[str],
    ) -> str:
        """Generate cache key for K-line data.

        Args:
            symbol: Stock symbol
            start_date: Start date
            end_date: End date

        Returns:
            Cache key string
        """
        parts = ["klines", symbol]

        if start_date:
            parts.append(start_date)
        else:
            parts.append("*")

        if end_date:
            parts.append(end_date)
        else:
            parts.append("*")

        return ":".join(parts)

    def _evict_lru(self) -> None:
        """Evict least recently used entry."""
        if not self._access_times:
            return

        # Find least recently used key
        lru_key = min(self._access_times.items(), key=lambda x: x[1])[0]
        self._remove(lru_key)

    def _remove(self, key: str) -> None:
        """Remove entry from cache and access times.

        Args:
            key: Cache key
        """
        self._cache.pop(key, None)
        self._access_times.pop(key, None)


class CacheDecorator:
    """Decorator for caching function results.

    Usage:
        cache = CacheManager()
        decorator = CacheDecorator(cache)

        @decorator.cached(ttl=60)
        def fetch_data(symbol):
            return expensive_operation(symbol)
    """

    def __init__(self, cache: CacheManager):
        """Initialize decorator with cache manager.

        Args:
            cache: CacheManager instance
        """
        self.cache = cache

    def cached(self, ttl: Optional[int] = None):
        """Decorator to cache function results.

        Args:
            ttl: Time-to-live in seconds

        Returns:
            Decorator function
        """
        def decorator(func):
            def wrapper(*args, **kwargs):
                # Generate cache key from function name and arguments
                key_parts = [func.__name__]
                key_parts.extend(str(arg) for arg in args)
                key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
                key = ":".join(key_parts)

                # Try to get from cache
                result = self.cache.get(key)
                if result is not None:
                    return result

                # Call function and cache result
                result = func(*args, **kwargs)
                self.cache.set(key, result, ttl)
                return result

            return wrapper
        return decorator
