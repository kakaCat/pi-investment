"""DailyOrchestrator / IntradayMonitor 随 FastAPI 启动的装配（2026-08-13 起唯一宿主）

背景：orchestrator tick（T+1 结转/信号推送/挂单撮合）与 intraday monitor
（止损止盈）原仅由 scheduler_daemon.py 注册。daemon 无 launchd 守护，
08-05 后进程消失，两层功能静默死亡 8 天——daily_orchestrator_state 停在
08-05，今世缘(603369) 08-07 买入后 T+1 从未结转（shares_available 恒 0），
08-13 卖出被 422「可卖 0 股」拦截。与 WatchEngine 08-02~08-12 静默消失
同一事故模式（见 watch_bootstrap.py 头注释）。

契约：这两个循环的唯一宿主 = FastAPI 5001 进程（lifespan 调用本模块启动）。
scheduler_daemon 不再承担该职责（见 tests/api/test_orchestrator_bootstrap.py
的契约守护测试）。
"""
import threading
from datetime import datetime
from typing import Optional, Tuple

import structlog

from application.services.trading_day_guard import TradingDayGuard
from domain.trading.services.market_session_policy import MarketSessionPolicy

logger = structlog.get_logger(__name__)

_TICK_INTERVAL_SEC = 60


def _in_orchestrator_window(now: datetime) -> bool:
    """编排器**运行时段**：交易日 08:00-17:59（沿用原 daemon cron 的 hour='8-17'）

    注意：这不是「市况判定」而是「编排器允许跑 tick 的时段」（含盘前/盘后），
    故时段部分**不**收敛到 `MarketSessionPolicy`（策略表达的是相位，不是运行时段）。

    日级判定**委托 `TradingDayGuard`**（RFC 016 §7 红线：禁止自算 weekday）——
    原实现用 `weekday() < 5`，法定节假日（如 10-01 周四）会被当交易日，
    使编排器在非交易日照跑 T+1 结转/挂单撮合。
    """
    return TradingDayGuard.is_trading_day(now.date()) and 8 <= now.hour <= 17


def _in_intraday_window(now: datetime) -> bool:
    """盘中监控窗口：连续竞价的 :00 与 :30（原为裸常量 09:30-11:30 / 13:00-15:00）

    RFC 016 §8.1：时段判定收敛到 `MarketSessionPolicy`（午休 11:30-13:00 明确不属于盘中，
    11:30 / 15:00 端点闭合沿用既有语义）。`:00 / :30` 是**节拍**约束（原 daemon cron），
    与市况无关，保留在此。

    日级判定**委托 `TradingDayGuard`**（同上，RFC §7 红线），不再自算 weekday。
    """
    if now.minute not in (0, 30):
        return False
    phase = MarketSessionPolicy.phase_for(
        now.time(), is_trading_day=TradingDayGuard.is_trading_day(now.date()),
    )
    return MarketSessionPolicy.is_market_open(phase)


def _monitor_loop(stop_event: threading.Event) -> None:
    from infrastructure.jobs import monitor_jobs
    from infrastructure.persistence.orm import close_session

    while not stop_event.is_set():
        now = datetime.now()
        try:
            if _in_orchestrator_window(now):
                monitor_jobs.daily_orchestrator_tick()
            if _in_intraday_window(now):
                monitor_jobs.intraday_monitor_check()
        except Exception as e:
            # 单次 tick 失败不能杀死线程——否则编排器再次静默死亡
            logger.error(f"orchestrator/monitor tick error: {e}", exc_info=True)
        finally:
            # tick 在本线程留下的 scoped session 必须每轮释放——否则连接在
            # 60s 间隔里呈 idle in transaction（挡 autovacuum/持旧快照，
            # 2026-08-18 后台线程连接治理）
            try:
                close_session()
            except Exception:
                pass
        stop_event.wait(_TICK_INTERVAL_SEC)


def start_orchestrator(skip: bool = False) -> Optional[Tuple[threading.Thread, threading.Event]]:
    """启动 DailyOrchestrator tick + IntradayMonitor 后台线程。

    Args:
        skip: pytest 等测试环境传 True，避免测试进程拉起调度循环。

    Returns:
        (thread, stop_event) 句柄供 lifespan 关闭时优雅停止；skip 时返回 None。
    """
    if skip:
        return None

    from application.services.daily_orchestrator import get_daily_orchestrator

    # 进程启动时断点续跑（如 9:20 重启，补跑 PRE_MARKET）
    try:
        get_daily_orchestrator().resume_from_breakpoint()
    except Exception as e:
        logger.error(f"orchestrator resume_from_breakpoint failed: {e}", exc_info=True)

    stop_event = threading.Event()
    thread = threading.Thread(
        target=_monitor_loop, args=(stop_event,),
        name='orchestrator-tick-thread', daemon=True)
    thread.start()
    logger.info('✅ DailyOrchestrator/IntradayMonitor tick 线程已启动（宿主: FastAPI 5001）')
    return thread, stop_event


def stop_orchestrator(handles: Optional[Tuple[threading.Thread, threading.Event]]) -> None:
    """优雅停止 tick 线程（最多等待一个 tick 周期）"""
    if not handles:
        return
    thread, stop_event = handles
    stop_event.set()
    thread.join(timeout=5)
