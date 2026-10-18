"""兼容 shim（2026-10-18）：已迁至二方包 qs_watch。
用 sys.modules 别名而非星号导出：保证 monkeypatch/inspect.getsource 打到真实模块实例。
30 天观察期后删除（方案卡 S8）。
"""
import sys

import qs_watch.application.services.opportunity_to_watch_rule_service as _real

sys.modules[__name__] = _real
