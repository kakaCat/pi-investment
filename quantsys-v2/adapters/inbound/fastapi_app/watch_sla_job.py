"""兼容 shim（2026-10-19）：WatchSlaJob 已下沉到 qs_watch 包。

到期巡检是盯盘闭环的应用层编排（不碰 inbound 任何东西），属于 qs_watch 的
「回执/待办闭环」职责；此前放在 inbound 层导致 qs_watch 的 watch_loop_wiring
反向 import 宿主适配器（分层倒置）。真身现位于：
    qs_watch.application.services.watch_engine.sla_job

旧 import 路径保留至 30 天观察期后删除（与包抽离 shim 同口径）。
"""
from qs_watch.application.services.watch_engine.sla_job import (  # noqa: F401
    DEFAULT_LIMIT, WatchSlaJob, run_sla_once,
)
