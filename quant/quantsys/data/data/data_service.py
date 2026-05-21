"""Unified data service with multi-source support."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd

from quantsys.data.data.sources.base_adapter import BaseDataAdapter
from quantsys.data.data.sources.akshare_adapter import AkShareAdapter
from quantsys.data.data.sources.data_source_manager import DataSourceManager
from quantsys.data.data.storage.cache_manager import CacheManager
from quantsys.data.data.cleaner.validator import DataValidator
from quantsys.data.data import config


class DataService:
    """Unified data service with multi-source support and caching.

    This service provides a high-level interface for fetching stock data
    with automatic fallback between multiple data sources, caching, and
    data validation.

    Example:
        service = DataService()
        df = service.get_daily_klines("000001", days=365)
        # Automatically tries tushare -> akshare with caching
    """

    def __init__(
        self,
        cache_enabled: bool = True,
        validate_data: bool = True,
    ):
        """Initialize data service.

        Args:
            cache_enabled: Enable caching (default True)
            validate_data: Enable data validation (default True)
        """
        self.cache_enabled = cache_enabled
        self.validate_data = validate_data

        # Initialize components
        self.manager = DataSourceManager()
        self.cache = CacheManager(
            max_size=config.CACHE_MAX_SIZE,
            default_ttl=config.CACHE_DEFAULT_TTL,
        ) if cache_enabled else None
        self.validator = DataValidator() if validate_data else None

        # Initialize data sources
        self._init_data_sources()

    def _init_data_sources(self):
        """Initialize all configured data sources."""
        # Add Tushare if token is available
        if config.TUSHARE_ENABLED:
            try:
                from quantsys.data.data.sources.tushare_adapter import TushareAdapter
                tushare = TushareAdapter(
                    token=config.TUSHARE_TOKEN,
                    rate_limit=config.TUSHARE_RATE_LIMIT,
                )
                self.manager.add_source(
                    "tushare",
                    tushare,
                    priority=config.DATA_SOURCE_PRIORITIES["tushare"],
                    enabled=True,
                )
                print("[DataService] Tushare adapter initialized")
            except Exception as exc:
                print(f"[DataService] Failed to initialize Tushare: {exc}")

        # Add AkShare (always available)
        if config.AKSHARE_ENABLED:
            try:
                akshare = AkShareAdapter()
                self.manager.add_source(
                    "akshare",
                    akshare,
                    priority=config.DATA_SOURCE_PRIORITIES["akshare"],
                    enabled=True,
                )
                print("[DataService] AkShare adapter initialized")
            except Exception as exc:
                print(f"[DataService] Failed to initialize AkShare: {exc}")

    def get_daily_klines(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        days: Optional[int] = None,
        adjust: str = "qfq",
        use_cache: bool = True,
    ) -> pd.DataFrame:
        """Get daily K-line data with caching and validation.

        Args:
            symbol: Stock symbol (e.g., "000001")
            start_date: Start date in YYYYMMDD format (optional)
            end_date: End date in YYYYMMDD format (optional)
            days: Number of days to fetch (alternative to start_date)
            adjust: Adjustment type - "qfq", "hfq", ""
            use_cache: Use cache if available (default True)

        Returns:
            DataFrame with K-line data

        Raises:
            ValueError: If date parameters are invalid
            RuntimeError: If all data sources fail
        """
        # Calculate date range
        if end_date is None:
            end_date = datetime.now().strftime("%Y%m%d")

        if start_date is None:
            if days is None:
                days = 365  # Default to 1 year
            start_dt = datetime.now() - timedelta(days=days)
            start_date = start_dt.strftime("%Y%m%d")

        # Check cache first
        if use_cache and self.cache:
            cached = self.cache.get_klines(symbol, start_date, end_date)
            if cached is not None:
                print(f"[DataService] Cache hit for {symbol}")
                return cached

        # Fetch from data sources
        df = self.manager.fetch_daily_klines(symbol, start_date, end_date, adjust)

        # Validate data
        if self.validate_data and self.validator and not df.empty:
            result = self.validator.validate(df)
            if not result["is_valid"]:
                print(f"[DataService] Data validation warnings for {symbol}:")
                for error in result["errors"]:
                    print(f"  - {error}")

        # Cache the result
        if use_cache and self.cache and not df.empty:
            self.cache.set_klines(symbol, df, start_date, end_date)

        return df

    def get_stock_list(
        self,
        market: str = "A",
        use_cache: bool = True,
    ) -> pd.DataFrame:
        """Get stock list with caching.

        Args:
            market: Market type - "A" or "HK"
            use_cache: Use cache if available (default True)

        Returns:
            DataFrame with stock list

        Raises:
            RuntimeError: If all data sources fail
        """
        cache_key = f"stock_list_{market}"

        # Check cache first
        if use_cache and self.cache:
            cached = self.cache.get(cache_key)
            if cached is not None:
                print(f"[DataService] Cache hit for stock list ({market})")
                return cached

        # Fetch from data sources
        df = self.manager.fetch_stock_list(market)

        # Cache the result
        if use_cache and self.cache and not df.empty:
            self.cache.set(cache_key, df, ttl=3600)  # Cache for 1 hour

        return df

    def get_realtime_quote(self, symbol: str) -> dict:
        """Get real-time quote.

        Args:
            symbol: Stock symbol

        Returns:
            Dict with quote data

        Raises:
            RuntimeError: If all data sources fail
        """
        return self.manager.fetch_realtime_quote(symbol)

    def get_health_status(self) -> dict:
        """Get health status of all data sources.

        Returns:
            Dict mapping source name to health status
        """
        return self.manager.get_health_status()

    def reset_health_status(self, source: Optional[str] = None):
        """Reset health status for a source or all sources.

        Args:
            source: Source name to reset, or None to reset all
        """
        self.manager.reset_health_status(source)

    def clear_cache(self):
        """Clear all cached data."""
        if self.cache:
            self.cache.clear()
            print("[DataService] Cache cleared")

    def get_cache_stats(self) -> dict:
        """Get cache statistics.

        Returns:
            Dict with cache statistics
        """
        if self.cache:
            return self.cache.get_stats()
        return {}
