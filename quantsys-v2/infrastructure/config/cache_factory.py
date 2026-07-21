"""
缓存工厂

根据配置创建合适的缓存后端（内存或Redis）。
"""
import logging
from typing import Optional

from infrastructure.cache import CacheService, MemoryCacheBackend
from infrastructure.config import get_redis_config

# RedisCacheBackend import - check if it exists
try:
    from infrastructure.cache.cache_service import RedisCacheBackend
except ImportError:
    RedisCacheBackend = None

logger = logging.getLogger(__name__)


def create_cache_service(use_redis: bool = True) -> CacheService:
    """
    创建缓存服务实例

    Args:
        use_redis: 是否使用Redis（默认True，失败时自动降级到内存缓存）

    Returns:
        CacheService实例
    """
    if use_redis:
        try:
            import redis

            # 获取Redis配置
            redis_config = get_redis_config()

            # 创建Redis客户端
            redis_client = redis.Redis(**redis_config)

            # 测试连接
            redis_client.ping()

            logger.info(f"Redis连接成功: {redis_config['host']}:{redis_config['port']}")

            # 创建Redis缓存后端
            backend = RedisCacheBackend(redis_client)
            return CacheService(backend)

        except ImportError:
            logger.warning("Redis库未安装，使用内存缓存。安装: pip install redis hiredis")
        except Exception as e:
            logger.warning(f"Redis连接失败，降级到内存缓存: {e}")

    # 降级到内存缓存
    logger.info("使用内存缓存后端")
    backend = MemoryCacheBackend()
    return CacheService(backend)


def create_redis_client() -> Optional['redis.Redis']:
    """
    创建Redis客户端（用于直接操作）

    Returns:
        Redis客户端实例，失败返回None
    """
    try:
        import redis

        redis_config = get_redis_config()
        client = redis.Redis(**redis_config)
        client.ping()

        logger.info("Redis客户端创建成功")
        return client

    except ImportError:
        logger.error("Redis库未安装")
        return None
    except Exception as e:
        logger.error(f"Redis客户端创建失败: {e}")
        return None
