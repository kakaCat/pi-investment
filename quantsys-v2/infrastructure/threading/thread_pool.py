"""
统一的线程池管理

提供全局线程池实例和管理接口，避免线程泄漏和资源竞争。
"""

import threading
from concurrent.futures import ThreadPoolExecutor, Future
from typing import Callable, Dict, Any, Optional
import structlog

logger = structlog.get_logger(__name__)


class ManagedThreadPool:
    """托管的线程池，提供生命周期管理和监控"""

    def __init__(
        self,
        max_workers: int = 10,
        thread_name_prefix: str = "worker",
        pool_name: str = "default"
    ):
        """
        初始化线程池

        Args:
            max_workers: 最大工作线程数
            thread_name_prefix: 线程名称前缀（用于调试和监控）
            pool_name: 线程池名称（用于日志和监控）
        """
        self.max_workers = max_workers
        self.thread_name_prefix = thread_name_prefix
        self.pool_name = pool_name

        self.executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix=thread_name_prefix
        )

        self._shutdown = False
        self._lock = threading.Lock()

        logger.info(
            "thread_pool_created",
            pool_name=pool_name,
            max_workers=max_workers,
            thread_name_prefix=thread_name_prefix
        )

    def submit(self, fn: Callable, *args, **kwargs) -> Future:
        """
        提交任务到线程池

        Args:
            fn: 要执行的函数
            *args: 位置参数
            **kwargs: 关键字参数

        Returns:
            Future 对象

        Raises:
            RuntimeError: 如果线程池已关闭
        """
        with self._lock:
            if self._shutdown:
                raise RuntimeError(f"Thread pool '{self.pool_name}' has been shut down")

        logger.debug(
            "task_submitted",
            pool_name=self.pool_name,
            function=fn.__name__
        )

        return self.executor.submit(fn, *args, **kwargs)

    def shutdown(self, wait: bool = True, timeout: Optional[float] = None):
        """
        关闭线程池

        Args:
            wait: 是否等待所有任务完成
            timeout: 等待超时时间（秒）
        """
        with self._lock:
            if self._shutdown:
                logger.warning("thread_pool_already_shutdown", pool_name=self.pool_name)
                return

            self._shutdown = True

        logger.info(
            "thread_pool_shutting_down",
            pool_name=self.pool_name,
            wait=wait,
            timeout=timeout
        )

        self.executor.shutdown(wait=wait, timeout=timeout)

        logger.info("thread_pool_shutdown_complete", pool_name=self.pool_name)

    def get_status(self) -> Dict[str, Any]:
        """
        获取线程池状态

        Returns:
            状态字典，包含：
            - pool_name: 线程池名称
            - max_workers: 最大工作线程数
            - active_threads: 当前活跃线程数
            - pending_tasks: 待处理任务数（近似值）
            - is_shutdown: 是否已关闭
        """
        # 注意：ThreadPoolExecutor 的内部属性是私有的，可能在未来版本改变
        try:
            active_threads = len(self.executor._threads) if hasattr(self.executor, '_threads') else None
            pending_tasks = self.executor._work_queue.qsize() if hasattr(self.executor, '_work_queue') else None
        except Exception as e:
            logger.warning("failed_to_get_thread_pool_internals", error=str(e))
            active_threads = None
            pending_tasks = None

        return {
            "pool_name": self.pool_name,
            "max_workers": self.max_workers,
            "thread_name_prefix": self.thread_name_prefix,
            "active_threads": active_threads,
            "pending_tasks": pending_tasks,
            "is_shutdown": self._shutdown,
        }

    def __enter__(self):
        """上下文管理器入口"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器退出"""
        self.shutdown(wait=True)


# ============================================================================
# 全局线程池实例
# ============================================================================

# 延迟初始化，避免循环导入
_default_pool = None
_io_pool = None
_compute_pool = None


def _get_settings():
    """延迟加载配置，避免循环导入"""
    from infrastructure.config.settings import get_settings
    return get_settings()


def _ensure_pools_initialized():
    """确保线程池已初始化"""
    global _default_pool, _io_pool, _compute_pool

    if _default_pool is None:
        settings = _get_settings()

        # 默认线程池：通用任务
        _default_pool = ManagedThreadPool(
            max_workers=settings.thread_pool.default_workers,
            thread_name_prefix="quantsys-default",
            pool_name="default"
        )

        # I/O 密集型任务池：数据库、网络请求等
        _io_pool = ManagedThreadPool(
            max_workers=settings.thread_pool.io_workers,
            thread_name_prefix="quantsys-io",
            pool_name="io"
        )

        # 计算密集型任务池：回测、因子计算等
        _compute_pool = ManagedThreadPool(
            max_workers=settings.thread_pool.compute_workers,
            thread_name_prefix="quantsys-compute",
            pool_name="compute"
        )


# 访问器函数
def get_default_pool():
    """获取默认线程池"""
    _ensure_pools_initialized()
    return _default_pool


def get_io_pool():
    """获取 I/O 线程池"""
    _ensure_pools_initialized()
    return _io_pool


def get_compute_pool():
    """获取计算线程池"""
    _ensure_pools_initialized()
    return _compute_pool


# 兼容性：提供模块级别的访问方式（延迟初始化）
class _PoolProxy:
    """线程池代理，支持延迟初始化"""
    def __init__(self, getter):
        self._getter = getter
        self._cached = None

    def __getattr__(self, name):
        if self._cached is None:
            self._cached = self._getter()
        return getattr(self._cached, name)

    def submit(self, *args, **kwargs):
        if self._cached is None:
            self._cached = self._getter()
        return self._cached.submit(*args, **kwargs)


default_pool = _PoolProxy(get_default_pool)
io_pool = _PoolProxy(get_io_pool)
compute_pool = _PoolProxy(get_compute_pool)


# ============================================================================
# 全局管理接口
# ============================================================================

def get_pool_status(pool_name: Optional[str] = None) -> Dict[str, Any]:
    """
    获取线程池状态

    Args:
        pool_name: 线程池名称（'default', 'io', 'compute'）
                  如果为 None，返回所有线程池状态

    Returns:
        线程池状态字典
    """
    # 确保线程池已初始化
    _ensure_pools_initialized()

    pools = {
        "default": _default_pool,
        "io": _io_pool,
        "compute": _compute_pool,
    }

    if pool_name:
        if pool_name not in pools:
            raise ValueError(f"Unknown pool name: {pool_name}. Available: {list(pools.keys())}")
        return pools[pool_name].get_status()

    # 返回所有线程池状态
    return {
        name: pool.get_status()
        for name, pool in pools.items()
    }


def shutdown_all_pools(wait: bool = True, timeout: Optional[float] = 30):
    """
    关闭所有全局线程池

    Args:
        wait: 是否等待所有任务完成
        timeout: 等待超时时间（秒）
    """
    logger.info("shutting_down_all_thread_pools", wait=wait, timeout=timeout)

    for pool in [default_pool, io_pool, compute_pool]:
        try:
            pool.shutdown(wait=wait, timeout=timeout)
        except Exception as e:
            logger.error(
                "failed_to_shutdown_pool",
                pool_name=pool.pool_name,
                error=str(e)
            )

    logger.info("all_thread_pools_shutdown_complete")
