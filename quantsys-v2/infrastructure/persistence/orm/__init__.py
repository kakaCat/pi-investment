"""L1 兼容 shim（S11 · Slice B-1 · 30 天观察期）。

原 ``infrastructure.persistence.orm`` 已迁至 ``qs_kernel.infrastructure.persistence.orm``。
已迁子模块经 sys.modules 别名绑定到 kernel 模块（保证 Base/engine 单例身份唯一）；
models 业务表模型仍在本目录，经本包 __path__ 保持可达。
"""
import importlib
import sys

_canonical = "qs_kernel.infrastructure.persistence.orm"
from qs_kernel.infrastructure.persistence.orm import (  # noqa: F401 canonical home
    Base,
    init_orm,
    get_session,
    get_db_session,
    close_session,
    close_orm,
    get_engine,
    is_initialized,
    TimestampMixin,
    to_dict,
    BaseORMRepository,
)

for _name in (
    "base",
    "base_repository",
    "async_base",
    "async_config",
    "config",
    "session_guard",
):
    _mod = importlib.import_module(f"{_canonical}.{_name}")
    sys.modules[f"infrastructure.persistence.orm.{_name}"] = _mod
    globals()[_name] = _mod

__all__ = [
    "Base",
    "init_orm",
    "get_session",
    "get_db_session",
    "close_session",
    "close_orm",
    "get_engine",
    "is_initialized",
    "TimestampMixin",
    "to_dict",
    "BaseORMRepository",
    "base",
    "base_repository",
    "async_base",
    "async_config",
    "config",
    "session_guard",
]
