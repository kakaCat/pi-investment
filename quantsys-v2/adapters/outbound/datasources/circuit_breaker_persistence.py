"""
Circuit Breaker State Persistence

提供熔断器状态持久化到 Redis，支持跨进程共享和重启后恢复
"""
import json
import logging
import time
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class CircuitBreakerStatePersistence:
    """熔断器状态持久化管理器

    将熔断器状态保存到 Redis，支持：
    - 跨进程共享熔断状态
    - 进程重启后恢复历史状态
    - 熔断历史记录追踪
    """

    def __init__(self, redis_client=None, key_prefix: str = 'cb:state'):
        """Initialize persistence manager

        Args:
            redis_client: Redis client instance (optional, will use in-memory fallback if None)
            key_prefix: Redis key prefix for circuit breaker state
        """
        self.redis_client = redis_client
        self.key_prefix = key_prefix
        self._memory_store: Dict[str, Dict[str, Any]] = {}  # Fallback to memory if Redis unavailable

        if redis_client is None:
            logger.warning("Redis client not provided, using in-memory fallback for circuit breaker state")

    def save_state(self, provider_name: str, state: Dict[str, Any]) -> bool:
        """Save circuit breaker state

        Args:
            provider_name: Provider name
            state: Circuit breaker state dict with keys:
                - state: 'closed' | 'open' | 'half_open'
                - opened_at: timestamp (float)
                - failure_count: int
                - success_count: int

        Returns:
            True if saved successfully, False otherwise
        """
        try:
            state_key = f"{self.key_prefix}:{provider_name}"
            state_data = {
                **state,
                'updated_at': time.time()
            }

            if self.redis_client:
                # Save to Redis with 7 days TTL
                self.redis_client.setex(
                    state_key,
                    7 * 24 * 3600,  # 7 days
                    json.dumps(state_data)
                )
            else:
                # Fallback to memory
                self._memory_store[state_key] = state_data

            return True

        except Exception as e:
            logger.error(f"Failed to save circuit breaker state for {provider_name}: {e}")
            return False

    def load_state(self, provider_name: str) -> Optional[Dict[str, Any]]:
        """Load circuit breaker state

        Args:
            provider_name: Provider name

        Returns:
            State dict or None if not found
        """
        try:
            state_key = f"{self.key_prefix}:{provider_name}"

            if self.redis_client:
                # Load from Redis
                data = self.redis_client.get(state_key)
                if data:
                    return json.loads(data)
            else:
                # Load from memory
                return self._memory_store.get(state_key)

            return None

        except Exception as e:
            logger.error(f"Failed to load circuit breaker state for {provider_name}: {e}")
            return None

    def delete_state(self, provider_name: str) -> bool:
        """Delete circuit breaker state

        Args:
            provider_name: Provider name

        Returns:
            True if deleted successfully, False otherwise
        """
        try:
            state_key = f"{self.key_prefix}:{provider_name}"

            if self.redis_client:
                self.redis_client.delete(state_key)
            else:
                self._memory_store.pop(state_key, None)

            return True

        except Exception as e:
            logger.error(f"Failed to delete circuit breaker state for {provider_name}: {e}")
            return False

    def save_history(self, provider_name: str, event: str, details: Dict[str, Any]) -> bool:
        """Save circuit breaker state transition history

        Args:
            provider_name: Provider name
            event: Event type ('opened' | 'closed' | 'half_opened')
            details: Event details dict

        Returns:
            True if saved successfully, False otherwise
        """
        try:
            history_key = f"{self.key_prefix}:history:{provider_name}"
            history_entry = {
                'event': event,
                'timestamp': time.time(),
                'details': details
            }

            if self.redis_client:
                # Use Redis list to store history (max 100 entries)
                self.redis_client.lpush(history_key, json.dumps(history_entry))
                self.redis_client.ltrim(history_key, 0, 99)  # Keep last 100 entries
                self.redis_client.expire(history_key, 30 * 24 * 3600)  # 30 days TTL
            else:
                # Fallback to memory (limited history)
                if history_key not in self._memory_store:
                    self._memory_store[history_key] = []
                self._memory_store[history_key].insert(0, history_entry)
                self._memory_store[history_key] = self._memory_store[history_key][:100]

            return True

        except Exception as e:
            logger.error(f"Failed to save circuit breaker history for {provider_name}: {e}")
            return False

    def get_history(self, provider_name: str, limit: int = 10) -> list:
        """Get circuit breaker state transition history

        Args:
            provider_name: Provider name
            limit: Max number of entries to return

        Returns:
            List of history entries (newest first)
        """
        try:
            history_key = f"{self.key_prefix}:history:{provider_name}"

            if self.redis_client:
                # Load from Redis
                entries = self.redis_client.lrange(history_key, 0, limit - 1)
                return [json.loads(e) for e in entries]
            else:
                # Load from memory
                entries = self._memory_store.get(history_key, [])
                return entries[:limit]

        except Exception as e:
            logger.error(f"Failed to get circuit breaker history for {provider_name}: {e}")
            return []

    def get_all_states(self) -> Dict[str, Dict[str, Any]]:
        """Get all circuit breaker states

        Returns:
            Dict mapping provider name to state dict
        """
        try:
            states = {}

            if self.redis_client:
                # Scan Redis for all state keys
                pattern = f"{self.key_prefix}:*"
                for key in self.redis_client.scan_iter(match=pattern):
                    key_str = key.decode('utf-8') if isinstance(key, bytes) else key
                    if ':history:' not in key_str:  # Skip history keys
                        provider_name = key_str.split(':')[-1]
                        data = self.redis_client.get(key)
                        if data:
                            states[provider_name] = json.loads(data)
            else:
                # Load from memory
                for key, value in self._memory_store.items():
                    if key.startswith(self.key_prefix) and ':history:' not in key:
                        provider_name = key.split(':')[-1]
                        states[provider_name] = value

            return states

        except Exception as e:
            logger.error(f"Failed to get all circuit breaker states: {e}")
            return {}


def get_persistence_manager(redis_client=None) -> CircuitBreakerStatePersistence:
    """Get circuit breaker state persistence manager singleton

    Args:
        redis_client: Redis client instance (optional)

    Returns:
        CircuitBreakerStatePersistence instance
    """
    global _persistence_manager
    if '_persistence_manager' not in globals():
        _persistence_manager = CircuitBreakerStatePersistence(redis_client)
    return _persistence_manager
