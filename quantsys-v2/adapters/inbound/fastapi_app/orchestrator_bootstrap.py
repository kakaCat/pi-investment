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
from typing import Any, Dict, Optional, Tuple

import structlog

from application.services.trading_day_gate import should_skip
from domain.trading.services.market_session_policy import MarketSessionPolicy

logger = structlog.get_logger(__name__)

_TICK_INTERVAL_SEC = 60

#: 日级预过滤的路径标识（受控二值，进日志 path 字段）——REQ-261006130750-0654
PATH_ORCHESTRATOR_TICK = 'orchestrator_tick'
PATH_INTRADAY_MONITOR = 'intraday_monitor'

#: 跳过日志去噪：path -> day（同一 path 同一天只留第一条）。
#: 内存态：进程重启即清，最坏后果 = 当天多一条跳过日志，无副作用。
_LAST_SKIP_LOG: Dict[str, str] = {}


def _should_run_today(now: datetime, *, path: str) -> Tuple[bool, Dict[str, Any]]:
    """A 层（循环）日级预过滤——REQ-261006130750-0654 FR-2 / FR-3。**永不抛、不发通知**。

    fail-open 铁律：**只有「日历明确答该跳过」才返回 `(False, info)`**；任何降级来源
    （`weekday_fallback` / `unavailable` / `compute-error` / `gate-error`）一律**照跑**——
    本层唯一的收益是省一次无信息量的重算，绝不能换成一次静默停摆。

    判据唯一来源 = `application.services.trading_day_gate.should_skip('trading-days', now)`；
    本函数内**不得**出现 `weekday()` 或直接查交易日历（那会成为第二份判定，明令禁止）。

    跳过时按 `(path, day)` 去噪记一条 info 日志：编排线程休市日会命中 600 次/天，
    逐次刷屏会淹没真正有用的留痕（盘中监控 10 次/天同理）。
    """
    try:
        skip, info = should_skip('trading-days', now)
    except Exception as e:  # noqa: BLE001 - should_skip 的契约是「绝不抛」，这里只是双保险
        logger.error('orchestrator_trading_day_gate_raised', path=path, error=str(e))
        return True, {'degraded': True, 'reason': f'gate raised: {e}'}

    if not skip:
        return True, info

    day = str(info.get('day') or '')
    if _LAST_SKIP_LOG.get(path) != day:
        _LAST_SKIP_LOG[path] = day
        logger.info(
            'orchestrator_trading_day_skip',
            path=path,
            day=day,
            is_trading_day=info.get('is_trading_day'),
            source=info.get('source'),
            degraded=info.get('degraded'),
            reason=info.get('reason'),
        )
    return False, info


def _in_orchestrator_window(now: datetime) -> bool:
    """编排器**运行时段**：工作日 08:00-17:59（沿用原 daemon cron 的 hour='8-17'）

    注意：这不是「市况判定」而是「编排器允许跑 tick 的时段」（含盘前/盘后），
    故**不**收敛到 `MarketSessionPolicy`（策略表达的是相位，不是运行时段）。

    ⚠️ 日级判据**不在本函数**（REQ-261006130750-0654）：2026-10-06 起由调用点
    `_should_run_today()` 承担（fail-open 交易日门）。本函数只回答"时段"。
    原先「刻意保持 weekday 近似、不接 TradingDayGuard」的两个实测理由已被那道门覆盖：
    ① 门在任何降级来源下**一律照跑**，不会因数据源一抖就静默停掉 T+1 结转与止损；
    ② 长假后首个交易日按**当日日历口径**判（覆盖命中即照跑），不受"近 7 日有 K 线"启发式影响。
    """
    return now.weekday() < 5 and 8 <= now.hour <= 17


def _in_intraday_window(now: datetime) -> bool:
    """盘中监控窗口：连续竞价的 :00 与 :30（原为裸常量 09:30-11:30 / 13:00-15:00）

    RFC 016 §8.1：时段判定收敛到 `MarketSessionPolicy`（午休 11:30-13:00 明确不属于盘中，
    11:30 / 15:00 端点闭合沿用既有语义）。`:00 / :30` 是**节拍**约束（原 daemon cron），
    与市况无关，保留在此。

    日级同 `_in_orchestrator_window`：**不在本函数**，由调用点 `_should_run_today()` 把关
    （fail-open 交易日门，REQ-261006130750-0654）；此处 `is_trading_day` 一律为真，是
    "时段"语义所需，不是日级判据。
    """
    if now.minute not in (0, 30):
        return False
    phase = MarketSessionPolicy.phase_for(
        now.time(), is_trading_day=now.weekday() < 5,
    )
    return MarketSessionPolicy.is_market_open(phase)


def _monitor_loop(stop_event: threading.Event) -> None:
    from infrastructure.jobs import monitor_jobs
    from infrastructure.persistence.orm import close_session

    while not stop_event.is_set():
        now = datetime.now()
        try:
            if _in_orchestrator_window(now):
                # A 层日级预过滤（REQ-261006130750-0654 FR-2）：休市日连调用都不发生。
                # 内层 daily_orchestrator 的 fail-closed 守卫**保持不变**（钱路语义），
                # 本层只负责"省掉每分钟一次的空转调用"。
                run, _info = _should_run_today(now, path=PATH_ORCHESTRATOR_TICK)
                if run:
                    monitor_jobs.daily_orchestrator_tick()
            if _in_intraday_window(now):
                # 同上（FR-1）：本层预过滤；check() 首部另有权威门兜住旁路调用。
                run, _info = _should_run_today(now, path=PATH_INTRADAY_MONITOR)
                if run:
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
