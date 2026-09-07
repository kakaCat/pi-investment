"""Tests for AnomalyDetectionStage."""

import pytest
import pandas as pd
from datetime import date

from domain.quantlib.stages.data_pipeline.anomaly_detection_stage import AnomalyDetectionStage
from domain.quantlib.stages.data_pipeline import PipelineContext, PipelineResult
from domain.quantlib.data_validator import DataValidator


class TestAnomalyDetectionStage:
    """Test suite for AnomalyDetectionStage."""

    def test_detect_price_jumps(self):
        """Test detection of large price jumps."""
        input_data = {
            'akshare': pd.DataFrame({
                'symbol': ['000001.SH'] * 3,
                'trade_date': [date(2024, 1, 5), date(2024, 1, 8), date(2024, 1, 9)],
                'close': [1800.0, 900.0, 1800.0],  # 50% drop then recovery
                'volume': [1000000, 1000000, 1000000]
            })
        }

        validator = DataValidator()
        stage = AnomalyDetectionStage(validator)

        context = PipelineContext(data=input_data, config={}, metadata={})
        result = stage.execute(context)

        assert result.success
        assert 'quality_reports' in result.metadata
        report = result.metadata['quality_reports']['akshare']
        assert report['quality_score'] < 100  # Quality degraded due to jump

    def test_high_quality_data_passes(self):
        """Test that clean data gets high quality score."""
        input_data = {
            'akshare': pd.DataFrame({
                'symbol': ['000001.SH'] * 3,
                'trade_date': [date(2024, 1, 5), date(2024, 1, 8), date(2024, 1, 9)],
                'close': [1800.0, 1810.0, 1820.0],  # Normal progression
                'volume': [1000000, 1100000, 1050000]
            })
        }

        validator = DataValidator()
        stage = AnomalyDetectionStage(validator)

        context = PipelineContext(data=input_data, config={}, metadata={})
        result = stage.execute(context)

        assert result.success
        report = result.metadata['quality_reports']['akshare']
        assert report['quality_score'] >= 80

    def test_volume_spike_detection(self):
        """Test detection of volume spikes."""
        input_data = {
            'akshare': pd.DataFrame({
                'symbol': ['000001.SH'] * 5,
                'trade_date': [
                    date(2024, 1, 5), date(2024, 1, 8), date(2024, 1, 9),
                    date(2024, 1, 10), date(2024, 1, 11)
                ],
                'close': [1800.0, 1810.0, 1820.0, 1830.0, 1840.0],
                'volume': [1000000, 1000000, 5000000, 1000000, 1000000]  # Spike on day 3
            })
        }

        validator = DataValidator()
        stage = AnomalyDetectionStage(validator)

        context = PipelineContext(data=input_data, config={}, metadata={})
        result = stage.execute(context)

        assert result.success
        report = result.metadata['quality_reports']['akshare']
        # Volume spike should be detected in warnings (as outliers or price jumps)
        assert any('volume' in warning['message'].lower()
                  for warning in report.get('warnings', []))

    def test_multiple_sources(self):
        """Test processing multiple data sources."""
        input_data = {
            'akshare': pd.DataFrame({
                'symbol': ['000001.SH'] * 3,
                'trade_date': [date(2024, 1, 5), date(2024, 1, 8), date(2024, 1, 9)],
                'close': [1800.0, 1810.0, 1820.0],
                'volume': [1000000, 1100000, 1050000]
            }),
            'tushare': pd.DataFrame({
                'symbol': ['000001.SZ'] * 3,
                'trade_date': [date(2024, 1, 5), date(2024, 1, 8), date(2024, 1, 9)],
                'close': [15.0, 15.1, 15.2],
                'volume': [5000000, 5100000, 5050000]
            })
        }

        validator = DataValidator()
        stage = AnomalyDetectionStage(validator)

        context = PipelineContext(data=input_data, config={}, metadata={})
        result = stage.execute(context)

        assert result.success
        assert 'akshare' in result.metadata['quality_reports']
        assert 'tushare' in result.metadata['quality_reports']
        assert 'akshare' in result.data
        assert 'tushare' in result.data

    def test_quality_score_added_to_dataframe(self):
        """Test that quality_score column is added to output DataFrame."""
        input_data = {
            'akshare': pd.DataFrame({
                'symbol': ['000001.SH'] * 3,
                'trade_date': [date(2024, 1, 5), date(2024, 1, 8), date(2024, 1, 9)],
                'close': [1800.0, 1810.0, 1820.0],
                'volume': [1000000, 1100000, 1050000]
            })
        }

        validator = DataValidator()
        stage = AnomalyDetectionStage(validator)

        context = PipelineContext(data=input_data, config={}, metadata={})
        result = stage.execute(context)

        assert result.success
        assert 'quality_score' in result.data['akshare'].columns
        assert result.data['akshare']['quality_score'].notna().all()

    def test_empty_dataframe_handling(self):
        """Test handling of empty DataFrames."""
        input_data = {
            'akshare': pd.DataFrame({
                'symbol': [],
                'trade_date': [],
                'close': [],
                'volume': []
            })
        }

        validator = DataValidator()
        stage = AnomalyDetectionStage(validator)

        context = PipelineContext(data=input_data, config={}, metadata={})
        result = stage.execute(context)

        # Should handle gracefully
        assert result.success or len(result.errors) > 0

    def test_negative_prices_detected(self):
        """Test detection of negative prices."""
        input_data = {
            'akshare': pd.DataFrame({
                'symbol': ['000001.SH'] * 3,
                'trade_date': [date(2024, 1, 5), date(2024, 1, 8), date(2024, 1, 9)],
                'close': [1800.0, -10.0, 1820.0],  # Negative price
                'volume': [1000000, 1100000, 1050000]
            })
        }

        validator = DataValidator()
        stage = AnomalyDetectionStage(validator)

        context = PipelineContext(data=input_data, config={}, metadata={})
        result = stage.execute(context)

        assert result.success
        report = result.metadata['quality_reports']['akshare']
        # Negative prices should be flagged as high severity issue
        assert any(issue['severity'] in ['high', 'critical']
                  for issue in report.get('issues', []))
        assert report['quality_score'] < 100

    def test_missing_data_handling(self):
        """Test handling of missing data."""
        input_data = {
            'akshare': pd.DataFrame({
                'symbol': ['000001.SH'] * 5,
                'trade_date': [
                    date(2024, 1, 5), date(2024, 1, 8), date(2024, 1, 9),
                    date(2024, 1, 10), date(2024, 1, 11)
                ],
                'close': [1800.0, None, 1820.0, None, 1840.0],  # 40% missing
                'volume': [1000000, 1100000, 1050000, 1075000, 1025000]
            })
        }

        validator = DataValidator()
        stage = AnomalyDetectionStage(validator)

        context = PipelineContext(data=input_data, config={}, metadata={})
        result = stage.execute(context)

        assert result.success
        report = result.metadata['quality_reports']['akshare']
        # High missing data should be detected
        assert 'missing_data_ratio' in report.get('statistics', {})

    def test_quality_score_reflects_data_quality(self):
        """Test that quality score accurately reflects data quality."""
        # Perfect data
        perfect_data = {
            'source1': pd.DataFrame({
                'symbol': ['000001.SH'] * 10,
                'trade_date': [date(2024, 1, i) for i in range(1, 11)],
                'close': [1800.0 + i * 10 for i in range(10)],
                'volume': [1000000 + i * 10000 for i in range(10)]
            })
        }

        # Bad data with multiple issues
        bad_data = {
            'source2': pd.DataFrame({
                'symbol': ['000001.SH'] * 5,
                'trade_date': [date(2024, 1, i) for i in range(1, 6)],
                'close': [1800.0, 900.0, 1800.0, -10.0, 3600.0],  # Jumps and negative
                'volume': [1000000, 5000000, 1000000, 1000000, 1000000]  # Spike
            })
        }

        validator = DataValidator()
        stage = AnomalyDetectionStage(validator)

        # Test perfect data
        context1 = PipelineContext(data=perfect_data, config={}, metadata={})
        result1 = stage.execute(context1)
        perfect_score = result1.metadata['quality_reports']['source1']['quality_score']

        # Test bad data
        context2 = PipelineContext(data=bad_data, config={}, metadata={})
        result2 = stage.execute(context2)
        bad_score = result2.metadata['quality_reports']['source2']['quality_score']

        # Perfect data should have higher score than bad data
        assert perfect_score > bad_score
        assert perfect_score >= 80
        assert bad_score < 80

    def test_error_handling_with_invalid_data(self):
        """Test error handling when processing fails."""
        input_data = {
            'akshare': "not a dataframe"  # Invalid data type
        }

        validator = DataValidator()
        stage = AnomalyDetectionStage(validator)

        context = PipelineContext(data=input_data, config={}, metadata={})
        result = stage.execute(context)

        # Should handle error gracefully
        assert result.success  # Stage doesn't fail, but reports error
        report = result.metadata['quality_reports']['akshare']
        assert report['quality_score'] == 0.0
        assert any(issue['severity'] == 'critical'
                  for issue in report.get('issues', []))
