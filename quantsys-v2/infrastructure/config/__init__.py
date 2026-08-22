"""配置驱动集成模块

P2-3: 配置驱动集成
- 配置数据模型
- 配置加载器
- 配置验证器
"""

from .models import ServiceConfig, ServicesConfig, ServiceLifecycle
from .loader import ConfigLoader
from .validator import ConfigValidator

__all__ = [
    'ServiceConfig',
    'ServicesConfig',
    'ServiceLifecycle',
    'ConfigLoader',
    'ConfigValidator',
]
