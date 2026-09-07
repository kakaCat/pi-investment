"""
Backward-compatibility shim for domain.quantlib.adapters.

These adapters have been migrated to adapters.outbound.datasources.providers.quantlib
as part of the architecture audit P0-2 fix (2026-08-19).

The domain layer should NOT contain outbound adapters — they belong in the adapters layer.
This shim re-exports from the new location to avoid breaking existing imports.

TODO: Remove this shim after all callers have updated their imports (target: 2026-09-19).
"""

import warnings

warnings.warn(
    "domain.quantlib.adapters is deprecated. "
    "Use adapters.outbound.datasources.providers.quantlib instead. "
    "This shim will be removed after 2026-09-19.",
    DeprecationWarning,
    stacklevel=2,
)

# Re-export everything from the new location
from adapters.outbound.datasources.providers.quantlib.factor_calculator_adapter import (  # noqa: F401
    FactorCalculatorAdapter,
    get_factor_adapter,
)
from adapters.outbound.datasources.providers.quantlib.base_adapter import BaseMarketAdapter  # noqa: F401
from adapters.outbound.datasources.providers.quantlib.akshare_adapter import AkShareAdapter  # noqa: F401
from adapters.outbound.datasources.providers.quantlib.factory import (  # noqa: F401
    get_adapter,
    register_adapter,
    list_adapters,
)
from adapters.outbound.datasources.providers.quantlib.eastmoney_adapter import EastMoneyAdapter  # noqa: F401
from adapters.outbound.datasources.providers.quantlib.sina_adapter import SinaAdapter  # noqa: F401

__all__ = [
    "FactorCalculatorAdapter",
    "get_factor_adapter",
    "BaseMarketAdapter",
    "AkShareAdapter",
    "EastMoneyAdapter",
    "SinaAdapter",
    "get_adapter",
    "register_adapter",
    "list_adapters",
]
