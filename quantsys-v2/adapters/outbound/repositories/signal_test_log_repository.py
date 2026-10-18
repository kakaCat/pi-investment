"""兼容 shim（2026-10-18）：已迁至二方包 qs_sourcing。
30 天观察期后删除（方案卡 S4）。
"""
import sys

import qs_sourcing.adapters.outbound.repositories.signal_test_log_repository as _real

sys.modules[__name__] = _real
