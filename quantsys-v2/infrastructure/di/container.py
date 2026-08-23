"""
依赖注入容器

统一管理所有服务的生命周期和依赖关系，替代 shared.py 中的全局变量。

使用方法:
    # 在 Flask app 中
    from infrastructure.di.container import Container

    app = Flask(__name__)
    container = Container()
    app.container = container

    # 在路由中使用
    service = current_app.container.stock_pool_service()
"""
from dependency_injector import containers, providers

from application.services.data_service import DataService
from application.services.strategy_code_service import StrategyCodeService
from application.services.stock_pool_service import StockPoolService
from application.services.opportunity_scoring_service import OpportunityScoringService
from application.services.sector_rotation_service import SectorRotationService
from application.services.pool_validation_service import PoolValidationService
from application.services.stock_scoring_service import StockScoringService
from adapters.outbound.repositories import StockPoolORMRepository, StrategyORMRepository
from infrastructure.quantlib.adapters import get_factor_adapter


class Container(containers.DeclarativeContainer):
    """
    依赖注入容器

    生命周期说明:
    - Singleton: 单例模式，整个应用生命周期只创建一次
    - Factory: 工厂模式，每次调用都创建新实例
    - ThreadLocalSingleton: 线程本地单例
    """

    # ==================== 配置 ====================
    config = providers.Configuration()

    # ==================== Repositories ====================
    # 数据访问层 - 使用单例模式（连接池共享）

    pool_repository = providers.Singleton(
        StockPoolORMRepository
    )

    strategy_repository = providers.Singleton(
        StrategyORMRepository
    )

    # ==================== Core Services ====================
    # 核心服务 - 使用单例模式（有状态服务）

    data_service = providers.Singleton(
        DataService
    )

    strategy_service = providers.Singleton(
        StrategyCodeService
    )

    factor_adapter = providers.Singleton(
        get_factor_adapter
    )

    # ==================== Business Services ====================
    # 业务服务 - 使用工厂模式（无状态服务，支持并发）

    opportunity_scoring_service = providers.Factory(
        OpportunityScoringService,
        kline_repo=data_service.provided.kline,
        stock_repo=data_service.provided.stock,
        factor_adapter=factor_adapter,
    )

    stock_scoring_service = providers.Factory(
        StockScoringService,
        data_service=data_service,
    )

    sector_rotation_service = providers.Factory(
        SectorRotationService,
        stock_repo=data_service.provided.stock,
        kline_repo=data_service.provided.kline,
    )

    stock_pool_service = providers.Factory(
        StockPoolService,
        stock_repo=data_service.provided.stock,
        pool_repo=pool_repository,
        scoring_service=opportunity_scoring_service,
    )

    pool_validation_service = providers.Factory(
        PoolValidationService,
        pool_repo=pool_repository,
        strategy_repo=strategy_repository,
    )

    # ==================== 游戏智能服务 ====================
    # 新增的博弈分析服务

    # opponent_behavior_service = providers.Factory(
    #     OpponentBehaviorService,
    #     data_service=data_service,
    # )

    # battlefield_assessor = providers.Factory(
    #     BattlefieldAssessor,
    #     data_service=data_service,
    # )

    # manipulation_detector = providers.Factory(
    #     ManipulationDetector,
    #     data_service=data_service,
    # )


def get_container() -> Container:
    """
    获取容器实例（用于非 Flask 环境）

    Returns:
        Container: 依赖注入容器实例
    """
    return Container()
