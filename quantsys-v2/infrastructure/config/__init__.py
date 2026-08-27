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

__all__ = [
    'ServiceConfig',
    'ServicesConfig',
    'ServiceLifecycle',
    'ConfigLoader',
    'ConfigValidator',
    'get_config',  # 向后兼容
]
