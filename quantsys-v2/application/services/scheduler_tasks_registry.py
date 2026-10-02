"""任务注册表 _TASK_HANDLERS 与查询入口（命令名 → 处理器）

2026-10-01（REQ-261001145152-3982 t-686185）：由 scheduler_tasks.py（原 1607 行）
机械拆分而来；函数体与签名**逐字未改**，原模块保留为转发壳，既有导入路径不受影响。
"""
from domain.ports import IKlineRepository, IStockRepository, IStrategyRepository
import structlog
from typing import Dict, Any, Callable
from datetime import datetime, date, timedelta
import json
from application.services.scheduler_tasks_data import handle_data_quality_check, handle_data_update, handle_financial_data_update, handle_market_style_update  # noqa: F401
from application.services.scheduler_tasks_factors import handle_factor_compute  # noqa: F401
from application.services.scheduler_tasks_models import handle_model_train, handle_model_train_auto  # noqa: F401
from application.services.scheduler_tasks_reports import handle_backtest_run, handle_benchmark_run, handle_chan_knowledge_distill, handle_chan_scan, handle_performance_report, handle_report_daily  # noqa: F401
from application.services.scheduler_tasks_runtime import handle_intraday_monitor, handle_orchestrator_tick  # noqa: F401
from application.services.scheduler_tasks_signals import handle_pool_refresh_daily, handle_signal_execution_daily, handle_signal_generate  # noqa: F401
from application.services.scheduler_tasks_strategy import handle_agent_reminder, handle_market_scan_preopen, handle_strategy_discover_weekly, handle_strategy_rotation, handle_strategy_validate_daily, handle_v13_daily_check  # noqa: F401

_TASK_HANDLERS: Dict[str, Callable] = {
    "data_quality_check": handle_data_quality_check,
    "data_update": handle_data_update,
    "signal_generate": handle_signal_generate,
    "pool_refresh_daily": handle_pool_refresh_daily,
    "signal_execution_daily": handle_signal_execution_daily,
    "report_daily": handle_report_daily,
    "backtest_run": handle_backtest_run,
    "strategy_backtest": handle_backtest_run,  # 别名
    "factor_compute": handle_factor_compute,
    "model_train": handle_model_train,
    "benchmark_run": handle_benchmark_run,
    "market_style_update": handle_market_style_update,
    "v13_daily_check": handle_v13_daily_check,
    # 新增 - 从旧调度器迁移
    "financial_data_update": handle_financial_data_update,
    "market_scan_preopen": handle_market_scan_preopen,
    "strategy_validate_daily": handle_strategy_validate_daily,
    "strategy_discover_weekly": handle_strategy_discover_weekly,
    # Agent相关
    "agent_reminder": handle_agent_reminder,
    # 自主轮转系统
    "orchestrator_tick": handle_orchestrator_tick,
    "intraday_monitor": handle_intraday_monitor,
    "performance_report": handle_performance_report,
    "strategy_rotation": handle_strategy_rotation,
    # 缠论学习闭环
    "chan_scan": handle_chan_scan,
    "chan_knowledge_distill": handle_chan_knowledge_distill,
    "model_train_auto": handle_model_train_auto,
}

def get_task_handler(command: str) -> Callable:
    """获取任务处理器

    Args:
        command: 任务命令名称

    Returns:
        任务处理函数

    Raises:
        ValueError: 如果命令不存在
    """
    handler = _TASK_HANDLERS.get(command)
    if handler is None:
        available = ', '.join(_TASK_HANDLERS.keys())
        raise ValueError(
            f"Unknown task command: {command!r}. "
            f"Available commands: {available}"
        )
    return handler


def list_available_commands() -> list:
    """列出所有可用的任务命令"""
    return list(_TASK_HANDLERS.keys())


