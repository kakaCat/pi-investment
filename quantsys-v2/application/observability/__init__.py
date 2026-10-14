"""application.observability —— 运行结果契约与失败可见性出口。

REQ-261004154902-a7cd · t1（FR-1 / FR-2 / FR-9）。

本包只做两件事：
- :mod:`run_outcome`：把「干了没干、成了没成、为什么没成」收成一个值对象；
- :mod:`failure_sink`：给失败提供**唯一**的可见性出口（日志 + 通知降级链）。

不含任何算法，也不依赖 adapters / live_trading。
"""
from application.observability.failure_sink import (
    SEVERITY_HIGH,
    SEVERITY_NORMAL,
    install_failure_alert_sink,
    report_failure,
)
from application.observability.run_outcome import (
    ACTION_HOLD,
    ACTION_REBALANCE,
    ACTION_SKIPPED,
    ACTION_STOP_LOSS,
    FAILED_REASONS,
    REASON_FACTOR_EMPTY,
    REASON_MARKET_CLOSED,
    REASON_MODEL_NOT_LOADED,
    REASON_NOT_DUE,
    REASON_NOT_TRADING_DAY,
    REASON_OK,
    REASON_OVERSELL_BLOCKED,
    REASON_MATCH_FAILED,
    REASON_PENDING_EXPIRED,
    REASON_REBALANCE_FAILED,
    REASON_STOP_LOSS_FAILED,
    SKIPPED_REASONS,
    RunOutcome,
)

__all__ = [
    "RunOutcome",
    "REASON_OK",
    "REASON_NOT_TRADING_DAY",
    "REASON_NOT_DUE",
    "REASON_MARKET_CLOSED",
    "REASON_MODEL_NOT_LOADED",
    "REASON_FACTOR_EMPTY",
    "REASON_REBALANCE_FAILED",
    "REASON_STOP_LOSS_FAILED",
    "REASON_OVERSELL_BLOCKED",
    "REASON_PENDING_EXPIRED",
    "REASON_MATCH_FAILED",
    "SKIPPED_REASONS",
    "FAILED_REASONS",
    "ACTION_REBALANCE",
    "ACTION_STOP_LOSS",
    "ACTION_HOLD",
    "ACTION_SKIPPED",
    "report_failure",
    "install_failure_alert_sink",
    "SEVERITY_NORMAL",
    "SEVERITY_HIGH",
]
