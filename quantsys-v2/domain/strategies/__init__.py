"""兼容 shim（2026-10-18）：已迁至二方包 qs_strategy。
__path__ 转发：保住 from domain.strategies import X 与子模块导入（含 value_objects）。
30 天观察期后删除（方案卡 S6）。
"""
import qs_strategy.domain.strategies as _real

__path__ = _real.__path__

from qs_strategy.domain.strategies import *  # noqa: F401,F403
