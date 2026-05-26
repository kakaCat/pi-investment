"""
Tests for DataBackfiller class.
"""
import pytest
from datetime import datetime, date
from unittest.mock import Mock, patch, call
import pandas as pd

from quantsys.data.data_backfiller import DataBackfiller
from quantsys.data.db import Database
from quantsys.data.trading_calendar import TradingCalendar
from quantsys.data.gap_detector import GapDetector
from quantsys.data.progress_tracker import ProgressTracker


@pytest.fixture
def mock_db():
    """Mock Database instance."""
    db = Mock(spec=Database)
    return db


@pytest.fixture
def mock_calendar():
    """Mock TradingCalendar instance."""
    calendar = Mock(spec=TradingCalendar)
    return calendar


@pytest.fixture
def mock_gap_detector():
    """Mock GapDetector instance."""
    detector = Mock(spec=GapDetector)
    return detector


@pytest.fixture
def mock_progress_tracker():
    """Mock ProgressTracker instance."""
    tracker = Mock(spec=ProgressTracker)
    return tracker


@pytest.fixture
def backfiller(mock_db, mock_calendar, mock_gap_detector, mock_progress_tracker):
    """Create DataBackfiller instance with mocked dependencies."""
    return DataBackfiller(
        db=mock_db,
        calendar=mock_calendar,
        gap_detector=mock_gap_detector,
        progress_tracker=mock_progress_tracker
    )


class TestDataBackfillerInit:
    """Test DataBackfiller initialization."""

    def test_init_stores_dependencies(self, mock_db, mock_calendar, mock_gap_detector, mock_progress_tracker):
        """Test that constructor stores all dependencies."""
        backfiller = DataBackfiller(mock_db, mock_calendar, mock_gap_detector, mock_progress_tracker)

        assert backfiller.db is mock_db
        assert backfiller.calendar is mock_calendar
        assert backfiller.gap_detector is mock_gap_detector
        assert backfiller.progress_tracker is mock_progress_tracker


class TestBackfillDaily:
    """Test backfill_daily method."""

    def test_backfill_daily_no_gaps(self, backfiller, mock_gap_detector):
        """Test backfill_daily when no gaps exist."""
        mock_gap_detector.detect_daily_gaps.return_value = []

        result = backfiller.backfill_daily("600519.SH", target_days=730)

        assert result == {
            "symbol": "600519.SH",
            "total": 0,
            "succeeded": 0,
            "failed": 0,
            "skipped": 0
        }
        mock_gap_detector.detect_daily_gaps.assert_called_once_with("600519.SH", 730)

    def test_backfill_daily_with_gaps_success(self, backfiller, mock_gap_detector, mock_progress_tracker, mock_db):
        """Test backfill_daily successfully downloads missing data."""
        missing_dates = [date(2026, 5, 20), date(2026, 5, 21)]
        mock_gap_detector.detect_daily_gaps.return_value = missing_dates
        mock_progress_tracker.is_completed.return_value = False

        # Mock successful downloads
        with patch.object(backfiller, '_download_daily_kline') as mock_download:
            mock_download.side_effect = [
                {
                    "symbol": "600519.SH",
                    "date": "2026-05-20",
                    "open": 100.0,
                    "high": 105.0,
                    "low": 99.0,
                    "close": 103.0,
                    "volume": 1000000,
                    "amount": 102000000.0
                },
                {
                    "symbol": "600519.SH",
                    "date": "2026-05-21",
                    "open": 103.0,
                    "high": 108.0,
                    "low": 102.0,
                    "close": 107.0,
                    "volume": 1200000,
                    "amount": 126000000.0
                }
            ]

            result = backfiller.backfill_daily("600519.SH", target_days=730)

        assert result == {
            "symbol": "600519.SH",
            "total": 2,
            "succeeded": 2,
            "failed": 0,
            "skipped": 0
        }
        assert mock_download.call_count == 2
        assert mock_db.upsert_daily_klines.call_count == 2
        assert mock_progress_tracker.mark_completed.call_count == 2

    def test_backfill_daily_skips_completed(self, backfiller, mock_gap_detector, mock_progress_tracker):
        """Test backfill_daily skips dates already in progress tracker."""
        missing_dates = [date(2026, 5, 20), date(2026, 5, 21)]
        mock_gap_detector.detect_daily_gaps.return_value = missing_dates
        mock_progress_tracker.is_completed.side_effect = [True, False]  # First is completed

        with patch.object(backfiller, '_download_daily_kline') as mock_download:
            mock_download.return_value = {
                "symbol": "600519.SH",
                "date": "2026-05-21",
                "open": 103.0,
                "high": 108.0,
                "low": 102.0,
                "close": 107.0,
                "volume": 1200000,
                "amount": 126000000.0
            }

            result = backfiller.backfill_daily("600519.SH", target_days=730)

        assert result["total"] == 2
        assert result["succeeded"] == 1
        assert result["skipped"] == 1
        assert mock_download.call_count == 1

    def test_backfill_daily_handles_download_failure(self, backfiller, mock_gap_detector, mock_progress_tracker):
        """Test backfill_daily continues on download failure."""
        missing_dates = [date(2026, 5, 20), date(2026, 5, 21)]
        mock_gap_detector.detect_daily_gaps.return_value = missing_dates
        mock_progress_tracker.is_completed.return_value = False

        with patch.object(backfiller, '_download_daily_kline') as mock_download:
            mock_download.side_effect = [
                None,  # First download fails
                {
                    "symbol": "600519.SH",
                    "date": "2026-05-21",
                    "open": 103.0,
                    "high": 108.0,
                    "low": 102.0,
                    "close": 107.0,
                    "volume": 1200000,
                    "amount": 126000000.0
                }
            ]

            result = backfiller.backfill_daily("600519.SH", target_days=730)

        assert result["total"] == 2
        assert result["succeeded"] == 1
        assert result["failed"] == 1


class TestBackfillMinute:
    """Test backfill_minute method."""

    def test_backfill_minute_no_gaps(self, backfiller, mock_gap_detector):
        """Test backfill_minute when no gaps exist."""
        mock_gap_detector.detect_minute_gaps.return_value = []

        result = backfiller.backfill_minute("600519.SH", target_days=365)

        assert result == {
            "symbol": "600519.SH",
            "total": 0,
            "succeeded": 0,
            "failed": 0,
            "skipped": 0
        }
        mock_gap_detector.detect_minute_gaps.assert_called_once_with("600519.SH", 365)

    def test_backfill_minute_with_gaps_success(self, backfiller, mock_gap_detector, mock_progress_tracker, mock_db):
        """Test backfill_minute successfully downloads missing data."""
        missing_dates = [date(2026, 5, 20)]
        mock_gap_detector.detect_minute_gaps.return_value = missing_dates
        mock_progress_tracker.is_completed.return_value = False

        with patch.object(backfiller, '_download_minute_kline') as mock_download:
            mock_download.return_value = [
                {
                    "symbol": "600519.SH",
                    "trade_datetime": "2026-05-20 09:31:00",
                    "open": 100.0,
                    "high": 101.0,
                    "low": 99.5,
                    "close": 100.5,
                    "volume": 10000,
                    "amount": 1005000.0
                },
                {
                    "symbol": "600519.SH",
                    "trade_datetime": "2026-05-20 09:32:00",
                    "open": 100.5,
                    "high": 102.0,
                    "low": 100.0,
                    "close": 101.5,
                    "volume": 12000,
                    "amount": 1218000.0
                }
            ]

            result = backfiller.backfill_minute("600519.SH", target_days=365)

        assert result == {
            "symbol": "600519.SH",
            "total": 1,
            "succeeded": 1,
            "failed": 0,
            "skipped": 0
        }
        assert mock_download.call_count == 1
        assert mock_db.upsert_minute_klines.call_count == 1
        assert mock_progress_tracker.mark_completed.call_count == 1

    def test_backfill_minute_handles_download_failure(self, backfiller, mock_gap_detector, mock_progress_tracker):
        """Test backfill_minute continues on download failure."""
        missing_dates = [date(2026, 5, 20), date(2026, 5, 21)]
        mock_gap_detector.detect_minute_gaps.return_value = missing_dates
        mock_progress_tracker.is_completed.return_value = False

        with patch.object(backfiller, '_download_minute_kline') as mock_download:
            mock_download.side_effect = [None, [{"symbol": "600519.SH", "trade_datetime": "2026-05-21 09:31:00", "open": 100.0, "high": 101.0, "low": 99.5, "close": 100.5, "volume": 10000, "amount": 1005000.0}]]

            result = backfiller.backfill_minute("600519.SH", target_days=365)

        assert result["total"] == 2
        assert result["succeeded"] == 1
        assert result["failed"] == 1


class TestDownloadDailyKline:
    """Test _download_daily_kline helper method."""

    @patch('quantsys.data.data_backfiller.ak.stock_zh_a_hist')
    @patch('quantsys.data.data_backfiller.time.sleep')
    def test_download_daily_kline_success(self, mock_sleep, mock_ak_hist, backfiller):
        """Test successful daily K-line download."""
        mock_df = pd.DataFrame({
            '日期': ['2026-05-20'],
            '开盘': [100.0],
            '最高': [105.0],
            '最低': [99.0],
            '收盘': [103.0],
            '成交量': [1000000],
            '成交额': [102000000.0]
        })
        mock_ak_hist.return_value = mock_df

        result = backfiller._download_daily_kline("600519.SH", "2026-05-20")

        assert result == {
            "symbol": "600519.SH",
            "date": "2026-05-20",
            "open": 100.0,
            "high": 105.0,
            "low": 99.0,
            "close": 103.0,
            "volume": 1000000,
            "amount": 102000000.0
        }
        mock_ak_hist.assert_called_once()

    @patch('quantsys.data.data_backfiller.ak.stock_zh_a_hist')
    @patch('quantsys.data.data_backfiller.time.sleep')
    def test_download_daily_kline_retries_on_failure(self, mock_sleep, mock_ak_hist, backfiller):
        """Test retry logic on download failure."""
        mock_ak_hist.side_effect = [
            Exception("Network error"),
            Exception("Network error"),
            pd.DataFrame({
                '日期': ['2026-05-20'],
                '开盘': [100.0],
                '最高': [105.0],
                '最低': [99.0],
                '收盘': [103.0],
                '成交量': [1000000],
                '成交额': [102000000.0]
            })
        ]

        result = backfiller._download_daily_kline("600519.SH", "2026-05-20")

        assert result is not None
        assert mock_ak_hist.call_count == 3
        assert mock_sleep.call_count == 2  # Sleep between retries

    @patch('quantsys.data.data_backfiller.ak.stock_zh_a_hist')
    @patch('quantsys.data.data_backfiller.time.sleep')
    def test_download_daily_kline_returns_none_after_max_retries(self, mock_sleep, mock_ak_hist, backfiller):
        """Test returns None after max retries."""
        mock_ak_hist.side_effect = Exception("Network error")

        result = backfiller._download_daily_kline("600519.SH", "2026-05-20")

        assert result is None
        assert mock_ak_hist.call_count == 3


class TestDownloadMinuteKline:
    """Test _download_minute_kline helper method."""

    @patch('quantsys.data.data_backfiller.ak.stock_zh_a_hist_min_em')
    @patch('quantsys.data.data_backfiller.time.sleep')
    def test_download_minute_kline_success(self, mock_sleep, mock_ak_hist_min, backfiller):
        """Test successful minute K-line download."""
        mock_df = pd.DataFrame({
            '时间': ['2026-05-20 09:31:00', '2026-05-20 09:32:00'],
            '开盘': [100.0, 100.5],
            '最高': [101.0, 102.0],
            '最低': [99.5, 100.0],
            '收盘': [100.5, 101.5],
            '成交量': [10000, 12000],
            '成交额': [1005000.0, 1218000.0]
        })
        mock_ak_hist_min.return_value = mock_df

        result = backfiller._download_minute_kline("600519.SH", "2026-05-20")

        assert len(result) == 2
        assert result[0] == {
            "symbol": "600519.SH",
            "trade_datetime": "2026-05-20 09:31:00",
            "open": 100.0,
            "high": 101.0,
            "low": 99.5,
            "close": 100.5,
            "volume": 10000,
            "amount": 1005000.0
        }
        mock_ak_hist_min.assert_called_once()

    @patch('quantsys.data.data_backfiller.ak.stock_zh_a_hist_min_em')
    @patch('quantsys.data.data_backfiller.time.sleep')
    def test_download_minute_kline_retries_on_failure(self, mock_sleep, mock_ak_hist_min, backfiller):
        """Test retry logic on download failure."""
        mock_ak_hist_min.side_effect = [
            Exception("Network error"),
            Exception("Network error"),
            pd.DataFrame({
                '时间': ['2026-05-20 09:31:00'],
                '开盘': [100.0],
                '最高': [101.0],
                '最低': [99.5],
                '收盘': [100.5],
                '成交量': [10000],
                '成交额': [1005000.0]
            })
        ]

        result = backfiller._download_minute_kline("600519.SH", "2026-05-20")

        assert result is not None
        assert mock_ak_hist_min.call_count == 3

    @patch('quantsys.data.data_backfiller.ak.stock_zh_a_hist_min_em')
    @patch('quantsys.data.data_backfiller.time.sleep')
    def test_download_minute_kline_returns_none_after_max_retries(self, mock_sleep, mock_ak_hist_min, backfiller):
        """Test returns None after max retries."""
        mock_ak_hist_min.side_effect = Exception("Network error")

        result = backfiller._download_minute_kline("600519.SH", "2026-05-20")

        assert result is None
        assert mock_ak_hist_min.call_count == 3
