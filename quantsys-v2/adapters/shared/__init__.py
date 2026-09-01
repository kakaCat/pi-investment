"""中立共享基础设施层 — 供 Flask 与 FastAPI 两个 API 层共用的框架无关代码

从 adapters/inbound/api/shared.py 解耦而来：服务单例、纯函数、任务状态、
文件存储、行情解析。两个 API 框架都从这里 import，互不依赖。
"""
from adapters.shared.json_helpers import (
    _safe_float, sanitize_for_json, to_camel_case, to_snake_case,
    convert_keys_to_camel, convert_keys_to_snake,
)
from adapters.shared.tasks import (
    acquire_task, release_task, get_running_tasks, get_running_tasks_snapshot,
)
from adapters.shared.stores import (
    _V2_ROOT, _PROJECT_ROOT_PATH, _LEGACY_QUANT_ROOT,
    _load_pipeline_runs, _save_pipeline_runs, _get_pipeline_run, _update_pipeline_run,
    _read_watchlist, _write_watchlist, _read_groups, _write_groups,
)
from adapters.shared.market_helpers import (
    _parse_sina_a_quote, _parse_sina_hk_quote, enrich_stock_data,
    signal_to_opportunity, _aggregate_weekly, _aggregate_monthly,
)

# 2026-08-25 修复（回测循环依赖）：原 `from adapters.shared.services import (ds, ...)` 
# 在 from-import 时立即对懒代理做 getattr，触发 ServiceFactory.get_strategy_code_service()
# 解析；而 StrategyCodeService.__init__ 里 get_data_provider_manager() 又会 import 本包
# ——形成 StrategyCodeService -> shared -> strategy_service -> StrategyCodeService 循环。
# 改为 PEP 562 模块级 __getattr__ 惰性转发，属性只在真正被使用时才解析。
_LAZY_SERVICE_NAMES = {
    'ds', 'strategy_service', 'stock_pool_service', 'scoring_service',
    'stock_scoring_service', 'sector_rotation_service', 'pool_validation_service',
    'pool_repo', 'strategy_repository', 'factor_adapter', 'ServiceFactory',
    'signal_repo', 'stock_repo', 'kline_repo', 'portfolio_repo', 'factor_repo', 'risk_repo', 'execution_repo', 'backtest_repo', 'simulation_repo',
}

# 某些名称在 services.py 中只有 getter 函数（如 get_portfolio_repo），
# 调用方期望直接拿到实例（如 shared.portfolio_repo），所以需要映射后调用。
_LAZY_GETTER_MAP = {
    'ds': 'get_data_service',
    'strategy_service': 'get_strategy_service',
    'stock_pool_service': 'get_stock_pool_service',
    'scoring_service': 'get_scoring_service',
    'stock_scoring_service': 'get_stock_scoring_service',
    'sector_rotation_service': 'get_sector_rotation_service',
    'pool_validation_service': 'get_pool_validation_service',
    'pool_repo': 'get_pool_repo',
    'strategy_repository': 'get_strategy_repository',
    'factor_adapter': 'get_factor_adapter',
    'ServiceFactory': 'get_service_factory',
    'signal_repo': 'get_signal_repo',
    'stock_repo': 'get_stock_repo',
    'kline_repo': 'get_kline_repo',
    'portfolio_repo': 'get_portfolio_repo',
    'factor_repo': 'get_factor_repo',
    'risk_repo': 'get_risk_repo',
    'execution_repo': 'get_execution_repo',
    'backtest_repo': 'get_backtest_repo',
    'simulation_repo': 'get_simulation_repo',
}


def __getattr__(name):
    if name in _LAZY_SERVICE_NAMES:
        from adapters.shared import services as _svc
        getter_name = _LAZY_GETTER_MAP.get(name)
        if getter_name:
            return getattr(_svc, getter_name)()
        return getattr(_svc, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
