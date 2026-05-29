"""Tests for GapDetector class."""

import pytest
from datetime import date, timedelta
from unittest.mock import Mock, MagicMock
from quantsys.data.gap_detector import GapDetector


class TestGapDetector:
    """Test suite for GapDetector class."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock Database instance."""
        return Mock()

    @pytest.fixture
    def mock_calendar(self):
        """Create a mock TradingCalendar instance."""
        return Mock()

    @pytest.fixture
    def gap_detector(self, mock_db, mock_calendar):
        """Create a GapDetector instance with mocked dependencies."""
        return GapDetector(mock_db, mock_calendar)

    def test_init(self, mock_db, mock_calendar):
        """Test GapDetector initialization."""
        detector = GapDetector(mock_db, mock_calendar)
        assert detector.db is mock_db
        assert detector.calendar is mock_calendar

    def test_detect_daily_gaps_no_data(self, gap_detector, mock_db, mock_calendar):
        """Test detect_daily_gaps when symbol has no data (new symbol case)."""
        # Mock: symbol has no data
        mock_db.get_kline_coverage.return_value = {
            "existing_days": 0,
            "first_date": None,
            "last_date": None
        }

        result = gap_detector.detect_daily_gaps("600519.SH", target_days=730)

        # Should return empty list for new symbols
        assert result == []
        mock_db.get_kline_coverage.assert_called_once_with("600519.SH")

    def test_detect_daily_gaps_with_missing_dates(self, gap_detector, mock_db, mock_calendar):
        """Test detect_daily_gaps when there are missing dates."""
        # Mock: symbol has data from 2024-01-02 to 2024-01-15
        mock_db.get_kline_coverage.return_value = {
            "existing_days": 8,
            "first_date": "2024-01-02",
            "last_date": "2024-01-15"
        }

        # Mock: trading calendar has 10 trading days
        trading_days = [
            date(2024, 1, 2),
            date(2024, 1, 3),
            date(2024, 1, 4),
            date(2024, 1, 5),
            date(2024, 1, 8),
            date(2024, 1, 9),
            date(2024, 1, 10),
            date(2024, 1, 11),
            date(2024, 1, 12),
            date(2024, 1, 15),
        ]
        mock_calendar.get_trading_days.return_value = trading_days

        # Mock: database query returns existing dates (missing 2024-01-04 and 2024-01-09)
        mock_cursor = Mock()
        mock_cursor.fetchall.return_value = [
            ("2024-01-02",),
            ("2024-01-03",),
            ("2024-01-05",),
            ("2024-01-08",),
            ("2024-01-10",),
            ("2024-01-11",),
            ("2024-01-12",),
            ("2024-01-15",),
        ]
        mock_db.get_connection.return_value.cursor.return_value = mock_cursor

        result = gap_detector.detect_daily_gaps("600519.SH", target_days=20)

        # Should return missing dates
        assert len(result) == 2
        assert "2024-01-04" in result
        assert "2024-01-09" in result

    def test_detect_daily_gaps_no_gaps(self, gap_detector, mock_db, mock_calendar):
        """Test detect_daily_gaps when there are no gaps."""
        # Mock: symbol has complete data
        mock_db.get_kline_coverage.return_value = {
            "existing_days": 5,
            "first_date": "2024-01-02",
            "last_date": "2024-01-08"
        }

        # Mock: trading calendar
        trading_days = [
            date(2024, 1, 2),
            date(2024, 1, 3),
            date(2024, 1, 4),
            date(2024, 1, 5),
            date(2024, 1, 8),
        ]
        mock_calendar.get_trading_days.return_value = trading_days

        # Mock: database has all dates
        mock_cursor = Mock()
        mock_cursor.fetchall.return_value = [
            ("2024-01-02",),
            ("2024-01-03",),
            ("2024-01-04",),
            ("2024-01-05",),
            ("2024-01-08",),
        ]
        mock_db.get_connection.return_value.cursor.return_value = mock_cursor

        result = gap_detector.detect_daily_gaps("600519.SH", target_days=10)

        # Should return empty list
        assert result == []

    def test_detect_minute_gaps_no_data(self, gap_detector, mock_db, mock_calendar):
        """Test detect_minute_gaps when symbol has no data."""
        # Mock: symbol has no minute data
        mock_db.get_minute_kline_dates.return_value = {
            "min_date": None,
            "max_date": None
        }

        result = gap_detector.detect_minute_gaps("600519.SH", target_days=365)

        # Should return empty list for new symbols
        assert result == []
        mock_db.get_minute_kline_dates.assert_called_once_with("600519.SH")

    def test_detect_minute_gaps_with_missing_dates(self, gap_detector, mock_db, mock_calendar):
        """Test detect_minute_gaps when there are missing dates."""
        # Mock: symbol has minute data from 2024-01-02 to 2024-01-10
        mock_db.get_minute_kline_dates.return_value = {
            "min_date": "2024-01-02",
            "max_date": "2024-01-10"
        }

        # Mock: trading calendar
        trading_days = [
            date(2024, 1, 2),
            date(2024, 1, 3),
            date(2024, 1, 4),
            date(2024, 1, 5),
            date(2024, 1, 8),
            date(2024, 1, 9),
            date(2024, 1, 10),
        ]
        mock_calendar.get_trading_days.return_value = trading_days

        # Mock: database query returns existing dates (missing 2024-01-04 and 2024-01-09)
        mock_cursor = Mock()
        mock_cursor.fetchall.return_value = [
            ("2024-01-02",),
            ("2024-01-03",),
            ("2024-01-05",),
            ("2024-01-08",),
            ("2024-01-10",),
        ]
        mock_db.get_connection.return_value.cursor.return_value = mock_cursor
        mock_db.provider = "postgres"

        result = gap_detector.detect_minute_gaps("600519.SH", target_days=10)

        # Should return missing dates
        assert len(result) == 2
        assert "2024-01-04" in result
        assert "2024-01-09" in result

    def test_detect_minute_gaps_uses_explicit_end_date(self, gap_detector, mock_db, mock_calendar):
        """Test detect_minute_gaps can fill through a fixed cutoff date."""
        mock_db.get_minute_kline_dates.return_value = {
            "min_date": "2025-05-28",
            "max_date": "2026-05-21"
        }
        mock_calendar.get_trading_days.return_value = [
            date(2026, 5, 21),
            date(2026, 5, 22),
            date(2026, 5, 25),
            date(2026, 5, 26),
            date(2026, 5, 27),
        ]

        mock_cursor = Mock()
        mock_cursor.fetchall.return_value = [("2026-05-21",)]
        mock_db.get_connection.return_value.cursor.return_value = mock_cursor
        mock_db.provider = "postgres"

        result = gap_detector.detect_minute_gaps(
            "600519.SH",
            target_days=365,
            end_date="2026-05-27",
        )

        assert result == ["2026-05-22", "2026-05-25", "2026-05-26", "2026-05-27"]
        start_date, end_date_arg = mock_calendar.get_trading_days.call_args[0]
        assert start_date == date(2025, 5, 27)
        assert end_date_arg == date(2026, 5, 27)
        executed_sql = mock_cursor.execute.call_args[0][0]
        assert "AS trade_date" in executed_sql
        assert "ORDER BY trade_date" in executed_sql

    def test_detect_minute_gaps_no_gaps(self, gap_detector, mock_db, mock_calendar):
        """Test detect_minute_gaps when there are no gaps."""
        # Mock: symbol has complete minute data
        mock_db.get_minute_kline_dates.return_value = {
            "min_date": "2024-01-02",
            "max_date": "2024-01-08"
        }

        # Mock: trading calendar
        trading_days = [
            date(2024, 1, 2),
            date(2024, 1, 3),
            date(2024, 1, 4),
            date(2024, 1, 5),
            date(2024, 1, 8),
        ]
        mock_calendar.get_trading_days.return_value = trading_days

        # Mock: database has all dates
        mock_cursor = Mock()
        mock_cursor.fetchall.return_value = [
            ("2024-01-02",),
            ("2024-01-03",),
            ("2024-01-04",),
            ("2024-01-05",),
            ("2024-01-08",),
        ]
        mock_db.get_connection.return_value.cursor.return_value = mock_cursor
        mock_db.provider = "postgres"

        result = gap_detector.detect_minute_gaps("600519.SH", target_days=10)

        # Should return empty list
        assert result == []

    def test_detect_daily_gaps_target_days_calculation(self, gap_detector, mock_db, mock_calendar):
        """Test that target_days correctly calculates the date range."""
        # Mock: symbol has data ending on 2024-12-31
        mock_db.get_kline_coverage.return_value = {
            "existing_days": 100,
            "first_date": "2024-01-01",
            "last_date": "2024-12-31"
        }

        # Mock: trading calendar
        mock_calendar.get_trading_days.return_value = []

        # Mock: database query
        mock_cursor = Mock()
        mock_cursor.fetchall.return_value = []
        mock_db.get_connection.return_value.cursor.return_value = mock_cursor

        gap_detector.detect_daily_gaps("600519.SH", target_days=365)

        # Verify get_trading_days was called with correct date range
        # Should be approximately 365 days before 2024-12-31
        call_args = mock_calendar.get_trading_days.call_args[0]
        start_date, end_date = call_args
        assert end_date == date(2024, 12, 31)
        # Allow some flexibility in the exact start date calculation
        assert (end_date - start_date).days >= 360
        assert (end_date - start_date).days <= 370

    def test_detect_minute_gaps_non_postgres_provider(self, gap_detector, mock_db, mock_calendar):
        """Test detect_minute_gaps raises RuntimeError for non-PostgreSQL providers."""
        # Mock: symbol has minute data
        mock_db.get_minute_kline_dates.return_value = {
            "min_date": "2024-01-02",
            "max_date": "2024-01-10"
        }

        # Mock: trading calendar
        mock_calendar.get_trading_days.return_value = [date(2024, 1, 2)]

        # Mock: database provider is SQLite
        mock_db.provider = "sqlite"

        # Should raise RuntimeError
        with pytest.raises(RuntimeError, match="Minute klines are only supported with PostgreSQL"):
            gap_detector.detect_minute_gaps("600519.SH", target_days=10)
