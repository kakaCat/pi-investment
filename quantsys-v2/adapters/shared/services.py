"""共享服务访问层（框架无关）— 从 adapters/inbound/api/shared.py 解耦而来

提供统一的服务访问入口，供 Flask 与 FastAPI 两个 API 层共用。
所有 getter 函数都是普通函数，延迟加载由 adapters.shared.__init__.__getattr__ 处理。
"""


def get_service_factory():
    from infrastructure.services.service_factory import ServiceFactory
    return ServiceFactory


def get_data_service():
    return get_service_factory().get_data_service()

def get_strategy_service():
    return get_service_factory().get_strategy_code_service()

def get_stock_pool_service():
    return get_service_factory().get_stock_pool_service()

def get_scoring_service():
    return get_service_factory().get_scoring_service()

def get_stock_scoring_service():
    return get_service_factory().get_stock_scoring_service()

def get_sector_rotation_service():
    return get_service_factory().get_sector_rotation_service()

def get_pool_validation_service():
    return get_service_factory().get_pool_validation_service()

def get_technical_analysis_service():
    return get_service_factory().get_technical_analysis_service()

def get_risk_service():
    return get_service_factory().get_risk_service()

def get_data_quality_service():
    return get_service_factory().get_data_quality_service()

# ── Repository getter 函数 ──

def get_pool_repo():
    from adapters.outbound.repositories import StockPoolORMRepository
    return StockPoolORMRepository()

def get_strategy_repository():
    from adapters.outbound.repositories import StrategyORMRepository
    return StrategyORMRepository()

def get_signal_repo():
    return get_service_factory().get_signal_repository()

def get_stock_repo():
    return get_service_factory().get_stock_repository()

def get_kline_repo():
    return get_service_factory().get_kline_repository()

def get_portfolio_repo():
    return get_service_factory().get_portfolio_repository()

def get_factor_repo():
    return get_service_factory().get_factor_repository()

def get_risk_repo():
    return get_service_factory().get_risk_repository()

def get_execution_repo():
    from adapters.outbound.repositories.signal_execution_repository import SignalExecutionORMRepository
    return SignalExecutionORMRepository()

def get_backtest_repo():
    from adapters.outbound.repositories.backtest_repository import BacktestORMRepository
    return BacktestORMRepository()

def get_simulation_repo():
    from adapters.outbound.repositories.simulation_repository import SimulationORMRepository
    return SimulationORMRepository()

def get_factor_adapter():
    from adapters.outbound.datasources.providers.quantlib import get_factor_adapter as _get
    return _get()

# ── P1-5 新增服务 getter 函数 ──

def get_order_service():
    return get_service_factory().get_order_service()

def get_account_trading_service():
    return get_service_factory().get_account_trading_service()

def get_market_data_service():
    return get_service_factory().get_market_data_service()

def get_hk_market_data_service():
    return get_service_factory().get_hk_market_data_service()

def get_stock_data_service():
    return get_service_factory().get_stock_data_service()

def get_lhb_service():
    return get_service_factory().get_lhb_service()

def get_dividend_service():
    return get_service_factory().get_dividend_service()

def get_diagnosis_service():
    return get_service_factory().get_diagnosis_service()

def get_chan_service():
    return get_service_factory().get_chan_service()

def get_backtest_engine():
    return get_service_factory().get_backtest_engine()

def get_performance_analysis_service():
    return get_service_factory().get_performance_analysis_service()

def get_data_async_service():
    return get_service_factory().get_data_async_service()

def get_market_data_async_service():
    return get_service_factory().get_market_data_async_service()

def get_decision_service():
    return get_service_factory().get_decision_service()

def get_knowledge_service():
    return get_service_factory().get_knowledge_service()

def get_session_service():
    return get_service_factory().get_session_service()

def get_realtime_signal_service():
    return get_service_factory().get_realtime_signal_service()

def get_simulation_service():
    return get_service_factory().get_simulation_service()

def get_stock_pool_async_service():
    return get_service_factory().get_stock_pool_async_service()

def get_signal_test_log():
    return get_service_factory().get_signal_test_log()

def get_strategy_service_v2():
    return get_service_factory().get_strategy_service()

def get_strategy_execution_service():
    return get_service_factory().get_strategy_execution_service()

def get_strategy_validation_service():
    return get_service_factory().get_strategy_validation_service()

def get_strategy_optimizer():
    return get_service_factory().get_strategy_optimizer()

def get_strategy_evolution_service():
    """策略进化引擎（RFC 012 P1）——from adapters.shared.services import
    strategy_evolution_service 经模块 __getattr__ 惰性转发到本 getter。"""
    return get_service_factory().get_strategy_evolution_service()

def get_game_alert_service():
    return get_service_factory().get_game_alert_service()


ds = get_data_service
strategy_service = get_strategy_service
stock_pool_service = get_stock_pool_service
scoring_service = get_scoring_service
stock_scoring_service = get_stock_scoring_service
sector_rotation_service = get_sector_rotation_service
pool_validation_service = get_pool_validation_service
pool_repo = get_pool_repo
strategy_repository = get_strategy_repository
factor_adapter = get_factor_adapter
decision_service = get_decision_service
simulation_service = get_simulation_service
stock_data_service = get_stock_data_service
signal_repo = get_signal_repo
stock_repo = get_stock_repo
kline_repo = get_kline_repo
portfolio_repo = get_portfolio_repo
factor_repo = get_factor_repo
risk_repo = get_risk_repo
execution_repo = get_execution_repo
backtest_repo = get_backtest_repo
simulation_repo = get_simulation_repo


# ────────────────────────────────────────────────────────────
# 2026-09-01 修复：模块级 __getattr__ 惰性兜底裸服务名
#
# 背景：55c0ce73 rewrite 后本文件只剩 getter 函数，但 22 处路由模块仍以
# `from adapters.shared.services import backtest_engine` 等裸名导入——
# 全部 ImportError → 19 个路由模块注册失败（strategy_list/alerts/events/
# trade-verify/risk 等业务面残缺）。
#
# 本 __getattr__ 把裸名惰性转发到对应 get_<name>() 调用（PEP 562）：
#   from adapters.shared.services import backtest_engine
#   → 等价于 get_backtest_engine() 的返回实例
# 惰性保证不在 import 时触发 ServiceFactory 解析（避免回测循环依赖复发，
# 见 adapters/shared/__init__.py 注释）。
# ────────────────────────────────────────────────────────────

# 裸名与 getter 名不一致的特例
_LAZY_NAME_ALIASES = {
    'ds': 'get_data_service',
}


class _LazyServiceProxy:
    """惰性服务代理：from-import 时只拿到代理，首次真正调用才解析服务。

    必要性：PEP 562 __getattr__ 在 from-import 时被立即调用，若直接返回
    get_xxx() 的解析结果，会在应用启动早期（ServiceFactory/ORM 未就绪）
    触发深层依赖解析失败（实测：IStockRepository not registered）。
    代理把解析推迟到首个方法/属性访问——此时应用通常已就绪。
    """

    __slots__ = ('_getter', '_resolved', '_lock')

    def __init__(self, getter):
        object.__setattr__(self, '_getter', getter)
        object.__setattr__(self, '_resolved', None)

    def _resolve(self):
        resolved = object.__getattribute__(self, '_resolved')
        if resolved is None:
            resolved = object.__getattribute__(self, '_getter')()
            object.__setattr__(self, '_resolved', resolved)
        return resolved

    def __getattr__(self, item):
        return getattr(self._resolve(), item)

    def __call__(self, *args, **kwargs):
        return self._resolve()(*args, **kwargs)

    def __repr__(self):
        return f'<LazyServiceProxy {object.__getattribute__(self, "_getter").__name__}>'


def __getattr__(name):
    getter_name = _LAZY_NAME_ALIASES.get(name, f'get_{name}')
    getter = globals().get(getter_name)
    if callable(getter):
        return _LazyServiceProxy(getter)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
