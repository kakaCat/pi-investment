"""
简化版依赖注入容器

避开类型注解问题，只包含核心可用服务。
暂时跳过有类型问题的服务，等待修复后再添加。
"""
from dependency_injector import containers, providers


class SimpleContainer(containers.DeclarativeContainer):
    """
    简化版容器 - 只包含无类型问题的服务

    待修复类型注解后，逐步迁移到完整的 Container
    """

    # ==================== 配置 ====================
    config = providers.Configuration()

    # ==================== 暂时使用 shared.py 的服务 ====================
    # 作为过渡方案，从 shared.py 获取已初始化的服务

    @staticmethod
    def _get_shared_service(service_name):
        """从 shared.py 获取服务（过渡方案）"""
        from adapters.inbound.api.shared import (
            ds,
            strategy_service,
            stock_pool_service,
            pool_validation_service,
            scoring_service,
            stock_scoring_service,
            sector_rotation_service,
        )

        services = {
            'data_service': ds,
            'strategy_service': strategy_service,
            'stock_pool_service': stock_pool_service,
            'pool_validation_service': pool_validation_service,
            'scoring_service': scoring_service,
            'stock_scoring_service': stock_scoring_service,
            'sector_rotation_service': sector_rotation_service,
        }
        return services.get(service_name)

    # ==================== 服务提供者 ====================
    # 使用 Callable provider 包装 shared.py 的服务

    data_service = providers.Callable(
        lambda: SimpleContainer._get_shared_service('data_service')
    )

    strategy_service = providers.Callable(
        lambda: SimpleContainer._get_shared_service('strategy_service')
    )

    stock_pool_service = providers.Callable(
        lambda: SimpleContainer._get_shared_service('stock_pool_service')
    )

    pool_validation_service = providers.Callable(
        lambda: SimpleContainer._get_shared_service('pool_validation_service')
    )

    scoring_service = providers.Callable(
        lambda: SimpleContainer._get_shared_service('scoring_service')
    )

    stock_scoring_service = providers.Callable(
        lambda: SimpleContainer._get_shared_service('stock_scoring_service')
    )

    sector_rotation_service = providers.Callable(
        lambda: SimpleContainer._get_shared_service('sector_rotation_service')
    )


def get_simple_container() -> SimpleContainer:
    """
    获取简化版容器实例

    Returns:
        SimpleContainer: 简化版依赖注入容器
    """
    return SimpleContainer()
