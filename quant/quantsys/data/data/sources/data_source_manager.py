"""Data source manager with automatic fallback support."""

from __future__ import annotations

import time
from typing import Any, Optional

import pandas as pd

from quantsys.data.data.sources.base_adapter import BaseDataAdapter


class DataSourceManager:
    """Manages multiple data sources with automatic fallback.

    Provides unified interface to fetch data from multiple sources with
    automatic fallback when primary source fails.

    Example:
        manager = DataSourceManager()
        manager.add_source("tushare", tushare_adapter, priority=1)
        manager.add_source("akshare", akshare_adapter, priority=2)

        # Automatically tries tushare first, falls back to akshare if it fails
        df = manager.fetch_daily_klines("000001", "20240101", "20240131")
    """

    def __init__(self):
        """Initialize data source manager."""
        self.sources: dict[str, dict[str, Any]] = {}
        self.health_status: dict[str, dict[str, Any]] = {}

    def add_source(
        self,
        name: str,
        adapter: BaseDataAdapter,
        priority: int = 100,
        enabled: bool = True,
    ):
        """Add a data source.

        Args:
            name: Source name (e.g., "tushare", "akshare")
            adapter: Data adapter instance
            priority: Priority (lower = higher priority, 1 is highest)
            enabled: Whether the source is enabled
        """
        self.sources[name] = {
            "adapter": adapter,
            "priority": priority,
            "enabled": enabled,
        }

        self.health_status[name] = {
            "available": True,
            "last_success": None,
            "last_failure": None,
            "failure_count": 0,
            "success_count": 0,
        }

        print(f"[DataSourceManager] Added source: {name} (priority={priority})")

    def remove_source(self, name: str):
        """Remove a data source.

        Args:
            name: Source name to remove
        """
        if name in self.sources:
            del self.sources[name]
            del self.health_status[name]
            print(f"[DataSourceManager] Removed source: {name}")

    def enable_source(self, name: str):
        """Enable a data source.

        Args:
            name: Source name to enable
        """
        if name in self.sources:
            self.sources[name]["enabled"] = True
            print(f"[DataSourceManager] Enabled source: {name}")

    def disable_source(self, name: str):
        """Disable a data source.

        Args:
            name: Source name to disable
        """
        if name in self.sources:
            self.sources[name]["enabled"] = False
            print(f"[DataSourceManager] Disabled source: {name}")

    def _get_sorted_sources(self) -> list[tuple[str, dict]]:
        """Get enabled sources sorted by priority.

        Returns:
            List of (name, source_info) tuples sorted by priority
        """
        enabled = [(name, info) for name, info in self.sources.items() if info["enabled"]]
        return sorted(enabled, key=lambda x: x[1]["priority"])

    def _mark_success(self, name: str):
        """Mark a source as successful.

        Args:
            name: Source name
        """
        status = self.health_status[name]
        status["available"] = True
        status["last_success"] = time.time()
        status["success_count"] += 1
        status["failure_count"] = 0  # Reset failure count on success

    def _mark_failure(self, name: str, error: Exception):
        """Mark a source as failed.

        Args:
            name: Source name
            error: Exception that occurred
        """
        status = self.health_status[name]
        status["last_failure"] = time.time()
        status["failure_count"] += 1

        # Disable source after 3 consecutive failures
        if status["failure_count"] >= 3:
            status["available"] = False
            print(f"[DataSourceManager] Source {name} disabled after 3 failures")

    def fetch_daily_klines(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        adjust: str = "qfq",
    ) -> pd.DataFrame:
        """Fetch daily K-line data with automatic fallback.

        Args:
            symbol: Stock symbol
            start_date: Start date in YYYYMMDD format
            end_date: End date in YYYYMMDD format
            adjust: Adjustment type - "qfq", "hfq", ""

        Returns:
            DataFrame with K-line data

        Raises:
            RuntimeError: If all sources fail
        """
        sources = self._get_sorted_sources()

        if not sources:
            raise RuntimeError("No data sources available")

        errors = []

        for name, info in sources:
            # Skip unavailable sources
            if not self.health_status[name]["available"]:
                continue

            adapter = info["adapter"]

            try:
                print(f"[DataSourceManager] Trying {name} for {symbol}...")
                df = adapter.fetch_daily_klines(symbol, start_date, end_date, adjust)

                if df is not None and not df.empty:
                    self._mark_success(name)
                    print(f"[DataSourceManager] ✓ {name} succeeded ({len(df)} rows)")
                    return df
                else:
                    print(f"[DataSourceManager] {name} returned empty data")

            except Exception as exc:
                self._mark_failure(name, exc)
                errors.append(f"{name}: {exc}")
                print(f"[DataSourceManager] ✗ {name} failed: {exc}")
                continue

        # All sources failed
        error_msg = f"All data sources failed for {symbol}:\n" + "\n".join(errors)
        raise RuntimeError(error_msg)

    def fetch_stock_list(self, market: str = "A") -> pd.DataFrame:
        """Fetch stock list with automatic fallback.

        Args:
            market: Market type - "A" or "HK"

        Returns:
            DataFrame with stock list

        Raises:
            RuntimeError: If all sources fail
        """
        sources = self._get_sorted_sources()

        if not sources:
            raise RuntimeError("No data sources available")

        errors = []

        for name, info in sources:
            if not self.health_status[name]["available"]:
                continue

            adapter = info["adapter"]

            try:
                print(f"[DataSourceManager] Trying {name} for stock list...")
                df = adapter.fetch_stock_list(market)

                if df is not None and not df.empty:
                    self._mark_success(name)
                    print(f"[DataSourceManager] ✓ {name} succeeded ({len(df)} stocks)")
                    return df

            except Exception as exc:
                self._mark_failure(name, exc)
                errors.append(f"{name}: {exc}")
                print(f"[DataSourceManager] ✗ {name} failed: {exc}")
                continue

        error_msg = f"All data sources failed for stock list:\n" + "\n".join(errors)
        raise RuntimeError(error_msg)

    def fetch_realtime_quote(self, symbol: str) -> dict:
        """Fetch real-time quote with automatic fallback.

        Args:
            symbol: Stock symbol

        Returns:
            Dict with quote data

        Raises:
            RuntimeError: If all sources fail
        """
        sources = self._get_sorted_sources()

        if not sources:
            raise RuntimeError("No data sources available")

        errors = []

        for name, info in sources:
            if not self.health_status[name]["available"]:
                continue

            adapter = info["adapter"]

            try:
                print(f"[DataSourceManager] Trying {name} for realtime quote...")
                quote = adapter.fetch_realtime_quote(symbol)

                if quote:
                    self._mark_success(name)
                    print(f"[DataSourceManager] ✓ {name} succeeded")
                    return quote

            except NotImplementedError:
                # Skip sources that don't support realtime quotes
                continue
            except Exception as exc:
                self._mark_failure(name, exc)
                errors.append(f"{name}: {exc}")
                print(f"[DataSourceManager] ✗ {name} failed: {exc}")
                continue

        error_msg = f"All data sources failed for realtime quote:\n" + "\n".join(errors)
        raise RuntimeError(error_msg)

    def get_health_status(self) -> dict[str, dict]:
        """Get health status of all sources.

        Returns:
            Dict mapping source name to health status
        """
        return self.health_status.copy()

    def reset_health_status(self, name: Optional[str] = None):
        """Reset health status for a source or all sources.

        Args:
            name: Source name to reset, or None to reset all
        """
        if name:
            if name in self.health_status:
                self.health_status[name] = {
                    "available": True,
                    "last_success": None,
                    "last_failure": None,
                    "failure_count": 0,
                    "success_count": 0,
                }
                print(f"[DataSourceManager] Reset health status for {name}")
        else:
            for source_name in self.health_status:
                self.health_status[source_name] = {
                    "available": True,
                    "last_success": None,
                    "last_failure": None,
                    "failure_count": 0,
                    "success_count": 0,
                }
            print("[DataSourceManager] Reset health status for all sources")
