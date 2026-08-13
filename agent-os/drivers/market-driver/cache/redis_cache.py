"""Redis cache layer for market data

Provides caching with TTL support. Falls back to no-cache if Redis unavailable.
"""
import json
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logger.warning("redis-py not installed, caching disabled")


class RedisCache:
    """Redis cache with graceful degradation"""

    def __init__(self, host: str = "localhost", port: int = 6379, db: int = 0):
        """Initialize Redis cache

        Args:
            host: Redis host
            port: Redis port
            db: Redis database number
        """
        self._client = None
        self._enabled = False

        if not REDIS_AVAILABLE:
            logger.warning("Redis cache disabled: redis-py not installed")
            return

        try:
            self._client = redis.Redis(
                host=host,
                port=port,
                db=db,
                decode_responses=False,  # We'll handle encoding ourselves
                socket_connect_timeout=2,
                socket_timeout=2,
            )
            # Test connection
            self._client.ping()
            self._enabled = True
            logger.info(f"Redis cache enabled: {host}:{port}/{db}")
        except Exception as e:
            logger.warning(f"Redis cache disabled: {e}")
            self._client = None
            self._enabled = False

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found
        """
        if not self._enabled or not self._client:
            return None

        try:
            value = self._client.get(key)
            if value is None:
                return None

            # Deserialize JSON
            return json.loads(value)
        except Exception as e:
            logger.warning(f"Redis get error: {e}")
            return None

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set value in cache with optional TTL

        Args:
            key: Cache key
            value: Value to cache (must be JSON serializable)
            ttl: Time to live in seconds (None = no expiration)

        Returns:
            True if successful, False otherwise
        """
        if not self._enabled or not self._client:
            return False

        try:
            # Serialize to JSON
            serialized = json.dumps(value, ensure_ascii=False, default=str)

            if ttl is not None:
                self._client.setex(key, ttl, serialized)
            else:
                self._client.set(key, serialized)

            return True
        except Exception as e:
            logger.warning(f"Redis set error: {e}")
            return False

    def delete(self, key: str) -> bool:
        """Delete key from cache

        Args:
            key: Cache key

        Returns:
            True if key was deleted, False otherwise
        """
        if not self._enabled or not self._client:
            return False

        try:
            result = self._client.delete(key)
            return result > 0
        except Exception as e:
            logger.warning(f"Redis delete error: {e}")
            return False

    def clear(self) -> bool:
        """Clear all keys in current database

        Returns:
            True if successful, False otherwise
        """
        if not self._enabled or not self._client:
            return False

        try:
            self._client.flushdb()
            return True
        except Exception as e:
            logger.warning(f"Redis clear error: {e}")
            return False

    @property
    def is_enabled(self) -> bool:
        """Check if cache is enabled and connected"""
        return self._enabled
