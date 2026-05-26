"""
Tests for backfill_klines.py main script.
"""
import sys
from datetime import date
from io import StringIO
from unittest.mock import Mock, patch, MagicMock, call

import pytest

# Add parent directory to path for imports
sys.path.insert(0, '/Users/mac/Documents/ai/pi-investment/quant')

from scripts.backfill_klines import (
    parse_args,
    get_symbol_list,
    process_batch,
    main
)


class TestParseArgs:
    """Test command-line argument parsing."""

    def test_parse_args_daily_with_symbols(self):
        """Test parsing daily backfill with specific symbols."""
        args = parse_args([
            '--data-type', 'daily',
            '--symbols', '600519.SH,000001.SZ'
        ])
        assert args.data_type == 'daily'
        assert args.symbols == '600519.SH,000001.SZ'
        assert args.market == 'A'
        assert args.target_days == 730
        assert args.batch_size == 10
        assert args.reset_progress is False

    def test_parse_args_minute_with_market(self):
        """Test parsing minute backfill with market filter."""
        args = parse_args([
            '--data-type', 'minute',
            '--market', 'HK',
            '--target-days', '180',
            '--batch-size', '5'
        ])
        assert args.data_type == 'minute'
        assert args.symbols is None
        assert args.market == 'HK'
        assert args.target_days == 180
        assert args.batch_size == 5

    def test_parse_args_with_reset_progress(self):
        """Test parsing with reset progress flag."""
        args = parse_args([
            '--data-type', 'daily',
            '--reset-progress'
        ])
        assert args.reset_progress is True

    def test_parse_args_missing_data_type(self):
        """Test that missing --data-type raises error."""
        with pytest.raises(SystemExit):
            parse_args([])

    def test_parse_args_invalid_data_type(self):
        """Test that invalid data type raises error."""
        with pytest.raises(SystemExit):
            parse_args(['--data-type', 'hourly'])

    def test_parse_args_invalid_market(self):
        """Test that invalid market raises error."""
        with pytest.raises(SystemExit):
            parse_args(['--data-type', 'daily', '--market', 'US'])


class TestGetSymbolList:
    """Test symbol list retrieval."""

    @patch('scripts.backfill_klines.Database')
    def test_get_symbol_list_from_args(self, mock_db_class):
        """Test getting symbols from command-line argument."""
        mock_db = Mock()
        symbols = get_symbol_list(mock_db, '600519.SH,000001.SZ', 'A')

        assert symbols == ['600519.SH', '000001.SZ']
        mock_db.get_all_symbols.assert_not_called()

    @patch('scripts.backfill_klines.Database')
    def test_get_symbol_list_from_database_a_share(self, mock_db_class):
        """Test getting A-share symbols from database."""
        mock_db = Mock()
        mock_db.get_all_symbols.return_value = [
            {'symbol': '600519.SH'},
            {'symbol': '000001.SZ'},
            {'symbol': '01234.HK'}  # Should be filtered out
        ]

        symbols = get_symbol_list(mock_db, None, 'A')

        assert symbols == ['600519.SH', '000001.SZ']
        mock_db.get_all_symbols.assert_called_once()

    @patch('scripts.backfill_klines.Database')
    def test_get_symbol_list_from_database_hk(self, mock_db_class):
        """Test getting HK symbols from database."""
        mock_db = Mock()
        mock_db.get_all_symbols.return_value = [
            {'symbol': '600519.SH'},  # Should be filtered out
            {'symbol': '01234.HK'},
            {'symbol': '00700.HK'}
        ]

        symbols = get_symbol_list(mock_db, None, 'HK')

        assert symbols == ['01234.HK', '00700.HK']
        mock_db.get_all_symbols.assert_called_once()

    @patch('scripts.backfill_klines.Database')
    def test_get_symbol_list_empty_result(self, mock_db_class):
        """Test handling empty symbol list."""
        mock_db = Mock()
        mock_db.get_all_symbols.return_value = []

        symbols = get_symbol_list(mock_db, None, 'A')

        assert symbols == []


class TestProcessBatch:
    """Test batch processing logic."""

    def test_process_batch_daily_all_success(self):
        """Test processing batch with all symbols succeeding."""
        mock_backfiller = Mock()
        mock_backfiller.backfill_daily.side_effect = [
            {'symbol': '600519.SH', 'total': 10, 'succeeded': 10, 'failed': 0, 'skipped': 0},
            {'symbol': '000001.SZ', 'total': 8, 'succeeded': 8, 'failed': 0, 'skipped': 0}
        ]

        symbols = ['600519.SH', '000001.SZ']
        results = process_batch(
            backfiller=mock_backfiller,
            symbols=symbols,
            data_type='daily',
            target_days=730,
            batch_num=1,
            total_batches=1
        )

        assert len(results) == 2
        assert results[0]['succeeded'] == 10
        assert results[1]['succeeded'] == 8
        assert mock_backfiller.backfill_daily.call_count == 2

    def test_process_batch_minute_with_failures(self):
        """Test processing batch with some failures."""
        mock_backfiller = Mock()
        mock_backfiller.backfill_minute.side_effect = [
            {'symbol': '600519.SH', 'total': 20, 'succeeded': 18, 'failed': 2, 'skipped': 0},
            {'symbol': '000001.SZ', 'total': 15, 'succeeded': 15, 'failed': 0, 'skipped': 0}
        ]

        symbols = ['600519.SH', '000001.SZ']
        results = process_batch(
            backfiller=mock_backfiller,
            symbols=symbols,
            data_type='minute',
            target_days=365,
            batch_num=1,
            total_batches=1
        )

        assert len(results) == 2
        assert results[0]['failed'] == 2
        assert mock_backfiller.backfill_minute.call_count == 2

    def test_process_batch_with_exception(self):
        """Test that batch continues processing after exception."""
        mock_backfiller = Mock()
        mock_backfiller.backfill_daily.side_effect = [
            Exception("Network error"),
            {'symbol': '000001.SZ', 'total': 8, 'succeeded': 8, 'failed': 0, 'skipped': 0}
        ]

        symbols = ['600519.SH', '000001.SZ']
        results = process_batch(
            backfiller=mock_backfiller,
            symbols=symbols,
            data_type='daily',
            target_days=730,
            batch_num=1,
            total_batches=1
        )

        # Should have 1 result (second symbol succeeded)
        assert len(results) == 1
        assert results[0]['symbol'] == '000001.SZ'

    def test_process_batch_empty_symbols(self):
        """Test processing empty symbol list."""
        mock_backfiller = Mock()

        symbols = []
        results = process_batch(
            backfiller=mock_backfiller,
            symbols=symbols,
            data_type='daily',
            target_days=730,
            batch_num=1,
            total_batches=1
        )

        assert results == []
        mock_backfiller.backfill_daily.assert_not_called()


class TestMain:
    """Test main function."""

    @patch('scripts.backfill_klines.Database')
    @patch('scripts.backfill_klines.TradingCalendar')
    @patch('scripts.backfill_klines.GapDetector')
    @patch('scripts.backfill_klines.ProgressTracker')
    @patch('scripts.backfill_klines.DataBackfiller')
    @patch('scripts.backfill_klines.get_symbol_list')
    @patch('scripts.backfill_klines.process_batch')
    def test_main_daily_with_symbols(
        self,
        mock_process_batch,
        mock_get_symbol_list,
        mock_backfiller_class,
        mock_tracker_class,
        mock_detector_class,
        mock_calendar_class,
        mock_db_class
    ):
        """Test main function with daily backfill and specific symbols."""
        # Setup mocks
        mock_db = Mock()
        mock_db_class.return_value = mock_db

        mock_calendar = Mock()
        mock_calendar_class.return_value = mock_calendar

        mock_detector = Mock()
        mock_detector_class.return_value = mock_detector

        mock_tracker = Mock()
        mock_tracker_class.return_value = mock_tracker

        mock_backfiller = Mock()
        mock_backfiller_class.return_value = mock_backfiller

        mock_get_symbol_list.return_value = ['600519.SH', '000001.SZ']
        mock_process_batch.return_value = [
            {'symbol': '600519.SH', 'total': 10, 'succeeded': 10, 'failed': 0, 'skipped': 0},
            {'symbol': '000001.SZ', 'total': 8, 'succeeded': 8, 'failed': 0, 'skipped': 0}
        ]

        # Run main
        exit_code = main([
            '--data-type', 'daily',
            '--symbols', '600519.SH,000001.SZ'
        ])

        assert exit_code == 0
        mock_db_class.assert_called_once()
        mock_calendar_class.assert_called_once_with(mock_db)
        mock_detector_class.assert_called_once_with(mock_db, mock_calendar)
        mock_tracker_class.assert_called_once_with(mock_db)
        mock_backfiller_class.assert_called_once_with(
            mock_db, mock_calendar, mock_detector, mock_tracker
        )
        mock_tracker.reset.assert_not_called()
        mock_tracker.save.assert_called()

    @patch('scripts.backfill_klines.Database')
    @patch('scripts.backfill_klines.TradingCalendar')
    @patch('scripts.backfill_klines.GapDetector')
    @patch('scripts.backfill_klines.ProgressTracker')
    @patch('scripts.backfill_klines.DataBackfiller')
    @patch('scripts.backfill_klines.get_symbol_list')
    @patch('scripts.backfill_klines.process_batch')
    def test_main_with_reset_progress(
        self,
        mock_process_batch,
        mock_get_symbol_list,
        mock_backfiller_class,
        mock_tracker_class,
        mock_detector_class,
        mock_calendar_class,
        mock_db_class
    ):
        """Test main function with reset progress flag."""
        # Setup mocks
        mock_db = Mock()
        mock_db_class.return_value = mock_db

        mock_tracker = Mock()
        mock_tracker_class.return_value = mock_tracker

        mock_get_symbol_list.return_value = ['600519.SH']
        mock_process_batch.return_value = [
            {'symbol': '600519.SH', 'total': 10, 'succeeded': 10, 'failed': 0, 'skipped': 0}
        ]

        # Run main
        exit_code = main([
            '--data-type', 'daily',
            '--symbols', '600519.SH',
            '--reset-progress'
        ])

        assert exit_code == 0
        mock_tracker.reset.assert_called_once()

    @patch('scripts.backfill_klines.Database')
    @patch('scripts.backfill_klines.TradingCalendar')
    @patch('scripts.backfill_klines.GapDetector')
    @patch('scripts.backfill_klines.ProgressTracker')
    @patch('scripts.backfill_klines.DataBackfiller')
    @patch('scripts.backfill_klines.get_symbol_list')
    def test_main_empty_symbol_list(
        self,
        mock_get_symbol_list,
        mock_backfiller_class,
        mock_tracker_class,
        mock_detector_class,
        mock_calendar_class,
        mock_db_class
    ):
        """Test main function with empty symbol list."""
        mock_get_symbol_list.return_value = []

        exit_code = main([
            '--data-type', 'daily',
            '--market', 'A'
        ])

        assert exit_code == 0

    @patch('scripts.backfill_klines.Database')
    @patch('scripts.backfill_klines.TradingCalendar')
    @patch('scripts.backfill_klines.GapDetector')
    @patch('scripts.backfill_klines.ProgressTracker')
    @patch('scripts.backfill_klines.DataBackfiller')
    @patch('scripts.backfill_klines.get_symbol_list')
    @patch('scripts.backfill_klines.process_batch')
    def test_main_keyboard_interrupt(
        self,
        mock_process_batch,
        mock_get_symbol_list,
        mock_backfiller_class,
        mock_tracker_class,
        mock_detector_class,
        mock_calendar_class,
        mock_db_class
    ):
        """Test main function handles Ctrl+C gracefully."""
        # Setup mocks
        mock_tracker = Mock()
        mock_tracker_class.return_value = mock_tracker

        mock_get_symbol_list.return_value = ['600519.SH', '000001.SZ']
        mock_process_batch.side_effect = KeyboardInterrupt()

        # Run main
        exit_code = main([
            '--data-type', 'daily',
            '--symbols', '600519.SH,000001.SZ'
        ])

        assert exit_code == 1
        mock_tracker.save.assert_called()

    @patch('scripts.backfill_klines.Database')
    @patch('scripts.backfill_klines.TradingCalendar')
    @patch('scripts.backfill_klines.GapDetector')
    @patch('scripts.backfill_klines.ProgressTracker')
    @patch('scripts.backfill_klines.DataBackfiller')
    @patch('scripts.backfill_klines.get_symbol_list')
    @patch('scripts.backfill_klines.process_batch')
    def test_main_multiple_batches(
        self,
        mock_process_batch,
        mock_get_symbol_list,
        mock_backfiller_class,
        mock_tracker_class,
        mock_detector_class,
        mock_calendar_class,
        mock_db_class
    ):
        """Test main function with multiple batches."""
        # Setup mocks
        mock_tracker = Mock()
        mock_tracker_class.return_value = mock_tracker

        # 15 symbols with batch size 10 = 2 batches
        symbols = [f'60{i:04d}.SH' for i in range(15)]
        mock_get_symbol_list.return_value = symbols

        mock_process_batch.side_effect = [
            # Batch 1: 10 symbols
            [{'symbol': s, 'total': 5, 'succeeded': 5, 'failed': 0, 'skipped': 0}
             for s in symbols[:10]],
            # Batch 2: 5 symbols
            [{'symbol': s, 'total': 5, 'succeeded': 5, 'failed': 0, 'skipped': 0}
             for s in symbols[10:]]
        ]

        # Run main
        exit_code = main([
            '--data-type', 'daily',
            '--market', 'A',
            '--batch-size', '10'
        ])

        assert exit_code == 0
        assert mock_process_batch.call_count == 2
        assert mock_tracker.save.call_count == 2  # Once per batch
