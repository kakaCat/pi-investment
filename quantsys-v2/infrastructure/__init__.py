"""
Infrastructure Bootstrap

This module initializes all infrastructure components at application startup.
Call setup_infrastructure() once during application initialization.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


def setup_infrastructure() -> None:
    """
    Setup all infrastructure components.

    This function should be called once at application startup to:
    1. Register broker implementations into domain registry
    2. Setup other infrastructure components as needed

    Usage:
        from infrastructure import setup_infrastructure

        # In your application startup (e.g., Flask app factory, FastAPI lifespan)
        setup_infrastructure()
    """
    logger.info("Setting up infrastructure...")

    # Setup brokers
    try:
        from domain.brokers import BrokerRegistry
        from infrastructure.brokers import setup_brokers

        registry = BrokerRegistry.instance()
        setup_brokers(registry)
        logger.info("✓ Brokers setup complete")
    except Exception as e:
        logger.error(f"✗ Failed to setup brokers: {e}", exc_info=True)

    # Add more infrastructure setup here as needed
    # e.g., setup_data_sources(), setup_ml_models(), etc.

    logger.info("Infrastructure setup complete")


def teardown_infrastructure() -> None:
    """
    Teardown infrastructure components.

    Call this during application shutdown for graceful cleanup.
    """
    logger.info("Tearing down infrastructure...")

    # Add cleanup logic here if needed
    # e.g., close connections, flush caches, etc.

    logger.info("Infrastructure teardown complete")
