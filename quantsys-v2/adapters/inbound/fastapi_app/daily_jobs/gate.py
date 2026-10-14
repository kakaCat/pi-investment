"""DailyJobs 交易日门——**兼容转发壳**（REQ-261005203907-2b8c → REQ-261006093620-a315 t3）

判据已上移到 `application/services/trading_day_gate.py`（**唯一真源**），原因见该模块 docstring：
② 库表调度（`infrastructure/scheduler/`）也要用同一份判据，而 `infrastructure/` 不能反向依赖
本入站适配器目录（分层方向）。本文件**只做转发**，不留任何判定实现。

## ⚠️ 打桩点（本仓 CLAUDE.md 的「打桩点规则」）

桩必须打在**被调函数所在模块**，即 `application.services.trading_day_gate.TradingDayGuard`。
打在本模块的 `TradingDayGuard` 名字上（哪怕手工造出来）**不会生效**——判定在那边取值。
`tests/test_daily_jobs_trading_day_gate.py` 里有一条**证伪用例**专门锁这条：桩打到新模块后，
经本壳调用得到的结论必须随之改变；打到本模块则必须毫无影响。

对外契约不变：`runtime.py` / `pipeline.py` 的导入路径与调用方式一行未改。
"""
from __future__ import annotations

from application.services.trading_day_gate import (  # noqa: F401
    SOURCE_GATE_ERROR,
    is_non_trading_day,
    skip_non_trading_day,
    verdict_info,
)

__all__ = [
    'SOURCE_GATE_ERROR',
    'is_non_trading_day',
    'skip_non_trading_day',
    'verdict_info',
]
