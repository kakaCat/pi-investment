"""WatchEngine 随 FastAPI 启动的装配（2026-08-12 起盯盘引擎唯一宿主）

背景：WatchEngine 常驻线程原仅由 scheduler_daemon.py 启动。08-02 生产切换到
FastAPI nohup 部署后 daemon 未再拉起，盯盘静默消失——规则照常创建但无人判定、
不唤醒 agent、不发飞书（watch_triggers 停在 08-05 14:58）。

契约：盯盘引擎唯一宿主 = FastAPI 5001 进程（lifespan 调用本模块启动）。
scheduler_daemon 不再承担该职责（见 tests/api/test_watch_engine_bootstrap.py
的契约守护测试）。
"""
from typing import Optional, Tuple

import structlog

logger = structlog.get_logger(__name__)


def start_watch_engine(skip: bool = False) -> Optional[Tuple[object, object]]:
    """启动 WatchEngine 后台线程。

    Args:
        skip: pytest 等测试环境传 True，避免测试进程拉起盯盘循环。

    Returns:
        (engine, thread) 句柄供 lifespan 关闭时优雅停止；skip 时返回 None。
    """
    if skip:
        return None

    from application.services.watch_engine.factory import start_watch_engine_in_thread
    engine, thread = start_watch_engine_in_thread()
    logger.info('✅ WatchEngine 实时盯盘线程已启动（宿主: FastAPI 5001）')
    return engine, thread
