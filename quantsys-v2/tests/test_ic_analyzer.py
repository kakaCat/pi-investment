"""
Tests for ICAnalyzer - IC/IR analysis for factor evaluation
"""

import numpy as np
import pandas as pd
import pytest
from unittest.mock import patch, MagicMock

from domain.quantlib.factor_analysis.ic_analyzer import ICAnalyzer


@pytest.fixture
def sample_factor_data():
    """Create sample factor data for testing"""
    dates = pd.date_range('2023-01-01', '2023-12-31', freq='D')
    symbols = [f'stock_{i}' for i in range(50)]

    np.random.seed(42)
    data = pd.DataFrame(
        np.random.randn(len(dates), len(symbols)),
        index=dates,
        columns=symbols
    )
    return data


@pytest.fixture
def sample_return_data():
    """Create sample return data for testing"""
    dates = pd.date_range('2023-01-01', '2023-12-31', freq='D')
    symbols = [f'stock_{i}' for i in range(50)]

    np.random.seed(43)
    data = pd.DataFrame(
        np.random.randn(len(dates), len(symbols)) * 0.02,
        index=dates,
        columns=symbols
    )
    return data


@pytest.fixture
def correlated_data():
    """Create factor and return data with known correlation"""
    dates = pd.date_range('2023-01-01', '2023-06-30', freq='D')
    symbols = [f'stock_{i}' for i in range(30)]

    np.random.seed(100)
    # Factor with predictive power
    factor_data = pd.DataFrame(
        np.random.randn(len(dates), len(symbols)),
        index=dates,
        columns=symbols
    )

    # Returns correlated with factor
    return_data = pd.DataFrame(
        factor_data.values * 0.01 + np.random.randn(len(dates), len(symbols)) * 0.015,
        index=dates,
        columns=symbols
    )

    return factor_data, return_data


class TestICAnalyzer:
    """Test suite for ICAnalyzer"""

    def test_initialization(self):
        """Test ICAnalyzer initialization"""
        analyzer = ICAnalyzer()
        assert analyzer.ic_series is None
        assert analyzer.ic_stats is None

    def test_calculate_ic_basic(self):
        """Test basic IC calculation"""
        analyzer = ICAnalyzer()

        # Perfect positive correlation
        factor_values = np.array([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
        forward_returns = np.array([0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.07, 0.08, 0.09, 0.10])

        ic = analyzer.calculate_ic(factor_values, forward_returns)
        assert ic == pytest.approx(1.0, abs=0.01)

    def test_calculate_ic_negative_correlation(self):
        """Test IC calculation with negative correlation"""
        analyzer = ICAnalyzer()

        # Perfect negative correlation
        factor_values = np.array([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
        forward_returns = np.array([0.10, 0.09, 0.08, 0.07, 0.06, 0.05, 0.04, 0.03, 0.02, 0.01])

        ic = analyzer.calculate_ic(factor_values, forward_returns)
        assert ic == pytest.approx(-1.0, abs=0.01)

    def test_calculate_ic_with_nan(self):
        """Test IC calculation handles NaN values"""
        analyzer = ICAnalyzer()

        factor_values = np.array([1, 2, np.nan, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15])
        forward_returns = np.array([0.01, 0.02, 0.03, np.nan, 0.05, 0.06, 0.07, 0.08, 0.09, 0.10, 0.11, 0.12, 0.13, 0.14, 0.15])

        ic = analyzer.calculate_ic(factor_values, forward_returns)
        # Should have enough valid samples after removing NaN
        if not np.isnan(ic):
            assert -1 <= ic <= 1

    def test_calculate_ic_insufficient_samples(self):
        """Test IC calculation with insufficient samples"""
        analyzer = ICAnalyzer()

        # Less than 10 samples
        factor_values = np.array([1, 2, 3, 4, 5])
        forward_returns = np.array([0.01, 0.02, 0.03, 0.04, 0.05])

        ic = analyzer.calculate_ic(factor_values, forward_returns)
        assert np.isnan(ic)

    def test_calculate_ic_all_nan(self):
        """Test IC calculation with all NaN values"""
        analyzer = ICAnalyzer()

        factor_values = np.array([np.nan] * 20)
        forward_returns = np.array([np.nan] * 20)

        ic = analyzer.calculate_ic(factor_values, forward_returns)
        assert np.isnan(ic)

    def test_calculate_ic_series(self, sample_factor_data, sample_return_data):
        """Test IC time series calculation"""
        analyzer = ICAnalyzer()

        periods = [1, 5, 10, 20]
        ic_series = analyzer.calculate_ic_series(
            sample_factor_data,
            sample_return_data,
            periods=periods
        )

        assert isinstance(ic_series, pd.DataFrame)
        assert len(ic_series.columns) == len(periods)
        assert all(f'IC_{p}D' in ic_series.columns for p in periods)
        assert analyzer.ic_series is not None

    def test_calculate_ic_series_single_period(self, sample_factor_data, sample_return_data):
        """Test IC series calculation with single period"""
        analyzer = ICAnalyzer()

        ic_series = analyzer.calculate_ic_series(
            sample_factor_data,
            sample_return_data,
            periods=[5]
        )

        assert len(ic_series.columns) == 1
        assert 'IC_5D' in ic_series.columns

    def test_calculate_ic_series_boundary(self, sample_factor_data, sample_return_data):
        """Test IC series handles boundary conditions"""
        analyzer = ICAnalyzer()

        # Period longer than data
        ic_series = analyzer.calculate_ic_series(
            sample_factor_data.head(30),
            sample_return_data.head(30),
            periods=[50]
        )

        assert len(ic_series) == 0 or ic_series.empty

    def test_calculate_ic_statistics(self, correlated_data):
        """Test IC statistics calculation"""
        factor_data, return_data = correlated_data
        analyzer = ICAnalyzer()

        ic_series = analyzer.calculate_ic_series(
            factor_data,
            return_data,
            periods=[1, 5, 10]
        )

        ic_stats = analyzer.calculate_ic_statistics()

        assert isinstance(ic_stats, pd.DataFrame)
        assert 'IC_mean' in ic_stats.columns
        assert 'IC_std' in ic_stats.columns
        assert 'IC_IR' in ic_stats.columns
        assert 'IC_positive_rate' in ic_stats.columns
        assert 'IC_abs_mean' in ic_stats.columns
        assert 'ICIR_annual' in ic_stats.columns
        assert 'IC_max' in ic_stats.columns
        assert 'IC_min' in ic_stats.columns
        assert analyzer.ic_stats is not None

    def test_calculate_ic_statistics_no_series(self):
        """Test IC statistics raises error without IC series"""
        analyzer = ICAnalyzer()

        with pytest.raises(ValueError, match="No IC series available"):
            analyzer.calculate_ic_statistics()

    def test_calculate_ic_statistics_custom_series(self):
        """Test IC statistics with custom IC series"""
        analyzer = ICAnalyzer()

        # Create custom IC series
        dates = pd.date_range('2023-01-01', '2023-06-30', freq='D')
        ic_series = pd.DataFrame({
            'IC_1D': np.random.randn(len(dates)) * 0.05,
            'IC_5D': np.random.randn(len(dates)) * 0.05
        }, index=dates)

        ic_stats = analyzer.calculate_ic_statistics(ic_series)

        assert isinstance(ic_stats, pd.DataFrame)
        assert len(ic_stats) == 2

    def test_calculate_ic_statistics_values(self, correlated_data):
        """Test IC statistics values are reasonable"""
        factor_data, return_data = correlated_data
        analyzer = ICAnalyzer()

        analyzer.calculate_ic_series(factor_data, return_data, periods=[5])
        ic_stats = analyzer.calculate_ic_statistics()

        # Check value ranges
        assert -1 <= ic_stats.loc['IC_5D', 'IC_mean'] <= 1
        assert ic_stats.loc['IC_5D', 'IC_std'] >= 0
        assert 0 <= ic_stats.loc['IC_5D', 'IC_positive_rate'] <= 1
        assert ic_stats.loc['IC_5D', 'IC_abs_mean'] >= 0

    def test_get_factor_quality_score(self, correlated_data):
        """Test factor quality score calculation"""
        factor_data, return_data = correlated_data
        analyzer = ICAnalyzer()

        analyzer.calculate_ic_series(factor_data, return_data, periods=[1, 5])
        analyzer.calculate_ic_statistics()

        scores = analyzer.get_factor_quality_score()

        assert isinstance(scores, dict)
        assert 'IC_1D' in scores
        assert 'IC_5D' in scores

        for period, score_dict in scores.items():
            assert 'ic_mean_score' in score_dict
            assert 'ic_ir_score' in score_dict
            assert 'ic_pos_score' in score_dict
            assert 'total_score' in score_dict
            assert 'quality' in score_dict

            # Check score ranges
            assert 4 <= score_dict['ic_mean_score'] <= 10
            assert 4 <= score_dict['ic_ir_score'] <= 10
            assert 4 <= score_dict['ic_pos_score'] <= 10
            assert 4 <= score_dict['total_score'] <= 10
            assert score_dict['quality'] in ['优秀', '良好', '一般', '较差']

    def test_get_factor_quality_score_no_stats(self):
        """Test quality score raises error without statistics"""
        analyzer = ICAnalyzer()

        with pytest.raises(ValueError, match="No IC statistics available"):
            analyzer.get_factor_quality_score()

    @pytest.mark.parametrize("ic_mean,expected_score", [
        (0.06, 10),
        (0.04, 8),
        (0.02, 6),
        (0.005, 4)
    ])
    def test_quality_score_ic_mean_thresholds(self, ic_mean, expected_score):
        """Test IC mean score thresholds"""
        analyzer = ICAnalyzer()

        # Create mock IC stats
        analyzer.ic_stats = pd.DataFrame({
            'IC_mean': [ic_mean],
            'IC_std': [0.05],
            'IC_IR': [1.0],
            'IC_positive_rate': [0.55],
            'IC_abs_mean': [0.05],
            'ICIR_annual': [1.0],
            'IC_max': [0.2],
            'IC_min': [-0.2]
        }, index=['IC_5D'])

        scores = analyzer.get_factor_quality_score()
        assert scores['IC_5D']['ic_mean_score'] == expected_score

    @pytest.mark.parametrize("ic_ir,expected_score", [
        (2.0, 10),
        (1.2, 8),
        (0.7, 6),
        (0.3, 4)
    ])
    def test_quality_score_ic_ir_thresholds(self, ic_ir, expected_score):
        """Test IC IR score thresholds"""
        analyzer = ICAnalyzer()

        analyzer.ic_stats = pd.DataFrame({
            'IC_mean': [0.03],
            'IC_std': [0.05],
            'IC_IR': [ic_ir],
            'IC_positive_rate': [0.55],
            'IC_abs_mean': [0.05],
            'ICIR_annual': [1.0],
            'IC_max': [0.2],
            'IC_min': [-0.2]
        }, index=['IC_5D'])

        scores = analyzer.get_factor_quality_score()
        assert scores['IC_5D']['ic_ir_score'] == expected_score

    @pytest.mark.parametrize("pos_rate,expected_score", [
        (0.65, 10),
        (0.57, 8),
        (0.52, 6),
        (0.45, 4)
    ])
    def test_quality_score_positive_rate_thresholds(self, pos_rate, expected_score):
        """Test IC positive rate score thresholds"""
        analyzer = ICAnalyzer()

        analyzer.ic_stats = pd.DataFrame({
            'IC_mean': [0.03],
            'IC_std': [0.05],
            'IC_IR': [1.0],
            'IC_positive_rate': [pos_rate],
            'IC_abs_mean': [0.05],
            'ICIR_annual': [1.0],
            'IC_max': [0.2],
            'IC_min': [-0.2]
        }, index=['IC_5D'])

        scores = analyzer.get_factor_quality_score()
        assert scores['IC_5D']['ic_pos_score'] == expected_score

    def test_get_quality_label(self):
        """Test quality label assignment"""
        analyzer = ICAnalyzer()

        assert analyzer._get_quality_label(9.5) == '优秀'
        assert analyzer._get_quality_label(7.5) == '良好'
        assert analyzer._get_quality_label(5.5) == '一般'
        assert analyzer._get_quality_label(4.0) == '较差'

    @patch('matplotlib.pyplot.savefig')
    @patch('matplotlib.pyplot.show')
    def test_plot_ic_series(self, mock_show, mock_savefig, correlated_data):
        """Test IC series plotting"""
        factor_data, return_data = correlated_data
        analyzer = ICAnalyzer()

        analyzer.calculate_ic_series(factor_data, return_data, periods=[1, 5])

        # Test show
        analyzer.plot_ic_series()
        mock_show.assert_called_once()

        # Test save
        analyzer.plot_ic_series(save_path='/tmp/test_ic.png')
        mock_savefig.assert_called_once_with('/tmp/test_ic.png')

    @patch('matplotlib.pyplot.show')
    def test_plot_ic_series_no_series(self, mock_show):
        """Test plotting raises error without IC series"""
        analyzer = ICAnalyzer()

        with pytest.raises(ValueError, match="No IC series available"):
            analyzer.plot_ic_series()

    def test_ic_series_persistence(self, sample_factor_data, sample_return_data):
        """Test IC series is stored in analyzer"""
        analyzer = ICAnalyzer()

        ic_series = analyzer.calculate_ic_series(
            sample_factor_data,
            sample_return_data,
            periods=[5]
        )

        assert analyzer.ic_series is not None
        pd.testing.assert_frame_equal(analyzer.ic_series, ic_series)

    def test_ic_stats_persistence(self, correlated_data):
        """Test IC stats is stored in analyzer"""
        factor_data, return_data = correlated_data
        analyzer = ICAnalyzer()

        analyzer.calculate_ic_series(factor_data, return_data, periods=[5])
        ic_stats = analyzer.calculate_ic_statistics()

        assert analyzer.ic_stats is not None
        pd.testing.assert_frame_equal(analyzer.ic_stats, ic_stats)

    def test_empty_factor_data(self):
        """Test handling of empty factor data"""
        analyzer = ICAnalyzer()

        empty_df = pd.DataFrame()

        # Empty dataframe should return empty result
        ic_series = analyzer.calculate_ic_series(empty_df, empty_df, periods=[1])
        assert len(ic_series) == 0

    def test_mismatched_dimensions(self, sample_factor_data):
        """Test handling of mismatched data dimensions"""
        analyzer = ICAnalyzer()

        # Same stocks but aligned
        common_stocks = sample_factor_data.columns[:30]
        factor_subset = sample_factor_data[common_stocks]
        return_subset = pd.DataFrame(
            np.random.randn(len(sample_factor_data), 30),
            index=sample_factor_data.index,
            columns=common_stocks
        )

        # Should handle gracefully
        ic_series = analyzer.calculate_ic_series(
            factor_subset,
            return_subset,
            periods=[5]
        )

        assert isinstance(ic_series, pd.DataFrame)

    def test_zero_std_ic_ir(self):
        """Test IC_IR calculation when std is zero"""
        analyzer = ICAnalyzer()

        # Create IC series with zero std
        dates = pd.date_range('2023-01-01', '2023-01-10', freq='D')
        ic_series = pd.DataFrame({
            'IC_1D': [0.05] * len(dates)  # Constant values
        }, index=dates)

        ic_stats = analyzer.calculate_ic_statistics(ic_series)

        # Should handle division by zero
        assert ic_stats.loc['IC_1D', 'IC_IR'] == 0
        assert ic_stats.loc['IC_1D', 'ICIR_annual'] == 0

    def test_annual_icir_calculation(self):
        """Test annual ICIR calculation"""
        analyzer = ICAnalyzer()

        dates = pd.date_range('2023-01-01', '2023-12-31', freq='D')
        ic_series = pd.DataFrame({
            'IC_1D': np.random.randn(len(dates)) * 0.05 + 0.03
        }, index=dates)

        ic_stats = analyzer.calculate_ic_statistics(ic_series)

        ic_mean = ic_stats.loc['IC_1D', 'IC_mean']
        ic_std = ic_stats.loc['IC_1D', 'IC_std']
        icir_annual = ic_stats.loc['IC_1D', 'ICIR_annual']

        expected_icir = (ic_mean / ic_std) * np.sqrt(252)
        assert icir_annual == pytest.approx(expected_icir, rel=1e-6)
