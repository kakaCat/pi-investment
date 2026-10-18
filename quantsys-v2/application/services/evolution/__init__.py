"""兼容 shim（2026-10-19）：已迁至二方包 qs_agenthub。
__path__ 转发：保住 from application.services.evolution import X 与子模块导入。
30 天观察期后删除（方案卡 S10）。
"""
import qs_agenthub.application.services.evolution as _real
__path__ = _real.__path__
from qs_agenthub.application.services.evolution import *  # noqa: F401,F403
