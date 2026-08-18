"""
Database Infrastructure

Provides database connection management and base repository classes.
"""

from infrastructure.persistence.database.engine import (
    init_engine,
    dispose_engine,
    get_engine,
    get_pool_status,
    _resolve_db_dsn,
    TEST_DB_SUFFIX,
)
from infrastructure.persistence.database.async_engine import (
    init_async_engine,
    dispose_async_engine,
    get_async_engine,
    get_async_pool_status,
)
from infrastructure.persistence.database.async_base_repository import (
    AsyncBaseRepository,
    init_async_pool,  # Deprecated
    close_async_pool,  # Deprecated
    get_async_pool,  # Deprecated
)

__all__ = [
    "_resolve_db_dsn",
    "init_engine",
    "dispose_engine",
    "get_engine",
    "get_pool_status",
    "init_async_engine",
    "dispose_async_engine",
    "get_async_engine",
    "get_async_pool_status",
    "AsyncBaseRepository",
    "init_async_pool",  # Deprecated
    "close_async_pool",  # Deprecated
    "get_async_pool",  # Deprecated
    "TEST_DB_SUFFIX",
]
