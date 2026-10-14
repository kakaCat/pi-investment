"""间隔任务（盯盘心跳/自愈）与其调度（拆分自 daily_jobs_bootstrap.py）

2026-10-01（REQ-261001145152-3982 t-686185）：由 daily_jobs_bootstrap.py 机械拆分而来
（原文件 1147 行）。函数体与签名**逐字未改**；原模块保留为转发壳，既有导入路径不受影响。
"""
import json
import os
import threading
import time
from dataclasses import dataclass
from datetime import datetime, time as dtime, timedelta
from typing import Any, Callable, Dict, List, Optional

import structlog

# 失败判定口径唯一来源（含嵌套下钻）：与 APScheduler 路径共用，避免两套标准
from infrastructure.scheduler.job_executor import find_result_failure
from adapters.inbound.fastapi_app.daily_jobs.defs import IntervalJobDef  # noqa: F401
from adapters.inbound.fastapi_app.daily_jobs.alerting import _summarize_result  # noqa: F401
from adapters.inbound.fastapi_app.daily_jobs.defs import _TICK_SEC, logger  # noqa: F401

DEFAULT_SELF_HEAL_INTERVAL_SEC = 600

def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ('1', 'true', 'yes', 'on')


def _self_heal_interval_sec() -> float:
    try:
        value = float(os.getenv('WATCH_SELF_HEAL_INTERVAL_SEC',
                                str(DEFAULT_SELF_HEAL_INTERVAL_SEC)))
    except (TypeError, ValueError):
        value = float(DEFAULT_SELF_HEAL_INTERVAL_SEC)
    return max(float(_TICK_SEC), value)


def _watch_loop_master_enabled() -> bool:
    """新闭环总闸（WATCH_TODO_ENABLED，默认 false）= SLA 巡检 + 心跳巡检的注册条件。"""
    return _env_flag('WATCH_TODO_ENABLED', False)


def _watch_heartbeat_job_enabled() -> bool:
    return _watch_loop_master_enabled() and _env_flag('WATCH_HEARTBEAT_ENABLED', True)


def _watch_self_heal_job_enabled() -> bool:
    return _watch_loop_master_enabled() and _env_flag('WATCH_SELF_HEAL_ENABLED', False)


def _job_watch_heartbeat() -> Dict[str, Any]:
    """引擎心跳 / 影子超期巡检（真实通知通道=NotificationFacade，t12 §6-项10）"""
    from adapters.inbound.fastapi_app.watch_heartbeat_job import run_heartbeat_check
    from adapters.outbound.repositories.watch_runtime_state_repository import (
        WatchRuntimeStateRepository,
    )
    from application.services.watch_engine.watch_channels import send_watch_alert
    return run_heartbeat_check(store=WatchRuntimeStateRepository(), sender=send_watch_alert)


def _job_watch_sla() -> Dict[str, Any]:
    """待办到期巡检（唯一收敛权威，architecture §4）"""
    from application.services.watch_engine.watch_loop_wiring import build_sla_job
    return build_sla_job().run_once()


def _job_watch_self_heal() -> Dict[str, Any]:
    """规则自愈扫描（反复触发 → 抑噪 + 修规则待办，R6）"""
    from application.services.watch_engine.watch_loop_wiring import build_self_heal_service
    return build_self_heal_service().scan()


def _build_interval_jobs() -> List[IntervalJobDef]:
    return [
        IntervalJobDef('watch_heartbeat_patrol', _job_watch_heartbeat, float(_TICK_SEC),
                       '盯盘引擎心跳/影子超期巡检（进程外，1 分钟）',
                       _watch_heartbeat_job_enabled),
        IntervalJobDef('watch_sla_patrol', _job_watch_sla, float(_TICK_SEC),
                       '盯盘待办到期巡检（唯一收敛权威，1 分钟）',
                       _watch_loop_master_enabled),
        IntervalJobDef('watch_self_heal_scan', _job_watch_self_heal, _self_heal_interval_sec(),
                       '盯盘规则自愈扫描（抑噪 + 修规则待办）',
                       _watch_self_heal_job_enabled),
    ]


def interval_due(job: IntervalJobDef, now_monotonic: float,
                 last_run_monotonic: Optional[float], running: bool) -> bool:
    """周期任务到期判定（纯函数，可单测）：开关开 + 不在跑 + 距上次 ≥ interval。"""
    if not job.enabled():
        return False
    if running:
        return False
    if last_run_monotonic is None:
        return True
    return (now_monotonic - last_run_monotonic) >= job.interval_sec


def _run_interval_job(job: IntervalJobDef) -> None:
    # 2026-09-20（w-6faac762，错误事件 7f0819b1）：interval 路径在独立守护线程跑 handler
    # 但从不 close_session——handler 一旦触库（如 watch_sla 超时升级查 watch_receipts），
    # scoped_session 线程本地的 Session 挂着 autobegin 的开放事务随线程终存活，
    # 300s 后被 session_guard 判 session_leak_detected（44 次/2 天）。
    # 对齐 _run_job（日任务路径 L988 finally close_session）补齐同一清理。
    from infrastructure.persistence.orm import close_session
    try:
        result = job.handler()
        logger.info('interval_job_done', job=job.job_id, summary=_summarize_result(result))
    except Exception as e:  # noqa: BLE001 - 单任务失败不许打挂宿主循环
        logger.error('interval_job_failed', job=job.job_id, error=str(e))
    finally:
        try:
            close_session()
        except Exception:
            pass


def _dispatch_interval_jobs(now_monotonic: float, last: Dict[str, float],
                            running: set) -> None:
    """派发到期周期任务（每次宿主唤醒调用一次；线程内执行，不阻塞调度循环）"""
    for job in _build_interval_jobs():
        if not interval_due(job, now_monotonic, last.get(job.job_id),
                            job.job_id in running):
            continue
        last[job.job_id] = now_monotonic
        running.add(job.job_id)

        def _runner(_job=job):
            try:
                _run_interval_job(_job)
            finally:
                running.discard(_job.job_id)

        threading.Thread(target=_runner, name=f'interval-{job.job_id}',
                         daemon=True).start()


