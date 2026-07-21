from abc import ABC
from typing import Dict, Any, Optional
from datetime import datetime
import os
import sys
import re
import logging
import warnings
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)

# Test database suffix for pytest safety checks
TEST_DB_SUFFIX = "_test"

__all__ = ["BaseRepository", "_resolve_db_dsn", "TEST_DB_SUFFIX"]


def _resolve_db_dsn():
    """
    Resolve database DSN from environment variables.

    Priority:
    1. QUANT_DATABASE_URL / DATABASE_URL / POSTGRES_DSN (full connection string)
    2. PG* environment variables (PGDATABASE, PGHOST, PGPORT, PGUSER, PGPASSWORD)

    Safety: When running under pytest, validates that database name ends with '_test'
    to prevent accidental connection to production database. This applies to both
    full DSN strings and PG* environment variables.

    Returns:
        str: PostgreSQL connection DSN, or None if no configuration found

    Raises:
        RuntimeError: If pytest environment detected but database is not a test database
    """
    dsn = (
        os.environ.get("QUANT_DATABASE_URL")
        or os.environ.get("DATABASE_URL")
        or os.environ.get("POSTGRES_DSN")
    )
    if not dsn:
        pgdatabase = os.environ.get("PGDATABASE")
        if pgdatabase:
            pghost = os.environ.get("PGHOST", "127.0.0.1")
            pgport = os.environ.get("PGPORT", "5432")
            pguser = os.environ.get("PGUSER", "")
            pgpassword = os.environ.get("PGPASSWORD", "")
            auth = f"{pguser}:{pgpassword}@" if pguser else ""
            dsn = f"postgresql://{auth}{pghost}:{pgport}/{pgdatabase}"

    # 安全检查：pytest 环境必须使用测试库
    # 这是第二层防护，防止绕过 conftest.py 的情况
    if dsn and "pytest" in sys.modules:
        # Extract database name from the ACTUAL DSN being used (not env var)
        # This prevents bypass via DATABASE_URL=prod + PGDATABASE=fake_test
        # Parse from DSN first: postgresql://user:pass@host:port/dbname
        # Handles both with and without query parameters
        match = re.search(r'://[^/]+/([^/?]+)(?:\?|$)', dsn)
        db_name = match.group(1) if match else ""

        # If DSN parsing failed and we built DSN from PGDATABASE, use PGDATABASE
        if not db_name and "PGDATABASE" in os.environ:
            db_name = os.environ["PGDATABASE"]

        if db_name and not db_name.endswith(TEST_DB_SUFFIX):
            raise RuntimeError(
                f"Security check failed: Detected pytest environment but "
                f"database name '{db_name}' is not a test database. "
                f"Test database name must end with '{TEST_DB_SUFFIX}'. "
                f"This prevents accidental connection to production database during tests."
            )

    return dsn


class BaseRepository(ABC):
    """
    基础Repository,基于 SQLAlchemy Engine 的统一连接管理。

    连接池特性(由 SQLAlchemy QueuePool 提供):
    - 自动复用连接,减少连接开销
    - 限制最大连接数(pool_size + max_overflow),保护数据库
    - 线程安全、fork 安全
    - pool_pre_ping 自动检测和移除坏连接
    - pool_recycle 防止 DB 端超时断开

    使用方式:
    1. 应用启动时调用 init_engine() (from infrastructure.persistence.database.engine)
    2. 创建 Repository 实例时自动从 Engine 池获取连接
    3. Repository 销毁时自动归还连接(或显式调用 close())
    """

    @classmethod
    def init_connection_pool(cls, dsn: str = None, minconn: int = 5, maxconn: int = 20):
        """
        DEPRECATED: 向后兼容旧脚本,内部转发到 init_engine()。

        新代码请直接使用:
            from infrastructure.persistence.database.engine import init_engine
            init_engine(pool_size=minconn, max_overflow=maxconn-minconn)

        Args:
            dsn: 数据库连接字符串,None 则从环境变量读取
            minconn: 映射到 pool_size
            maxconn: 映射到 pool_size + max_overflow
        """
        from infrastructure.persistence.database.engine import init_engine
        warnings.warn(
            "BaseRepository.init_connection_pool() is deprecated. "
            "Use 'from infrastructure.persistence.database.engine import init_engine; "
            "init_engine(pool_size=..., max_overflow=...)' instead.",
            DeprecationWarning,
            stacklevel=2
        )
        overflow = max(0, maxconn - minconn)
        init_engine(dsn=dsn, pool_size=minconn, max_overflow=overflow)

    @classmethod
    def close_connection_pool(cls):
        """
        DEPRECATED: 向后兼容。新代码用 dispose_engine()。
        """
        from infrastructure.persistence.database.engine import dispose_engine
        warnings.warn(
            "BaseRepository.close_connection_pool() is deprecated. "
            "Use 'from infrastructure.persistence.database.engine import dispose_engine; "
            "dispose_engine()' instead.",
            DeprecationWarning,
            stacklevel=2
        )
        dispose_engine()

    @classmethod
    def get_pool_status(cls) -> Dict[str, Any]:
        """获取连接池状态(用于监控)。"""
        from infrastructure.persistence.database.engine import get_pool_status
        return get_pool_status()

    def __init__(self, db_connection=None):
        """
        初始化 Repository。

        Args:
            db_connection: 可选的外部连接(用于测试或事务管理)。
                          可以是 psycopg2 connection 或 SQLAlchemy Connection。
        """
        self._sqlalchemy_conn = None  # SQLAlchemy Connection 对象
        self._owns_connection = False

        if db_connection is not None:
            # 外部连接(测试场景)
            # 判断是否为 SQLAlchemy Connection:有 .connection 且该属性不是 callable
            # (MagicMock 的 .connection 是 MagicMock,SQLAlchemy Connection 的是真实 DBAPI conn)
            if hasattr(db_connection, 'connection') and hasattr(db_connection.connection, 'cursor'):
                # SQLAlchemy Connection,有 .connection 属性指向底层 DBAPI conn
                self._sqlalchemy_conn = db_connection
                self.db = db_connection.connection
            else:
                # 直接传入的 psycopg2 connection(旧测试兼容)
                self.db = db_connection
            self._owns_connection = False
        else:
            # 正常路径:从全局 Engine 获取连接(立即初始化以支持 self.db.cursor() 调用)
            self._owns_connection = True
            self._get_connection()  # 立即初始化连接

    def _get_connection(self):
        """Lazy 从 Engine 获取 SQLAlchemy Connection,缓存到 self._sqlalchemy_conn。

        Returns:
            SQLAlchemy Connection 对象
        """
        if self._sqlalchemy_conn is None:
            from infrastructure.persistence.database.engine import get_engine
            engine = get_engine()
            self._sqlalchemy_conn = engine.connect()
            # 提取底层 psycopg2 connection,向后兼容现有 Repository 子类
            self.db = self._sqlalchemy_conn.connection
        return self._sqlalchemy_conn

    def _get_cursor(self):
        """Get a database cursor,向后兼容现有 Repository 子类。

        Returns:
            psycopg2 RealDictCursor object (returns rows as dicts)

        Note:
            内部调用 _get_connection(),从 Engine 池 lazy 获取连接。
            SQLAlchemy 的 pool_pre_ping 自动处理坏连接,无需手工 retry。
        """
        self._get_connection()
        return self.db.cursor(cursor_factory=RealDictCursor)

    def cursor(self):
        """Public method to get a RealDictCursor.

        Returns:
            psycopg2 RealDictCursor object (returns rows as dicts)
        """
        return self._get_cursor()

    def _get_db(self):
        """Return db connection(psycopg2),向后兼容。

        Returns:
            psycopg2 connection object

        Raises:
            RuntimeError: 如果无法获取连接
        """
        try:
            self._get_connection()
            return self.db
        except Exception as e:
            raise RuntimeError(
                f"Database connection unavailable: {e}. "
                "Check PostgreSQL status and Engine initialization."
            )

    def _release_connection(self):
        """释放连接(归还 Engine 池),幂等。

        SQLAlchemy Connection.close() 会将连接归还池,不是真正关闭 socket。
        """
        if not self._owns_connection:
            return

        if self._sqlalchemy_conn is not None:
            try:
                self._sqlalchemy_conn.close()
                logger.debug("Connection returned to Engine pool")
            except Exception as e:
                logger.error(f"Error releasing connection: {e}")
            finally:
                self._sqlalchemy_conn = None
                self.db = None

    def close(self):
        """释放数据库连接(归还 Engine 池),幂等。"""
        self._release_connection()

    def __enter__(self):
        """支持 with 语句,退出时自动释放连接。"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    def __del__(self):
        """析构函数:归还连接。

        注意:__del__ 在进程被 terminate()、引用循环等场景下不保证执行,
        因此不能作为唯一的连接释放手段。调用方应优先用 close() 或
        DataService.close() 显式释放(理想情况下配合 with 语句)。
        """
        self._release_connection()

    # ==================== Validation 辅助方法 ====================

    def _validate_symbol(self, symbol: str) -> bool:
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
        if not date_str:
            raise ValueError("Date cannot be empty")
        try:
            datetime.strptime(date_str, "%Y-%m-%d")
            return True
        except ValueError:
            raise ValueError(f"Invalid date format: {date_str}, expected YYYY-MM-DD")

    def _validate_positive_number(self, value: float, name: str) -> bool:
        if value is None:
            raise ValueError(f"{name} cannot be None")
        if value <= 0:
            raise ValueError(f"{name} must be positive, got {value}")
        return True

    def _to_domain_object(self, db_row: Dict[str, Any]) -> Dict[str, Any]:
        return db_row

    def _to_db_row(self, domain_object: Dict[str, Any]) -> Dict[str, Any]:
        return domain_object

    def _log_query(self, operation: str, params: Dict[str, Any]):
        logger.debug(f"Repository operation: {operation}, params: {params}")
