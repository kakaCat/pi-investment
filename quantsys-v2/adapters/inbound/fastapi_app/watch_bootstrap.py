"""WatchEngine 随 FastAPI 启动的装配（2026-08-12 起盯盘引擎唯一宿主）

背景：WatchEngine 常驻线程原仅由 scheduler_daemon.py 启动。08-02 生产切换到
FastAPI nohup 部署后 daemon 未再拉起，盯盘静默消失——规则照常创建但无人判定、
不唤醒 agent、不发飞书（watch_triggers 停在 08-05 14:58）。

契约：盯盘引擎唯一宿主 = FastAPI 5001 进程（lifespan 调用本模块启动）。
scheduler_daemon 不再承担该职责（见 tests/api/test_watch_engine_bootstrap.py
的契约守护测试）。
"""
import os
from typing import Optional, Tuple

import structlog

logger = structlog.get_logger(__name__)

#: V1 盯盘开关（2026-10-23：与 V2 拆分）。默认 true = 保持既有行为。
#: 下周切 V2 时置 false：V1 循环不启动，V2 的 5 个定时任务照常注册。
_ENV_V1_ENABLED = 'WATCH_V1_ENABLED'


def v1_enabled() -> bool:
    """V1 常驻循环是否启动（DISABLE_WATCH_ENGINE 仍是总闸）。"""
    if os.getenv('DISABLE_WATCH_ENGINE', '').lower() == 'true':
        return False
    raw = os.getenv(_ENV_V1_ENABLED)
    if raw is None:
        return True
    return raw.strip().lower() not in ('0', 'false', 'no', 'off')


def start_watch_engine(skip: bool = False) -> Optional[Tuple[object, object]]:
    """启动 WatchEngine 后台线程。

    Args:
        skip: pytest 等测试环境传 True，避免测试进程拉起盯盘循环。

    Returns:
        (engine, thread) 句柄供 lifespan 关闭时优雅停止；skip 时返回 None。
    """
    if skip:
        return None

    from qs_watch.application.services.watch_engine.factory import start_watch_engine_in_thread
    engine, thread = start_watch_engine_in_thread()
    logger.info('✅ WatchEngine 实时盯盘线程已启动（宿主: FastAPI 5001）')
    return engine, thread


def start_watch_sidecars(skip: bool = False):
    """V1 判定循环下线时保留旁路服务（2026-10-24，V2 接管判定）。

    sidecar/心跳/板块映射/政策扫描仍需要跑（新仓自动补止损、新闻监控、走势回填、
    池级对账、收盘日报）；停掉整个 V1 线程会让这些能力静默消失。判定循环
    ``run_forever`` 不启动 —— 盯盘触发只由 V2 定时任务产生。

    Returns: engine 句柄（挂 app.state 供优雅停止）；skip 时返回 None。
    """
    if skip:
        return None
    from qs_watch.application.services.watch_engine.factory import (
        start_watch_sidecars_in_thread,
    )
    engine = start_watch_sidecars_in_thread()
    logger.info('✅ WatchEngine V1 旁路服务已启动（判定循环未启动，判定归 V2）')
    return engine
