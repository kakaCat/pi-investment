"""Tests for ImputationStage - Fill missing values (Priority 4)."""

import pandas as pd
import pytest
from domain.quantlib.stages.data_pipeline import PipelineContext, PipelineResult
from domain.quantlib.stages.data_pipeline.imputation_stage import ImputationStage


class TestImputationStage:
    """Test suite for ImputationStage."""

    def test_forward_fill_close_prices(self):
        """Test forward-fill for close prices."""
        stage = ImputationStage()

        # Create test data with missing close prices
        df = pd.DataFrame({
            'symbol': ['000001.SH', '000001.SH', '000001.SH'],
            'trade_date': ['2024-01-01', '2024-01-02', '2024-01-03'],
            'close': [100.0, None, None],
            'volume': [1000, 2000, 3000],
            'open': [99.0, 100.5, 101.0],
            'high': [101.0, 102.0, 103.0],
            'low': [98.0, 99.0, 100.0],
        })

        context = PipelineContext(data=df, config={})
        result = stage.execute(context)

        assert result.success is True
        assert result.data['close'].tolist() == [100.0, 100.0, 100.0]
        assert result.metadata['missing_before']['close'] == 2
        assert result.metadata['filled_count']['close'] == 2

    def test_zero_fill_volume(self):
        """Test zero-fill for volume."""
        stage = ImputationStage()

        # Create test data with missing volume
        df = pd.DataFrame({
            'symbol': ['000001.SH', '000001.SH'],
            'trade_date': ['2024-01-01', '2024-01-02'],
            'close': [100.0, 101.0],
            'volume': [1000, None],
            'open': [99.0, 100.5],
            'high': [101.0, 102.0],
            'low': [98.0, 99.0],
        })

        context = PipelineContext(data=df, config={})
        result = stage.execute(context)

        assert result.success is True
        assert result.data['volume'].tolist() == [1000, 0]
        assert result.metadata['missing_before']['volume'] == 1
        assert result.metadata['filled_count']['volume'] == 1

    def test_multiple_price_columns(self):
        """Test forward-fill for all price columns (open, high, low, close)."""
        stage = ImputationStage()

        df = pd.DataFrame({
            'symbol': ['000001.SH', '000001.SH', '000001.SH'],
            'trade_date': ['2024-01-01', '2024-01-02', '2024-01-03'],
            'close': [100.0, None, None],
            'open': [99.0, None, 101.0],
            'high': [101.0, None, None],
            'low': [98.0, 99.0, None],
            'volume': [1000, None, 3000],
        })

        context = PipelineContext(data=df, config={})
        result = stage.execute(context)

        assert result.success is True
        # Forward-fill prices
        assert result.data['close'].tolist() == [100.0, 100.0, 100.0]
        assert result.data['open'].tolist() == [99.0, 99.0, 101.0]
        assert result.data['high'].tolist() == [101.0, 101.0, 101.0]
        assert result.data['low'].tolist() == [98.0, 99.0, 99.0]
        # Zero-fill volume
        assert result.data['volume'].tolist() == [1000, 0, 3000]

    def test_groupby_symbol_independence(self):
        """Test that forward-fill respects symbol boundaries."""
        stage = ImputationStage()

        # Two symbols with missing values
        df = pd.DataFrame({
            'symbol': ['000001.SH', '000001.SH', '000001.SZ', '000001.SZ'],
            'trade_date': ['2024-01-01', '2024-01-02', '2024-01-01', '2024-01-02'],
            'close': [100.0, None, 50.0, None],
            'volume': [1000, 2000, 500, None],
            'open': [99.0, 100.5, 49.0, 50.5],
            'high': [101.0, 102.0, 51.0, 52.0],
            'low': [98.0, 99.0, 48.0, 49.0],
        })

        context = PipelineContext(data=df, config={})
        result = stage.execute(context)

        assert result.success is True
        # Each symbol should forward-fill independently
        assert result.data.loc[result.data['symbol'] == '000001.SH', 'close'].tolist() == [100.0, 100.0]
        assert result.data.loc[result.data['symbol'] == '000001.SZ', 'close'].tolist() == [50.0, 50.0]
        # Volume zero-fill
        assert result.data.loc[result.data['symbol'] == '000001.SZ', 'volume'].tolist() == [500, 0]

    def test_empty_input(self):
        """Test handling of empty DataFrame."""
        stage = ImputationStage()

        df = pd.DataFrame()
        context = PipelineContext(data=df, config={})
        result = stage.execute(context)

        assert result.success is False
        assert len(result.errors) == 1
        assert 'empty' in result.errors[0]['error'].lower()

    def test_missing_required_columns(self):
        """Test handling of missing required columns."""
        stage = ImputationStage()

        # Missing 'close' column
        df = pd.DataFrame({
            'symbol': ['000001.SH'],
            'trade_date': ['2024-01-01'],
            'volume': [1000],
        })

        context = PipelineContext(data=df, config={})
        result = stage.execute(context)

        assert result.success is False
        assert len(result.errors) == 1
        assert 'missing required columns' in result.errors[0]['error'].lower()

    def test_statistics_tracking(self):
        """Test that imputation statistics are tracked correctly."""
        stage = ImputationStage()

        df = pd.DataFrame({
            'symbol': ['000001.SH', '000001.SH', '000001.SH'],
            'trade_date': ['2024-01-01', '2024-01-02', '2024-01-03'],
            'close': [100.0, None, None],
            'volume': [1000, None, None],
            'open': [99.0, None, 101.0],
            'high': [101.0, 102.0, 103.0],
            'low': [98.0, 99.0, 100.0],
        })

        context = PipelineContext(data=df, config={})
        result = stage.execute(context)

        assert result.success is True
        # Check metadata structure
        assert 'missing_before' in result.metadata
        assert 'filled_count' in result.metadata
        assert 'symbols_with_missing' in result.metadata

        # Check counts
        assert result.metadata['missing_before']['close'] == 2
        assert result.metadata['missing_before']['volume'] == 2
        assert result.metadata['missing_before']['open'] == 1
        assert result.metadata['filled_count']['close'] == 2
        assert result.metadata['filled_count']['volume'] == 2
        assert result.metadata['filled_count']['open'] == 1

        # Check symbols list
        assert '000001.SH' in result.metadata['symbols_with_missing']

    def test_dataframe_immutability(self):
        """Test that input DataFrame is not mutated."""
        stage = ImputationStage()

        df = pd.DataFrame({
            'symbol': ['000001.SH', '000001.SH'],
            'trade_date': ['2024-01-01', '2024-01-02'],
            'close': [100.0, None],
            'volume': [1000, None],
            'open': [99.0, 100.5],
            'high': [101.0, 102.0],
            'low': [98.0, 99.0],
        })

        # Store original values
        original_close = df['close'].copy()
        original_volume = df['volume'].copy()

        context = PipelineContext(data=df, config={})
        result = stage.execute(context)

        assert result.success is True
        # Original DataFrame should not be mutated
        pd.testing.assert_series_equal(df['close'], original_close)
        pd.testing.assert_series_equal(df['volume'], original_volume)

    def test_warning_for_many_missing_values(self):
        """Test warning logged for symbols with >50% missing values."""
        stage = ImputationStage()

        # Symbol with 3/4 = 75% missing close prices
        df = pd.DataFrame({
            'symbol': ['000001.SH', '000001.SH', '000001.SH', '000001.SH'],
            'trade_date': ['2024-01-01', '2024-01-02', '2024-01-03', '2024-01-04'],
            'close': [100.0, None, None, None],
            'volume': [1000, 2000, 3000, 4000],
            'open': [99.0, 100.5, 101.0, 102.0],
            'high': [101.0, 102.0, 103.0, 104.0],
            'low': [98.0, 99.0, 100.0, 101.0],
        })

        context = PipelineContext(data=df, config={})
        result = stage.execute(context)

        assert result.success is True
        # Check that warning is in metadata
        assert 'warnings' in result.metadata
        assert len(result.metadata['warnings']) > 0
        assert '000001.SH' in result.metadata['warnings'][0]

    def test_no_missing_values(self):
        """Test handling of data with no missing values."""
        stage = ImputationStage()

        df = pd.DataFrame({
            'symbol': ['000001.SH', '000001.SH'],
            'trade_date': ['2024-01-01', '2024-01-02'],
            'close': [100.0, 101.0],
            'volume': [1000, 2000],
            'open': [99.0, 100.5],
            'high': [101.0, 102.0],
            'low': [98.0, 99.0],
        })

        context = PipelineContext(data=df, config={})
        result = stage.execute(context)

        assert result.success is True
        # Data should be unchanged
        pd.testing.assert_frame_equal(result.data, df)
        # All counts should be zero
        assert result.metadata['missing_before']['close'] == 0
        assert result.metadata['filled_count']['close'] == 0

    def test_not_a_dataframe(self):
        """Test handling of non-DataFrame input."""
        stage = ImputationStage()

        context = PipelineContext(data="not a dataframe", config={})
        result = stage.execute(context)

        assert result.success is False
        assert len(result.errors) == 1
        assert 'not a dataframe' in result.errors[0]['error'].lower()
