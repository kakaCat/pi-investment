"""
异步ORM配置模块 - 管理SQLAlchemy异步Engine和AsyncSession

本模块提供：
1. AsyncEngine - 异步数据库引擎
2. async_session_maker - 异步Session工厂
3. init_async_orm() - 应用启动时初始化
4. get_async_session() - 获取AsyncSession（用于依赖注入）
"""
import logging
from typing import Optional, AsyncIterator, Tuple
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    create_async_engine,
    async_sessionmaker,
)
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

# 全局变量
_async_engine: Optional[AsyncEngine] = None
_async_session_maker: Optional[async_sessionmaker] = None
_async_orm_initialized = False


def init_async_orm(
    dsn: Optional[str] = None,
    pool_size: int = 10,
    max_overflow: int = 20,
    pool_pre_ping: bool = True,
    pool_recycle: int = 3600,
    echo: bool = False
) -> Tuple[AsyncEngine, async_sessionmaker]:
    """初始化异步ORM（应用启动时调用一次）

    Args:
        dsn: 数据库连接字符串，需要使用异步驱动（postgresql+asyncpg://...）
        pool_size: 连接池保持的常驻连接数
        max_overflow: 超过pool_size时允许的临时连接数
        pool_pre_ping: 连接取出前先ping，坏连接自动移除
        pool_recycle: 连接回收时间（秒），防止DB端超时断开
        echo: 是否打印SQL日志（调试用）

    Returns:
        (async_engine, async_session_maker) 元组

    Raises:
        RuntimeError: 数据库配置不存在时
    """
    global _async_engine, _async_session_maker, _async_orm_initialized

    if _async_orm_initialized:
        logger.info("Async ORM already initialized, skipping")
        return _async_engine, _async_session_maker

    # 解析DSN并转换为异步驱动
    if dsn is None:
        from infrastructure.persistence.database.base_repository import _resolve_db_dsn
        dsn = _resolve_db_dsn()

    if not dsn:
        raise RuntimeError(
            "No database DSN configured. "
            "Set QUANT_DATABASE_URL, DATABASE_URL, or POSTGRES_DSN."
        )

    # 转换为异步驱动（postgresql:// -> postgresql+asyncpg://）
    if dsn.startswith("postgresql://"):
        dsn = dsn.replace("postgresql://", "postgresql+asyncpg://", 1)
    elif not dsn.startswith("postgresql+asyncpg://"):
        raise ValueError(f"DSN must use asyncpg driver: {dsn}")

    # 创建异步Engine
    _async_engine = create_async_engine(
        dsn,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_pre_ping=pool_pre_ping,
        pool_recycle=pool_recycle,
        echo=echo,
    )

    # 创建异步session工厂
    _async_session_maker = async_sessionmaker(
        bind=_async_engine,
        class_=AsyncSession,
        expire_on_commit=False,  # 避免访问已过期对象时重新查询
    )

    _async_orm_initialized = True
    logger.info(
        f"Async ORM initialized: pool_size={pool_size}, "
        f"max_overflow={max_overflow}, echo={echo}"
    )

    # 注册退出时清理
    import atexit
    atexit.register(lambda: _close_async_orm_sync())

    return _async_engine, _async_session_maker


async def get_async_session() -> AsyncIterator[AsyncSession]:
    """获取异步Session（用于FastAPI依赖注入）

    Usage:
        @app.get("/pools")
        async def list_pools(session: AsyncSession = Depends(get_async_session)):
            result = await session.execute(select(StockPool))
            return result.scalars().all()

    Yields:
        AsyncSession实例

    Raises:
        RuntimeError: 异步ORM未初始化时
    """
    if _async_session_maker is None:
        # 自动初始化（便于开发，生产环境应显式init）
        logger.warning("Async ORM not initialized, auto-initializing...")
        init_async_orm()

    async with _async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def get_async_session_context() -> AsyncIterator[AsyncSession]:
    """获取异步Session上下文管理器（用于Service层）

    Usage:
        async with get_async_session_context() as session:
            result = await session.execute(query)
            return result.scalars().all()

    Yields:
        AsyncSession实例
    """
    if _async_session_maker is None:
        logger.warning("Async ORM not initialized, auto-initializing...")
        init_async_orm()

    async with _async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def close_async_orm():
    """关闭异步ORM（进程退出时调用）"""
    global _async_engine, _async_session_maker, _async_orm_initialized

    if _async_engine:
        try:
            await _async_engine.dispose()
            logger.info("Async ORM engine disposed")
        except Exception as e:
            logger.error(f"Error disposing async ORM engine: {e}")
        finally:
            _async_engine = None
            _async_session_maker = None
            _async_orm_initialized = False


def _close_async_orm_sync():
    """同步关闭异步ORM（用于atexit）"""
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(close_async_orm())
        else:
            loop.run_until_complete(close_async_orm())
    except Exception as e:
        logger.error(f"Error in sync close: {e}")


def get_async_engine() -> Optional[AsyncEngine]:
    """获取异步Engine实例（用于原生SQL执行）"""
    return _async_engine


def is_async_initialized() -> bool:
    """检查异步ORM是否已初始化"""
    return _async_orm_initialized


__all__ = [
    'init_async_orm',
    'get_async_session',
    'get_async_session_context',
    'close_async_orm',
    'get_async_engine',
    'is_async_initialized',
]
