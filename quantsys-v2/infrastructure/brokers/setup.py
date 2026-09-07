"""
Broker Setup - Register concrete broker implementations

This module is responsible for wiring up concrete broker implementations
(from adapters layer) into the domain broker registry.

Architecture:
- Domain layer (domain.brokers) defines interfaces and registry
- Adapters layer (adapters.outbound.brokers) provides concrete implementations
- Infrastructure layer (this module) wires them together at startup

Usage:
    from infrastructure.brokers import setup_brokers
    from domain.brokers import BrokerRegistry

    registry = BrokerRegistry.instance()
    setup_brokers(registry)
"""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from domain.brokers.broker_registry import BrokerRegistry

logger = logging.getLogger(__name__)


def setup_brokers(registry: 'BrokerRegistry') -> None:
    """
    Register all available broker implementations.

    Args:
        registry: Domain broker registry to register into

    This function imports concrete adapters and registers them.
    New brokers should be added here.
    """
    logger.info("Setting up brokers...")
    registered_count = 0

    # AkShare (Chinese A-share data)
    try:
        from adapters.outbound.brokers.akshare_broker import AkshareBroker
        registry.register(AkshareBroker())
        logger.info("✓ Registered: AkShare")
        registered_count += 1
    except ImportError as e:
        logger.warning(f"✗ AkShare not available: {e}")
    except Exception as e:
        logger.error(f"✗ Failed to register AkShare: {e}")

    # Interactive Brokers
    try:
        from adapters.outbound.brokers.ibkr_broker import IBKRBroker
        registry.register(IBKRBroker())
        logger.info("✓ Registered: Interactive Brokers")
        registered_count += 1
    except ImportError as e:
        logger.debug(f"✗ IBKR not available: {e}")
    except Exception as e:
        logger.warning(f"✗ Failed to register IBKR: {e}")

    # Alpaca Markets
    try:
        from adapters.outbound.brokers.alpaca_broker import AlpacaBroker
        registry.register(AlpacaBroker())
        logger.info("✓ Registered: Alpaca Markets")
        registered_count += 1
    except ImportError as e:
        logger.debug(f"✗ Alpaca not available: {e}")
    except Exception as e:
        logger.warning(f"✗ Failed to register Alpaca: {e}")

    logger.info(f"Broker setup complete: {registered_count} brokers registered")
