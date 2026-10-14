"""调度任务处理器 —— **转发壳**（2026-10-01 · REQ-261001145152-3982 t-686185）

原 1607 行单文件已按职责拆入 `scheduler_tasks_*.py` 一族模块（data / signals / reports /
factors / training_guard / models / strategy / runtime / registry）。本文件只做转发，
**保持既有导入路径不变**；实现与签名逐字未改。
"""
from application.services.scheduler_tasks_data import (  # noqa: F401
    handle_data_quality_check,
    handle_data_update,
    handle_financial_data_update,
    handle_market_style_update,
)
from application.services.scheduler_tasks_signals import (  # noqa: F401
    DEFAULT_SCAN_STRATEGY_IDS,
    _is_pool_refresh_due,
    _scan_pool_signals_by_name,
    handle_pool_refresh_daily,
    handle_signal_execution_daily,
    handle_signal_generate,
)
from application.services.scheduler_tasks_reports import (  # noqa: F401
    handle_backtest_run,
    handle_benchmark_run,
    handle_chan_knowledge_distill,
    handle_chan_scan,
    handle_performance_report,
    handle_report_daily,
)
from application.services.scheduler_tasks_factors import (  # noqa: F401
    MIN_BARS_FOR_FACTORS,
    _NON_EQUITY_NAME_KEYWORDS,
    _filter_factor_universe,
    handle_factor_compute,
)
from application.services.scheduler_tasks_training_guard import (  # noqa: F401
    RETRAIN_MIN_ACCURACY,
    RETRAIN_MIN_AGE_DAYS,
    _age_needs_retrain,
    _check_train_needed,
    _model_age_days,
    _release_thread_session,
)
from application.services.scheduler_tasks_models import (  # noqa: F401
    _try_switch_model,
    handle_model_train,
    handle_model_train_auto,
)
from application.services.scheduler_tasks_strategy import (  # noqa: F401
    handle_agent_reminder,
    handle_market_scan_preopen,
    handle_strategy_discover_weekly,
    handle_strategy_rotation,
    handle_strategy_validate_daily,
    handle_v13_daily_check,
)
from application.services.scheduler_tasks_runtime import (  # noqa: F401
    handle_intraday_monitor,
    handle_orchestrator_tick,
    handle_pending_orders_match,
)
from application.services.scheduler_tasks_registry import (  # noqa: F401
    _TASK_HANDLERS,
    get_task_handler,
    list_available_commands,
)
from application.services.scheduler_tasks_common import (  # noqa: F401
    logger,
)

__all__ = [
    "handle_data_quality_check",
    "handle_data_update",
    "handle_financial_data_update",
    "handle_market_style_update",
    "DEFAULT_SCAN_STRATEGY_IDS",
    "_is_pool_refresh_due",
    "_scan_pool_signals_by_name",
    "handle_pool_refresh_daily",
    "handle_signal_execution_daily",
    "handle_signal_generate",
    "handle_backtest_run",
    "handle_benchmark_run",
    "handle_chan_knowledge_distill",
    "handle_chan_scan",
    "handle_performance_report",
    "handle_report_daily",
    "MIN_BARS_FOR_FACTORS",
    "_NON_EQUITY_NAME_KEYWORDS",
    "_filter_factor_universe",
    "handle_factor_compute",
    "RETRAIN_MIN_ACCURACY",
    "RETRAIN_MIN_AGE_DAYS",
    "_age_needs_retrain",
    "_check_train_needed",
    "_model_age_days",
    "_release_thread_session",
    "_try_switch_model",
    "handle_model_train",
    "handle_model_train_auto",
    "handle_agent_reminder",
    "handle_market_scan_preopen",
    "handle_strategy_discover_weekly",
    "handle_strategy_rotation",
    "handle_strategy_validate_daily",
    "handle_v13_daily_check",
    "handle_intraday_monitor",
    "handle_orchestrator_tick",
    "handle_pending_orders_match",
    "_TASK_HANDLERS",
    "get_task_handler",
    "list_available_commands",
    "logger",
]
