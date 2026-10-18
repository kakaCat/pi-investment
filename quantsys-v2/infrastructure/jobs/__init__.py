"""兼容 shim（2026-10-18）：作业装配已迁至二方包 qs_ops。
__path__ 转发：保住 from infrastructure.jobs import X 与子模块导入。
30 天观察期后删除（方案卡 S9）。
"""
import qs_ops.infrastructure.jobs as _real
__path__ = _real.__path__
from qs_ops.infrastructure.jobs import *  # noqa: F401,F403
