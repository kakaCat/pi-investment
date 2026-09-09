"""v2 → Agent OS 结构化错误上报包（REQ-a42aa4 Batch C，2026-09-10）。

子模块：
  agent_os_reporter —— 纯 stdlib 上报器：异步队列 POST、风暴保护、根 logger ERROR Handler。
入口：
  install()                  挂根 logger ERROR Handler（main.py 启动期调用）
  report_event(...)          主动上报事件（任意位置）
  report_exception(...)      已捕获异常（含 traceback detail）上报
"""
from .agent_os_reporter import (
    AgentOSErrorLogHandler,
    install,
    report_event,
    report_exception,
)

__all__ = [
    "AgentOSErrorLogHandler",
    "install",
    "report_event",
    "report_exception",
]
