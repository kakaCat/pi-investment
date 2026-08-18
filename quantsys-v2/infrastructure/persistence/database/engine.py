"""
SQLAlchemy Engine 全局单例 - 统一数据库连接管理

所有同步数据库访问(BaseRepository、scheduler、脚本)统一通过此 Engine。
异步路径见 async_engine.py。
"""
import os
import logging
from typing import Optional
from sqlalchemy import create_engine, Engine
from sqlalchemy.pool import QueuePool

logger = logging.getLogger(__name__)

_engine: Optional[Engine] = None
_engine_initialized = False


def get_engine() -> Engine:
    """获取全局 Engine 单例,未初始化时自动 init。

    Returns:
        Engine 实例

    Raises:
        RuntimeError: Engine 未初始化且无法自动初始化时
    """
    if _engine is None:
        init_engine()
    return _engine


def init_engine(
    dsn: Optional[str] = None,
    pool_size: int = 10,
    max_overflow: int = 20,
    pool_pre_ping: bool = True,
    pool_recycle: int = 3600,
    echo: bool = False
) -> Engine:
    """初始化全局 Engine(进程启动时调用一次)。

    Args:
        dsn: 数据库连接字符串,None 则从环境变量读取
        pool_size: 连接池保持的常驻连接数(默认 10)
        max_overflow: 超过 pool_size 时允许的临时连接数(默认 20)
                      总连接上限 = pool_size + max_overflow = 30
        pool_pre_ping: 连接取出前先 ping,坏连接自动移除(默认 True)
        pool_recycle: 连接回收时间(秒),防止 DB 端超时断开(默认 3600)
        echo: 是否打印 SQL 日志(调试用,默认 False)

    Returns:
        Engine 实例

    配置指南:
        - 单进程服务(API/scheduler):pool_size=10, max_overflow=20 足够
        - 多进程训练脚本:每进程 pool_size 降到 5,确保 N_workers × 30 < PG max_connections
        - PostgreSQL 默认 max_connections=100,生产环境建议调到 200+
    """
    global _engine, _engine_initialized

    if _engine_initialized:
        logger.info("Engine already initialized, skipping")
        return _engine

    if dsn is None:
        from infrastructure.persistence.database.base_repository import _resolve_db_dsn
        dsn = _resolve_db_dsn()

    if not dsn:
        raise RuntimeError(
            "No database DSN configured. "
            "Set QUANT_DATABASE_URL, DATABASE_URL, or POSTGRES_DSN."
        )

    _engine = create_engine(
        dsn,
        poolclass=QueuePool,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_pre_ping=pool_pre_ping,
        pool_recycle=pool_recycle,
        echo=echo,
    )

    _engine_initialized = True
    logger.info(
        f"SQLAlchemy Engine initialized: pool_size={pool_size}, "
        f"max_overflow={max_overflow}, total_capacity={pool_size + max_overflow}"
    )

    # 注册 atexit,进程退出时关闭 Engine
    import atexit
    atexit.register(dispose_engine)

    # fork 安全:子进程清空继承的 Engine,强制重新 init
    _register_fork_handler()

    return _engine


def dispose_engine():
    """关闭 Engine(进程退出时调用)。"""
    global _engine, _engine_initialized
    if _engine is not None:
        try:
            _engine.dispose()
            logger.info("Engine disposed")
        except Exception as e:
            logger.error(f"Error disposing engine: {e}")
        finally:
            _engine = None
            _engine_initialized = False


_fork_handler_registered = False


def _register_fork_handler():
    """fork 后在子进程重置 Engine,避免继承父进程的连接池 socket。"""
    global _fork_handler_registered
    if _fork_handler_registered:
        return
    register = getattr(os, "register_at_fork", None)
    if register is None:
        _fork_handler_registered = True
        return

    def _reset_engine_in_child():
        global _engine, _engine_initialized
        # 不 dispose:会关父进程的 socket。只丢引用,子进程需要时重新 init。
        _engine = None
        _engine_initialized = False

    register(after_in_child=_reset_engine_in_child)
    _fork_handler_registered = True


def get_pool_status() -> dict:
    """获取连接池状态(用于监控)。

    Returns:
        包含池状态信息的字典
    """
    if _engine is None:
        return {"initialized": False}

    pool = _engine.pool
    return {
        "initialized": _engine_initialized,
        "pool_size": pool.size(),
        "checked_in": pool.checkedin(),
        "checked_out": pool.checkedout(),
        "overflow": pool.overflow(),
        "total": pool.size() + pool.overflow(),
    }


# ==================== db_cursor: per-operation 游标（替代 legacy BaseRepository） ====================

from contextlib import contextmanager


@contextmanager
def db_cursor(commit: bool = False):
    """单次操作级数据库游标（RealDictCursor），with 块结束立即归还连接池。

    替代 legacy BaseRepository 的实例级持连接模式。
    - commit=False（默认，读操作）：退出时显式 rollback（psycopg2 默认事务模式，
      SELECT 也开事务，不 rollback 归还会留 idle-in-transaction 残影）
    - commit=True（写操作）：正常退出 commit；异常 rollback 并重抛

    行类型为 psycopg2 RealDictRow（dict 子类），与旧 BaseRepository 完全一致。
    """
    from psycopg2.extras import RealDictCursor

    conn = get_engine().connect()
    try:
        raw = conn.connection  # 底层 psycopg2 connection（与旧 BaseRepository 同路径）
        cursor = raw.cursor(cursor_factory=RealDictCursor)
        try:
            yield cursor
            if commit:
                raw.commit()
            else:
                raw.rollback()
        except Exception:
            raw.rollback()
            raise
        finally:
            cursor.close()
    finally:
        conn.close()
