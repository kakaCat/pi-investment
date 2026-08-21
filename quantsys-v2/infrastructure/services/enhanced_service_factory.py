"""
增强版服务工厂 - 支持依赖声明和自动解析

P2-1 Phase 1: Dependency Injection Standardization
提供自动依赖解析、生命周期管理、服务注册等高级特性
"""
import logging
from typing import Type, TypeVar, Callable, Dict, Any, Optional, List
from enum import Enum
import inspect
from functools import wraps

logger = logging.getLogger(__name__)

T = TypeVar('T')


class ServiceLifecycle(Enum):
    """服务生命周期"""
    SINGLETON = "singleton"  # 全局单例
    SCOPED = "scoped"        # 请求作用域（未来FastAPI集成用）
    TRANSIENT = "transient"  # 每次创建新实例


class ServiceDescriptor:
    """服务描述符 - 描述如何创建和管理服务"""

    def __init__(
        self,
        service_type: Type,
        implementation_type: Optional[Type] = None,
        factory: Optional[Callable] = None,
        lifecycle: ServiceLifecycle = ServiceLifecycle.SINGLETON,
        dependencies: Optional[List[Type]] = None
    ):
        """
        Args:
            service_type: 服务接口类型（Port接口或抽象类）
            implementation_type: 实现类型（Adapter或具体服务类）
            factory: 工厂函数（如果提供则优先使用）
            lifecycle: 生命周期
            dependencies: 显式声明的依赖（如果不提供则自动从构造函数推断）
        """
        self.service_type = service_type
        self.implementation_type = implementation_type or service_type
        self.factory = factory
        self.lifecycle = lifecycle
        self.dependencies = dependencies or []

        # 如果没有显式声明依赖，从构造函数签名推断
        if not self.dependencies and not self.factory:
            self.dependencies = self._infer_dependencies()

    def _infer_dependencies(self) -> List[Type]:
        """从构造函数签名推断依赖"""
        try:
            sig = inspect.signature(self.implementation_type.__init__)
            deps = []
            for param_name, param in sig.parameters.items():
                if param_name == 'self':
                    continue
                if param.annotation != inspect.Parameter.empty:
                    # 跳过字符串类型注解（forward reference）
                    if isinstance(param.annotation, str):
                        logger.warning(
                            f"Skipping string annotation '{param.annotation}' in {self.implementation_type.__name__}. "
                            "Use explicit dependencies parameter or resolve forward references."
                        )
                        continue
                    deps.append(param.annotation)
            return deps
        except Exception as e:
            logger.warning(f"Failed to infer dependencies for {self.implementation_type}: {e}")
            return []


class EnhancedServiceFactory:
    """增强版服务工厂

    特性：
    1. 自动依赖解析 - 根据构造函数签名自动注入依赖
    2. 生命周期管理 - 支持 Singleton/Scoped/Transient
    3. 服务注册 - 允许运行时注册新服务
    4. 循环依赖检测 - 防止无限递归
    """

    _descriptors: Dict[Type, ServiceDescriptor] = {}
    _singletons: Dict[Type, Any] = {}
    _resolution_stack: List[Type] = []  # 用于检测循环依赖

    @classmethod
    def register(
        cls,
        service_type: Type[T],
        implementation_type: Optional[Type[T]] = None,
        factory: Optional[Callable[[], T]] = None,
        lifecycle: ServiceLifecycle = ServiceLifecycle.SINGLETON,
        dependencies: Optional[List[Type]] = None
    ) -> None:
        """注册服务

        Args:
            service_type: 服务接口类型
            implementation_type: 实现类型（如果为None则使用service_type）
            factory: 工厂函数（如果提供则优先使用）
            lifecycle: 生命周期
            dependencies: 显式声明的依赖

        Example:
            # 注册接口到实现的映射
            EnhancedServiceFactory.register(
                IStockRepository,
                StockORMRepository,
                lifecycle=ServiceLifecycle.SINGLETON
            )

            # 注册带显式依赖的服务
            EnhancedServiceFactory.register(
                StockPoolService,
                dependencies=[IStockRepository, IDataService]
            )

            # 注册使用工厂函数的服务
            EnhancedServiceFactory.register(
                DataService,
                factory=lambda: DataService()
            )
        """
        descriptor = ServiceDescriptor(
            service_type=service_type,
            implementation_type=implementation_type,
            factory=factory,
            lifecycle=lifecycle,
            dependencies=dependencies
        )
        cls._descriptors[service_type] = descriptor
        logger.info(f"Registered service: {service_type.__name__} -> {descriptor.implementation_type.__name__} ({lifecycle.value})")

    @classmethod
    def resolve(cls, service_type: Type[T]) -> T:
        """解析服务实例

        Args:
            service_type: 要解析的服务类型

        Returns:
            服务实例

        Raises:
            ValueError: 服务未注册或存在循环依赖
        """
        # 检查循环依赖
        if service_type in cls._resolution_stack:
            cycle = ' -> '.join(t.__name__ for t in cls._resolution_stack) + f' -> {service_type.__name__}'
            raise ValueError(f"Circular dependency detected: {cycle}")

        # 获取服务描述符
        descriptor = cls._descriptors.get(service_type)
        if not descriptor:
            raise ValueError(f"Service not registered: {service_type.__name__}")

        # Singleton: 如果已创建则直接返回
        if descriptor.lifecycle == ServiceLifecycle.SINGLETON:
            if service_type in cls._singletons:
                return cls._singletons[service_type]

        # 开始解析
        cls._resolution_stack.append(service_type)
        try:
            instance = cls._create_instance(descriptor)

            # Singleton: 缓存实例
            if descriptor.lifecycle == ServiceLifecycle.SINGLETON:
                cls._singletons[service_type] = instance

            return instance
        finally:
            cls._resolution_stack.pop()

    @classmethod
    def _create_instance(cls, descriptor: ServiceDescriptor) -> Any:
        """创建服务实例"""
        # 如果提供了工厂函数，优先使用
        if descriptor.factory:
            return descriptor.factory()

        # 解析所有依赖
        resolved_deps = []
        for dep_type in descriptor.dependencies:
            dep_instance = cls.resolve(dep_type)
            resolved_deps.append(dep_instance)

        # 创建实例
        try:
            instance = descriptor.implementation_type(*resolved_deps)
            logger.debug(f"Created instance of {descriptor.implementation_type.__name__}")
            return instance
        except Exception as e:
            logger.error(f"Failed to create instance of {descriptor.implementation_type.__name__}: {e}")
            raise

    @classmethod
    def is_registered(cls, service_type: Type) -> bool:
        """检查服务是否已注册"""
        return service_type in cls._descriptors

    @classmethod
    def reset(cls) -> None:
        """重置所有服务（用于测试）"""
        cls._descriptors.clear()
        cls._singletons.clear()
        cls._resolution_stack.clear()
        logger.info("Enhanced service factory reset")

    @classmethod
    def get_registered_services(cls) -> List[str]:
        """获取所有已注册服务的名称"""
        return [desc.service_type.__name__ for desc in cls._descriptors.values()]


def inject(*dependencies: Type):
    """依赖注入装饰器 - 用于标注服务的依赖

    Example:
        @inject(IStockRepository, IDataService)
        class StockPoolService:
            def __init__(self, stock_repo: IStockRepository, data_service: IDataService):
                self.stock_repo = stock_repo
                self.data_service = data_service
    """
    def decorator(cls):
        # 注册服务时会自动使用这些依赖信息
        original_init = cls.__init__

        @wraps(original_init)
        def wrapped_init(self, *args, **kwargs):
            if len(args) == 0 and len(kwargs) == 0:
                # 如果没有传参数，尝试自动解析
                resolved = [EnhancedServiceFactory.resolve(dep) for dep in dependencies]
                original_init(self, *resolved)
            else:
                original_init(self, *args, **kwargs)

        cls.__init__ = wrapped_init
        cls._injected_dependencies = dependencies
        return cls

    return decorator


# 提供便捷的注册函数
def register_service(service_type: Type[T], **kwargs) -> Type[T]:
    """装饰器形式的服务注册

    Example:
        @register_service(IStockRepository)
        class StockORMRepository(IStockRepository):
            pass
    """
    def decorator(implementation_type: Type[T]) -> Type[T]:
        EnhancedServiceFactory.register(
            service_type=service_type,
            implementation_type=implementation_type,
            **kwargs
        )
        return implementation_type
    return decorator


__all__ = [
    'EnhancedServiceFactory',
    'ServiceLifecycle',
    'ServiceDescriptor',
    'inject',
    'register_service',
]
