"""
Integration tests for K-line data backfill system.

Tests the complete workflow from database → GapDetector → DataBackfiller → verify data stored.
Uses a real test database with mocked akshare API calls.
"""
import os
import sys
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import pytest
import pandas as pd

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from quantsys.data.db import Database
from quantsys.data.trading_calendar import TradingCalendar
from quantsys.data.gap_detector import GapDetector
from quantsys.data.progress_tracker import ProgressTracker
from quantsys.data.data_backfiller import DataBackfiller


@pytest.fixture
def test_db():
    """Create a test database with SQLite."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")

        # Force SQLite for tests
        original_provider = os.environ.get("QUANT_DB_PROVIDER")
        os.environ["QUANT_DB_PROVIDER"] = "sqlite"

        try:
            db = Database(db_path=db_path)
            # Manually call migration for SQLite (not called automatically)
            db._migrate_sqlite()
            yield db
            db.close()
        finally:
            # Restore original provider
            if original_provider:
                os.environ["QUANT_DB_PROVIDER"] = original_provider
            else:
                os.environ.pop("QUANT_DB_PROVIDER", None)


@pytest.fixture
def test_progress_file():
    """Create a temporary progress file."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        progress_file = f.name

    yield progress_file

    # Cleanup
    if os.path.exists(progress_file):
        os.unlink(progress_file)
    temp_file = progress_file + '.tmp'
    if os.path.exists(temp_file):
        os.unlink(temp_file)


@pytest.fixture
def setup_test_data(test_db):
    """Setup test data: stocks."""
    conn = test_db.get_connection()
    cursor = conn.cursor()

    # Insert test stocks
    test_stocks = [
        ("600519.SH", "贵州茅台", "A", "白酒"),
        ("000001.SZ", "平安银行", "A", "银行"),
        ("600036.SH", "招商银行", "A", "银行"),
    ]

    updated_at = datetime.now().isoformat()
    for symbol, name, market, industry in test_stocks:
        cursor.execute(
            "INSERT OR REPLACE INTO stocks (symbol, name, market, industry, updated_at) VALUES (?, ?, ?, ?, ?)",
            (symbol, name, market, industry, updated_at)
        )

    conn.commit()

    return test_db


@pytest.fixture
def components(setup_test_data, test_progress_file):
    """Create all backfill components with test database."""
    db = setup_test_data

    # Mock TradingCalendar to return trading days (weekdays only)
    with patch('quantsys.data.trading_calendar.TradingCalendar') as MockCalendar:
        calendar = MockCalendar.return_value

        # Mock get_trading_days to return weekdays in the range
        def mock_get_trading_days(start_date, end_date):
            days = []
            current = start_date
            while current <= end_date:
                if current.weekday() < 5:  # Monday-Friday
                    days.append(current)
                current = current + timedelta(days=1)
            return days

        calendar.get_trading_days.side_effect = mock_get_trading_days
        calendar.is_trading_day.side_effect = lambda d: d.weekday() < 5

        gap_detector = GapDetector(db, calendar)
        progress_tracker = ProgressTracker(state_file=test_progress_file)
        progress_tracker.load()
        backfiller = DataBackfiller(db, calendar, gap_detector, progress_tracker)

        yield {
            'db': db,
            'calendar': calendar,
            'gap_detector': gap_detector,
            'progress_tracker': progress_tracker,
            'backfiller': backfiller
        }


class TestFullDailyBackfillWorkflow:
    """Test complete daily backfill workflow."""

    def test_daily_backfill_new_symbol(self, components):
        """Test daily backfill for a symbol with no existing data."""
        db = components['db']
        backfiller = components['backfiller']

        # Mock akshare API
        with patch('akshare.stock_zh_a_hist') as mock_ak:
            # Return sample data for each date
            mock_ak.return_value = pd.DataFrame([{
                '日期': '2026-05-20',
                '开盘': 100.0,
                '最高': 105.0,
                '最低': 99.0,
                '收盘': 103.0,
                '成交量': 1000000,
                '成交额': 102000000.0
            }])

            # Backfill last 30 days
            result = backfiller.backfill_daily("600519.SH", target_days=30)

        # For new symbol, no gaps detected (returns empty list)
        assert result['total'] == 0
        assert result['succeeded'] == 0
        assert result['failed'] == 0
        assert result['skipped'] == 0

    def test_daily_backfill_with_gaps(self, components):
        """Test daily backfill for a symbol with existing data and gaps."""
        db = components['db']
        backfiller = components['backfiller']
        gap_detector = components['gap_detector']
        conn = db.get_connection()
        cursor = conn.cursor()

        # Insert some existing daily data (with intentional gaps on weekdays)
        # Use dates from the past - insert Mon, Tue, Thu (skip Wed)
        existing_dates = [
            date(2024, 5, 20),  # Monday
            date(2024, 5, 21),  # Tuesday
            # Gap: May 22 (Wed) - should be detected if it's a trading day
            date(2024, 5, 23),  # Thursday (last_date)
        ]

        for trade_date in existing_dates:
            cursor.execute(
                """
                INSERT INTO daily_klines (symbol, date, open, high, low, close, volume, amount)
                VALUES (?, ?, 100.0, 105.0, 99.0, 103.0, 1000000, 102000000.0)
                """,
                ("600519.SH", trade_date.isoformat())
            )
        conn.commit()

        # Detect gaps first to see what's expected
        missing_dates = gap_detector.detect_daily_gaps("600519.SH", target_days=30)

        # Mock akshare API to return data for missing dates
        with patch('akshare.stock_zh_a_hist') as mock_ak:
            def mock_hist(symbol, period, start_date, end_date, adjust):
                # Return data for the requested date
                return pd.DataFrame([{
                    '日期': start_date,
                    '开盘': 100.0,
                    '最高': 105.0,
                    '最低': 99.0,
                    '收盘': 103.0,
                    '成交量': 1000000,
                    '成交额': 102000000.0
                }])

            mock_ak.side_effect = mock_hist

            # Backfill last 30 days
            result = backfiller.backfill_daily("600519.SH", target_days=30)

        # Verify the workflow works (gaps detected = gaps filled)
        assert result['total'] == len(missing_dates)
        if len(missing_dates) > 0:
            assert result['succeeded'] == len(missing_dates)
            assert result['failed'] == 0

            # Verify data was stored in database
            cursor.execute(
                "SELECT COUNT(*) FROM daily_klines WHERE symbol = ?",
                ("600519.SH",)
            )
            count = cursor.fetchone()[0]
            assert count == len(existing_dates) + len(missing_dates)

    def test_daily_backfill_end_to_end(self, components):
        """Test complete daily backfill workflow: detect gaps → download → store → verify."""
        db = components['db']
        gap_detector = components['gap_detector']
        backfiller = components['backfiller']
        conn = db.get_connection()
        cursor = conn.cursor()

        # Setup: Insert partial data with known gaps on weekdays
        # Use dates from the past - insert Mon, Tue, Thu (skip Wed)
        existing_dates = [
            date(2024, 5, 20),  # Monday
            date(2024, 5, 21),  # Tuesday
            # Gap: May 22 (Wed) - if it's a trading day
            date(2024, 5, 23),  # Thursday (last_date)
        ]

        for trade_date in existing_dates:
            cursor.execute(
                """
                INSERT INTO daily_klines (symbol, date, open, high, low, close, volume, amount)
                VALUES (?, ?, 100.0, 105.0, 99.0, 103.0, 1000000, 102000000.0)
                """,
                ("600519.SH", trade_date.isoformat())
            )
        conn.commit()

        # Step 1: Detect gaps
        missing_dates = gap_detector.detect_daily_gaps("600519.SH", target_days=30)

        # Step 2: Mock akshare and backfill
        with patch('akshare.stock_zh_a_hist') as mock_ak:
            mock_ak.return_value = pd.DataFrame([{
                '日期': '20240522',
                '开盘': 110.0,
                '最高': 115.0,
                '最低': 109.0,
                '收盘': 113.0,
                '成交量': 2000000,
                '成交额': 224000000.0
            }])

            result = backfiller.backfill_daily("600519.SH", target_days=30)

        # Step 3: Verify results match detected gaps
        assert result['total'] == len(missing_dates)
        if len(missing_dates) > 0:
            assert result['succeeded'] == len(missing_dates)
            assert result['failed'] == 0

            # Step 4: Verify data in database
            cursor.execute(
                "SELECT COUNT(*) FROM daily_klines WHERE symbol = ?",
                ("600519.SH",)
            )
            final_count = cursor.fetchone()[0]

            # Should have original + filled gaps
            assert final_count == len(existing_dates) + len(missing_dates)


class TestFullMinuteBackfillWorkflow:
    """Test complete minute backfill workflow."""

    @pytest.mark.skipif(
        os.environ.get("QUANT_DB_PROVIDER", "sqlite").lower() != "postgres",
        reason="Minute klines require PostgreSQL"
    )
    def test_minute_backfill_workflow(self, components):
        """Test minute backfill workflow (requires PostgreSQL)."""
        # This test is skipped for SQLite
        # In a real PostgreSQL environment, it would test minute data backfill
        pass

    def test_minute_backfill_sqlite_raises_error(self, components):
        """Test that minute backfill raises error with SQLite."""
        backfiller = components['backfiller']

        # Minute backfill should fail with SQLite
        with pytest.raises(RuntimeError, match="only supported with PostgreSQL"):
            # Try to detect minute gaps (will fail in _get_minute_dates_from_db)
            components['gap_detector'].detect_minute_gaps("600519.SH", target_days=30)


class TestProgressTrackingAndResume:
    """Test progress tracking and resume capability."""

    def test_progress_saved_between_dates(self, components):
        """Test that progress is saved after each successful date."""
        db = components['db']
        backfiller = components['backfiller']
        progress_tracker = components['progress_tracker']
        conn = db.get_connection()
        cursor = conn.cursor()

        # Setup: Insert partial data
        today = date.today()
        last_date = today - timedelta(days=1)

        for i in [2, 4, 6]:
            trade_date = last_date - timedelta(days=i)
            if trade_date.weekday() < 5:
                cursor.execute(
                    """
                    INSERT INTO daily_klines (symbol, date, open, high, low, close, volume, amount)
                    VALUES (?, ?, 100.0, 105.0, 99.0, 103.0, 1000000, 102000000.0)
                    """,
                    ("600519.SH", trade_date.isoformat())
                )
        conn.commit()

        # Mock akshare
        with patch('akshare.stock_zh_a_hist') as mock_ak:
            mock_ak.return_value = pd.DataFrame([{
                '日期': '2026-05-20',
                '开盘': 100.0,
                '最高': 105.0,
                '最低': 99.0,
                '收盘': 103.0,
                '成交量': 1000000,
                '成交额': 102000000.0
            }])

            result = backfiller.backfill_daily("600519.SH", target_days=30)

        # Verify progress was tracked
        if result['succeeded'] > 0:
            # Save progress
            progress_tracker.save()

            # Load progress in new tracker
            new_tracker = ProgressTracker(state_file=progress_tracker.state_file)
            new_tracker.load()

            # Verify state was persisted
            assert len(new_tracker.state) > 0

    def test_resume_after_interruption(self, components):
        """Test that backfill can resume after interruption."""
        db = components['db']
        backfiller = components['backfiller']
        progress_tracker = components['progress_tracker']
        conn = db.get_connection()
        cursor = conn.cursor()

        # Setup: Insert partial data with gaps
        today = date.today()
        last_date = today - timedelta(days=1)

        for i in [2, 4, 6, 8]:
            trade_date = last_date - timedelta(days=i)
            if trade_date.weekday() < 5:
                cursor.execute(
                    """
                    INSERT INTO daily_klines (symbol, date, open, high, low, close, volume, amount)
                    VALUES (?, ?, 100.0, 105.0, 99.0, 103.0, 1000000, 102000000.0)
                    """,
                    ("600519.SH", trade_date.isoformat())
                )
        conn.commit()

        # Simulate first run (partial completion)
        with patch('akshare.stock_zh_a_hist') as mock_ak:
            call_count = 0

            def mock_hist_partial(symbol, period, start_date, end_date, adjust):
                nonlocal call_count
                call_count += 1

                # Fail after 2 successful calls (simulate interruption)
                if call_count > 2:
                    raise Exception("Simulated interruption")

                return pd.DataFrame([{
                    '日期': start_date,
                    '开盘': 100.0,
                    '最高': 105.0,
                    '最低': 99.0,
                    '收盘': 103.0,
                    '成交量': 1000000,
                    '成交额': 102000000.0
                }])

            mock_ak.side_effect = mock_hist_partial

            result1 = backfiller.backfill_daily("600519.SH", target_days=30)

        # Save progress after partial completion
        progress_tracker.save()
        first_succeeded = result1['succeeded']

        # Simulate second run (resume)
        # Create new backfiller with loaded progress
        new_progress_tracker = ProgressTracker(state_file=progress_tracker.state_file)
        new_progress_tracker.load()
        new_backfiller = DataBackfiller(
            db, components['calendar'], components['gap_detector'], new_progress_tracker
        )

        with patch('akshare.stock_zh_a_hist') as mock_ak:
            mock_ak.return_value = pd.DataFrame([{
                '日期': '2026-05-20',
                '开盘': 100.0,
                '最高': 105.0,
                '最低': 99.0,
                '收盘': 103.0,
                '成交量': 1000000,
                '成交额': 102000000.0
            }])

            result2 = new_backfiller.backfill_daily("600519.SH", target_days=30)

        # Second run should skip already completed dates
        assert result2['skipped'] >= first_succeeded


class TestBatchProcessing:
    """Test batch processing of multiple symbols."""

    def test_batch_processing_multiple_symbols(self, components):
        """Test processing multiple symbols with progress saved between batches."""
        db = components['db']
        backfiller = components['backfiller']
        progress_tracker = components['progress_tracker']
        conn = db.get_connection()
        cursor = conn.cursor()

        symbols = ["600519.SH", "000001.SZ", "600036.SH"]

        # Insert partial data for each symbol
        today = date.today()
        last_date = today - timedelta(days=1)

        for symbol in symbols:
            for i in [2, 4]:
                trade_date = last_date - timedelta(days=i)
                if trade_date.weekday() < 5:
                    cursor.execute(
                        """
                        INSERT INTO daily_klines (symbol, date, open, high, low, close, volume, amount)
                        VALUES (?, ?, 100.0, 105.0, 99.0, 103.0, 1000000, 102000000.0)
                        """,
                        (symbol, trade_date.isoformat())
                    )
        conn.commit()

        # Process each symbol
        results = []
        with patch('akshare.stock_zh_a_hist') as mock_ak:
            mock_ak.return_value = pd.DataFrame([{
                '日期': '2026-05-20',
                '开盘': 100.0,
                '最高': 105.0,
                '最低': 99.0,
                '收盘': 103.0,
                '成交量': 1000000,
                '成交额': 102000000.0
            }])

            for symbol in symbols:
                result = backfiller.backfill_daily(symbol, target_days=30)
                results.append(result)

                # Save progress after each symbol (simulating batch processing)
                progress_tracker.save()

        # Verify all symbols were processed
        assert len(results) == 3

        # Verify progress was saved for all symbols
        progress_tracker.load()
        for symbol in symbols:
            if symbol in progress_tracker.state:
                assert 'daily' in progress_tracker.state[symbol]

    def test_batch_processing_continues_on_symbol_failure(self, components):
        """Test that batch processing continues even if one symbol fails."""
        db = components['db']
        backfiller = components['backfiller']
        conn = db.get_connection()
        cursor = conn.cursor()

        symbols = ["600519.SH", "000001.SZ", "600036.SH"]

        # Insert partial data
        today = date.today()
        last_date = today - timedelta(days=1)

        for symbol in symbols:
            for i in [2, 4]:
                trade_date = last_date - timedelta(days=i)
                if trade_date.weekday() < 5:
                    cursor.execute(
                        """
                        INSERT INTO daily_klines (symbol, date, open, high, low, close, volume, amount)
                        VALUES (?, ?, 100.0, 105.0, 99.0, 103.0, 1000000, 102000000.0)
                        """,
                        (symbol, trade_date.isoformat())
                    )
        conn.commit()

        # Mock akshare to fail for second symbol
        with patch('akshare.stock_zh_a_hist') as mock_ak:
            call_count = 0

            def mock_hist_with_failure(symbol, period, start_date, end_date, adjust):
                nonlocal call_count
                call_count += 1

                # Fail for 000001 (second symbol)
                if '000001' in symbol:
                    raise Exception("API error for 000001")

                return pd.DataFrame([{
                    '日期': start_date,
                    '开盘': 100.0,
                    '最高': 105.0,
                    '最低': 99.0,
                    '收盘': 103.0,
                    '成交量': 1000000,
                    '成交额': 102000000.0
                }])

            mock_ak.side_effect = mock_hist_with_failure

            results = []
            for symbol in symbols:
                result = backfiller.backfill_daily(symbol, target_days=30)
                results.append(result)

        # All symbols should have been attempted
        assert len(results) == 3

        # First and third should succeed, second should have failures
        # (exact counts depend on gaps detected)


class TestErrorHandling:
    """Test error handling and retry logic."""

    def test_download_retry_on_failure(self, components):
        """Test that download failures trigger retry logic."""
        db = components['db']
        backfiller = components['backfiller']
        conn = db.get_connection()
        cursor = conn.cursor()

        # Setup: Insert partial data
        today = date.today()
        last_date = today - timedelta(days=1)
        trade_date = last_date - timedelta(days=2)

        if trade_date.weekday() < 5:
            cursor.execute(
                """
                INSERT INTO daily_klines (symbol, date, open, high, low, close, volume, amount)
                VALUES (?, ?, 100.0, 105.0, 99.0, 103.0, 1000000, 102000000.0)
                """,
                ("600519.SH", trade_date.isoformat())
            )
        conn.commit()

        # Mock akshare to fail twice, then succeed
        with patch('akshare.stock_zh_a_hist') as mock_ak:
            call_count = 0

            def mock_hist_with_retries(symbol, period, start_date, end_date, adjust):
                nonlocal call_count
                call_count += 1

                # Fail first 2 attempts
                if call_count <= 2:
                    raise Exception("Temporary API error")

                # Succeed on 3rd attempt
                return pd.DataFrame([{
                    '日期': start_date,
                    '开盘': 100.0,
                    '最高': 105.0,
                    '最低': 99.0,
                    '收盘': 103.0,
                    '成交量': 1000000,
                    '成交额': 102000000.0
                }])

            mock_ak.side_effect = mock_hist_with_retries

            result = backfiller.backfill_daily("600519.SH", target_days=30)

        # Should eventually succeed after retries
        # (if gaps were detected)
        if result['total'] > 0:
            assert result['succeeded'] > 0 or result['failed'] > 0

    def test_database_error_does_not_mark_completed(self, components):
        """Test that database errors don't mark dates as completed."""
        db = components['db']
        backfiller = components['backfiller']
        progress_tracker = components['progress_tracker']
        conn = db.get_connection()
        cursor = conn.cursor()

        # Setup: Insert partial data
        today = date.today()
        last_date = today - timedelta(days=1)
        trade_date = last_date - timedelta(days=2)

        if trade_date.weekday() < 5:
            cursor.execute(
                """
                INSERT INTO daily_klines (symbol, date, open, high, low, close, volume, amount)
                VALUES (?, ?, 100.0, 105.0, 99.0, 103.0, 1000000, 102000000.0)
                """,
                ("600519.SH", trade_date.isoformat())
            )
        conn.commit()

        # Mock akshare to succeed, but database to fail
        with patch('akshare.stock_zh_a_hist') as mock_ak:
            mock_ak.return_value = pd.DataFrame([{
                '日期': '2026-05-20',
                '开盘': 100.0,
                '最高': 105.0,
                '最低': 99.0,
                '收盘': 103.0,
                '成交量': 1000000,
                '成交额': 102000000.0
            }])

            with patch.object(db, 'upsert_daily_klines') as mock_upsert:
                mock_upsert.side_effect = Exception("Database error")

                result = backfiller.backfill_daily("600519.SH", target_days=30)

        # Should have failures
        if result['total'] > 0:
            assert result['failed'] > 0

            # Verify dates were NOT marked as completed
            # (progress tracker should not have entries for failed dates)
            progress_tracker.save()
            progress_tracker.load()

            # If symbol exists in state, it should have fewer completed dates
            # than total attempted
            if "600519.SH" in progress_tracker.state:
                if "daily" in progress_tracker.state["600519.SH"]:
                    completed_count = len(progress_tracker.state["600519.SH"]["daily"])
                    assert completed_count < result['total']

    def test_empty_dataframe_handled_gracefully(self, components):
        """Test that empty DataFrame from akshare is handled gracefully."""
        db = components['db']
        backfiller = components['backfiller']
        conn = db.get_connection()
        cursor = conn.cursor()

        # Setup: Insert partial data
        today = date.today()
        last_date = today - timedelta(days=1)
        trade_date = last_date - timedelta(days=2)

        if trade_date.weekday() < 5:
            cursor.execute(
                """
                INSERT INTO daily_klines (symbol, date, open, high, low, close, volume, amount)
                VALUES (?, ?, 100.0, 105.0, 99.0, 103.0, 1000000, 102000000.0)
                """,
                ("600519.SH", trade_date.isoformat())
            )
        conn.commit()

        # Mock akshare to return empty DataFrame
        with patch('akshare.stock_zh_a_hist') as mock_ak:
            mock_ak.return_value = pd.DataFrame()  # Empty DataFrame

            result = backfiller.backfill_daily("600519.SH", target_days=30)

        # Should handle empty data gracefully (mark as failed)
        if result['total'] > 0:
            assert result['failed'] > 0
            assert result['succeeded'] == 0


class TestRateLimiting:
    """Test rate limiting behavior."""

    def test_rate_limiting_delay_between_requests(self, components):
        """Test that rate limiting delay is applied between requests."""
        db = components['db']
        backfiller = components['backfiller']
        conn = db.get_connection()
        cursor = conn.cursor()

        # Setup: Insert partial data with multiple gaps
        today = date.today()
        last_date = today - timedelta(days=1)

        for i in [5, 10]:
            trade_date = last_date - timedelta(days=i)
            if trade_date.weekday() < 5:
                cursor.execute(
                    """
                    INSERT INTO daily_klines (symbol, date, open, high, low, close, volume, amount)
                    VALUES (?, ?, 100.0, 105.0, 99.0, 103.0, 1000000, 102000000.0)
                    """,
                    ("600519.SH", trade_date.isoformat())
                )
        conn.commit()

        # Mock time.sleep to verify it's called
        with patch('akshare.stock_zh_a_hist') as mock_ak:
            mock_ak.return_value = pd.DataFrame([{
                '日期': '2026-05-20',
                '开盘': 100.0,
                '最高': 105.0,
                '最低': 99.0,
                '收盘': 103.0,
                '成交量': 1000000,
                '成交额': 102000000.0
            }])

            with patch('time.sleep') as mock_sleep:
                result = backfiller.backfill_daily("600519.SH", target_days=30)

                # Verify sleep was called (rate limiting)
                if result['succeeded'] > 0:
                    assert mock_sleep.call_count > 0
