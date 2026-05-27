"""Gap detector for identifying missing K-line data.

This module provides the GapDetector class that compares database records
against the trading calendar to identify missing daily and minute K-line data.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import List, TYPE_CHECKING

if TYPE_CHECKING:
    from quantsys.data.db import Database
    from quantsys.data.trading_calendar import TradingCalendar


class GapDetector:
    """Detect missing K-line data by comparing database records against trading calendar.

    This class identifies gaps in both daily and minute K-line data by:
    1. Querying existing data coverage from the database
    2. Getting expected trading days from the calendar
    3. Computing the set difference to find missing dates
    """

    def __init__(self, db: Database, calendar: TradingCalendar) -> None:
        """Initialize the gap detector.

        Args:
            db: Database instance for querying K-line data
            calendar: TradingCalendar instance for getting expected trading days
        """
        self.db = db
        self.calendar = calendar

    def detect_daily_gaps(self, symbol: str, target_days: int = 730) -> List[str]:
        """Detect missing daily K-line data for a symbol.

        Args:
            symbol: Stock symbol (e.g., "600519.SH")
            target_days: Number of calendar days to check backwards from last date
                        (Note: This is calendar days, not trading days. 730 calendar days
                        covers approximately 2 years of trading days)

        Returns:
            List of missing dates in "YYYY-MM-DD" format, sorted ascending.
            Returns empty list if symbol has no data (new symbol case).
        """
        # Get existing coverage from database
        coverage = self.db.get_kline_coverage(symbol)

        # If no data exists, return empty list (new symbol case)
        if coverage["existing_days"] == 0 or coverage["last_date"] is None:
            return []

        # Parse the last date
        last_date_str = coverage["last_date"]
        last_date = date.fromisoformat(last_date_str)

        # Calculate start date (target_days calendar days before last_date)
        start_date = last_date - timedelta(days=target_days)

        # Get expected trading days from calendar
        expected_dates = self.calendar.get_trading_days(start_date, last_date)
        expected_dates_set = set(expected_dates)

        # Get actual dates from database
        actual_dates_set = self._get_daily_dates_from_db(symbol, start_date, last_date)

        # Find missing dates
        missing_dates = expected_dates_set - actual_dates_set

        # Convert to sorted list of strings
        return sorted([d.isoformat() for d in missing_dates])

    def detect_minute_gaps(self, symbol: str, target_days: int = 365) -> List[str]:
        """Detect missing minute K-line data for a symbol.

        Args:
            symbol: Stock symbol (e.g., "600519.SH")
            target_days: Number of calendar days to check backwards from last date
                        (Note: This is calendar days, not trading days. 365 calendar days
                        covers approximately 1 year of trading days)

        Returns:
            List of missing dates in "YYYY-MM-DD" format, sorted ascending.
            Returns empty list if symbol has no data (new symbol case).
        """
        # Get existing coverage from database
        date_range = self.db.get_minute_kline_dates(symbol)

        # If no data exists, return empty list (new symbol case)
        if date_range["min_date"] is None or date_range["max_date"] is None:
            return []

        # Parse the last date
        last_date_str = date_range["max_date"]
        last_date = date.fromisoformat(last_date_str)

        # Calculate start date (target_days calendar days before last_date)
        start_date = last_date - timedelta(days=target_days)

        # Get expected trading days from calendar
        expected_dates = self.calendar.get_trading_days(start_date, last_date)
        expected_dates_set = set(expected_dates)

        # Get actual dates from database
        actual_dates_set = self._get_minute_dates_from_db(symbol, start_date, last_date)

        # Find missing dates
        missing_dates = expected_dates_set - actual_dates_set

        # Convert to sorted list of strings
        return sorted([d.isoformat() for d in missing_dates])

    def _get_daily_dates_from_db(self, symbol: str, start_date: date, end_date: date) -> set[date]:
        """Query database for actual daily K-line dates within date range.

        Args:
            symbol: Stock symbol
            start_date: Start of date range
            end_date: End of date range

        Returns:
            Set of date objects representing dates with data in database
        """
        connection = self.db.get_connection()
        cursor = connection.cursor()

        try:
            if self.db.provider == "postgres":
                cursor.execute(
                    """
                    SELECT DISTINCT trade_date::text
                    FROM quant.daily_klines
                    WHERE symbol = %s
                      AND trade_date >= %s::date
                      AND trade_date <= %s::date
                    ORDER BY trade_date
                    """,
                    (symbol, start_date.isoformat(), end_date.isoformat()),
                )
            else:
                cursor.execute(
                    """
                    SELECT DISTINCT date
                    FROM daily_klines
                    WHERE symbol = ?
                      AND date >= ?
                      AND date <= ?
                    ORDER BY date
                    """,
                    (symbol, start_date.isoformat(), end_date.isoformat()),
                )

            rows = cursor.fetchall()

            # Convert to set of date objects using set comprehension
            return {date.fromisoformat(row[0]) for row in rows}

        finally:
            cursor.close()

    def _get_minute_dates_from_db(self, symbol: str, start_date: date, end_date: date) -> set[date]:
        """Query database for actual minute K-line dates within date range.

        Args:
            symbol: Stock symbol
            start_date: Start of date range
            end_date: End of date range

        Returns:
            Set of date objects representing dates with data in database

        Raises:
            RuntimeError: If database provider is not PostgreSQL
        """
        if self.db.provider != "postgres":
            raise RuntimeError("Minute klines are only supported with PostgreSQL")

        connection = self.db.get_connection()
        cursor = connection.cursor()

        try:
            cursor.execute(
                """
                SELECT DISTINCT trade_datetime::date::text
                FROM quant.minute_klines
                WHERE symbol = %s
                  AND trade_datetime::date >= %s::date
                  AND trade_datetime::date <= %s::date
                ORDER BY trade_datetime::date
                """,
                (symbol, start_date.isoformat(), end_date.isoformat()),
            )

            rows = cursor.fetchall()

            # Convert to set of date objects using set comprehension
            return {date.fromisoformat(row[0]) for row in rows}

        finally:
            cursor.close()
