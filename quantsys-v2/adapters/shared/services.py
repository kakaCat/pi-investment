"""共享服务实例（框架无关）— 从 adapters/inbound/api/shared.py 解耦而来

服务单例与 repository 实例，供 Flask 与 FastAPI 两个 API 层共用。
"""
from infrastructure.services.service_factory import ServiceFactory

# ── 服务实例（使用工厂模式） ──
ds = ServiceFactory.get_data_service()
strategy_service = ServiceFactory.get_strategy_code_service()
stock_pool_service = ServiceFactory.get_stock_pool_service()
scoring_service = ServiceFactory.get_scoring_service()
stock_scoring_service = ServiceFactory.get_stock_scoring_service()
sector_rotation_service = ServiceFactory.get_sector_rotation_service()
pool_validation_service = ServiceFactory.get_pool_validation_service()

# Repository 实例
from adapters.outbound.repositories import StockPoolORMRepository, StrategyORMRepository
pool_repo = StockPoolORMRepository()
strategy_repository = StrategyORMRepository()

# 因子适配器
from domain.quantlib.adapters import get_factor_adapter
factor_adapter = get_factor_adapter()

__all__ = [
    'ds', 'strategy_service', 'stock_pool_service', 'pool_repo',
    'pool_validation_service', 'factor_adapter', 'scoring_service',
    'stock_scoring_service', 'sector_rotation_service', 'strategy_repository',
    'ServiceFactory',
]
