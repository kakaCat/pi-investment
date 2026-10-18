"""兼容 shim（2026-10-18）：已迁至二方包 qs_trading。
__path__ 转发：保住 from domain.trading import X 与子模块导入（含 ports）。
30 天观察期后删除（方案卡 S7）。
"""
import qs_trading.domain.trading as _real

__path__ = _real.__path__

from qs_trading.domain.trading import *  # noqa: F401,F403
