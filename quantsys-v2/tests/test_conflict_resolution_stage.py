"""Tests for ConflictResolutionStage."""

import pandas as pd
import pytest
from datetime import datetime

from domain.quantlib.stages.data_pipeline import PipelineContext, PipelineResult
from domain.quantlib.stages.data_pipeline.conflict_resolution_stage import ConflictResolutionStage


class TestConflictResolutionStage:
    """Test suite for ConflictResolutionStage."""

    def test_basic_merge_no_conflicts(self):
        """Test basic merge of two sources with no overlapping data."""
        stage = ConflictResolutionStage()

        # Source 1: akshare
        df1 = pd.DataFrame({
            'symbol': ['000001.SH', '000001.SZ'],
            'trade_date': ['2024-01-01', '2024-01-01'],
            'close': [1800.0, 12.5],
            'volume': [1000000, 2000000],
            'source': ['akshare', 'akshare']
        })

        # Source 2: tushare (different symbols)
        df2 = pd.DataFrame({
            'symbol': ['600036.SH', '000002.SZ'],
            'trade_date': ['2024-01-01', '2024-01-01'],
            'close': [35.0, 25.0],
            'volume': [3000000, 4000000],
            'source': ['tushare', 'tushare']
        })

        context = PipelineContext(
            data={'akshare': df1, 'tushare': df2},
            config={'sources': ['akshare', 'tushare']}
        )

        result = stage.execute(context)

        assert result.success is True
        assert isinstance(result.data, pd.DataFrame)
        assert len(result.data) == 4  # All 4 records preserved
        assert 'conflicts_detected' in result.metadata
        assert result.metadata['conflicts_detected'] == 0

    def test_priority_order_akshare_wins(self):
        """Test that akshare data takes priority over tushare when both exist."""
        stage = ConflictResolutionStage()

        # Source 1: akshare (higher priority)
        df1 = pd.DataFrame({
            'symbol': ['000001.SH'],
            'trade_date': ['2024-01-01'],
            'close': [1800.0],
            'volume': [1000000],
            'source': ['akshare']
        })

        # Source 2: tushare (lower priority, same symbol+date)
        df2 = pd.DataFrame({
            'symbol': ['000001.SH'],
            'trade_date': ['2024-01-01'],
            'close': [1805.0],  # Different value
            'volume': [1100000],
            'source': ['tushare']
        })

        context = PipelineContext(
            data={'akshare': df1, 'tushare': df2},
            config={'sources': ['akshare', 'tushare']}
        )

        result = stage.execute(context)

        assert result.success is True
        assert len(result.data) == 1  # Only one record kept
        assert result.data.iloc[0]['close'] == 1800.0  # akshare value
        assert result.data.iloc[0]['source'] == 'akshare'

    def test_conflict_detection_different_close_prices(self):
        """Test that conflicts are detected when close prices differ."""
        stage = ConflictResolutionStage()

        df1 = pd.DataFrame({
            'symbol': ['000001.SH'],
            'trade_date': ['2024-01-01'],
            'close': [1800.0],
            'volume': [1000000],
            'source': ['akshare']
        })

        df2 = pd.DataFrame({
            'symbol': ['000001.SH'],
            'trade_date': ['2024-01-01'],
            'close': [1850.0],  # 50 yuan difference
            'volume': [1000000],
            'source': ['tushare']
        })

        context = PipelineContext(
            data={'akshare': df1, 'tushare': df2},
            config={'sources': ['akshare', 'tushare']}
        )

        result = stage.execute(context)

        assert result.success is True
        assert result.metadata['conflicts_detected'] == 1
        assert 'conflict_details' in result.metadata

        conflicts = result.metadata['conflict_details']
        assert len(conflicts) == 1
        assert conflicts[0]['symbol'] == '000001.SH'
        assert conflicts[0]['trade_date'] == '2024-01-01'
        assert 'akshare' in conflicts[0]['sources']
        assert 'tushare' in conflicts[0]['sources']
        assert 'close_diff' in conflicts[0]

    def test_empty_input(self):
        """Test handling of empty input data."""
        stage = ConflictResolutionStage()

        context = PipelineContext(
            data={},
            config={'sources': ['akshare', 'tushare']}
        )

        result = stage.execute(context)

        assert result.success is False
        assert len(result.errors) > 0
        assert 'empty' in result.errors[0]['error'].lower()

    def test_missing_config_sources(self):
        """Test handling of missing sources config."""
        stage = ConflictResolutionStage()

        df1 = pd.DataFrame({
            'symbol': ['000001.SH'],
            'trade_date': ['2024-01-01'],
            'close': [1800.0],
            'source': ['akshare']
        })

        context = PipelineContext(
            data={'akshare': df1},
            config={}  # Missing 'sources' key
        )

        result = stage.execute(context)

        assert result.success is False
        assert len(result.errors) > 0
        assert 'sources' in result.errors[0]['error'].lower()

    def test_source_not_in_data(self):
        """Test handling when config source is not in data dict."""
        stage = ConflictResolutionStage()

        df1 = pd.DataFrame({
            'symbol': ['000001.SH'],
            'trade_date': ['2024-01-01'],
            'close': [1800.0],
            'source': ['akshare']
        })

        context = PipelineContext(
            data={'akshare': df1},
            config={'sources': ['akshare', 'tushare', 'yahoo']}  # tushare, yahoo missing
        )

        result = stage.execute(context)

        assert result.success is True  # Should continue with available sources
        assert len(result.data) == 1
        # Should have warnings in metadata
        assert 'warnings' in result.metadata
        assert len(result.metadata['warnings']) == 2

    def test_single_source_no_conflicts(self):
        """Test that single source has no conflicts."""
        stage = ConflictResolutionStage()

        df1 = pd.DataFrame({
            'symbol': ['000001.SH', '000001.SZ'],
            'trade_date': ['2024-01-01', '2024-01-01'],
            'close': [1800.0, 12.5],
            'volume': [1000000, 2000000],
            'source': ['akshare', 'akshare']
        })

        context = PipelineContext(
            data={'akshare': df1},
            config={'sources': ['akshare']}
        )

        result = stage.execute(context)

        assert result.success is True
        assert len(result.data) == 2
        assert result.metadata['conflicts_detected'] == 0

    def test_multiple_conflicts_same_symbol(self):
        """Test multiple conflicts for the same symbol on different dates."""
        stage = ConflictResolutionStage()

        df1 = pd.DataFrame({
            'symbol': ['000001.SH', '000001.SH'],
            'trade_date': ['2024-01-01', '2024-01-02'],
            'close': [1800.0, 1810.0],
            'volume': [1000000, 1100000],
            'source': ['akshare', 'akshare']
        })

        df2 = pd.DataFrame({
            'symbol': ['000001.SH', '000001.SH'],
            'trade_date': ['2024-01-01', '2024-01-02'],
            'close': [1850.0, 1860.0],  # Both dates have conflicts
            'volume': [1200000, 1300000],
            'source': ['tushare', 'tushare']
        })

        context = PipelineContext(
            data={'akshare': df1, 'tushare': df2},
            config={'sources': ['akshare', 'tushare']}
        )

        result = stage.execute(context)

        assert result.success is True
        assert result.metadata['conflicts_detected'] == 2
        assert len(result.metadata['conflict_details']) == 2

    def test_three_sources_priority(self):
        """Test priority resolution with three sources."""
        stage = ConflictResolutionStage()

        # Highest priority
        df1 = pd.DataFrame({
            'symbol': ['000001.SH'],
            'trade_date': ['2024-01-01'],
            'close': [1800.0],
            'source': ['akshare']
        })

        # Medium priority
        df2 = pd.DataFrame({
            'symbol': ['000001.SH'],
            'trade_date': ['2024-01-01'],
            'close': [1805.0],
            'source': ['tushare']
        })

        # Lowest priority
        df3 = pd.DataFrame({
            'symbol': ['000001.SH'],
            'trade_date': ['2024-01-01'],
            'close': [1810.0],
            'source': ['yahoo']
        })

        context = PipelineContext(
            data={'akshare': df1, 'tushare': df2, 'yahoo': df3},
            config={'sources': ['akshare', 'tushare', 'yahoo']}
        )

        result = stage.execute(context)

        assert result.success is True
        assert len(result.data) == 1
        assert result.data.iloc[0]['close'] == 1800.0  # akshare wins
        assert result.metadata['conflicts_detected'] == 1  # 1 conflict event with 3 sources
        assert len(result.metadata['conflict_details'][0]['sources']) == 3  # All 3 sources involved

    def test_no_conflict_when_prices_identical(self):
        """Test that identical prices from different sources don't count as conflicts."""
        stage = ConflictResolutionStage()

        df1 = pd.DataFrame({
            'symbol': ['000001.SH'],
            'trade_date': ['2024-01-01'],
            'close': [1800.0],
            'volume': [1000000],
            'source': ['akshare']
        })

        df2 = pd.DataFrame({
            'symbol': ['000001.SH'],
            'trade_date': ['2024-01-01'],
            'close': [1800.0],  # Same price
            'volume': [1000000],
            'source': ['tushare']
        })

        context = PipelineContext(
            data={'akshare': df1, 'tushare': df2},
            config={'sources': ['akshare', 'tushare']}
        )

        result = stage.execute(context)

        assert result.success is True
        assert result.metadata['conflicts_detected'] == 0  # No conflict

    def test_conflict_with_volume_difference(self):
        """Test conflict detection includes volume differences."""
        stage = ConflictResolutionStage()

        df1 = pd.DataFrame({
            'symbol': ['000001.SH'],
            'trade_date': ['2024-01-01'],
            'close': [1800.0],
            'volume': [1000000],
            'source': ['akshare']
        })

        df2 = pd.DataFrame({
            'symbol': ['000001.SH'],
            'trade_date': ['2024-01-01'],
            'close': [1800.0],  # Same close
            'volume': [2000000],  # Different volume
            'source': ['tushare']
        })

        context = PipelineContext(
            data={'akshare': df1, 'tushare': df2},
            config={'sources': ['akshare', 'tushare']}
        )

        result = stage.execute(context)

        assert result.success is True
        # Should detect conflict due to volume difference
        conflicts = result.metadata['conflict_details']
        assert len(conflicts) == 1, "Expected exactly 1 conflict for volume difference"
        assert 'volume_diff' in conflicts[0]
        assert conflicts[0]['volume_diff'] == 1000000

    def test_dataframe_immutability(self):
        """Test that input DataFrames are not mutated."""
        stage = ConflictResolutionStage()

        df1 = pd.DataFrame({
            'symbol': ['000001.SH'],
            'trade_date': ['2024-01-01'],
            'close': [1800.0],
            'source': ['akshare']
        })

        df1_original = df1.copy()

        context = PipelineContext(
            data={'akshare': df1},
            config={'sources': ['akshare']}
        )

        result = stage.execute(context)

        # Verify original DataFrame unchanged
        pd.testing.assert_frame_equal(df1, df1_original)
