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
from adapters.inbound.fastapi_app.daily_jobs.alerting import _format_elapsed, _send_feishu, _summarize_result  # noqa: F401
from adapters.inbound.fastapi_app.daily_jobs.interval import _dispatch_interval_jobs  # noqa: F401
from adapters.inbound.fastapi_app.daily_jobs.defs import _CATCHUP_WINDOW_DAYS, _FAILED_RETRY_HOURS, _ORPHAN_GRACE_MINUTES, _RUNNING_STALE_HOURS, _TICK_SEC, logger  # noqa: F401
# 交易日门（REQ-261005203907-2b8c · FR-1/FR-3）：只在交易日执行的任务在休市日整段跳过。
# 模块级导入是有意的——用例需按"桩打在被调函数所在模块"的纪律 patch `runtime.skip_non_trading_day`。
from adapters.inbound.fastapi_app.daily_jobs.gate import skip_non_trading_day  # noqa: F401
# 通知判据（REQ-261006165125-23a9 · FR-1/FR-2）："本次没有事情发生"（no_event / no_output）时，
# 开始与完成两条飞书都不发——判据唯一入口在 notify_policy，本模块不再自己判断。
from adapters.inbound.fastapi_app.daily_jobs import notify_policy  # noqa: F401
from adapters.inbound.fastapi_app.daily_jobs.alerting import format_completion  # noqa: F401

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


def _run_job(job: JobDef, run_date: str, manual: bool = False) -> None:
    """在独立线程执行一个任务（异常隔离 + 落库 + 告警 + 生命周期通知）

    `manual=True`（= `trigger_job` 手动触发）时**始终**回一条结果消息（FR-6）——
    人主动点的运行必须有回执，否则"点了没反应"；定时路径（含跨日补跑）用默认 `False`。
    """
    from infrastructure.persistence.orm import close_session
    from infrastructure.monitoring.business_metrics import (
        scheduler_job_runs_total,
        scheduler_job_duration_seconds,
    )
    
    t0 = time.time()
    # 超阈值提示的定时器句柄（FR-3）：在 finally 里取消——任务在阈值内结束就一条消息都不发。
    running_timer: Optional[threading.Timer] = None
    try:
        _mark_running(job.job_id, run_date)
        logger.info("inprocess_job_start", job=job.job_id, date=run_date)

        # ── 交易日门（REQ-261005203907-2b8c · FR-1/FR-3）────────────────────────────
        # 早退点**必须**在下面那条 _send_feishu 之前：休市日跳过的语义是「留痕 + 不打扰」，
        # 通知一旦发出去就白做（2026-10-05 实测：空跑 22 秒 + 开始/完成两条飞书）。
        # 门本身是 fail-open 的（见 daily_jobs/gate.py）：只有"日历明确答休市且未降级"才跳过，
        # 任何降级/门自身异常 → 照跑（宁可多跑一次，也不许静默停摆）。
        gate_info: Dict[str, Any] = {}
        if job.trading_days_only:
            skip, gate_info = skip_non_trading_day()
            if skip:
                skipped_result = {
                    'skipped': True,
                    'reason': f"非交易日（{gate_info['day']}）：{gate_info['reason']}",
                    'trading_day': gate_info,
                }
                _mark_done(job.job_id, run_date, 'skipped', result=skipped_result)
                scheduler_job_runs_total.labels(job=job.job_id, status='skipped').inc()
                # 刻意不观测 scheduler_job_duration_seconds：跳过不是"执行耗时"，
                # 观测进去会污染耗时直方图的低分位（设计决策，非疏漏）。
                logger.info("inprocess_job_skipped", job=job.job_id, date=run_date,
                            source=gate_info['source'], degraded=gate_info['degraded'])
                return

        # ── 通知判据（REQ-261006165125-23a9 · FR-2/FR-3）──────────────────────────
        # 默认**不再**无条件发开始消息："无事"的任务连开始消息都不该发（用户裁定 A），
        # 而"这次会不会有事"在 handler 返回之前无从得知。故默认路径拆成两步：
        #   ① 现在只 arm 一个超阈值提示——跑太久才说"我还在跑"（信息量为真的那一条）；
        #   ② 结果出来后由 should_send_completion 决定发不发完成消息。
        # 回滚态（DAILY_JOBS_NOTIFY_NOOP=true）才恢复"立即发开始消息"的旧行为。
        if notify_policy.should_send_start():
            _send_feishu(f"▶️ 每日任务开始：{job.job_id}\n{job.description}\n时间: {datetime.now().strftime('%H:%M')}", 
                        webhook_url=job.webhook_url)
        running_timer = _arm_running_notice(job)
        result = job.handler()

        # 照跑路径也把判定来源带进 result：**降级必须可见**（日历不可用却照跑，要让人看得出来）
        if job.trading_days_only:
            if isinstance(result, dict) and 'trading_day' not in result:
                result['trading_day'] = gate_info
            if gate_info.get('degraded'):
                logger.warning("inprocess_job_trading_day_degraded", job=job.job_id, date=run_date,
                               source=gate_info.get('source'))

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
                f"（handler 未抛异常但返回失败态）错误: {inner_error[:300]}",
                webhook_url=job.webhook_url
            )
            return

        elapsed = time.time() - t0
        
        _mark_done(job.job_id, run_date, 'success', result=result)
        scheduler_job_runs_total.labels(job=job.job_id, status='success').inc()
        scheduler_job_duration_seconds.labels(job=job.job_id, phase='execution').observe(elapsed)
        
        logger.info("inprocess_job_done", job=job.job_id, date=run_date)
        # REQ-261005210015-1603 t-4b35ba（FR-1 / FR-3）＋ REQ-261006165125-23a9（FR-2/FR-5/FR-6/FR-7）：
        # ① 耗时按量级显示——1.21 秒的活曾被印成「0.0 分钟」，收消息的人分不清"真快"还是"没干活"（不变）；
        # ② 完成消息**只在"有事"时**发：handler 自报 no_output=True 或 status ∈ {no_event, no_op} 时静默
        #    （用户裁定 A / D-2）。人工触发与回滚态例外（FR-6 / FR-7）。
        #    **只静默外发、不静默留痕**：台账仍写 success——判 failed 会牵动 2h 失败重试与跨日补跑链。
        # ③ 旧口径（零产出改 ⚠️ 语气但**仍要发**）保留为回滚态与人工触发可达的分支，文本逐字不变。
        #    与本函数上方的交易日门跳过分支（REQ-261005203907-2b8c）互不相交：跳过路径在 return 处结束，
        #    不会走到本行；本卡不改其分支，也不改 _mark_done 语义。
        no_output = isinstance(result, dict) and result.get('no_output') is True
        if notify_policy.should_send_completion(result=result, manual=manual):
            _send_feishu(format_completion(
                job.job_id, job.description, elapsed, result,
                manual=manual,
                warn_no_output=notify_policy.notify_noop_enabled() and no_output,
            ), webhook_url=job.webhook_url)
        else:
            # 静默必须**可解释**：日后有人问"今天怎么没消息"，日志能直接回答（design/data-model.md §5）
            logger.info("inprocess_job_notify_skipped", job=job.job_id, date=run_date,
                        reason="no_op", manual=manual)
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
        _send_feishu(f"🚨 每日任务失败：{job.job_id}\n{job.description}\n错误: {str(e)[:300]}", 
                    webhook_url=job.webhook_url)
    finally:
        # 任务在阈值内结束 → 取消定时器 → "仍在运行"提示不会发（FR-3）
        if running_timer is not None:
            try:
                running_timer.cancel()
            except Exception:  # noqa: BLE001 - 取消失败不影响任务终态与台账
                logger.error("inprocess_job_running_notice_cancel_error", job=job.job_id)
        try:
            close_session()
        except Exception:
            pass


def _arm_running_notice(job: JobDef) -> Optional[threading.Timer]:
    """arm 一条「⏳ 每日任务仍在运行」提示（REQ-261006165125-23a9 · FR-3）。

    为什么用 Timer 而不是在 handler 前后 sleep：handler 是**同步**调用，宿主线程必须等它；
    Timer 是独立 daemon 线程，到点才发消息，不阻塞任务本身，也不新增线程池。

    阈值 <= 0 = 显式关闭该提示（`notify_policy.running_notice_seconds`）→ 返回 None。

    ⚠️ 回调 `_send_running_notice` **必须住在本模块**：它读的是 `runtime._send_feishu`
    这个全局名。搬到别的模块会让打桩点漂移（`CLAUDE.md` 通知守卫一节），
    测试与 notify-guard 会同时失配。
    """
    secs = notify_policy.running_notice_seconds()
    if secs <= 0:
        return None
    timer = threading.Timer(secs, _send_running_notice, args=(job.job_id, job.description, secs, job.webhook_url))
    timer.daemon = True
    timer.start()
    return timer


def _send_running_notice(job_id: str, description: str, secs: float, webhook_url: Optional[str] = None) -> None:
    """超阈值提示回调（FR-3）。

    自己吞异常并记日志：timer 线程里抛出的异常会被 Python 静默丢弃（只打 traceback），
    既没人消费、也不该影响任务终态——所以这里必须显式接住。
    """
    try:
        _send_feishu(f"⏳ 每日任务仍在运行：{job_id}\n{description}\n已跑 {_format_elapsed(secs)}", 
                    webhook_url=webhook_url)
    except Exception as e:  # noqa: BLE001
        logger.error("inprocess_job_running_notice_error", job=job_id, error=str(e))


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
    # manual=True（FR-6）：人主动点的运行必须有回执——即使本次"无事"也回一条，否则"点了没反应"
    threading.Thread(target=_run_job, args=(job, today), kwargs={'manual': True},
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


