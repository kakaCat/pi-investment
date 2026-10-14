"""运行状态、到期判定与宿主循环（拆分自 daily_jobs_bootstrap.py）

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
from adapters.inbound.fastapi_app.daily_jobs.defs import JobDef  # noqa: F401
from adapters.inbound.fastapi_app.daily_jobs.alerting import _send_feishu, _summarize_result  # noqa: F401
from adapters.inbound.fastapi_app.daily_jobs.interval import _dispatch_interval_jobs  # noqa: F401
from adapters.inbound.fastapi_app.daily_jobs.defs import _CATCHUP_WINDOW_DAYS, _FAILED_RETRY_HOURS, _ORPHAN_GRACE_MINUTES, _RUNNING_STALE_HOURS, _TICK_SEC, logger  # noqa: F401

def _ensure_table() -> None:
    from infrastructure.persistence.database.engine import get_engine
    from infrastructure.persistence.orm.models import InProcessJobRun

    InProcessJobRun.__table__.create(bind=get_engine(), checkfirst=True)


def _get_run(job_id: str, run_date: str) -> Optional[Dict[str, Any]]:
    """取某任务某日的运行态（仓储化，2026-09-14，REQ-24e15d B4-c4）。"""
    from adapters.outbound.repositories.job_run_repository import JobRunRepository
    return JobRunRepository().get_run(job_id, run_date)


def _mark_running(job_id: str, run_date: str) -> None:
    """置 running（UPSERT）。仓储化，2026-09-14，REQ-24e15d B4-c4。"""
    from adapters.outbound.repositories.job_run_repository import JobRunRepository
    JobRunRepository().mark_running(job_id, run_date)


def _mark_done(job_id: str, run_date: str, status: str,
               result: Optional[Dict] = None, error: Optional[str] = None) -> None:
    """写终态（仓储化，2026-09-14，REQ-24e15d B4-c4）。

    json.dumps(..., default=str) 这个兜底已下沉到仓储里（见 JobRunRepository.mark_done），
    调用方不再自己序列化 —— 否则两处序列化口径会漂。
    """
    from adapters.outbound.repositories.job_run_repository import JobRunRepository
    JobRunRepository().mark_done(job_id, run_date, status, result=result, error=error)


def is_due(job: JobDef, now: datetime, last_run: Optional[Dict[str, Any]]) -> bool:
    """任务当前是否应运行

    规则：今天是对应工作日 且 已过运行点 且 今天没有 success/running（未僵死）记录。
    漏跑补跑：晚间重启进程时，已过点但未跑的任务会立即补跑。
    """
    if now.weekday() not in job.weekdays:
        return False
    if now.time() < job.run_at:
        return False
    if last_run is None:
        return True
    if last_run['status'] == 'success':
        return False
    if last_run['status'] == 'running':
        # 僵死判定：running 超过阈值视为死亡，允许重跑
        started = last_run.get('started_at')
        if started is not None:
            # 用传入的 now（而非真实当前时间）计算年龄——可测试且语义一致
            now_aware = now.replace(tzinfo=started.tzinfo) if started.tzinfo else now
            age_hours = (now_aware - started).total_seconds() / 3600
            return age_hours > _RUNNING_STALE_HOURS
        return False
    if last_run['status'] == 'failed':
        # 失败冷却 2h 后自动重试（探活门控下失败 pass 秒级结束，重试成本低；
        # 跨自然日由新日期的空记录重新计时，不会无限重试）
        started = last_run.get('started_at')
        if started is not None:
            now_aware = now.replace(tzinfo=started.tzinfo) if started.tzinfo else now
            age_hours = (now_aware - started).total_seconds() / 3600
            return age_hours > _FAILED_RETRY_HOURS
        return False
    return False


def _run_job(job: JobDef, run_date: str) -> None:
    """在独立线程执行一个任务（异常隔离 + 落库 + 告警 + 生命周期通知）"""
    from infrastructure.persistence.orm import close_session
    from infrastructure.monitoring.business_metrics import (
        scheduler_job_runs_total,
        scheduler_job_duration_seconds,
    )
    
    t0 = time.time()
    try:
        _mark_running(job.job_id, run_date)
        logger.info("inprocess_job_start", job=job.job_id, date=run_date)
        _send_feishu(f"▶️ 每日任务开始：{job.job_id}\n{job.description}\n时间: {datetime.now().strftime('%H:%M')}")
        result = job.handler()

        # 结果契约（2026-09-13，w-32314d00）：**只看有没有抛异常 = 假成功工厂**。
        # 实证（近 30 天 quant.inprocess_job_runs）：evening_pipeline 09-03/04/07/08/09
        # 五天记 success，结果里却是 {'kline_sync': {'status':'error', 'error':
        # 'column "updated_at" does not exist'}}；financial_statements 09-05 记 success
        # 但结果是 {'success': False}。APScheduler 路径早有 classify_job_result 判内层失败，
        # 宿主这一条漏了 → 现在统一走 find_result_failure（含嵌套下钻），失败即记 failed。
        inner_error = find_result_failure(result)
        if inner_error:
            elapsed = time.time() - t0
            logger.error("inprocess_job_inner_failed", job=job.job_id, date=run_date,
                         error=inner_error)
            scheduler_job_runs_total.labels(job=job.job_id, status='failed').inc()
            scheduler_job_duration_seconds.labels(job=job.job_id, phase='execution').observe(elapsed)
            try:
                _mark_done(job.job_id, run_date, 'failed', result=result, error=inner_error)
            except Exception:
                logger.error("inprocess_job_mark_failed_error", job=job.job_id)
            _send_feishu(
                f"🚨 每日任务失败：{job.job_id}\n{job.description}\n"
                f"（handler 未抛异常但返回失败态）错误: {inner_error[:300]}"
            )
            return

        elapsed = time.time() - t0
        
        _mark_done(job.job_id, run_date, 'success', result=result)
        scheduler_job_runs_total.labels(job=job.job_id, status='success').inc()
        scheduler_job_duration_seconds.labels(job=job.job_id, phase='execution').observe(elapsed)
        
        logger.info("inprocess_job_done", job=job.job_id, date=run_date)
        elapsed_min = elapsed / 60
        summary = _summarize_result(result)
        _send_feishu(
            f"✅ 每日任务完成：{job.job_id}\n{job.description}\n"
            f"耗时: {elapsed_min:.1f} 分钟" + (f"\n{summary}" if summary else '')
        )
    except Exception as e:
        elapsed = time.time() - t0
        logger.error("inprocess_job_failed", job=job.job_id, date=run_date,
                     error=str(e), exc_info=True)
        scheduler_job_runs_total.labels(job=job.job_id, status='failed').inc()
        scheduler_job_duration_seconds.labels(job=job.job_id, phase='execution').observe(elapsed)
        try:
            _mark_done(job.job_id, run_date, 'failed', error=str(e))
        except Exception:
            logger.error("inprocess_job_mark_failed_error", job=job.job_id)
        _send_feishu(f"🚨 每日任务失败：{job.job_id}\n{job.description}\n错误: {str(e)[:300]}")
    finally:
        try:
            close_session()
        except Exception:
            pass


def catchup_due(job: JobDef, now: datetime, has_recent_failure: bool) -> bool:
    """跨日补跑判定（纯函数，便于单测）。

    2026-09-13（w-32314d00）：is_due 只认"今天是不是它的排班日"——周六任务周六失败后
    要等到下周六才重试（一周空窗）。用户要求"需要自动重跑"，故对**失败过**的任务
    在窗口期内允许跨日补跑一次：非排班日 + 已过该任务当天的执行时刻 + 近 3 天内有 failed。
    """
    if now.weekday() in job.weekdays:
        return False           # 排班日交给 is_due（含 2h 失败重试）
    if now.time() < job.run_at:
        return False           # 未到该任务当天的执行时刻
    return bool(has_recent_failure)


def _recent_failed_run(job_id: str, days: int = _CATCHUP_WINDOW_DAYS) -> Optional[Dict[str, Any]]:
    """近 N 天内最近一条 failed 记录（跨日补跑判定用）。仓储化，2026-09-14，REQ-24e15d B4-c4。"""
    from adapters.outbound.repositories.job_run_repository import JobRunRepository
    return JobRunRepository().get_recent_failed(job_id, days=days)


def _reap_orphan_runs(now: Optional[datetime] = None) -> int:
    """把上一进程遗留的 running 行判死（启动时调用一次）。

    2026-09-13（w-32314d00）：is_due 只查**当天**的 run 行、_job_failure_watch 只看 failed，
    于是"进程被杀/任务僵死在 running"的行既不会被重跑也不会被告警——永久隐形。
    实证：financial_statements 2026-09-12 23:00 起 running 12h+（正是财报数据超期的那个 job）。
    本函数在宿主启动时把早于宽限期的 running 行标 failed，使其进入失败巡检（看门狗可见 +
    次日 freshness_guard 的失败残留告警），并允许 is_due 按失败冷却重跑。
    """
    # 取数/写入收口到仓储（2026-09-14，REQ-24e15d B4-c4）：
    # 原先在同一个 engine.begin() 里先 SELECT 再条件 UPDATE。现在两步各自走仓储。
    # 事务语义差异：原实现是"查到才更新"且两步同事务；现在 list 与 update 分两次提交。
    # 对判死场景无差异 —— 两次之间的新增 running 行会被下一次启动/巡检看到，
    # 且 UPDATE 自身带同样的 status/started_at 条件（不会误伤新行）。
    from adapters.outbound.repositories.job_run_repository import JobRunRepository
    now = now or datetime.now()
    cutoff = now - timedelta(minutes=_ORPHAN_GRACE_MINUTES)
    repo = JobRunRepository()
    rows = repo.list_orphan_runs(cutoff)
    if rows:
        repo.mark_orphans_failed(cutoff)
    if rows:
        # 2026-09-13（w-32314d00，事件 c0e69791）：这里**刻意用 warning 而非 error**——
        # 孤儿 running 是"已被本函数发现并收尾"的既成事实，不是当前进程的失败：
        #   · 事故记录已落在 quant.inprocess_job_runs（status=failed + error 原因），
        #     并可被 _job_failure_watch 巡检（次日 freshness_guard 飞书告警）；
        #   · 用 error 级会在每次实例重启时生成一条需要人工闭环的 error_events 卡片，
        #     把"已经处理好的事"变成待办噪声（实测 11:37 重启即产生 c0e69791）。
        # 一条聚合 warning 带明细，日志里照样看得见，但不再制造待闭环事件。
        logger.warning(
            "inprocess_job_orphans_reaped",
            count=len(rows),
            jobs=[f"{job_id}@{run_date}" for job_id, run_date in rows],
        )
    return len(rows)


def _jobs_loop(stop_event: threading.Event) -> None:
    # 惰性导入：registry 依赖各作业模块，模块级导入会成环
    from adapters.inbound.fastapi_app.daily_jobs.registry import JOBS
    _ensure_table()
    try:
        _reap_orphan_runs()   # 明细 warning 由 _reap_orphan_runs 内部输出（聚合一条）
    except Exception as e:  # 判死失败不能阻断宿主
        logger.error("inprocess_job_orphan_reap_error", error=str(e))
    interval_last: Dict[str, float] = {}
    interval_running: set = set()
    while not stop_event.is_set():
        now = datetime.now()
        today = now.strftime('%Y-%m-%d')
        for job in JOBS:
            try:
                last = _get_run(job.job_id, today)
                catchup = False
                if not is_due(job, now, last) and last is None:
                    # 跨日补跑（2026-09-13，w-32314d00）：失败过的任务不必等下一个排班日。
                    # 只在"今天还没有任何记录"时判定，跑完即写今天的行 → 天然每天最多一次。
                    try:
                        recent = _recent_failed_run(job.job_id)
                    except Exception as e:
                        recent = None
                        logger.error("inprocess_job_catchup_query_error", job=job.job_id, error=str(e))
                    catchup = catchup_due(job, now, recent is not None)
                    if catchup:
                        logger.warning("inprocess_job_catchup", job=job.job_id,
                                       description=job.description, run_date=today)
                if is_due(job, now, last) or catchup:
                    threading.Thread(
                        target=_run_job, args=(job, today),
                        name=f"job-{job.job_id}", daemon=True,
                    ).start()
            except Exception as e:
                # 单任务调度异常不能杀死循环
                logger.error("inprocess_job_schedule_error", job=job.job_id, error=str(e))
        # 进程外周期任务（REQ-c9f899 t12）：与每日任务共用宿主线程，但独立于 JobDef 幂等模型
        try:
            _dispatch_interval_jobs(time.monotonic(), interval_last, interval_running)
        except Exception as e:  # noqa: BLE001 - 派发异常不许打挂循环
            logger.error("interval_job_dispatch_error", error=str(e))
        stop_event.wait(_TICK_SEC)


def start_daily_jobs(skip: bool = False) -> Optional[threading.Event]:
    """启动每日任务宿主线程。返回 stop_event（测试/关闭用）。"""
    # 惰性导入：registry 依赖各作业模块，模块级导入会成环
    from adapters.inbound.fastapi_app.daily_jobs.registry import JOBS
    if skip:
        return None
    stop = threading.Event()
    t = threading.Thread(target=_jobs_loop, args=(stop,),
                         name='daily-jobs', daemon=True)
    t.start()
    logger.info("✅ daily-jobs host thread started", jobs=[j.job_id for j in JOBS])
    return stop


def trigger_job(job_id: str, force: bool = False) -> Dict[str, Any]:
    """手动触发（运维/补跑用）。force=True 忽略当日已有记录。"""
    # 惰性导入：registry 依赖各作业模块，模块级导入会成环
    from adapters.inbound.fastapi_app.daily_jobs.registry import JOBS
    job = next((j for j in JOBS if j.job_id == job_id), None)
    if not job:
        return {'success': False, 'error': f'未知任务: {job_id}',
                'available': [j.job_id for j in JOBS]}
    today = datetime.now().strftime('%Y-%m-%d')
    last = _get_run(job_id, today)
    if not force and last and last['status'] in ('running', 'success'):
        return {'success': False,
                'error': f"今日已有记录（{last['status']}），force=true 可强制重跑"}
    threading.Thread(target=_run_job, args=(job, today),
                     name=f"job-{job_id}-manual", daemon=True).start()
    return {'success': True, 'message': f'{job_id} 已触发（后台运行）'}


def list_today_runs() -> List[Dict[str, Any]]:
    """今日任务运行状态（巡检/排障用）。仓储化，2026-09-14，REQ-24e15d B4-c4。"""
    # 惰性导入：registry 依赖各作业模块，模块级导入会成环
    from adapters.inbound.fastapi_app.daily_jobs.registry import JOBS
    from adapters.outbound.repositories.job_run_repository import JobRunRepository
    _ensure_table()
    ran = JobRunRepository().map_by_date()
    return [
        {'job_id': j.job_id, 'description': j.description,
         'scheduled_at': j.run_at.strftime('%H:%M'),
         **ran.get(j.job_id, {'status': 'not_run', 'started_at': None,
                              'finished_at': None, 'error': None})}
        for j in JOBS
    ]


