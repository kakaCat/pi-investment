"""
服务工厂 - 替代shared.py的全局单例模式

提供服务实例的统一获取接口，支持延迟初始化和单例模式
"""
import logging
from typing import Optional
from functools import lru_cache

logger = logging.getLogger(__name__)


class ServiceFactory:
    """服务工厂类

    使用单例模式管理服务实例，替代shared.py的全局变量
    """

    _instances = {}

    @classmethod
    @lru_cache(maxsize=1)
    def get_data_service(cls):
        """获取DataService实例"""
        if 'data_service' not in cls._instances:
            from application.services.data_service import DataService
            cls._instances['data_service'] = DataService()
            logger.info("DataService initialized")
        return cls._instances['data_service']

    @classmethod
    @lru_cache(maxsize=1)
    def get_strategy_code_service(cls):
        """获取StrategyCodeService实例"""
        if 'strategy_code_service' not in cls._instances:
            from application.services.strategy_code_service import StrategyCodeService
            cls._instances['strategy_code_service'] = StrategyCodeService()
            logger.info("StrategyCodeService initialized")
        return cls._instances['strategy_code_service']

    @classmethod
    @lru_cache(maxsize=1)
    def get_stock_pool_service(cls):
        """获取StockPoolService实例"""
        if 'stock_pool_service' not in cls._instances:
            from application.services.stock_pool_service import StockPoolService
            from adapters.outbound.repositories import StockPoolORMRepository
            from application.services.opportunity_scoring_service import OpportunityScoringService
            from adapters.outbound.datasources.providers.quantlib import get_factor_adapter

            ds = cls.get_data_service()
            pool_repo = StockPoolORMRepository()
            factor_adapter = get_factor_adapter()
            scoring_service = OpportunityScoringService(ds.kline, ds.stock, factor_adapter)

            cls._instances['stock_pool_service'] = StockPoolService(
                ds.stock,
                pool_repo=pool_repo,
                scoring_service=scoring_service
            )
            logger.info("StockPoolService initialized")
        return cls._instances['stock_pool_service']

    @classmethod
    @lru_cache(maxsize=1)
    def get_scoring_service(cls):
        """获取OpportunityScoringService实例"""
        if 'scoring_service' not in cls._instances:
            from application.services.opportunity_scoring_service import OpportunityScoringService
            from adapters.outbound.datasources.providers.quantlib import get_factor_adapter

            ds = cls.get_data_service()
            factor_adapter = get_factor_adapter()
            cls._instances['scoring_service'] = OpportunityScoringService(
                ds.kline, ds.stock, factor_adapter
            )
            logger.info("OpportunityScoringService initialized")
        return cls._instances['scoring_service']

    @classmethod
    @lru_cache(maxsize=1)
    def get_stock_scoring_service(cls):
        """获取StockScoringService实例"""
        if 'stock_scoring_service' not in cls._instances:
            from application.services.stock_scoring_service import StockScoringService
            ds = cls.get_data_service()
            cls._instances['stock_scoring_service'] = StockScoringService(ds)
            logger.info("StockScoringService initialized")
        return cls._instances['stock_scoring_service']

    @classmethod
    @lru_cache(maxsize=1)
    def get_sector_rotation_service(cls):
        """获取SectorRotationService实例"""
        if 'sector_rotation_service' not in cls._instances:
            from application.services.sector_rotation_service import SectorRotationService
            ds = cls.get_data_service()
            cls._instances['sector_rotation_service'] = SectorRotationService(
                ds.stock, ds.kline
            )
            logger.info("SectorRotationService initialized")
        return cls._instances['sector_rotation_service']

    @classmethod
    @lru_cache(maxsize=1)
    def get_pool_validation_service(cls):
        """获取PoolValidationService实例"""
        if 'pool_validation_service' not in cls._instances:
            from application.services.pool_validation_service import PoolValidationService
            from adapters.outbound.repositories import StockPoolORMRepository, StrategyORMRepository

            pool_repo = StockPoolORMRepository()
            strategy_repo = StrategyORMRepository()
            cls._instances['pool_validation_service'] = PoolValidationService(
                pool_repo=pool_repo,
                strategy_repo=strategy_repo
            )
            logger.info("PoolValidationService initialized")
        return cls._instances['pool_validation_service']

    @classmethod
    @lru_cache(maxsize=1)
    def get_scheduler_config_service(cls):
        """获取SchedulerConfigService实例"""
        if 'scheduler_config_service' not in cls._instances:
            from application.services.scheduler_config_service import SchedulerConfigService
            cls._instances['scheduler_config_service'] = SchedulerConfigService()
            logger.info("SchedulerConfigService initialized")
        return cls._instances['scheduler_config_service']

    @classmethod
    @lru_cache(maxsize=1)
    def get_condition_monitor_service(cls):
        """获取ConditionMonitorService实例"""
        if 'condition_monitor_service' not in cls._instances:
            from application.services.condition_monitor import ConditionMonitorService
            cls._instances['condition_monitor_service'] = ConditionMonitorService()
            logger.info("ConditionMonitorService initialized")
        return cls._instances['condition_monitor_service']

    @classmethod
    @lru_cache(maxsize=1)
    def get_technical_analysis_service(cls):
        """获取TechnicalAnalysisService实例"""
        if 'technical_analysis_service' not in cls._instances:
            from application.services.technical_analysis_service import TechnicalAnalysisService
            cls._instances['technical_analysis_service'] = TechnicalAnalysisService()
            logger.info("TechnicalAnalysisService initialized")
        return cls._instances['technical_analysis_service']

    @classmethod
    @lru_cache(maxsize=1)
    def get_risk_service(cls):
        """获取RiskService实例"""
        if 'risk_service' not in cls._instances:
            from application.services.risk_service import RiskService
            cls._instances['risk_service'] = RiskService()
            logger.info("RiskService initialized")
        return cls._instances['risk_service']

    @classmethod
    @lru_cache(maxsize=1)
    def get_data_quality_service(cls):
        """获取DataQualityService实例"""
        if 'data_quality_service' not in cls._instances:
            from application.services.data_quality_service import DataQualityService
            cls._instances['data_quality_service'] = DataQualityService()
            logger.info("DataQualityService initialized")
        return cls._instances['data_quality_service']

    @classmethod
    @lru_cache(maxsize=1)
    def get_strategy_rotation_service(cls):
        """获取StrategyRotationService实例"""
        if 'strategy_rotation_service' not in cls._instances:
            from application.services.strategy_rotation_service import StrategyRotationService
            cls._instances['strategy_rotation_service'] = StrategyRotationService()
            logger.info("StrategyRotationService initialized")
        return cls._instances['strategy_rotation_service']

    @classmethod
    def reset_all(cls):
        """重置所有服务实例（用于测试）"""
        cls._instances.clear()
        cls.get_data_service.cache_clear()
        cls.get_strategy_code_service.cache_clear()
        cls.get_stock_pool_service.cache_clear()
        cls.get_scoring_service.cache_clear()
        cls.get_stock_scoring_service.cache_clear()
        cls.get_sector_rotation_service.cache_clear()
        cls.get_pool_validation_service.cache_clear()
        cls.get_scheduler_config_service.cache_clear()
        cls.get_condition_monitor_service.cache_clear()
        cls.get_technical_analysis_service.cache_clear()
        cls.get_risk_service.cache_clear()
        cls.get_data_quality_service.cache_clear()
        cls.get_strategy_rotation_service.cache_clear()
        logger.info("All services reset")


# 提供兼容旧代码的全局访问方式
def get_data_service():
    """获取DataService实例（兼容接口）"""
    return ServiceFactory.get_data_service()


def get_strategy_service():
    """获取StrategyCodeService实例（兼容接口）"""
    return ServiceFactory.get_strategy_code_service()


def get_stock_pool_service():
    """获取StockPoolService实例（兼容接口）"""
    return ServiceFactory.get_stock_pool_service()


# 导出所有服务获取函数
__all__ = [
    'ServiceFactory',
    'get_data_service',
    'get_strategy_service',
    'get_stock_pool_service',
]
