"""Adapter factory — single entrypoint for obtaining a market data adapter.

Usage::

    from domain.quantlib.adapters.factory import get_adapter

    adapter = get_adapter()           # uses QUANT_MARKET_ADAPTER env var, default "akshare"
    adapter = get_adapter("akshare")  # explicit

The factory decouples callers from concrete adapter classes so that:
  * Switching data sources is a one-line config change (env var).
  * New adapters (tushare, wind, etc.) can be registered here without
    touching business logic.
"""

from __future__ import annotations

import os
from typing import Optional

from domain.quantlib.adapters.base_adapter import BaseMarketAdapter

# Registry of known adapter names → import path
_REGISTRY: dict[str, str] = {
    "akshare": "quantlib.adapters.akshare_adapter.AkShareAdapter",
}


def get_adapter(name: Optional[str] = None) -> BaseMarketAdapter:
    """Return a BaseMarketAdapter instance.

    Resolution order:
      1. Explicit *name* argument
      2. ``QUANT_MARKET_ADAPTER`` environment variable
      3. Built-in default ``"akshare"``

    Raises:
        ValueError: if the named adapter is not registered.
        ImportError: if the adapter class cannot be imported.
    """
    resolved = name or os.environ.get("QUANT_MARKET_ADAPTER", "akshare")

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
