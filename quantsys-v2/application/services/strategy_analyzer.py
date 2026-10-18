"""兼容 shim（2026-10-18）：已迁至二方包 qs_strategy。
用 sys.modules 别名而非星号导出：保证 monkeypatch/inspect.getsource 打到真实模块实例。
30 天观察期后删除（方案卡 S6）。
"""
import sys

import qs_strategy.application.services.strategy_analyzer as _real

sys.modules[__name__] = _real
