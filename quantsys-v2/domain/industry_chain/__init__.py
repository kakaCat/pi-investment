"""兼容 shim（2026-10-18）：已迁至二方包 qs_intel。
__path__ 转发：保住 from domain.industry_chain import X 与子模块导入。
30 天观察期后删除（方案卡 S5）。
"""
import qs_intel.domain.industry_chain as _real

__path__ = _real.__path__

from qs_intel.domain.industry_chain import *  # noqa: F401,F403
