"""daily_jobs 包（拆分自 daily_jobs_bootstrap.py）。

对外仍由 adapters/inbound/fastapi_app/daily_jobs_bootstrap.py 转发，
故既有 `from ...daily_jobs_bootstrap import JOBS` 等导入路径不受影响。
"""
from adapters.inbound.fastapi_app.daily_jobs.defs import (  # noqa: F401
    JobDef,
    IntervalJobDef,
    _TICK_SEC,
    _RUNNING_STALE_HOURS,
    _FAILED_RETRY_HOURS,
    _ORPHAN_GRACE_MINUTES,
    _CATCHUP_WINDOW_DAYS,
    logger,
)
from adapters.inbound.fastapi_app.daily_jobs.alerting import (  # noqa: F401
    _send_feishu,
    _job_failure_watch,
    _summarize_result,
)
from adapters.inbound.fastapi_app.daily_jobs.pipeline import (  # noqa: F401
    _probe_kline_sources,
    _kline_coverage,
    _job_evening_pipeline,
    _job_chip_distribution,
    _job_financial_statements,
    _job_evolution_fitness,
    _job_freshness_guard,
    _last_trading_day,
    KLINE_COVERAGE_FRESH_THRESHOLD,
)
from adapters.inbound.fastapi_app.daily_jobs.pools import (  # noqa: F401
    _refresh_all_dynamic_pools,
    _job_pool_daily_refresh,
    _job_pool_weekly_review,
)
from adapters.inbound.fastapi_app.daily_jobs.health import (  # noqa: F401
    _job_watch_rule_health,
    _event_md,
    _job_event_calendar_check,
    _EVENT_TYPE_LABELS,
)
from adapters.inbound.fastapi_app.daily_jobs.interval import (  # noqa: F401
    _env_flag,
    _self_heal_interval_sec,
    _watch_loop_master_enabled,
    _watch_heartbeat_job_enabled,
    _watch_self_heal_job_enabled,
    _job_watch_heartbeat,
    _job_watch_sla,
    _job_watch_self_heal,
    _build_interval_jobs,
    interval_due,
    _run_interval_job,
    _dispatch_interval_jobs,
    DEFAULT_SELF_HEAL_INTERVAL_SEC,
)
from adapters.inbound.fastapi_app.daily_jobs.runtime import (  # noqa: F401
    _ensure_table,
    _get_run,
    _mark_running,
    _mark_done,
    is_due,
    _run_job,
    catchup_due,
    _recent_failed_run,
    _reap_orphan_runs,
    _jobs_loop,
    start_daily_jobs,
    trigger_job,
    list_today_runs,
)
from adapters.inbound.fastapi_app.daily_jobs.registry import (  # noqa: F401
    JOBS,
)
