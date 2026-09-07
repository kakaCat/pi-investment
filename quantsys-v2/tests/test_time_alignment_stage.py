"""Tests for TimeAlignmentStage - Time and calendar alignment."""

import pytest
import pandas as pd
from datetime import date

from domain.quantlib.stages.data_pipeline.time_alignment_stage import TimeAlignmentStage
from domain.quantlib.stages.data_pipeline import PipelineContext, PipelineResult


class TestTimeAlignmentStage:
    """Test suite for TimeAlignmentStage."""

    def test_filter_non_trading_days(self):
        """Test that non-trading days are filtered out."""
        input_data = {
            'akshare': pd.DataFrame({
                'symbol': ['000001.SH'] * 3,
                'trade_date': [
                    date(2024, 1, 5),   # Friday (trading)
                    date(2024, 1, 6),   # Saturday (non-trading)
                    date(2024, 1, 8)    # Monday (trading)
                ],
                'close': [1800.0, 1810.0, 1820.0],
                'volume': [1000000, 1000000, 1000000]
            })
        }

        # Mock trading calendar with only weekdays
        trading_days = {date(2024, 1, 5), date(2024, 1, 8)}

        stage = TimeAlignmentStage(calendar='SSE', timezone='Asia/Shanghai')
        stage.trading_calendar = trading_days

        context = PipelineContext(data=input_data, config={}, metadata={})
        result = stage.execute(context)

        assert result.success
        assert len(result.data['akshare']) == 2  # Only trading days
        dates = result.data['akshare']['trade_date'].tolist()
        assert date(2024, 1, 6) not in dates

    def test_mark_suspensions(self):
        """Test that zero-volume days are marked as suspended."""
        input_data = {
            'akshare': pd.DataFrame({
                'symbol': ['000001.SH'] * 2,
                'trade_date': [date(2024, 1, 5), date(2024, 1, 8)],
                'close': [1800.0, 1800.0],
                'volume': [1000000, 0]  # Second day suspended
            })
        }

        trading_days = {date(2024, 1, 5), date(2024, 1, 8)}

        stage = TimeAlignmentStage(calendar='SSE')
        stage.trading_calendar = trading_days

        context = PipelineContext(data=input_data, config={}, metadata={})
        result = stage.execute(context)

        assert result.success
        assert result.data['akshare'].iloc[0]['is_suspended'] == False
        assert result.data['akshare'].iloc[1]['is_suspended'] == True

    def test_mark_suspensions_with_null_volume(self):
        """Test that NULL volume days are marked as suspended."""
        input_data = {
            'akshare': pd.DataFrame({
                'symbol': ['000001.SH'] * 2,
                'trade_date': [date(2024, 1, 5), date(2024, 1, 8)],
                'close': [1800.0, 1800.0],
                'volume': [1000000, None]  # Second day has NULL volume
            })
        }

        trading_days = {date(2024, 1, 5), date(2024, 1, 8)}

        stage = TimeAlignmentStage(calendar='SSE')
        stage.trading_calendar = trading_days

        context = PipelineContext(data=input_data, config={}, metadata={})
        result = stage.execute(context)

        assert result.success
        assert result.data['akshare'].iloc[0]['is_suspended'] == False
        assert result.data['akshare'].iloc[1]['is_suspended'] == True

    def test_datetime_conversion(self):
        """Test that datetime objects are converted to date."""
        input_data = {
            'akshare': pd.DataFrame({
                'symbol': ['000001.SH'] * 2,
                'trade_date': pd.to_datetime(['2024-01-05', '2024-01-08']),
                'close': [1800.0, 1820.0],
                'volume': [1000000, 1000000]
            })
        }

        trading_days = {date(2024, 1, 5), date(2024, 1, 8)}

        stage = TimeAlignmentStage(calendar='SSE')
        stage.trading_calendar = trading_days

        context = PipelineContext(data=input_data, config={}, metadata={})
        result = stage.execute(context)

        assert result.success
        assert len(result.data['akshare']) == 2
        # Verify dates are date objects, not datetime
        assert all(isinstance(d, date) for d in result.data['akshare']['trade_date'])

    def test_empty_trading_calendar(self):
        """Test behavior with empty trading calendar."""
        input_data = {
            'akshare': pd.DataFrame({
                'symbol': ['000001.SH'] * 2,
                'trade_date': [date(2024, 1, 5), date(2024, 1, 8)],
                'close': [1800.0, 1820.0],
                'volume': [1000000, 1000000]
            })
        }

        stage = TimeAlignmentStage(calendar='SSE')
        stage.trading_calendar = set()  # Empty calendar

        context = PipelineContext(data=input_data, config={}, metadata={})
        result = stage.execute(context)

        assert result.success
        assert len(result.data['akshare']) == 0  # All filtered out

    def test_multiple_sources(self):
        """Test alignment across multiple data sources."""
        input_data = {
            'akshare': pd.DataFrame({
                'symbol': ['000001.SH'] * 2,
                'trade_date': [date(2024, 1, 5), date(2024, 1, 6)],
                'close': [1800.0, 1810.0],
                'volume': [1000000, 1000000]
            }),
            'tushare': pd.DataFrame({
                'symbol': ['000001.SH'] * 2,
                'trade_date': [date(2024, 1, 5), date(2024, 1, 6)],
                'close': [1800.0, 1810.0],
                'volume': [1000000, 0]
            })
        }

        trading_days = {date(2024, 1, 5)}  # Only Jan 5 is trading day

        stage = TimeAlignmentStage(calendar='SSE')
        stage.trading_calendar = trading_days

        context = PipelineContext(data=input_data, config={}, metadata={})
        result = stage.execute(context)

        assert result.success
        assert len(result.data['akshare']) == 1
        assert len(result.data['tushare']) == 1
        assert 'alignment_stats' in result.metadata
        assert 'akshare' in result.metadata['alignment_stats']
        assert 'tushare' in result.metadata['alignment_stats']

    def test_metadata_statistics(self):
        """Test that metadata contains alignment statistics."""
        input_data = {
            'akshare': pd.DataFrame({
                'symbol': ['000001.SH'] * 4,
                'trade_date': [
                    date(2024, 1, 5),
                    date(2024, 1, 6),
                    date(2024, 1, 8),
                    date(2024, 1, 9)
                ],
                'close': [1800.0, 1810.0, 1820.0, 1820.0],
                'volume': [1000000, 1000000, 0, 1000000]
            })
        }

        trading_days = {date(2024, 1, 5), date(2024, 1, 8), date(2024, 1, 9)}

        stage = TimeAlignmentStage(calendar='SSE')
        stage.trading_calendar = trading_days

        context = PipelineContext(data=input_data, config={}, metadata={})
        result = stage.execute(context)

        assert result.success
        stats = result.metadata['alignment_stats']['akshare']
        assert stats['original'] == 4
        assert stats['after_alignment'] == 3
        assert stats['filtered'] == 1
        assert stats['suspensions'] == 1
