"""Configuration management for data sources.

Handles API keys and other configuration via environment variables.
"""

import os
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)


class DataSourceConfig:
    """Centralized configuration for all data sources.

    Reads API keys and configuration from environment variables.
    Provides validation and fallback mechanisms.
    """

    # API Key environment variable names
    ENV_VARS = {
        "akshare": None,  # AkShare doesn't require API key
        "fred": "FRED_API_KEY",
        "world_bank": None,  # World Bank API doesn't require key
        "yahoo_finance": None,  # Yahoo Finance doesn't require key
        "binance": None,  # Binance public API doesn't require key
        "polygon": "POLYGON_API_KEY",
        "alpha_vantage": "ALPHA_VANTAGE_API_KEY",
        "twelve_data": "TWELVE_DATA_API_KEY",
        "iex_cloud": "IEX_CLOUD_API_KEY",
        "tiingo": "TIINGO_API_KEY",
        "fmp": "FMP_API_KEY",
        # Phase 4: Satellite & Maritime data sources
        "sentinelhub": "SENTINELHUB_CLIENT_ID",  # + SENTINELHUB_CLIENT_SECRET
        "n2yo": "N2YO_API_KEY",
        "nasa_gibs": None,  # NASA GIBS is public, no API key required
        "copernicus": "COPERNICUS_API_KEY",
        "oscar": None,  # WMO OSCAR is public, no API key required
        "marinetraffic": "MARINETRAFFIC_API_KEY",
        "weforum": None,  # WEForum is public, no API key required
    }

    @classmethod
    def get_api_key(cls, source: str) -> Optional[str]:
        """Get API key for a data source.

        Args:
            source: Data source name (e.g., "fred", "polygon")

        Returns:
            API key string or None if not configured
        """
        env_var = cls.ENV_VARS.get(source.lower())
        if env_var is None:
            return None

        api_key = os.environ.get(env_var, "")
        if not api_key:
            logger.warning(f"API key not configured for {source}. Set {env_var} environment variable.")
            return None

        return api_key

    @classmethod
    def is_configured(cls, source: str) -> bool:
        """Check if a data source is properly configured.

        Args:
            source: Data source name

        Returns:
            True if configured (or doesn't require config), False otherwise
        """
        env_var = cls.ENV_VARS.get(source.lower())

        # If no env var needed, it's always configured
        if env_var is None:
            return True

        # Check if env var is set
        return bool(os.environ.get(env_var))

    @classmethod
    def get_all_configured_sources(cls) -> Dict[str, bool]:
        """Get configuration status for all data sources.

        Returns:
            Dict mapping source name to configuration status
        """
        return {
            source: cls.is_configured(source)
            for source in cls.ENV_VARS.keys()
        }

    @classmethod
    def validate_all(cls) -> Dict[str, str]:
        """Validate all data source configurations.

        Returns:
            Dict mapping source name to status message
        """
        results = {}
        for source in cls.ENV_VARS.keys():
            if cls.is_configured(source):
                results[source] = "✓ Configured"
            else:
                env_var = cls.ENV_VARS[source]
                if env_var:
                    results[source] = f"✗ Missing {env_var}"
                else:
                    results[source] = "✓ No config required"
        return results


# Convenience functions
def get_fred_api_key() -> Optional[str]:
    """Get FRED API key."""
    return DataSourceConfig.get_api_key("fred")


def get_polygon_api_key() -> Optional[str]:
    """Get Polygon.io API key."""
    return DataSourceConfig.get_api_key("polygon")


def get_alpha_vantage_api_key() -> Optional[str]:
    """Get Alpha Vantage API key."""
    return DataSourceConfig.get_api_key("alpha_vantage")


def get_binance_api_key() -> Optional[str]:
    """Get Binance API key (optional for public endpoints)."""
    return DataSourceConfig.get_api_key("binance")
