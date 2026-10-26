"""
WatchEngine - 实时盯盘引擎

监控市场条件并触发告警
"""
# ── 子包归类 __path__ shim（2026-10-22）────────────────────────────
# 模块已归类到 rules/notify/market/lifecycle/core 子包；把子目录挂进 __path__
# 使旧绝对路径（qs_watch...watch_engine.conditions）仍解析到新位置——
# 外部 import 一行不改。所有 import 继续走旧路径，无双加载（无新路径 import）。
import os as _os
_here = _os.path.dirname(__file__)
for _sub in ('rules', 'notify', 'market', 'lifecycle', 'core'):
    _p = _os.path.join(_here, _sub)
    if _os.path.isdir(_p) and _p not in __path__:
        __path__.append(_p)

from .core.engine import WatchEngine

__all__ = ['WatchEngine']
