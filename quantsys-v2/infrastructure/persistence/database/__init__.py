"""L1 兼容 shim（S11 · Slice B-1 · 30 天观察期）。

原 ``infrastructure.persistence.database`` 已迁至
``qs_kernel.infrastructure.persistence.database``。包与全部子模块经
sys.modules 别名绑定到 kernel 模块 —— engine 持模块级单例，严禁裸拷贝。
"""
import importlib
import sys

_canonical = "qs_kernel.infrastructure.persistence.database"
_canonical_pkg = importlib.import_module(_canonical)

for _name in ("engine", "async_engine", "async_base_repository", "validators"):
    _mod = importlib.import_module(f"{_canonical}.{_name}")
    sys.modules[f"infrastructure.persistence.database.{_name}"] = _mod

sys.modules["infrastructure.persistence.database"] = _canonical_pkg

__all__ = getattr(_canonical_pkg, "__all__", [])
