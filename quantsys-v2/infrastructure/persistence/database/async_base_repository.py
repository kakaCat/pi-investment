"""
异步数据库基础Repository

使用 SQLAlchemy AsyncEngine + asyncpg 实现异步数据库访问。
性能目标：相比同步版本提升100倍。
"""
from abc import ABC
from typing import Dict, Any, Optional, List
from datetime import datetime
import os
import sys
import re
import logging
from contextlib import asynccontextmanager
import warnings

from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy import text

logger = logging.getLogger(__name__)

# Test database suffix for pytest safety checks
TEST_DB_SUFFIX = "_test"

# Regex pattern to extract database name from PostgreSQL DSN
DSN_DB_NAME_PATTERN = r'://[^/]+/([^/?]+)(?:\?|$)'

__all__ = [
    "AsyncBaseRepository",
    "AsyncConnectionPool",  # Deprecated alias for backward compatibility
    "init_async_pool",  # Deprecated, 保留向后兼容
    "close_async_pool",  # Deprecated
    "get_async_pool",  # Deprecated
    "_resolve_db_dsn",
    "TEST_DB_SUFFIX",
]


def _resolve_db_dsn():
    """
    Resolve database DSN from Pydantic Settings configuration.

    Uses infrastructure.config.get_config() for type-safe configuration access.
    Falls back to environment variables only for legacy DATABASE_URL / POSTGRES_DSN.

    Safety: When running under pytest, validates that database name ends with '_test'
    to prevent accidental connection to production database.

    Returns:
        str: PostgreSQL connection DSN (async format), or None if no configuration found

    Raises:
        RuntimeError: If pytest environment detected but database is not a test database
    """
    from infrastructure.config import get_config
    import os
    
    # Priority 1: Legacy full DSN env vars (for backward compat)
    dsn = (
        os.environ.get("QUANT_DATABASE_URL")
        or os.environ.get("DATABASE_URL")
        or os.environ.get("POSTGRES_DSN")
    )
    
    # Priority 2: Pydantic Settings (recommended)
    if not dsn:
        config = get_config()
        dsn = config.database.async_url  # Use async URL format

    # 安全检查：pytest 环境必须使用测试库
    # 这是第二层防护，防止绕过 conftest.py 的情况
    if dsn and "pytest" in sys.modules:
        # Extract database name from the ACTUAL DSN being used (not env var)
        # This prevents bypass via DATABASE_URL=prod + PGDATABASE=fake_test
        # Parse from DSN first: postgresql://user:pass@host:port/dbname
        # Handles both with and without query parameters
        match = re.search(DSN_DB_NAME_PATTERN, dsn)
        db_name = match.group(1) if match else ""

        # If DSN parsing failed, try config
        if not db_name:
            try:
                config = get_config()
                db_name = config.database.database
            except:
                pass

        if db_name and not db_name.endswith(TEST_DB_SUFFIX):
            raise RuntimeError(
                f"Security check failed: Detected pytest environment but "
                f"database name '{db_name}' is not a test database. "
                f"Test database name must end with '{TEST_DB_SUFFIX}'. "
                f"This prevents accidental connection to production database during tests."
            )

    return dsn


# ==================== Deprecated Compatibility Layer ====================

class AsyncConnectionPool:
    """
    DEPRECATED: Alias for backward compatibility.

    This class previously implemented a custom asyncpg connection pool.
    All async database access now uses SQLAlchemy AsyncEngine.

    Use instead:
        from infrastructure.persistence.database.async_engine import init_async_engine
        await init_async_engine(pool_size=min_size, max_overflow=max_size-min_size)

    This class remains as a no-op to prevent import errors in legacy code.
    """
    def __init__(self, *args, **kwargs):
        warnings.warn(
            "AsyncConnectionPool is deprecated. "
            "Use 'from infrastructure.persistence.database.async_engine import init_async_engine; "
            "await init_async_engine(pool_size=..., max_overflow=...)' instead.",
            DeprecationWarning,
            stacklevel=2
        )


async def init_async_pool(
    dsn: Optional[str] = None,
    min_size: int = 10,
    max_size: int = 50,
):
    """
    DEPRECATED: 向后兼容旧脚本,内部转发到 init_async_engine()。

    新代码请直接使用:
        from infrastructure.persistence.database.async_engine import init_async_engine
        await init_async_engine(pool_size=min_size, max_overflow=max_size-min_size)

    Args:
        dsn: 数据库连接字符串,None 则从环境变量读取
        min_size: 映射到 pool_size
        max_size: 映射到 pool_size + max_overflow
    """
    from infrastructure.persistence.database.async_engine import init_async_engine
    warnings.warn(
        "init_async_pool() is deprecated. "
        "Use 'from infrastructure.persistence.database.async_engine import init_async_engine; "
        "await init_async_engine(pool_size=..., max_overflow=...)' instead.",
        DeprecationWarning,
        stacklevel=2
    )
    overflow = max(0, max_size - min_size)
    return await init_async_engine(dsn=dsn, pool_size=min_size, max_overflow=overflow)


async def close_async_pool():
    """
    DEPRECATED: 向后兼容。新代码用 dispose_async_engine()。
    """
    from infrastructure.persistence.database.async_engine import dispose_async_engine
    warnings.warn(
        "close_async_pool() is deprecated. "
        "Use 'from infrastructure.persistence.database.async_engine import dispose_async_engine; "
        "await dispose_async_engine()' instead.",
        DeprecationWarning,
        stacklevel=2
    )
    await dispose_async_engine()


async def get_async_pool():
    """
    DEPRECATED: 向后兼容。新代码用 get_async_engine()。

    Returns a mock object to prevent breakage in legacy code that expects
    an AsyncConnectionPool instance.
    """
    from infrastructure.persistence.database.async_engine import get_async_engine
    warnings.warn(
        "get_async_pool() is deprecated. "
        "Use 'from infrastructure.persistence.database.async_engine import get_async_engine; "
        "engine = get_async_engine()' instead.",
        DeprecationWarning,
        stacklevel=2
    )
    # Return engine directly - callers should migrate to AsyncBaseRepository
    return get_async_engine()


# ==================== AsyncBaseRepository ====================

class AsyncBaseRepository(ABC):
    """
    异步基础Repository,基于 SQLAlchemy AsyncEngine 的统一连接管理。

    连接池特性(由 SQLAlchemy AsyncAdaptedQueuePool 提供):
    - 自动复用连接,减少连接开销
    - 限制最大连接数(pool_size + max_overflow),保护数据库
    - 异步安全
    - pool_recycle 防止 DB 端超时断开

    使用方式:
    1. 应用启动时调用 init_async_engine() (from infrastructure.persistence.database.async_engine)
    2. 创建 Repository 实例,自动从 AsyncEngine 池获取连接
    3. Repository 方法内部自动管理连接获取和释放

    性能目标: 相比同步版本提升100倍(asyncpg + 异步IO)
    """

    def __init__(self, async_connection: Optional[AsyncConnection] = None):
        """
        初始化异步 Repository。

        Args:
            async_connection: 可选的外部 AsyncConnection(用于测试或事务管理)。
        """
        self._external_connection = async_connection
        self._owns_connection = async_connection is None

    async def _get_connection(self) -> AsyncConnection:
        """
        从 AsyncEngine 获取 AsyncConnection。

        如果构造时传入了外部连接,则直接返回外部连接。
        否则从全局 AsyncEngine 获取新连接。

        Returns:
            AsyncConnection 对象

        Note:
            调用方负责关闭返回的连接(如果是从 engine.connect() 获取的)。
            建议使用 @asynccontextmanager 包装的方法来自动管理连接生命周期。
        """
        if self._external_connection is not None:
            return self._external_connection

        from infrastructure.persistence.database.async_engine import get_async_engine
        engine = get_async_engine()
        # 返回新连接,调用方负责关闭
        return engine.connect()

    @asynccontextmanager
    async def _connection_context(self):
        """
        连接上下文管理器,自动处理连接的获取和释放。

        Yields:
            AsyncConnection 对象
        """
        if self._external_connection is not None:
            # 外部连接,不自动关闭
            yield self._external_connection
        else:
            # 从 engine 获取连接,自动关闭
            conn = await self._get_connection()
            try:
                yield conn
            finally:
                await conn.close()

    async def fetch(self, query: str, *args) -> List[Dict[str, Any]]:
        """
        执行查询并返回所有结果。

        Args:
            query: SQL 查询语句(可使用 $1, $2, ... 占位符)
            *args: 查询参数

        Returns:
            List[Dict]: 结果行列表,每行是字典
        """
        async with self._connection_context() as conn:
            # SQLAlchemy text() + bindparams
            # asyncpg 使用 $1, $2, ... 占位符
            result = await conn.execute(text(query), args)
            rows = result.fetchall()
            # 将 Row 对象转换为字典
            return [dict(row._mapping) for row in rows]

    async def fetchrow(self, query: str, *args) -> Optional[Dict[str, Any]]:
        """
        执行查询并返回单行结果。

        Args:
            query: SQL 查询语句
            *args: 查询参数

        Returns:
            Dict or None: 结果行字典,无结果时返回 None
        """
        async with self._connection_context() as conn:
            result = await conn.execute(text(query), args)
            row = result.fetchone()
            return dict(row._mapping) if row else None

    async def fetchval(self, query: str, *args) -> Any:
        """
        执行查询并返回单个值。

        Args:
            query: SQL 查询语句
            *args: 查询参数

        Returns:
            查询结果的第一行第一列的值,无结果时返回 None
        """
        async with self._connection_context() as conn:
            result = await conn.execute(text(query), args)
            row = result.fetchone()
            return row[0] if row else None

    async def execute(self, query: str, *args) -> str:
        """
        执行命令(INSERT/UPDATE/DELETE)。

        Args:
            query: SQL 命令
            *args: 命令参数

        Returns:
            str: 执行结果状态(如 "INSERT 0 1")
        """
        async with self._connection_context() as conn:
            result = await conn.execute(text(query), args)
            await conn.commit()
            # SQLAlchemy CursorResult 的 rowcount 属性
            return f"EXECUTE {result.rowcount}"

    async def executemany(self, query: str, args_list: List[tuple]) -> None:
        """
        批量执行命令。

        Args:
            query: SQL 命令
            args_list: 参数列表,每个元素是一组参数元组
        """
        async with self._connection_context() as conn:
            for args in args_list:
                await conn.execute(text(query), args)
            await conn.commit()

    @asynccontextmanager
    async def transaction(self):
        """
        获取事务上下文。

        Yields:
            AsyncConnection 对象,在事务中执行操作

        Example:
            async with repo.transaction() as conn:
                await conn.execute(text("INSERT INTO ..."), ...)
                await conn.execute(text("UPDATE ..."), ...)
            # 自动 commit,异常时自动 rollback
        """
        async with self._connection_context() as conn:
            async with conn.begin():
                yield conn

    # ==================== 验证方法 ====================

    def _validate_symbol(self, symbol: str) -> bool:
        """验证股票代码格式"""
        if not symbol:
            raise ValueError("股票代码不能为空")
        if not isinstance(symbol, str):
            raise ValueError("股票代码必须是字符串")

        base = symbol.strip().upper()
        for suffix in (".SZ", ".SH", ".HK"):
            if base.endswith(suffix):
                base = base[: -len(suffix)]
                break

        if not base.isdigit() or not (4 <= len(base) <= 6):
            raise ValueError(f"股票代码格式错误: {symbol}")
        return True

    def _validate_date(self, date_str: str) -> bool:
        """验证日期格式"""
        if not date_str:
            raise ValueError("Date cannot be empty")
        try:
            datetime.strptime(date_str, "%Y-%m-%d")
            return True
        except ValueError:
            raise ValueError(f"Invalid date format: {date_str}, expected YYYY-MM-DD")

    def _validate_positive_number(self, value: float, name: str) -> bool:
        """验证正数"""
        if value is None:
            raise ValueError(f"{name} cannot be None")
        if value <= 0:
            raise ValueError(f"{name} must be positive, got {value}")
        return True

    def _to_domain_object(self, db_row: Dict[str, Any]) -> Dict[str, Any]:
        """将数据库行转换为领域对象"""
        return db_row

    def _to_db_row(self, domain_object: Dict[str, Any]) -> Dict[str, Any]:
        """将领域对象转换为数据库行"""
        return domain_object

    def _log_query(self, operation: str, params: Dict[str, Any]):
        """记录查询日志"""
        logger.debug(f"Async repository operation: {operation}, params: {params}")

    async def close(self):
        """
        关闭连接(如果持有自有连接)。

        Note:
            使用外部连接时,此方法不会关闭连接。
            使用 AsyncEngine 自动管理的连接时,每次查询后自动归还连接池,
            此方法为向后兼容保留。
        """
        # AsyncEngine 自动管理连接,每次查询后自动归还池
        # 外部连接由调用方管理,此处不关闭
        pass
