"""
调度任务的模块级包装函数。

背景（2026-07-22 daemon 启动失败根因）：
APScheduler 的 SQLAlchemyJobStore 需要 pickle 任务函数。
绑定方法（如 get_intraday_monitor().check）会连带序列化实例持有的
ORM Session，导致 PicklingError，daemon 在 scheduler.start() 时崩溃。
模块级函数按 "模块:函数名" 引用序列化，运行时才解析单例，可安全持久化。
"""
import structlog

logger = structlog.get_logger(__name__)


def daily_orchestrator_tick():
    """日常编排器 tick：运行时才获取单例，避免序列化绑定方法。"""
    from application.services.daily_orchestrator import get_daily_orchestrator
    get_daily_orchestrator().tick()


def intraday_monitor_check():
    """盘中监控 check：运行时才获取单例，避免序列化绑定方法。"""
    from application.services.intraday_monitor import get_intraday_monitor
    get_intraday_monitor().check()
