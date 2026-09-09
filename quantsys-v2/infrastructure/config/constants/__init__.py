"""配置常量模块

提供项目中所有魔法数字的集中配置管理。

目录结构:
- base.py: 配置基类
- mathematical.py: 数学常量
- trading/: 交易相关配置
- scoring/: 评分系统配置
- detection/: 检测系统配置
- technical_analysis/: 技术分析配置
- system/: 系统配置
"""

from .base import ConfigBase

__all__ = ['ConfigBase']
