"""
Tests for FactorLayeringBacktest - factor layering backtest analysis
"""

import numpy as np
import pandas as pd
import pytest
from unittest.mock import patch, MagicMock

from domain.quantlib.factor_analysis.layering_backtest import FactorLayeringBacktest


@pytest.fixture
def sample_factor_data():
    """Create sample factor data"""
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
    """Create sample return data"""
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
def predictive_factor_data():
    """Create factor data with predictive power"""
    dates = pd.date_range('2023-01-01', '2023-06-30', freq='D')
    symbols = [f'stock_{i}' for i in range(30)]

    np.random.seed(100)
    factor_data = pd.DataFrame(
        np.random.randn(len(dates), len(symbols)),
        index=dates,
        columns=symbols
    )

    # Returns correlated with factor
    return_data = pd.DataFrame(
        factor_data.values * 0.005 + np.random.randn(len(dates), len(symbols)) * 0.015,
        index=dates,
        columns=symbols
    )

    return factor_data, return_data


class TestFactorLayeringBacktest:
    """Test suite for FactorLayeringBacktest"""

    def test_initialization(self):
        """Test FactorLayeringBacktest initialization"""
        backtester = FactorLayeringBacktest(n_quantiles=5)
        assert backtester.n_quantiles == 5
        assert backtester.layer_returns is None
        assert backtester.layer_stats is None

    def test_initialization_default(self):
        """Test default initialization"""
        backtester = FactorLayeringBacktest()
        assert backtester.n_quantiles == 5

    @pytest.mark.parametrize("n_quantiles", [3, 5, 10])
    def test_initialization_different_quantiles(self, n_quantiles):
        """Test initialization with different quantile numbers"""
        backtester = FactorLayeringBacktest(n_quantiles=n_quantiles)
        assert backtester.n_quantiles == n_quantiles

    def test_backtest_basic(self, sample_factor_data, sample_return_data):
        """Test basic backtest execution"""
        backtester = FactorLayeringBacktest(n_quantiles=5)

        layer_returns = backtester.backtest(
            sample_factor_data,
            sample_return_data,
            holding_period=20
        )

        assert isinstance(layer_returns, pd.DataFrame)
        assert layer_returns.shape[1] == 5
        assert all(col in layer_returns.columns for col in ['Layer_1', 'Layer_2', 'Layer_3', 'Layer_4', 'Layer_5'])
        assert backtester.layer_returns is not None

    def test_backtest_different_holding_periods(self, sample_factor_data, sample_return_data):
        """Test backtest with different holding periods"""
        backtester = FactorLayeringBacktest(n_quantiles=5)

        for period in [5, 10, 20]:
            layer_returns = backtester.backtest(
                sample_factor_data,
                sample_return_data,
                holding_period=period
            )

            assert isinstance(layer_returns, pd.DataFrame)
            assert len(layer_returns) > 0

    def test_backtest_column_names(self, sample_factor_data, sample_return_data):
        """Test backtest generates correct column names"""
        backtester = FactorLayeringBacktest(n_quantiles=3)

        layer_returns = backtester.backtest(
            sample_factor_data,
            sample_return_data,
            holding_period=10
        )

        expected_columns = ['Layer_1', 'Layer_2', 'Layer_3']
        assert list(layer_returns.columns) == expected_columns

    def test_backtest_return_values(self, predictive_factor_data):
        """Test backtest return values are reasonable"""
        factor_data, return_data = predictive_factor_data
        backtester = FactorLayeringBacktest(n_quantiles=5)

        layer_returns = backtester.backtest(
            factor_data,
            return_data,
            holding_period=10
        )

        # Check returns are in reasonable range
        assert (layer_returns.abs() < 1.0).all().all()  # No 100%+ returns

    def test_backtest_insufficient_data(self):
        """Test backtest with insufficient data"""
        backtester = FactorLayeringBacktest(n_quantiles=5)

        # Very short data
        dates = pd.date_range('2023-01-01', '2023-01-10', freq='D')
        symbols = [f'stock_{i}' for i in range(20)]

        factor_data = pd.DataFrame(np.random.randn(len(dates), len(symbols)), index=dates, columns=symbols)
        return_data = pd.DataFrame(np.random.randn(len(dates), len(symbols)) * 0.02, index=dates, columns=symbols)

        layer_returns = backtester.backtest(factor_data, return_data, holding_period=20)

        # Should return empty or very short result
        assert len(layer_returns) == 0

    def test_backtest_with_nan(self):
        """Test backtest handles NaN values"""
        backtester = FactorLayeringBacktest(n_quantiles=5)

        dates = pd.date_range('2023-01-01', '2023-06-30', freq='D')
        symbols = [f'stock_{i}' for i in range(30)]

        factor_data = pd.DataFrame(np.random.randn(len(dates), len(symbols)), index=dates, columns=symbols)
        return_data = pd.DataFrame(np.random.randn(len(dates), len(symbols)) * 0.02, index=dates, columns=symbols)

        # Add some NaN values
        factor_data.iloc[10:20, 5:10] = np.nan

        layer_returns = backtester.backtest(factor_data, return_data, holding_period=10)

        # Should handle NaN gracefully
        assert isinstance(layer_returns, pd.DataFrame)

    def test_calculate_layer_statistics(self, predictive_factor_data):
        """Test layer statistics calculation"""
        factor_data, return_data = predictive_factor_data
        backtester = FactorLayeringBacktest(n_quantiles=5)

        backtester.backtest(factor_data, return_data, holding_period=10)
        layer_stats = backtester.calculate_layer_statistics()

        assert isinstance(layer_stats, pd.DataFrame)
        assert 'mean_return' in layer_stats.columns
        assert 'std_return' in layer_stats.columns
        assert 'sharpe_ratio' in layer_stats.columns
        assert 'win_rate' in layer_stats.columns
        assert 'cumulative_return' in layer_stats.columns
        assert 'max_return' in layer_stats.columns
        assert 'min_return' in layer_stats.columns
        assert backtester.layer_stats is not None

    def test_calculate_layer_statistics_no_returns(self):
        """Test statistics raises error without layer returns"""
        backtester = FactorLayeringBacktest(n_quantiles=5)

        with pytest.raises(ValueError, match="No layer returns available"):
            backtester.calculate_layer_statistics()

    def test_calculate_layer_statistics_custom_returns(self):
        """Test statistics with custom layer returns"""
        backtester = FactorLayeringBacktest(n_quantiles=5)

        dates = pd.date_range('2023-01-01', '2023-06-30', freq='D')
        layer_returns = pd.DataFrame({
            'Layer_1': np.random.randn(len(dates)) * 0.02,
            'Layer_2': np.random.randn(len(dates)) * 0.02,
            'Layer_3': np.random.randn(len(dates)) * 0.02
        }, index=dates)

        layer_stats = backtester.calculate_layer_statistics(layer_returns)

        assert isinstance(layer_stats, pd.DataFrame)
        assert len(layer_stats) == 3

    def test_calculate_layer_statistics_values(self, predictive_factor_data):
        """Test layer statistics values are reasonable"""
        factor_data, return_data = predictive_factor_data
        backtester = FactorLayeringBacktest(n_quantiles=5)

        backtester.backtest(factor_data, return_data, holding_period=10)
        layer_stats = backtester.calculate_layer_statistics()

        # Check value ranges
        assert (layer_stats['win_rate'] >= 0).all()
        assert (layer_stats['win_rate'] <= 1).all()
        assert (layer_stats['std_return'] >= 0).all()

    def test_calculate_long_short_returns(self, predictive_factor_data):
        """Test long-short returns calculation"""
        factor_data, return_data = predictive_factor_data
        backtester = FactorLayeringBacktest(n_quantiles=5)

        backtester.backtest(factor_data, return_data, holding_period=10)
        long_short = backtester.calculate_long_short_returns()

        assert isinstance(long_short, pd.Series)
        assert len(long_short) == len(backtester.layer_returns)

    def test_calculate_long_short_returns_formula(self, predictive_factor_data):
        """Test long-short returns formula is correct"""
        factor_data, return_data = predictive_factor_data
        backtester = FactorLayeringBacktest(n_quantiles=5)

        layer_returns = backtester.backtest(factor_data, return_data, holding_period=10)
        long_short = backtester.calculate_long_short_returns()

        # Should be top layer - bottom layer
        expected = layer_returns.iloc[:, -1] - layer_returns.iloc[:, 0]
        pd.testing.assert_series_equal(long_short, expected)

    def test_calculate_long_short_returns_no_returns(self):
        """Test long-short raises error without layer returns"""
        backtester = FactorLayeringBacktest(n_quantiles=5)

        with pytest.raises(ValueError, match="No layer returns available"):
            backtester.calculate_long_short_returns()

    def test_check_monotonicity(self, predictive_factor_data):
        """Test monotonicity check"""
        factor_data, return_data = predictive_factor_data
        backtester = FactorLayeringBacktest(n_quantiles=5)

        backtester.backtest(factor_data, return_data, holding_period=10)
        backtester.calculate_layer_statistics()

        monotonicity = backtester.check_monotonicity()

        assert isinstance(monotonicity, dict)
        assert 'is_monotonic_increasing' in monotonicity
        assert 'is_monotonic_decreasing' in monotonicity
        assert 'monotonicity_score' in monotonicity
        assert 'mean_returns' in monotonicity

    def test_check_monotonicity_score_range(self, predictive_factor_data):
        """Test monotonicity score is in valid range"""
        factor_data, return_data = predictive_factor_data
        backtester = FactorLayeringBacktest(n_quantiles=5)

        backtester.backtest(factor_data, return_data, holding_period=10)
        backtester.calculate_layer_statistics()

        monotonicity = backtester.check_monotonicity()

        assert 0 <= monotonicity['monotonicity_score'] <= 1

    def test_check_monotonicity_perfect_increasing(self):
        """Test monotonicity with perfect increasing returns"""
        backtester = FactorLayeringBacktest(n_quantiles=5)

        # Create perfect monotonic increasing stats
        backtester.layer_stats = pd.DataFrame({
            'mean_return': [0.01, 0.02, 0.03, 0.04, 0.05]
        }, index=['Layer_1', 'Layer_2', 'Layer_3', 'Layer_4', 'Layer_5'])

        monotonicity = backtester.check_monotonicity()

        assert monotonicity['is_monotonic_increasing'] is True
        assert monotonicity['monotonicity_score'] == 1.0

    def test_check_monotonicity_perfect_decreasing(self):
        """Test monotonicity with perfect decreasing returns"""
        backtester = FactorLayeringBacktest(n_quantiles=5)

        backtester.layer_stats = pd.DataFrame({
            'mean_return': [0.05, 0.04, 0.03, 0.02, 0.01]
        }, index=['Layer_1', 'Layer_2', 'Layer_3', 'Layer_4', 'Layer_5'])

        monotonicity = backtester.check_monotonicity()

        assert monotonicity['is_monotonic_decreasing'] is True
        assert monotonicity['monotonicity_score'] == 1.0

    def test_check_monotonicity_no_stats(self):
        """Test monotonicity raises error without statistics"""
        backtester = FactorLayeringBacktest(n_quantiles=5)

        with pytest.raises(ValueError, match="No layer statistics available"):
            backtester.check_monotonicity()

    def test_get_factor_effectiveness_score(self, predictive_factor_data):
        """Test factor effectiveness score calculation"""
        factor_data, return_data = predictive_factor_data
        backtester = FactorLayeringBacktest(n_quantiles=5)

        backtester.backtest(factor_data, return_data, holding_period=10)
        backtester.calculate_layer_statistics()

        effectiveness = backtester.get_factor_effectiveness_score()

        assert isinstance(effectiveness, dict)
        assert 'monotonicity_score' in effectiveness
        assert 'return_score' in effectiveness
        assert 'sharpe_score' in effectiveness
        assert 'total_score' in effectiveness
        assert 'long_short_return' in effectiveness
        assert 'long_short_sharpe' in effectiveness
        assert 'long_short_win_rate' in effectiveness
        assert 'effectiveness' in effectiveness

    def test_get_factor_effectiveness_score_ranges(self, predictive_factor_data):
        """Test effectiveness score values are in valid ranges"""
        factor_data, return_data = predictive_factor_data
        backtester = FactorLayeringBacktest(n_quantiles=5)

        backtester.backtest(factor_data, return_data, holding_period=10)
        backtester.calculate_layer_statistics()

        effectiveness = backtester.get_factor_effectiveness_score()

        assert 0 <= effectiveness['monotonicity_score'] <= 10
        assert 4 <= effectiveness['return_score'] <= 10
        assert 4 <= effectiveness['sharpe_score'] <= 10
        assert 0 <= effectiveness['total_score'] <= 10
        assert 0 <= effectiveness['long_short_win_rate'] <= 1
        assert effectiveness['effectiveness'] in ['非常有效', '有效', '一般', '无效']

    def test_get_factor_effectiveness_score_no_stats(self):
        """Test effectiveness score raises error without statistics"""
        backtester = FactorLayeringBacktest(n_quantiles=5)

        with pytest.raises(ValueError, match="No layer statistics available"):
            backtester.get_factor_effectiveness_score()

    @pytest.mark.parametrize("score,expected_label", [
        (9.5, '非常有效'),
        (8.0, '有效'),
        (6.0, '一般'),
        (4.0, '无效')
    ])
    def test_get_effectiveness_label(self, score, expected_label):
        """Test effectiveness label assignment"""
        backtester = FactorLayeringBacktest(n_quantiles=5)
        assert backtester._get_effectiveness_label(score) == expected_label

    @patch('matplotlib.pyplot.savefig')
    @patch('matplotlib.pyplot.show')
    def test_plot_layer_performance(self, mock_show, mock_savefig, predictive_factor_data):
        """Test layer performance plotting"""
        factor_data, return_data = predictive_factor_data
        backtester = FactorLayeringBacktest(n_quantiles=5)

        backtester.backtest(factor_data, return_data, holding_period=10)
        backtester.calculate_layer_statistics()

        # Test show
        backtester.plot_layer_performance()
        mock_show.assert_called_once()

        # Test save
        backtester.plot_layer_performance(save_path='/tmp/test_layer.png')
        mock_savefig.assert_called_once_with('/tmp/test_layer.png')

    @patch('matplotlib.pyplot.show')
    def test_plot_layer_performance_no_returns(self, mock_show):
        """Test plotting raises error without layer returns"""
        backtester = FactorLayeringBacktest(n_quantiles=5)

        with pytest.raises(ValueError, match="No layer returns available"):
            backtester.plot_layer_performance()

    def test_layer_returns_persistence(self, sample_factor_data, sample_return_data):
        """Test layer returns are stored in backtester"""
        backtester = FactorLayeringBacktest(n_quantiles=5)

        layer_returns = backtester.backtest(
            sample_factor_data,
            sample_return_data,
            holding_period=10
        )

        assert backtester.layer_returns is not None
        pd.testing.assert_frame_equal(backtester.layer_returns, layer_returns)

    def test_layer_stats_persistence(self, predictive_factor_data):
        """Test layer stats are stored in backtester"""
        factor_data, return_data = predictive_factor_data
        backtester = FactorLayeringBacktest(n_quantiles=5)

        backtester.backtest(factor_data, return_data, holding_period=10)
        layer_stats = backtester.calculate_layer_statistics()

        assert backtester.layer_stats is not None
        pd.testing.assert_frame_equal(backtester.layer_stats, layer_stats)

    def test_empty_factor_data(self):
        """Test handling of empty factor data"""
        backtester = FactorLayeringBacktest(n_quantiles=5)

        empty_df = pd.DataFrame()

        # Empty dataframe should return empty result
        layer_returns = backtester.backtest(empty_df, empty_df, holding_period=10)
        assert len(layer_returns) == 0

    def test_single_stock(self):
        """Test backtest with single stock"""
        backtester = FactorLayeringBacktest(n_quantiles=5)

        dates = pd.date_range('2023-01-01', '2023-06-30', freq='D')
        factor_data = pd.DataFrame({'stock_1': np.random.randn(len(dates))}, index=dates)
        return_data = pd.DataFrame({'stock_1': np.random.randn(len(dates)) * 0.02}, index=dates)

        # Cannot split single stock into 5 layers
        layer_returns = backtester.backtest(factor_data, return_data, holding_period=10)

        # Should handle gracefully (may be empty or have fewer layers)
        assert isinstance(layer_returns, pd.DataFrame)

    def test_few_stocks(self):
        """Test backtest with few stocks"""
        backtester = FactorLayeringBacktest(n_quantiles=5)

        dates = pd.date_range('2023-01-01', '2023-06-30', freq='D')
        symbols = [f'stock_{i}' for i in range(3)]  # Only 3 stocks

        factor_data = pd.DataFrame(np.random.randn(len(dates), len(symbols)), index=dates, columns=symbols)
        return_data = pd.DataFrame(np.random.randn(len(dates), len(symbols)) * 0.02, index=dates, columns=symbols)

        # Should handle gracefully
        layer_returns = backtester.backtest(factor_data, return_data, holding_period=10)

        assert isinstance(layer_returns, pd.DataFrame)

    def test_duplicate_factor_values(self):
        """Test backtest with duplicate factor values"""
        backtester = FactorLayeringBacktest(n_quantiles=5)

        dates = pd.date_range('2023-01-01', '2023-06-30', freq='D')
        symbols = [f'stock_{i}' for i in range(30)]

        # Many duplicate values
        factor_data = pd.DataFrame(
            np.random.choice([1, 2, 3], size=(len(dates), len(symbols))),
            index=dates,
            columns=symbols
        )
        return_data = pd.DataFrame(np.random.randn(len(dates), len(symbols)) * 0.02, index=dates, columns=symbols)

        # Should handle duplicates with 'drop' parameter
        layer_returns = backtester.backtest(factor_data, return_data, holding_period=10)

        assert isinstance(layer_returns, pd.DataFrame)

    def test_sharpe_ratio_calculation(self, predictive_factor_data):
        """Test Sharpe ratio calculation in statistics"""
        factor_data, return_data = predictive_factor_data
        backtester = FactorLayeringBacktest(n_quantiles=5)

        backtester.backtest(factor_data, return_data, holding_period=10)
        layer_stats = backtester.calculate_layer_statistics()

        # Check Sharpe ratio formula
        for layer in layer_stats.index:
            mean_ret = layer_stats.loc[layer, 'mean_return']
            std_ret = layer_stats.loc[layer, 'std_return']
            sharpe = layer_stats.loc[layer, 'sharpe_ratio']

            if std_ret > 0:
                expected_sharpe = mean_ret / std_ret * np.sqrt(252)
                assert sharpe == pytest.approx(expected_sharpe, rel=1e-6)
            else:
                assert sharpe == 0

    def test_cumulative_return_calculation(self, predictive_factor_data):
        """Test cumulative return calculation"""
        factor_data, return_data = predictive_factor_data
        backtester = FactorLayeringBacktest(n_quantiles=5)

        layer_returns = backtester.backtest(factor_data, return_data, holding_period=10)
        layer_stats = backtester.calculate_layer_statistics()

        # Check cumulative return formula
        for layer in layer_stats.index:
            returns = layer_returns[layer].dropna()
            expected_cum = (1 + returns).prod() - 1
            actual_cum = layer_stats.loc[layer, 'cumulative_return']

            assert actual_cum == pytest.approx(expected_cum, rel=1e-6)

    def test_win_rate_calculation(self, predictive_factor_data):
        """Test win rate calculation"""
        factor_data, return_data = predictive_factor_data
        backtester = FactorLayeringBacktest(n_quantiles=5)

        layer_returns = backtester.backtest(factor_data, return_data, holding_period=10)
        layer_stats = backtester.calculate_layer_statistics()

        # Check win rate formula
        for layer in layer_stats.index:
            returns = layer_returns[layer].dropna()
            expected_win_rate = (returns > 0).sum() / len(returns)
            actual_win_rate = layer_stats.loc[layer, 'win_rate']

            assert actual_win_rate == pytest.approx(expected_win_rate, rel=1e-6)

    def test_different_quantile_numbers(self, sample_factor_data, sample_return_data):
        """Test backtest with different quantile numbers"""
        for n_quantiles in [3, 5, 10]:
            backtester = FactorLayeringBacktest(n_quantiles=n_quantiles)

            layer_returns = backtester.backtest(
                sample_factor_data,
                sample_return_data,
                holding_period=10
            )

            assert layer_returns.shape[1] == n_quantiles
