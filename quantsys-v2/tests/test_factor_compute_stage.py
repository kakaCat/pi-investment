"""Tests for FactorComputeStage - Trigger factor computation on stored data."""

import pytest
import pandas as pd
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from domain.quantlib.stages.data_pipeline import PipelineContext, PipelineResult
from domain.quantlib.stages.data_pipeline.factor_compute_stage import FactorComputeStage


class TestFactorComputeStage:
    """Test suite for FactorComputeStage."""

    @pytest.fixture
    def mock_factor_stage(self):
        """Mock FactorStage for testing."""
        with patch('domain.quantlib.stages.data_pipeline.factor_compute_stage.FactorStage') as mock:
            mock_instance = Mock()
            mock.return_value = mock_instance
            yield mock_instance

    @pytest.fixture
    def mock_kline_repo(self):
        """Mock KlineRepository for testing."""
        mock = Mock()
        mock.get_daily_klines.return_value = [
            {'trade_date': '2024-01-01', 'close': 100.0, 'high': 102.0, 'low': 98.0, 'open': 99.0, 'volume': 1000000},
            {'trade_date': '2024-01-02', 'close': 101.0, 'high': 103.0, 'low': 99.0, 'open': 100.0, 'volume': 1100000},
        ]
        return mock

    @pytest.fixture
    def mock_factor_repo(self):
        """Mock FactorRepository for testing."""
        mock = Mock()
        mock.save_factors.return_value = True
        return mock

    @pytest.fixture
    def sample_dataframe(self):
        """Sample DataFrame with stored data."""
        return pd.DataFrame({
            'symbol': ['000001.SH', '000001.SZ', '000001.SH'],
            'trade_date': ['2024-01-01', '2024-01-01', '2024-01-02'],
            'close': [100.0, 50.0, 101.0],
            'high': [102.0, 52.0, 103.0],
            'low': [98.0, 48.0, 99.0],
            'open': [99.0, 49.0, 100.0],
            'volume': [1000000, 500000, 1100000]
        })

    def test_empty_dataframe(self, mock_factor_stage, mock_kline_repo, mock_factor_repo):
        """Test handling of empty DataFrame."""
        stage = FactorComputeStage(
            kline_repo=mock_kline_repo,
            factor_repo=mock_factor_repo
        )

        empty_df = pd.DataFrame()
        context = PipelineContext(data=empty_df, config={})

        result = stage.execute(context)

        assert result.success is True
        assert result.data.equals(empty_df)
        assert len(result.errors) == 0
        assert result.metadata['factors_computed'] == 0
        assert result.metadata['symbols_processed'] == 0

    def test_factor_computation_triggered(
        self,
        sample_dataframe,
        mock_factor_stage,
        mock_kline_repo,
        mock_factor_repo
    ):
        """Test that factor computation is triggered for each symbol."""
        # Setup mock to return factors
        mock_factor_stage.process.return_value = {
            'factors': {
                'ma5': 100.5,
                'ma10': 99.8,
                'rsi14': 65.3
            }
        }

        stage = FactorComputeStage(
            kline_repo=mock_kline_repo,
            factor_repo=mock_factor_repo
        )

        context = PipelineContext(data=sample_dataframe, config={})
        result = stage.execute(context)

        # Should process 2 unique symbols
        assert result.success is True
        assert mock_kline_repo.get_daily_klines.call_count == 2
        assert mock_factor_stage.process.call_count == 2
        assert mock_factor_repo.save_factors.call_count == 2

    def test_dataframe_passthrough(
        self,
        sample_dataframe,
        mock_factor_stage,
        mock_kline_repo,
        mock_factor_repo
    ):
        """Test that DataFrame is passed through unchanged."""
        mock_factor_stage.process.return_value = {'factors': {'ma5': 100.5}}

        stage = FactorComputeStage(
            kline_repo=mock_kline_repo,
            factor_repo=mock_factor_repo
        )

        context = PipelineContext(data=sample_dataframe, config={})
        result = stage.execute(context)

        # DataFrame should be unchanged
        assert result.data.equals(sample_dataframe)
        assert id(result.data) == id(sample_dataframe)  # Same object

    def test_factor_computation_statistics(
        self,
        sample_dataframe,
        mock_factor_stage,
        mock_kline_repo,
        mock_factor_repo
    ):
        """Test that statistics are tracked correctly."""
        mock_factor_stage.process.return_value = {
            'factors': {
                'ma5': 100.5,
                'ma10': 99.8,
                'rsi14': 65.3
            }
        }

        stage = FactorComputeStage(
            kline_repo=mock_kline_repo,
            factor_repo=mock_factor_repo
        )

        context = PipelineContext(data=sample_dataframe, config={})
        result = stage.execute(context)

        assert result.metadata['symbols_processed'] == 2  # 2 unique symbols
        assert result.metadata['factors_computed'] == 6  # 2 symbols * 3 factors each
        assert result.metadata['total_records'] == 3

    def test_factor_stage_error_handling(
        self,
        sample_dataframe,
        mock_factor_stage,
        mock_kline_repo,
        mock_factor_repo
    ):
        """Test handling of FactorStage computation errors."""
        # First call succeeds, second call fails
        mock_factor_stage.process.side_effect = [
            {'factors': {'ma5': 100.5}},
            Exception("Factor computation failed")
        ]

        stage = FactorComputeStage(
            kline_repo=mock_kline_repo,
            factor_repo=mock_factor_repo
        )

        context = PipelineContext(data=sample_dataframe, config={})
        result = stage.execute(context)

        # Should still succeed with partial results
        assert result.success is True
        assert len(result.errors) == 1
        assert 'Factor computation failed' in result.errors[0]['error']
        assert result.metadata['symbols_processed'] == 1  # Only first succeeded
        assert result.metadata['symbols_failed'] == 1

    def test_factor_write_error_handling(
        self,
        sample_dataframe,
        mock_factor_stage,
        mock_kline_repo,
        mock_factor_repo
    ):
        """Test handling of factor write errors."""
        mock_factor_stage.process.return_value = {'factors': {'ma5': 100.5}}

        # First write succeeds, second write fails
        mock_factor_repo.save_factors.side_effect = [
            True,
            Exception("Database write failed")
        ]

        stage = FactorComputeStage(
            kline_repo=mock_kline_repo,
            factor_repo=mock_factor_repo
        )

        context = PipelineContext(data=sample_dataframe, config={})
        result = stage.execute(context)

        # Should still succeed with partial results
        assert result.success is True
        assert len(result.errors) == 1
        assert 'Database write failed' in result.errors[0]['error']

    def test_no_kline_data_for_symbol(
        self,
        sample_dataframe,
        mock_factor_stage,
        mock_kline_repo,
        mock_factor_repo
    ):
        """Test handling when no kline data exists for a symbol."""
        # Return empty list for klines
        mock_kline_repo.get_daily_klines.return_value = []

        stage = FactorComputeStage(
            kline_repo=mock_kline_repo,
            factor_repo=mock_factor_repo
        )

        context = PipelineContext(data=sample_dataframe, config={})
        result = stage.execute(context)

        # Should succeed but skip symbols with no data
        assert result.success is True
        assert result.metadata['symbols_processed'] == 0  # None processed
        assert result.metadata['symbols_skipped'] == 2  # Both skipped
        assert mock_factor_stage.process.call_count == 0

    def test_date_range_extraction(
        self,
        sample_dataframe,
        mock_factor_stage,
        mock_kline_repo,
        mock_factor_repo
    ):
        """Test that date range is correctly extracted from DataFrame."""
        mock_factor_stage.process.return_value = {'factors': {'ma5': 100.5}}

        stage = FactorComputeStage(
            kline_repo=mock_kline_repo,
            factor_repo=mock_factor_repo
        )

        context = PipelineContext(data=sample_dataframe, config={})
        result = stage.execute(context)

        # Check that get_daily_klines was called with correct date range
        calls = mock_kline_repo.get_daily_klines.call_args_list
        for call in calls:
            symbol, start_date, end_date = call[0]
            # Start date should be earlier due to lookback (120 days default)
            assert start_date < '2024-01-01'
            assert end_date == '2024-01-02'

    def test_custom_lookback_days(
        self,
        sample_dataframe,
        mock_factor_stage,
        mock_kline_repo,
        mock_factor_repo
    ):
        """Test custom lookback days configuration."""
        mock_factor_stage.process.return_value = {'factors': {'ma5': 100.5}}

        stage = FactorComputeStage(
            kline_repo=mock_kline_repo,
            factor_repo=mock_factor_repo
        )

        # Configure custom lookback
        context = PipelineContext(
            data=sample_dataframe,
            config={'factor_lookback_days': 60}
        )
        result = stage.execute(context)

        assert result.success is True
        # Lookback should extend the start date
        calls = mock_kline_repo.get_daily_klines.call_args_list
        for call in calls:
            symbol, start_date, end_date = call[0]
            # Start date should be earlier than data range
            assert start_date < '2024-01-01'

    def test_batch_processing(
        self,
        mock_factor_stage,
        mock_kline_repo,
        mock_factor_repo
    ):
        """Test batch processing of multiple symbols."""
        # Create DataFrame with many symbols
        symbols = [f'60{i:04d}.SH' for i in range(10)]
        df = pd.DataFrame({
            'symbol': symbols,
            'trade_date': ['2024-01-01'] * 10,
            'close': [100.0] * 10,
            'high': [102.0] * 10,
            'low': [98.0] * 10,
            'open': [99.0] * 10,
            'volume': [1000000] * 10
        })

        mock_factor_stage.process.return_value = {'factors': {'ma5': 100.5}}

        stage = FactorComputeStage(
            kline_repo=mock_kline_repo,
            factor_repo=mock_factor_repo
        )

        context = PipelineContext(data=df, config={})
        result = stage.execute(context)

        assert result.success is True
        assert result.metadata['symbols_processed'] == 10
        assert mock_factor_stage.process.call_count == 10
