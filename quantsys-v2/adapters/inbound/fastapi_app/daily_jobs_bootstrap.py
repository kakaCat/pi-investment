"""每日数据任务进程内宿主（2026-09-02）

背景：Agent OS 调度器中核心数据任务（kline_update / factor_compute_daily /
data_pipeline_daily / chip_distribution_update / data_quality_check）全部禁用，
数据新鲜度靠 agent 例程自觉——实测（2026-09-02）：601857 K线停在 8-27、
8-31 因子只覆盖 10 只、9-01 因子缺失。与 orchestrator/watch 的静默死亡
事故同根：**无宿主 = 会死**。

设计（与 orchestrator_bootstrap 同模式）：
- 唯一宿主 = FastAPI 5001 进程（lifespan 启动本模块守护线程）
- DB 落库 quant.inprocess_job_runs（job_id + run_date 唯一）：
  每日幂等（重启不重复跑）、漏跑补跑（当天已过点但未成功 → 立即补）、
  失败留痕（status=failed + error）
- 任务失败 → 飞书告警（不再静默死亡）
- freshness_guard 兜底：K线/因子滞后 >1 交易日 → 飞书告警
  （即使 pipeline 本身挂了也能被发现）

任务表（调整请同步文档 docs/guides/quantsys-v2-capability-assessment.md）：
- evening_pipeline   15:40 周一~五：K线全市场同步 → 因子全市场计算（串行链式）
- data_quality       17:15 周一~五：数据质量检查
- freshness_guard    17:55 周一~五：新鲜度巡检（兜底告警）
- chip_distribution  18:30 周一~五：筹码分布更新
- financial_statements 周六 20:00：季度财报更新
"""
import json
import threading
import time
from dataclasses import dataclass
from datetime import datetime, time as dtime
from typing import Any, Callable, Dict, List, Optional

import structlog

logger = structlog.get_logger(__name__)

_TICK_SEC = 60
_RUNNING_STALE_HOURS = 3  # running 状态超过 3 小时视为死亡，允许重跑

# ── 任务定义 ─────────────────────────────────────────────────


@dataclass
class JobDef:
    job_id: str
    run_at: dtime
    weekdays: tuple          # 0=周一 ... 6=周日
    handler: Callable[[], Dict[str, Any]]
    description: str


def _job_evening_pipeline() -> Dict[str, Any]:
    """K线全市场同步 → 因子全市场计算（链式：因子依赖当日K线）"""
    results: Dict[str, Any] = {}

    from infrastructure.jobs.kline_update_job import update_gem_klines
    logger.info("evening_pipeline: kline_sync start (scope=all)")
    results['kline_sync'] = update_gem_klines(scope='all', days=5)

    from application.services.scheduler_tasks import handle_factor_compute
    logger.info("evening_pipeline: factor_compute start (full market)")
    results['factor_compute'] = handle_factor_compute({'max_symbols': 6000})

    return results


def _job_data_quality() -> Dict[str, Any]:
    from application.services.scheduler_tasks import handle_data_quality_check
    return handle_data_quality_check()


def _job_chip_distribution() -> Dict[str, Any]:
    from infrastructure.jobs.chip_distribution_update_job import execute
    return execute()


def _job_financial_statements() -> Dict[str, Any]:
    from infrastructure.jobs.financial_statement_update_job import execute
    return execute()


def _last_trading_day(ref: datetime) -> str:
    """最近一个应为交易日的日期（周末排除法；节假日由告警人工复核）"""
    d = ref.date()
    # 收盘前（15:30 前）看前一工作日；收盘后看今天
    if ref.time() < dtime(15, 30) or d.weekday() >= 5:
        d = d - __import__('datetime').timedelta(days=1)
    while d.weekday() >= 5:
        d = d - __import__('datetime').timedelta(days=1)
    return d.strftime('%Y-%m-%d')


def _job_freshness_guard() -> Dict[str, Any]:
    """新鲜度巡检：K线/因子滞后于最近交易日 → 飞书告警"""
    from infrastructure.persistence.database.engine import get_engine
    from sqlalchemy import text

    expected = _last_trading_day(datetime.now())
    engine = get_engine()
    with engine.connect() as conn:
        kline_latest = conn.execute(
            text("SELECT max(trade_date) FROM quant.daily_klines")).scalar()
        factor_latest = conn.execute(
            text("SELECT max(factor_date) FROM quant.factor_values")).scalar()

    stale: List[str] = []
    if not kline_latest or str(kline_latest) < expected:
        stale.append(f"daily_klines 最新={kline_latest}（期望≥{expected}）")
    if not factor_latest or str(factor_latest) < expected:
        stale.append(f"factor_values 最新={factor_latest}（期望≥{expected}）")

    if stale:
        msg = ("🚨 数据新鲜度告警\n" + "\n".join(f"- {s}" for s in stale) +
               "\n请检查 evening_pipeline 运行状态（/api/jobs/inprocess/status）")
        _send_feishu(msg)
        return {'status': 'stale', 'stale': stale, 'expected': expected,
                'alert_sent': True}

    return {'status': 'fresh', 'expected': expected,
            'kline_latest': str(kline_latest), 'factor_latest': str(factor_latest)}


def _send_feishu(text: str) -> bool:
    """飞书告警（失败只记日志，不阻断任务流）"""
    try:
        from application.services.feishu_service import FeishuNotificationService
        return FeishuNotificationService().send_text(text)
    except Exception as e:
        logger.error("freshness/job alert feishu send failed", error=str(e))
        return False


JOBS: List[JobDef] = [
    JobDef('evening_pipeline', dtime(15, 40), (0, 1, 2, 3, 4),
           _job_evening_pipeline, 'K线全市场同步 → 因子全市场计算'),
    JobDef('data_quality', dtime(17, 15), (0, 1, 2, 3, 4),
           _job_data_quality, '数据质量检查'),
    JobDef('freshness_guard', dtime(17, 55), (0, 1, 2, 3, 4),
           _job_freshness_guard, 'K线/因子新鲜度巡检'),
    JobDef('chip_distribution', dtime(18, 30), (0, 1, 2, 3, 4),
           _job_chip_distribution, '筹码分布更新'),
    JobDef('financial_statements', dtime(20, 0), (5,),
           _job_financial_statements, '季度财报更新'),
]

# ── 运行状态表（幂等核心） ─────────────────────────────────────

_DDL = """
CREATE TABLE IF NOT EXISTS quant.inprocess_job_runs (
    job_id      text        NOT NULL,
    run_date    date        NOT NULL,
    status      text        NOT NULL,   -- running/success/failed
    started_at  timestamptz NOT NULL DEFAULT now(),
    finished_at timestamptz,
    result      jsonb,
    error       text,
    PRIMARY KEY (job_id, run_date)
)
"""


def _ensure_table() -> None:
    from infrastructure.persistence.database.engine import get_engine
    engine = get_engine()
    with engine.begin() as conn:
        conn.exec_driver_sql(_DDL)


def _get_run(job_id: str, run_date: str) -> Optional[Dict[str, Any]]:
    from infrastructure.persistence.database.engine import get_engine
    from sqlalchemy import text
    engine = get_engine()
    with engine.connect() as conn:
        row = conn.execute(text(
            "SELECT status, started_at FROM quant.inprocess_job_runs "
            "WHERE job_id=:j AND run_date=:d"
        ), {'j': job_id, 'd': run_date}).fetchone()
    if not row:
        return None
    return {'status': row[0], 'started_at': row[1]}


def _mark_running(job_id: str, run_date: str) -> None:
    from infrastructure.persistence.database.engine import get_engine
    from sqlalchemy import text
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO quant.inprocess_job_runs (job_id, run_date, status, started_at) "
            "VALUES (:j, :d, 'running', now()) "
            "ON CONFLICT (job_id, run_date) DO UPDATE "
            "SET status='running', started_at=now(), finished_at=NULL, error=NULL"
        ), {'j': job_id, 'd': run_date})


def _mark_done(job_id: str, run_date: str, status: str,
               result: Optional[Dict] = None, error: Optional[str] = None) -> None:
    from infrastructure.persistence.database.engine import get_engine
    from sqlalchemy import text
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text(
            "UPDATE quant.inprocess_job_runs "
            "SET status=:s, finished_at=now(), result=:r, error=:e "
            "WHERE job_id=:j AND run_date=:d"
        ), {'s': status, 'r': json.dumps(result, ensure_ascii=False, default=str) if result else None,
            'e': (error or '')[:1000] or None, 'j': job_id, 'd': run_date})


# ── 调度判定（纯函数，可单测） ──────────────────────────────────

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
    # failed：不自动重跑（等人工/告警），由 manual trigger 恢复
    return False


def _run_job(job: JobDef, run_date: str) -> None:
    """在独立线程执行一个任务（异常隔离 + 落库 + 告警）"""
    from infrastructure.persistence.orm import close_session
    try:
        _mark_running(job.job_id, run_date)
        logger.info("inprocess_job_start", job=job.job_id, date=run_date)
        result = job.handler()
        _mark_done(job.job_id, run_date, 'success', result=result)
        logger.info("inprocess_job_done", job=job.job_id, date=run_date)
    except Exception as e:
        logger.error("inprocess_job_failed", job=job.job_id, date=run_date,
                     error=str(e), exc_info=True)
        try:
            _mark_done(job.job_id, run_date, 'failed', error=str(e))
        except Exception:
            logger.error("inprocess_job_mark_failed_error", job=job.job_id)
        _send_feishu(f"🚨 每日任务失败：{job.job_id}\n{job.description}\n错误: {str(e)[:300]}")
    finally:
        # 与 orchestrator_bootstrap 同款连接治理：释放本线程的 scoped session
        try:
            close_session()
        except Exception:
            pass


# ── 宿主循环 ─────────────────────────────────────────────────

def _jobs_loop(stop_event: threading.Event) -> None:
    _ensure_table()
    while not stop_event.is_set():
        now = datetime.now()
        today = now.strftime('%Y-%m-%d')
        for job in JOBS:
            try:
                last = _get_run(job.job_id, today)
                if is_due(job, now, last):
                    threading.Thread(
                        target=_run_job, args=(job, today),
                        name=f"job-{job.job_id}", daemon=True,
                    ).start()
            except Exception as e:
                # 单任务调度异常不能杀死循环
                logger.error("inprocess_job_schedule_error", job=job.job_id, error=str(e))
        stop_event.wait(_TICK_SEC)


def start_daily_jobs(skip: bool = False) -> Optional[threading.Event]:
    """启动每日任务宿主线程。返回 stop_event（测试/关闭用）。"""
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
    """今日任务运行状态（巡检/排障用）"""
    from infrastructure.persistence.database.engine import get_engine
    from sqlalchemy import text
    _ensure_table()
    engine = get_engine()
    today = datetime.now().strftime('%Y-%m-%d')
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT job_id, status, started_at, finished_at, error "
            "FROM quant.inprocess_job_runs WHERE run_date=:d ORDER BY started_at"
        ), {'d': today}).fetchall()
    ran = {r[0]: {'status': r[1], 'started_at': str(r[2]),
                  'finished_at': str(r[3]) if r[3] else None,
                  'error': r[4]} for r in rows}
    return [
        {'job_id': j.job_id, 'description': j.description,
         'scheduled_at': j.run_at.strftime('%H:%M'),
         **ran.get(j.job_id, {'status': 'not_run', 'started_at': None,
                              'finished_at': None, 'error': None})}
        for j in JOBS
    ]
