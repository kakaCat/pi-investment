"""兼容 shim（2026-10-18）：已迁至二方包 qs_ops。
用 sys.modules 别名：保证 monkeypatch/inspect 打到真实模块实例。
30 天观察期后删除（方案卡 S9）。
"""
import sys
import qs_ops.application.services.scheduler_tasks_factors as _real
sys.modules[__name__] = _real
