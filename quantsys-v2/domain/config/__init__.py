"""domain 层配置模块

提供 get_config 和 create_cache_service 函数
"""


def get_config(key: str = None, default=None):
    """
    获取配置

    Args:
        key: 配置键
        default: 默认值

    Returns:
        配置值
    """
    if key is None:
        return {}
    return default


def create_cache_service():
    """创建缓存服务"""
    from infrastructure.cache import CacheService
    return CacheService()
