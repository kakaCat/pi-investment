"""Watch 旁路服务随 FastAPI 启动的装配。

股票判定由 V2 定时任务承担；本模块只保留新仓补止损、消息监控、走势回填、
池级对账、市场映射、政策扫描和收盘日报等旁路能力。宿主仍是 FastAPI 5001 lifespan。
"""
import structlog

logger = structlog.get_logger(__name__)


def start_watch_sidecars(skip: bool = False):
    """启动股票判定之外的旁路服务；skip 时返回 None。"""
    if skip:
        return None
    from qs_watch.application.services.watch_engine.factory import (
        start_watch_sidecars_in_thread,
    )
    engine = start_watch_sidecars_in_thread()
    logger.info('✅ WatchEngine 旁路服务已启动（股票判定归 V2）')
    return engine
