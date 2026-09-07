"""
SQLAlchemy AsyncEngine 全局单例 - 统一异步数据库连接管理

所有异步数据库访问(AsyncBaseRepository)统一通过此 AsyncEngine。
同步路径见 engine.py。
"""
import os
import logging
from typing import Optional
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine, AsyncConnection
from sqlalchemy.pool import NullPool, AsyncAdaptedQueuePool

logger = logging.getLogger(__name__)

_async_engine: Optional[AsyncEngine] = None
_async_engine_initialized = False


def get_async_engine() -> AsyncEngine:
    """获取全局 AsyncEngine 单例,未初始化时自动 init。

    Returns:
        AsyncEngine 实例

    Raises:
        RuntimeError: AsyncEngine 未初始化且无法自动初始化时
    """
    if _async_engine is None:
        raise RuntimeError(
            "AsyncEngine not initialized. "
            "Call init_async_engine() first (usually in async startup hook)."
        )
    return _async_engine


async def init_async_engine(
    dsn: Optional[str] = None,
    pool_size: int = 10,
    max_overflow: int = 20,
    pool_recycle: int = 3600,
    echo: bool = False
) -> AsyncEngine:
    """初始化全局 AsyncEngine(异步应用启动时调用一次)。

    Args:
        dsn: 数据库连接字符串,None 则从环境变量读取
        pool_size: 连接池保持的常驻连接数(默认 10)
        max_overflow: 超过 pool_size 时允许的临时连接数(默认 20)
                      总连接上限 = pool_size + max_overflow = 30
        pool_recycle: 连接回收时间(秒),防止 DB 端超时断开(默认 3600)
        echo: 是否打印 SQL 日志(调试用,默认 False)

    Returns:
        AsyncEngine 实例

    配置指南:
        - 异步层池容量应与同步层相当
        - pool_size=10, max_overflow=20 适合单服务异步路径
        - asyncpg 没有 pool_pre_ping,靠 pool_recycle 定期更新连接
    """
    global _async_engine, _async_engine_initialized

    if _async_engine_initialized:
        logger.info("AsyncEngine already initialized, skipping")
        return _async_engine

    if dsn is None:
        from infrastructure.persistence.database.engine import _resolve_db_dsn
        dsn = _resolve_db_dsn()

    if not dsn:
        raise RuntimeError(
            "No database DSN configured. "
            "Set QUANT_DATABASE_URL, DATABASE_URL, or POSTGRES_DSN."
        )

    # SQLAlchemy async 需要 asyncpg driver
    # 将 postgresql:// 改为 postgresql+asyncpg://
    if dsn.startswith('postgresql://'):
        dsn = dsn.replace('postgresql://', 'postgresql+asyncpg://', 1)
    elif not dsn.startswith('postgresql+asyncpg://'):
        raise ValueError(
            f"Async DSN must use asyncpg driver. "
            f"Got: {dsn[:30]}... Expected: postgresql+asyncpg://..."
        )

    _async_engine = create_async_engine(
        dsn,
        poolclass=AsyncAdaptedQueuePool,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_recycle=pool_recycle,
        echo=echo,
    )

    _async_engine_initialized = True
    logger.info(
        f"SQLAlchemy AsyncEngine initialized: pool_size={pool_size}, "
        f"max_overflow={max_overflow}, total_capacity={pool_size + max_overflow}"
    )

    # 注册清理钩子(异步应用框架通常有自己的 shutdown hook)
    # 不依赖 atexit,因为异步 dispose 需要 event loop

    return _async_engine


async def dispose_async_engine():
    """关闭 AsyncEngine(异步应用退出时调用)。"""
    global _async_engine, _async_engine_initialized
    if _async_engine is not None:
        try:
            await _async_engine.dispose()
            logger.info("AsyncEngine disposed")
        except Exception as e:
            logger.error(f"Error disposing async engine: {e}")
        finally:
            _async_engine = None
            _async_engine_initialized = False


def get_async_pool_status() -> dict:
    """获取异步连接池状态(用于监控)。

    Returns:
        包含池状态信息的字典
    """
    if _async_engine is None:
        return {"initialized": False}

    pool = _async_engine.pool
    return {
        "initialized": _async_engine_initialized,
        "pool_size": pool.size(),
        "checked_in": pool.checkedin(),
        "checked_out": pool.checkedout(),
        "overflow": pool.overflow(),
        "total": pool.size() + pool.overflow(),
    }
