"""
基础设施配置模块
"""

# 缓存配置
CACHE_TTL = {
    'default': 300,      # 5分钟
    'short': 60,         # 1分钟
    'medium': 600,       # 10分钟
    'long': 1800,        # 30分钟
    'daily': 86400,      # 1天
}

CACHE_NAMESPACE = {
    'stock': 'stock',
    'kline': 'kline',
    'financial': 'financial',
    'quote': 'quote',
    'market': 'market',
}

# 数据库配置
DB_POOL_SIZE = 20
DB_MAX_OVERFLOW = 10
DB_POOL_TIMEOUT = 30

# API配置
API_TIMEOUT = 30
API_RETRY_TIMES = 3

# Redis 配置
def get_redis_config():
    """获取 Redis 配置（向后兼容旧接口）
    
    Returns:
        dict: Redis 连接配置
    """
    from infrastructure.config.settings import get_config
    config = get_config()
    return {
        'host': config.redis.host,
        'port': config.redis.port,
        'db': config.redis.db,
        'password': config.redis.password,
    }

__all__ = [
    'CACHE_TTL',
    'CACHE_NAMESPACE',
    'DB_POOL_SIZE',
    'DB_MAX_OVERFLOW',
    'DB_POOL_TIMEOUT',
    'API_TIMEOUT',
    'API_RETRY_TIMES',
    'get_redis_config',
]

# Cache factory functions - 延迟导入避免循环依赖
def create_cache_service(use_redis: bool = True):
    from infrastructure.config.cache_factory import create_cache_service as _create
    return _create(use_redis)

def create_redis_client():
    from infrastructure.config.cache_factory import create_redis_client as _create
    return _create()

__all__.extend(['create_cache_service', 'create_redis_client'])

# Pydantic Settings-based configuration (NEW - 2026-08-19)
# Unified type-safe configuration management
from infrastructure.config.settings import (
    Config,
    get_config,
    reload_config,
    DatabaseSettings,
    RedisSettings,
    ThreadSettings,
    ExternalServiceSettings,
    ProxySettings,
    LoggingSettings,
    AppSettings,
)

__all__.extend([
    'Config',
    'get_config',
    'reload_config',
    'DatabaseSettings',
    'RedisSettings',
    'ThreadSettings',
    'ExternalServiceSettings',
    'ProxySettings',
    'LoggingSettings',
    'AppSettings',
])
