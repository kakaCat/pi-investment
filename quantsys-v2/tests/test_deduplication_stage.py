"""Tests for DeduplicationStage."""

import pytest
import pandas as pd
from datetime import datetime
from domain.quantlib.stages.data_pipeline.deduplication_stage import DeduplicationStage
from domain.quantlib.stages.data_pipeline import PipelineContext, PipelineResult


class TestDeduplicationStage:
    def test_remove_duplicates_keep_latest(self):
        """Test that duplicates are removed, keeping the most recent fetch."""
        input_data = {
            'akshare': pd.DataFrame({
                'symbol': ['000001.SH', '000001.SH', '000001.SZ'],
                'trade_date': ['2024-01-05', '2024-01-05', '2024-01-05'],
                'close': [1800.0, 1805.0, 15.0],
                'fetch_time': [
                    datetime(2024, 1, 5, 16, 0),
                    datetime(2024, 1, 5, 16, 30),  # Latest
                    datetime(2024, 1, 5, 16, 0)
                ]
            })
        }

        stage = DeduplicationStage()
        context = PipelineContext(data=input_data, config={}, metadata={})
        result = stage.execute(context)

        assert result.success
        assert len(result.data['akshare']) == 2  # 3 -> 2 records

        # Verify latest record kept for 000001.SH
        maotai = result.data['akshare'][result.data['akshare']['symbol'] == '000001.SH']
        assert len(maotai) == 1
        assert maotai.iloc[0]['close'] == 1805.0

    def test_no_duplicates_unchanged(self):
        """Test that data without duplicates passes through unchanged."""
        input_data = {
            'akshare': pd.DataFrame({
                'symbol': ['000001.SH', '000001.SZ'],
                'trade_date': ['2024-01-05', '2024-01-05'],
                'close': [1800.0, 15.0]
            })
        }

        stage = DeduplicationStage()
        context = PipelineContext(data=input_data, config={}, metadata={})
        result = stage.execute(context)

        assert result.success
        assert len(result.data['akshare']) == 2
        assert result.metadata['deduplication_stats']['akshare']['removed'] == 0

    def test_multiple_sources(self):
        """Test deduplication across multiple data sources."""
        input_data = {
            'akshare': pd.DataFrame({
                'symbol': ['000001.SH', '000001.SH'],
                'trade_date': ['2024-01-05', '2024-01-05'],
                'close': [1800.0, 1805.0],
                'fetch_time': [
                    datetime(2024, 1, 5, 16, 0),
                    datetime(2024, 1, 5, 16, 30)
                ]
            }),
            'tushare': pd.DataFrame({
                'symbol': ['000001.SZ', '000001.SZ', '000001.SZ'],
                'trade_date': ['2024-01-05', '2024-01-05', '2024-01-05'],
                'close': [15.0, 15.1, 15.2],
                'fetch_time': [
                    datetime(2024, 1, 5, 16, 0),
                    datetime(2024, 1, 5, 16, 15),
                    datetime(2024, 1, 5, 16, 30)  # Latest
                ]
            })
        }

        stage = DeduplicationStage()
        context = PipelineContext(data=input_data, config={}, metadata={})
        result = stage.execute(context)

        assert result.success
        assert len(result.data['akshare']) == 1
        assert len(result.data['tushare']) == 1
        assert result.data['tushare'].iloc[0]['close'] == 15.2

    def test_no_fetch_time_column(self):
        """Test deduplication when fetch_time column is missing."""
        input_data = {
            'akshare': pd.DataFrame({
                'symbol': ['000001.SH', '000001.SH', '000001.SZ'],
                'trade_date': ['2024-01-05', '2024-01-05', '2024-01-05'],
                'close': [1800.0, 1805.0, 15.0]
            })
        }

        stage = DeduplicationStage()
        context = PipelineContext(data=input_data, config={}, metadata={})
        result = stage.execute(context)

        assert result.success
        # Without fetch_time, keeps last occurrence in DataFrame order
        assert len(result.data['akshare']) == 2

    def test_missing_required_columns(self):
        """Test handling of missing required columns."""
        input_data = {
            'akshare': pd.DataFrame({
                'close': [1800.0],  # Missing symbol and trade_date
            })
        }

        stage = DeduplicationStage()
        context = PipelineContext(data=input_data, config={}, metadata={})
        result = stage.execute(context)

        assert not result.success  # Should fail
        assert len(result.errors) > 0
        assert 'Missing required columns' in result.errors[0]['error']
        assert 'symbol' in result.errors[0]['error']
        assert 'trade_date' in result.errors[0]['error']

    def test_empty_dataframe(self):
        """Test handling of empty DataFrame."""
        input_data = {
            'akshare': pd.DataFrame(columns=['symbol', 'trade_date', 'close'])
        }

        stage = DeduplicationStage()
        context = PipelineContext(data=input_data, config={}, metadata={})
        result = stage.execute(context)

        assert result.success
        assert len(result.data['akshare']) == 0
        assert result.metadata['deduplication_stats']['akshare']['removed'] == 0

    def test_partial_missing_columns(self):
        """Test handling when only one required column is missing."""
        input_data = {
            'akshare': pd.DataFrame({
                'symbol': ['000001.SH'],
                'close': [1800.0]  # Missing trade_date
            })
        }

        stage = DeduplicationStage()
        context = PipelineContext(data=input_data, config={}, metadata={})
        result = stage.execute(context)

        assert not result.success
        assert len(result.errors) > 0
        assert 'trade_date' in result.errors[0]['error']

    def test_mutation_prevention(self):
        """Test that input DataFrame is not mutated when fetch_time is missing."""
        original_df = pd.DataFrame({
            'symbol': ['000001.SH', '000001.SH'],
            'trade_date': ['2024-01-05', '2024-01-05'],
            'close': [1800.0, 1805.0]
        })

        input_data = {'akshare': original_df}
        original_id = id(original_df)

        stage = DeduplicationStage()
        context = PipelineContext(data=input_data, config={}, metadata={})
        result = stage.execute(context)

        # Verify input DataFrame was not mutated
        assert id(input_data['akshare']) == original_id
        assert len(input_data['akshare']) == 2  # Original still has 2 rows
        assert len(result.data['akshare']) == 1  # Result has deduplicated data
