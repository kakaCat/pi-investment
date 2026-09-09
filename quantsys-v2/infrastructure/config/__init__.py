"""配置驱动集成模块

P2-3: 配置驱动集成
- 配置数据模型
- 配置加载器
- 配置验证器
"""

from .models import ServiceConfig, ServicesConfig, ServiceLifecycle
from .loader import ConfigLoader
from .validator import ConfigValidator

# 向后兼容：提供旧的 get_config 函数
def get_config(key: str = None, default=None):
    """
    向后兼容函数

    旧代码可能使用 `from infrastructure.config import get_config`
    为了避免破坏现有代码，提供此函数作为兼容层

    注意：这是一个临时兼容层，新代码应该使用 ConfigLoader
    """
    # 返回默认配置字典（空配置）
    if key is None:
        return {}
    return default


def get_redis_config():
    """获取 Redis 连接配置（向后兼容旧接口）

    cache_factory 依赖此函数构造 Redis 客户端。从环境变量读取，
    缺省指向本机 6379（同 async_cache_service 默认值）。

    Returns:
        dict: Redis 连接配置（redis.Redis kwargs）
    """
    import os

    return {
        'host': os.getenv('REDIS_HOST', 'localhost'),
        'port': int(os.getenv('REDIS_PORT', 6379)),
        'db': int(os.getenv('REDIS_DB', 0)),
        'password': os.getenv('REDIS_PASSWORD'),
    }


# 向后兼容：re-export 缓存工厂（scripts/tools/benchmark_cache.py 等仍从本模块导入）
from .cache_factory import create_cache_service, create_redis_client  # noqa: E402

__all__ = [
    'ServiceConfig',
    'ServicesConfig',
    'ServiceLifecycle',
    'ConfigLoader',
    'ConfigValidator',
    'get_config',  # 向后兼容
    'get_redis_config',  # 向后兼容
    'create_cache_service',
    'create_redis_client',
]
