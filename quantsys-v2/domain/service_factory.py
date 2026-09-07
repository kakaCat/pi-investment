# domain/service_factory.py
"""
领域服务工厂 - 创建和组装领域服务

负责创建领域服务实例并注入依赖。
"""
from typing import Optional
import structlog

from domain.accounts.services.account_service import AccountService
from domain.portfolio.services.position_service import PositionService
from domain.trading.services.order_service import OrderService

logger = structlog.get_logger(__name__)


class DomainServiceFactory:
    """领域服务工厂 - 单例模式"""
    
    _instance = None
    _account_service: Optional[AccountService] = None
    _position_service: Optional[PositionService] = None
    _order_service: Optional[OrderService] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def initialize(
        self,
        account_repo,
        position_repo,
        order_repo,
    ) -> None:
        """初始化领域服务
        
        Args:
            account_repo: IAccountRepository 实现
            position_repo: IPositionRepository 实现
            order_repo: IOrderRepository 实现
        """
        # 创建服务（按依赖顺序）
        self._account_service = AccountService(account_repo=account_repo)
        self._position_service = PositionService(position_repo=position_repo)
        self._order_service = OrderService(
            account_service=self._account_service,
            position_service=self._position_service,
            order_repo=order_repo,
        )
        
        logger.info("DomainServiceFactory initialized")
    
    @property
    def account_service(self) -> AccountService:
        """获取账户服务"""
        if self._account_service is None:
            raise RuntimeError("DomainServiceFactory not initialized. Call initialize() first.")
        return self._account_service
    
    @property
    def position_service(self) -> PositionService:
        """获取持仓服务"""
        if self._position_service is None:
            raise RuntimeError("DomainServiceFactory not initialized. Call initialize() first.")
        return self._position_service
    
    @property
    def order_service(self) -> OrderService:
        """获取订单服务"""
        if self._order_service is None:
            raise RuntimeError("DomainServiceFactory not initialized. Call initialize() first.")
        return self._order_service
    
    def reset(self) -> None:
        """重置工厂（用于测试）"""
        self._account_service = None
        self._position_service = None
        self._order_service = None
        DomainServiceFactory._instance = None


# 全局单例
domain_service_factory = DomainServiceFactory()
