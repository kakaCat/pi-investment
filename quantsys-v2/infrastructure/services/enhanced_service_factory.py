"""
增强版服务工厂 - 支持依赖声明和自动解析

P2-1 Phase 1: Dependency Injection Standardization
提供自动依赖解析、生命周期管理、服务注册等高级特性

P2-3: Config-Driven Integration
支持从配置文件加载和注册服务
"""
import logging
from typing import Type, TypeVar, Callable, Dict, Any, Optional, List, Union
from enum import Enum
import inspect
from functools import wraps
import importlib

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
                    # 跳过 Optional/Union 类型注解（如 Optional[List]）——它们不是可注入服务
                    # 默认值参数（providers=None 等）不应被当作服务依赖推断
                    origin = getattr(param.annotation, '__origin__', None)
                    if origin is Union or origin is Optional:
                        logger.debug(
                            f"Skipping Optional/Union annotation '{param.annotation}' in "
                            f"{self.implementation_type.__name__} (param={param_name})"
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
                dependencies=[IStockRepository, IKlineRepository]
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

    # ── P2-3: 配置驱动集成 ──

    @classmethod
    def register_from_config(cls, config: 'ServicesConfig') -> None:
        """从配置对象注册所有服务

        Args:
            config: ServicesConfig 配置对象

        P2-3: 支持从配置文件批量注册服务
        """
        from infrastructure.config.models import ServicesConfig

        merged_services = config.get_merged_services()

        logger.info(f"Registering {len(merged_services)} services from config (environment: {config.current_environment})")

        for service_name, service_config in merged_services.items():
            try:
                cls._register_service_from_config(service_name, service_config)
            except Exception as e:
                logger.error(f"Failed to register service '{service_name}' from config: {e}")
                # 继续注册其他服务

        logger.info("Config-driven service registration completed")

    @classmethod
    def _register_service_from_config(cls, service_name: str, service_config: 'ServiceConfig') -> None:
        """从单个服务配置注册服务

        Args:
            service_name: 服务名称
            service_config: 服务配置对象
        """
        from infrastructure.config.models import ServiceConfig

        # 1. 解析生命周期
        lifecycle_map = {
            'singleton': ServiceLifecycle.SINGLETON,
            'transient': ServiceLifecycle.TRANSIENT,
            'scoped': ServiceLifecycle.SCOPED,
        }
        lifecycle = lifecycle_map.get(service_config.lifecycle, ServiceLifecycle.SINGLETON)

        # 2. 确定服务类型和实现类型
        service_type = None
        implementation_type = None
        factory_func = None

        # 情况1: 使用工厂函数
        if service_config.factory:
            factory_func = cls._load_callable(service_config.factory)
            # 工厂函数模式：service_type 从 class_path 或 interface 推断
            if service_config.class_path:
                service_type = cls._load_class(service_config.class_path)
            elif service_config.interface:
                service_type = cls._load_class(service_config.interface)
            else:
                logger.warning(f"Service '{service_name}' has factory but no class_path or interface, skipping")
                return

        # 情况2: 接口-实现模式
        elif service_config.interface and service_config.implementation:
            service_type = cls._load_class(service_config.interface)
            implementation_type = cls._load_class(service_config.implementation)

        # 情况3: 直接类路径
        elif service_config.class_path:
            service_type = cls._load_class(service_config.class_path)
            implementation_type = service_type

        else:
            logger.warning(f"Service '{service_name}' has invalid config, skipping")
            return

        # 3. 处理依赖
        # 依赖配置格式: {param_name: dependency_service_name}
        # 需要将 dependency_service_name 解析为实际的类型
        dependencies = None
        if service_config.dependencies:
            dependencies = cls._resolve_dependency_types(service_config.dependencies, service_name)

        # 4. 创建工厂函数（包装配置中的依赖和 config 字段）
        if factory_func:
            # 如果已有工厂函数，直接使用
            final_factory = factory_func
        elif service_config.dependencies:
            # 如果有显式依赖配置，创建工厂函数
            # 注意：这里使用 service_config.dependencies 而不是 dependencies
            # 因为 _resolve_dependency_types 当前返回 None
            final_factory = cls._create_factory_with_dependencies(
                implementation_type or service_type,
                service_config.dependencies,
                service_config.config
            )
        else:
            # 否则让 EnhancedServiceFactory 自动推断
            final_factory = None

        # 5. 注册服务
        cls.register(
            service_type=service_type,
            implementation_type=implementation_type,
            factory=final_factory,
            lifecycle=lifecycle,
            dependencies=dependencies if not final_factory else None
        )

        logger.debug(f"Registered '{service_name}' -> {service_type.__name__} ({lifecycle.value})")

    @classmethod
    def _load_class(cls, class_path: str) -> Type:
        """加载类

        Args:
            class_path: 类路径，格式: module.path.ClassName

        Returns:
            类对象

        Raises:
            ImportError: 模块无法导入
            AttributeError: 类不存在
        """
        try:
            module_path, class_name = class_path.rsplit('.', 1)
            module = importlib.import_module(module_path)
            return getattr(module, class_name)
        except Exception as e:
            logger.error(f"Failed to load class '{class_path}': {e}")
            raise

    @classmethod
    def _load_callable(cls, callable_path: str) -> Callable:
        """加载可调用对象（函数）

        Args:
            callable_path: 函数路径，格式: module.path.function_name

        Returns:
            可调用对象

        Raises:
            ImportError: 模块无法导入
            AttributeError: 函数不存在
        """
        try:
            module_path, func_name = callable_path.rsplit('.', 1)
            module = importlib.import_module(module_path)
            func = getattr(module, func_name)
            if not callable(func):
                raise ValueError(f"'{callable_path}' is not callable")
            return func
        except Exception as e:
            logger.error(f"Failed to load callable '{callable_path}': {e}")
            raise

    @classmethod
    def _resolve_dependency_types(
        cls,
        dependency_config: Dict[str, str],
        service_name: str
    ) -> List[Type]:
        """解析依赖配置为类型列表

        Args:
            dependency_config: 依赖配置 {param_name: dependency_service_name}
            service_name: 当前服务名称（用于日志）

        Returns:
            依赖类型列表（按参数顺序）

        注意：这里我们需要从 dependency_service_name 反查其对应的类型。
        由于配置中依赖是 service_name，我们需要：
        1. 先查找该服务是否已注册
        2. 如果未注册，尝试从配置中查找其类型
        """
        # 这里简化处理：假设依赖服务名称对应的类型可以从已注册服务中查找
        # 或者使用服务名称本身作为类型（需要配置文件中明确指定）

        # 由于这是循环依赖的问题，我们返回 None，让工厂函数处理
        return None

    @classmethod
    def _create_factory_with_dependencies(
        cls,
        implementation_type: Type,
        dependency_config: Dict[str, str],
        config: Dict[str, Any]
    ) -> Callable:
        """创建带依赖注入的工厂函数

        Args:
            implementation_type: 实现类型
            dependency_config: 依赖配置 {param_name: dependency_service_name}
            config: 服务配置字典

        Returns:
            工厂函数
        """
        def factory():
            # 解析依赖
            kwargs = {}
            for param_name, dep_service_name in dependency_config.items():
                # 从服务名称查找对应的类型
                dep_type = cls._find_service_type_by_name(dep_service_name)
                if dep_type:
                    kwargs[param_name] = cls.resolve(dep_type)
                else:
                    logger.warning(f"Dependency '{dep_service_name}' not found for parameter '{param_name}'")

            # 添加配置（如果服务构造函数接受 config 参数）
            sig = inspect.signature(implementation_type.__init__)
            if 'config' in sig.parameters:
                kwargs['config'] = config

            return implementation_type(**kwargs)

        return factory

    @classmethod
    def _find_service_type_by_name(cls, service_name: str) -> Optional[Type]:
        """根据服务名称查找服务类型

        Args:
            service_name: 服务名称（如 'repositories.kline' 或 'chan_service'）

        Returns:
            服务类型，如果未找到返回 None
        """
        # 处理 repositories.xxx 格式的引用
        if service_name.startswith('repositories.'):
            repo_name = service_name.split('.', 1)[1]
            # 从配置中查找对应的 interface
            try:
                from infrastructure.config.loader import load_config
                config = load_config()
                if hasattr(config, 'repositories') and repo_name in config.repositories:
                    repo_config = config.repositories[repo_name]
                    interface_path = repo_config.interface
                    # 加载接口类型
                    return cls._load_class(interface_path)
            except Exception as e:
                logger.warning(f"Failed to resolve repository reference '{service_name}': {e}")
                return None

        # 从已注册的服务中查找
        for service_type, descriptor in cls._descriptors.items():
            # 尝试匹配服务名称
            type_name = service_type.__name__.lower()
            if type_name == service_name.lower().replace('_', '').replace('.', ''):
                return service_type

            # 尝试匹配完整名称
            full_name = f"{service_type.__module__}.{service_type.__name__}"
            if full_name == service_name:
                return service_type

        return None


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
