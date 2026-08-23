"""Adapter factory — single entrypoint for obtaining a market data adapter.

Usage::

    from adapters.outbound.datasources.providers.quantlib.factory import get_adapter

    adapter = get_adapter()           # uses config.app.quant_market_adapter, default "akshare"
    adapter = get_adapter("akshare")  # explicit

The factory decouples callers from concrete adapter classes so that:
  * Switching data sources is a one-line config change.
  * New adapters (tushare, wind, etc.) can be registered here without
    touching business logic.
"""

from __future__ import annotations

from typing import Optional

from .base_adapter import BaseMarketAdapter
# from infrastructure.config import get_config  # TODO: 配置系统重构

# Registry of known adapter names → import path
_REGISTRY: dict[str, str] = {
    "akshare": "adapters.outbound.datasources.providers.quantlib.akshare_adapter.AkShareAdapter",
}


def get_adapter(name: Optional[str] = None) -> BaseMarketAdapter:
    """Return a BaseMarketAdapter instance.

    Resolution order:
      1. Explicit *name* argument
      2. Config setting (config.app.quant_market_adapter)
      3. Built-in default ``"akshare"``

    Raises:
        ValueError: if the named adapter is not registered.
        ImportError: if the adapter class cannot be imported.
    """
    if name is None:
        # TODO: 配置系统重构后从配置读取
        resolved = "akshare"  # 默认使用 akshare
    else:
        resolved = name

    if resolved not in _REGISTRY:
        valid = ", ".join(sorted(_REGISTRY))
        raise ValueError(
            f"Unknown adapter '{resolved}'. Registered adapters: {valid}"
        )

    import_path = _REGISTRY[resolved]
    module_path, class_name = import_path.rsplit(".", 1)

    try:
        import importlib
        module = importlib.import_module(module_path)
        adapter_class = getattr(module, class_name)
    except ImportError as exc:
        raise ImportError(
            f"Could not import adapter module for '{resolved}': {exc}"
        ) from exc
    except AttributeError as exc:
        raise ImportError(
            f"Adapter class '{class_name}' not found in '{module_path}' "
            f"for adapter '{resolved}'"
        ) from exc

    return adapter_class()


def register_adapter(name: str, import_path: str) -> None:
    """Register a new adapter so it can be resolved by name.

    Args:
        name: Short name (e.g. "tushare").
        import_path: Fully-qualified dotted path to the class
            (e.g. "quantlib.adapters.tushare_adapter.TushareAdapter").
    """
    _REGISTRY[name] = import_path


def list_adapters() -> list[str]:
    """Return the names of all registered adapters."""
    return sorted(_REGISTRY)
