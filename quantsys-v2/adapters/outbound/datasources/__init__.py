"""兼容 shim（2026-10-18）：datasources 已迁至二方包 qs_market_data。
旧路径（含 providers 深层子模块）经 __path__ 转发，30 天观察期后删除（方案卡 S3）。
"""
import qs_market_data.adapters.outbound.datasources as _t

__path__ = _t.__path__
from qs_market_data.adapters.outbound.datasources import *  # noqa: F401,F403
