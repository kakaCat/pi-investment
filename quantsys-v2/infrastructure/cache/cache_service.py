"""
缓存服务 (CacheService)

实现 look-aside 缓存模式，支持内存缓存（默认）和 Redis（可选）。
提供命名空间隔离、TTL支持、模式匹配清除等功能。
"""
from typing import Any, Optional, Dict, List
from datetime import datetime, timedelta
import json
import hashlib
import logging
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class CacheBackend(ABC):
    """缓存后端抽象基类"""

    @abstractmethod
    def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        pass

    @abstractmethod
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """设置缓存值"""
        pass

    @abstractmethod
    def delete(self, key: str) -> bool:
        """删除缓存"""
        pass

    @abstractmethod
    def clear(self) -> bool:
        """清空所有缓存"""
        pass

    @abstractmethod
    def keys(self, pattern: str = "*") -> List[str]:
        """获取匹配模式的所有键"""
        pass


class MemoryCacheBackend(CacheBackend):
    """内存缓存后端（默认实现）"""

    def __init__(self):
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._stats = {
            'hits': 0,
            'misses': 0,
            'sets': 0,
            'deletes': 0,
        }

    def get(self, key: str) -> Optional[Any]:
        """获取缓存值，检查TTL"""
        if key not in self._cache:
            self._stats['misses'] += 1
            return None

        entry = self._cache[key]

        # 检查是否过期
        if entry['expires_at'] is not None:
            if datetime.now() > entry['expires_at']:
                # 过期，删除并返回None
                del self._cache[key]
                self._stats['misses'] += 1
                return None

        self._stats['hits'] += 1
        return entry['value']

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """设置缓存值"""
        expires_at = None
        if ttl is not None:
            expires_at = datetime.now() + timedelta(seconds=ttl)

        self._cache[key] = {
            'value': value,
            'expires_at': expires_at,
            'created_at': datetime.now(),
        }
        self._stats['sets'] += 1
        return True

    def delete(self, key: str) -> bool:
        """删除缓存"""
        if key in self._cache:
            del self._cache[key]
            self._stats['deletes'] += 1
            return True
        return False

    def clear(self) -> bool:
        """清空所有缓存"""
        count = len(self._cache)
        self._cache.clear()
        logger.info(f"Cleared {count} cache entries")
        return True

    def keys(self, pattern: str = "*") -> List[str]:
        """获取匹配模式的所有键（简单通配符支持）"""
        import fnmatch
        return [k for k in self._cache.keys() if fnmatch.fnmatch(k, pattern)]

    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        total_requests = self._stats['hits'] + self._stats['misses']
        hit_rate = self._stats['hits'] / total_requests if total_requests > 0 else 0.0

        return {
            'backend': 'memory',
            'entries': len(self._cache),
            'hits': self._stats['hits'],
            'misses': self._stats['misses'],
            'sets': self._stats['sets'],
            'deletes': self._stats['deletes'],
            'hit_rate': hit_rate,
        }


class RedisCacheBackend(CacheBackend):
    """Redis缓存后端（可选）"""

    def __init__(self, redis_client):
        """
        初始化Redis缓存后端

        Args:
            redis_client: Redis客户端实例（redis.Redis）
        """
        self._redis = redis_client
        self._stats = {
            'hits': 0,
            'misses': 0,
            'sets': 0,
            'deletes': 0,
        }

    def get(self, key: str) -> Optional[Any]:
        """从Redis获取缓存值"""
        try:
            value = self._redis.get(key)
            if value is None:
                self._stats['misses'] += 1
                return None

            self._stats['hits'] += 1
            # 反序列化
            return json.loads(value)
        except Exception as e:
            logger.error(f"Redis get error: {e}")
            self._stats['misses'] += 1
            return None

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """设置Redis缓存值"""
        try:
            # 序列化
            serialized = json.dumps(value, default=str)
            if ttl is not None:
                self._redis.setex(key, ttl, serialized)
            else:
                self._redis.set(key, serialized)
            self._stats['sets'] += 1
            return True
        except Exception as e:
            logger.error(f"Redis set error: {e}")
            return False

    def delete(self, key: str) -> bool:
        """删除Redis缓存"""
        try:
            result = self._redis.delete(key)
            if result > 0:
                self._stats['deletes'] += 1
            return result > 0
        except Exception as e:
            logger.error(f"Redis delete error: {e}")
            return False

    def clear(self) -> bool:
        """清空Redis数据库（谨慎使用）"""
        try:
            self._redis.flushdb()
            logger.warning("Redis database flushed")
            return True
        except Exception as e:
            logger.error(f"Redis clear error: {e}")
            return False

    def keys(self, pattern: str = "*") -> List[str]:
        """获取匹配模式的所有键"""
        try:
            keys = self._redis.keys(pattern)
            return [k.decode('utf-8') if isinstance(k, bytes) else k for k in keys]
        except Exception as e:
            logger.error(f"Redis keys error: {e}")
            return []

    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        total_requests = self._stats['hits'] + self._stats['misses']
        hit_rate = self._stats['hits'] / total_requests if total_requests > 0 else 0.0

        try:
            info = self._redis.info('stats')
            return {
                'backend': 'redis',
                'hits': self._stats['hits'],
                'misses': self._stats['misses'],
                'sets': self._stats['sets'],
                'deletes': self._stats['deletes'],
                'hit_rate': hit_rate,
                'redis_keyspace_hits': info.get('keyspace_hits', 0),
                'redis_keyspace_misses': info.get('keyspace_misses', 0),
            }
        except Exception:
            return {
                'backend': 'redis',
                'hits': self._stats['hits'],
                'misses': self._stats['misses'],
                'sets': self._stats['sets'],
                'deletes': self._stats['deletes'],
                'hit_rate': hit_rate,
            }


class CacheService:
    """
    缓存服务，实现 look-aside 缓存模式

    支持命名空间隔离、TTL、模式匹配清除等功能。
    """

    def __init__(self, backend: Optional[CacheBackend] = None):
        """
        初始化缓存服务

        Args:
            backend: 缓存后端实例，默认使用内存缓存
        """
        self._backend = backend or MemoryCacheBackend()
        logger.info(f"CacheService initialized with backend: {type(self._backend).__name__}")

    def _make_key(self, namespace: str, key: str) -> str:
        """生成带命名空间的缓存键"""
        return f"{namespace}:{key}"

    def get(self, namespace: str, key: str) -> Optional[Any]:
        """
        获取缓存值

        Args:
            namespace: 命名空间（如 'klines', 'factors', 'daily'）
            key: 缓存键

        Returns:
            缓存值，不存在或过期返回None
        """
        cache_key = self._make_key(namespace, key)
        return self._backend.get(cache_key)

    def set(self, namespace: str, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """
        设置缓存值

        Args:
            namespace: 命名空间
            key: 缓存键
            value: 缓存值
            ttl: 过期时间（秒），None表示永不过期

        Returns:
            是否成功
        """
        cache_key = self._make_key(namespace, key)
        return self._backend.set(cache_key, value, ttl)

    def delete(self, namespace: str, key: str) -> bool:
        """
        删除缓存

        Args:
            namespace: 命名空间
            key: 缓存键

        Returns:
            是否成功
        """
        cache_key = self._make_key(namespace, key)
        return self._backend.delete(cache_key)

    def invalidate_by_pattern(self, namespace: str, pattern: str) -> int:
        """
        根据模式清除缓存

        Args:
            namespace: 命名空间
            pattern: 匹配模式（支持通配符 *）

        Returns:
            清除的缓存数量
        """
        full_pattern = self._make_key(namespace, pattern)
        keys = self._backend.keys(full_pattern)

        count = 0
        for key in keys:
            if self._backend.delete(key):
                count += 1

        if count > 0:
            logger.info(f"Invalidated {count} cache entries matching {full_pattern}")

        return count

    def clear_namespace(self, namespace: str) -> int:
        """
        清空整个命名空间

        Args:
            namespace: 命名空间

        Returns:
            清除的缓存数量
        """
        return self.invalidate_by_pattern(namespace, "*")

    def clear_all(self) -> bool:
        """清空所有缓存"""
        return self._backend.clear()

    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        return self._backend.get_stats()

    def hash_key(self, *args) -> str:
        """
        生成缓存键的哈希值（用于复杂参数）

        Args:
            *args: 任意参数

        Returns:
            MD5哈希字符串
        """
        key_str = json.dumps(args, sort_keys=True, default=str)
        return hashlib.md5(key_str.encode()).hexdigest()


# 全局缓存实例（可选）
_global_cache: Optional[CacheService] = None


def get_cache_service() -> CacheService:
    """获取全局缓存服务实例"""
    global _global_cache
    if _global_cache is None:
        _global_cache = CacheService()
    return _global_cache


def init_cache_service(backend: Optional[CacheBackend] = None) -> CacheService:
    """
    初始化全局缓存服务

    Args:
        backend: 缓存后端实例

    Returns:
        缓存服务实例
    """
    global _global_cache
    _global_cache = CacheService(backend)
    return _global_cache
