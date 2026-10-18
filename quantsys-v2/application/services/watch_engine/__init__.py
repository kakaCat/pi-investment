"""兼容 shim（2026-10-18）：已迁至二方包 qs_watch。
__path__ 转发：保住 from application.services.watch_engine import X 与子模块导入。
30 天观察期后删除（方案卡 S8）。
"""
import qs_watch.application.services.watch_engine as _real

__path__ = _real.__path__

from qs_watch.application.services.watch_engine import *  # noqa: F401,F403
