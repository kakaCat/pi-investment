"""
DataBackfiller - Downloads missing K-line data from akshare and stores in database.
"""
import logging
import time
from datetime import date
from typing import Dict, Any, Optional, List

import akshare as ak
import pandas as pd

from .db import Database
from .trading_calendar import TradingCalendar
from .gap_detector import GapDetector
from .progress_tracker import ProgressTracker

logger = logging.getLogger(__name__)


class DataBackfiller:
    """Downloads missing K-line data and stores in database."""

    def __init__(
        self,
        db: Database,
        calendar: TradingCalendar,
        gap_detector: GapDetector,
        progress_tracker: ProgressTracker
    ):
        """
        Initialize DataBackfiller.

        Args:
            db: Database instance for storage
            calendar: TradingCalendar for trading day validation
            gap_detector: GapDetector for identifying missing data
            progress_tracker: ProgressTracker for resume support
        """
        self.db = db
        self.calendar = calendar
        self.gap_detector = gap_detector
        self.progress_tracker = progress_tracker

    def backfill_daily(self, symbol: str, target_days: int = 730) -> Dict[str, Any]:
        """
        Backfill missing daily K-line data.

        Args:
            symbol: Stock symbol (e.g., "600519.SH")
            target_days: Number of days to look back (default: 730)

        Returns:
            Summary dict with keys: symbol, total, succeeded, failed, skipped
        """
        logger.info(f"Starting daily backfill for {symbol}, target_days={target_days}")

        # Detect missing dates
        missing_dates = self.gap_detector.detect_daily_gaps(symbol, target_days)
        total = len(missing_dates)

        if total == 0:
            logger.info(f"No missing daily data for {symbol}")
            return {
                "symbol": symbol,
                "total": 0,
                "succeeded": 0,
                "failed": 0,
                "skipped": 0
            }

        succeeded = 0
        failed = 0
        skipped = 0

        for missing_date in missing_dates:
            date_str = missing_date.strftime("%Y-%m-%d")

            # Skip if already completed
            if self.progress_tracker.is_completed(symbol, missing_date, "daily"):
                logger.debug(f"Skipping {symbol} {date_str} (already completed)")
                skipped += 1
                continue

            # Download data
            kline_data = self._download_daily_kline(symbol, date_str)

            if kline_data is None:
                logger.error(f"Failed to download daily data for {symbol} {date_str}")
                failed += 1
                continue

            # Store in database
            try:
                self.db.upsert_daily_klines([kline_data])
                self.progress_tracker.mark_completed(symbol, missing_date, "daily")
                succeeded += 1
                logger.info(f"Successfully backfilled {symbol} {date_str}")
            except Exception as e:
                logger.error(f"Failed to store daily data for {symbol} {date_str}: {e}")
                failed += 1

            # Small delay to avoid rate limiting
            time.sleep(0.1)

        logger.info(
            f"Daily backfill complete for {symbol}: "
            f"total={total}, succeeded={succeeded}, failed={failed}, skipped={skipped}"
        )

        return {
            "symbol": symbol,
            "total": total,
            "succeeded": succeeded,
            "failed": failed,
            "skipped": skipped
        }

    def backfill_minute(self, symbol: str, target_days: int = 365) -> Dict[str, Any]:
        """
        Backfill missing minute K-line data.

        Args:
            symbol: Stock symbol (e.g., "600519.SH")
            target_days: Number of days to look back (default: 365)

        Returns:
            Summary dict with keys: symbol, total, succeeded, failed, skipped
        """
        logger.info(f"Starting minute backfill for {symbol}, target_days={target_days}")

        # Detect missing dates
        missing_dates = self.gap_detector.detect_minute_gaps(symbol, target_days)
        total = len(missing_dates)

        if total == 0:
            logger.info(f"No missing minute data for {symbol}")
            return {
                "symbol": symbol,
                "total": 0,
                "succeeded": 0,
                "failed": 0,
                "skipped": 0
            }

        succeeded = 0
        failed = 0
        skipped = 0

        for missing_date in missing_dates:
            date_str = missing_date.strftime("%Y-%m-%d")

            # Skip if already completed
            if self.progress_tracker.is_completed(symbol, missing_date, "minute"):
                logger.debug(f"Skipping {symbol} {date_str} (already completed)")
                skipped += 1
                continue

            # Download data
            kline_data_list = self._download_minute_kline(symbol, date_str)

            if kline_data_list is None:
                logger.error(f"Failed to download minute data for {symbol} {date_str}")
                failed += 1
                continue

            # Store in database
            try:
                self.db.upsert_minute_klines(kline_data_list)
                self.progress_tracker.mark_completed(symbol, missing_date, "minute")
                succeeded += 1
                logger.info(f"Successfully backfilled {symbol} {date_str} ({len(kline_data_list)} bars)")
            except Exception as e:
                logger.error(f"Failed to store minute data for {symbol} {date_str}: {e}")
                failed += 1

            # Small delay to avoid rate limiting
            time.sleep(0.1)

        logger.info(
            f"Minute backfill complete for {symbol}: "
            f"total={total}, succeeded={succeeded}, failed={failed}, skipped={skipped}"
        )

        return {
            "symbol": symbol,
            "total": total,
            "succeeded": succeeded,
            "failed": failed,
            "skipped": skipped
        }

    def _download_daily_kline(self, symbol: str, date_str: str) -> Optional[Dict[str, Any]]:
        """
        Download daily K-line data for one date from akshare.

        Args:
            symbol: Stock symbol (e.g., "600519.SH")
            date_str: Date string in format "YYYY-MM-DD"

        Returns:
            Dict with keys: symbol, date, open, high, low, close, volume, amount
            None if download fails after retries
        """
        # Convert symbol format for akshare (remove .SH/.SZ suffix)
        ak_symbol = symbol.split('.')[0]

        max_retries = 3
        for attempt in range(max_retries):
            try:
                # Download data from akshare
                df = ak.stock_zh_a_hist(
                    symbol=ak_symbol,
                    period="daily",
                    start_date=date_str.replace('-', ''),
                    end_date=date_str.replace('-', ''),
                    adjust=""
                )

                if df.empty:
                    logger.warning(f"No data returned for {symbol} {date_str}")
                    return None

                # Extract first row (should be only row for single date)
                row = df.iloc[0]

                return {
                    "symbol": symbol,
                    "date": date_str,
                    "open": float(row['开盘']),
                    "high": float(row['最高']),
                    "low": float(row['最低']),
                    "close": float(row['收盘']),
                    "volume": int(row['成交量']),
                    "amount": float(row['成交额'])
                }

            except Exception as e:
                logger.warning(
                    f"Attempt {attempt + 1}/{max_retries} failed for {symbol} {date_str}: {e}"
                )
                if attempt < max_retries - 1:
                    # Exponential backoff
                    sleep_time = 2 ** attempt
                    time.sleep(sleep_time)
                else:
                    logger.error(f"All retries exhausted for {symbol} {date_str}")
                    return None

        return None

    def _download_minute_kline(self, symbol: str, date_str: str) -> Optional[List[Dict[str, Any]]]:
        """
        Download 1-minute K-line data for one date from akshare.

        Args:
            symbol: Stock symbol (e.g., "600519.SH")
            date_str: Date string in format "YYYY-MM-DD"

        Returns:
            List of dicts with keys: symbol, trade_datetime, open, high, low, close, volume, amount
            None if download fails after retries
        """
        # Convert symbol format for akshare (remove .SH/.SZ suffix)
        ak_symbol = symbol.split('.')[0]

        max_retries = 3
        for attempt in range(max_retries):
            try:
                # Download data from akshare
                df = ak.stock_zh_a_hist_min_em(
                    symbol=ak_symbol,
                    period="1",
                    start_date=f"{date_str} 09:30:00",
                    end_date=f"{date_str} 15:00:00",
                    adjust=""
                )

                if df.empty:
                    logger.warning(f"No minute data returned for {symbol} {date_str}")
                    return None

                # Convert DataFrame to list of dicts
                result = []
                for _, row in df.iterrows():
                    result.append({
                        "symbol": symbol,
                        "trade_datetime": str(row['时间']),
                        "open": float(row['开盘']),
                        "high": float(row['最高']),
                        "low": float(row['最低']),
                        "close": float(row['收盘']),
                        "volume": int(row['成交量']),
                        "amount": float(row['成交额'])
                    })

                return result

            except Exception as e:
                logger.warning(
                    f"Attempt {attempt + 1}/{max_retries} failed for {symbol} {date_str}: {e}"
                )
                if attempt < max_retries - 1:
                    # Exponential backoff
                    sleep_time = 2 ** attempt
                    time.sleep(sleep_time)
                else:
                    logger.error(f"All retries exhausted for {symbol} {date_str}")
                    return None

        return None
