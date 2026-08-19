"""
Backward-compatibility shim for domain.brokers.adapters.

These broker adapters have been migrated to adapters.outbound.brokers
as part of the architecture audit P0-2 fix (2026-08-19).

The domain layer should NOT contain outbound adapters — they belong in the adapters layer.
This shim re-exports from the new location to avoid breaking existing imports.

TODO: Remove this shim after all callers have updated their imports (target: 2026-09-19).
"""

import warnings

warnings.warn(
    "domain.brokers.adapters is deprecated. "
    "Use adapters.outbound.brokers instead. "
    "This shim will be removed after 2026-09-19.",
    DeprecationWarning,
    stacklevel=2,
)

# Re-export everything from the new location
from adapters.outbound.brokers.akshare_broker import AkshareBroker  # noqa: F401
from adapters.outbound.brokers.ibkr_broker import IBKRBroker  # noqa: F401
from adapters.outbound.brokers.alpaca_broker import AlpacaBroker  # noqa: F401

__all__ = [
    "AkshareBroker",
    "IBKRBroker",
    "AlpacaBroker",
]
