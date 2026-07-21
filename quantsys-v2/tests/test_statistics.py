"""
Unit Tests for Statistical Analysis Module
===========================================

Tests the StatisticalAnalyzer functionality.
"""

import pytest
import numpy as np
import pandas as pd

from domain.quantlib.statistics import StatisticalAnalyzer
from domain.quantlib.core.exceptions import DataValidationError, InsufficientDataError


class TestStatisticalAnalyzer:
    """Test StatisticalAnalyzer class."""

    def test_bootstrap_mean(self):
        """Test bootstrap resampling for mean."""
        np.random.seed(42)
        data = np.random.randn(100) + 5  # Mean around 5

        analyzer = StatisticalAnalyzer()
        result = analyzer.bootstrap_resample(
            data,
            statistic='mean',
            n_iterations=1000,
            confidence_level=0.95,
            random_seed=42
        )

        # Check that original mean is close to 5
        assert 4.5 < result['value']['statistic'] < 5.5

        # Check confidence interval contains the mean
        ci_lower, ci_upper = result['value']['confidence_interval']
        assert ci_lower < result['value']['statistic'] < ci_upper

        # Check metadata
        assert 'bootstrap_distribution' in result['metadata']
        assert len(result['metadata']['bootstrap_distribution']) == 1000

    def test_bootstrap_sharpe(self):
        """Test bootstrap resampling for Sharpe ratio."""
        np.random.seed(42)
        returns = np.random.randn(100) * 0.02 + 0.001  # Small positive returns

        analyzer = StatisticalAnalyzer()
        result = analyzer.bootstrap_resample(
            returns,
            statistic='sharpe',
            n_iterations=1000,
            random_seed=42
        )

        assert 'statistic' in result['value']
        assert 'confidence_interval' in result['value']
        assert 'standard_error' in result['value']

    def test_one_sample_t_test(self):
        """Test one-sample t-test."""
        np.random.seed(42)
        # Sample with mean around 5
        data = np.random.randn(50) + 5

        analyzer = StatisticalAnalyzer()
        result = analyzer.t_test(data, mu=0.0, alternative='two-sided')

        # Should reject null hypothesis (mean != 0)
        assert result['metadata']['is_significant'] == True
        assert result['value']['p_value'] < 0.05

        # Test against true mean
        result2 = analyzer.t_test(data, mu=5.0, alternative='two-sided')
        # Should not reject (mean ≈ 5)
        assert result2['value']['p_value'] > 0.05

    def test_two_sample_t_test(self):
        """Test two-sample t-test."""
        np.random.seed(42)
        sample1 = np.random.randn(50) + 5
        sample2 = np.random.randn(50) + 5.5  # Slightly higher mean

        analyzer = StatisticalAnalyzer()
        result = analyzer.t_test(sample1, sample2, alternative='two-sided')

        assert 't_statistic' in result['value']
        assert 'p_value' in result['value']
        assert result['parameters']['test_type'] == 'two_sample'
        assert 'effect_size' in result['metadata']

    def test_paired_t_test(self):
        """Test paired t-test."""
        np.random.seed(42)
        before = np.random.randn(30) + 10
        after = before + np.random.randn(30) * 0.5 + 1  # Increase by ~1

        analyzer = StatisticalAnalyzer()
        result = analyzer.paired_t_test(before, after, alternative='two-sided')

        # Should detect the difference
        assert result['metadata']['is_significant'] == True
        assert result['metadata']['mean_difference'] > 0
        assert 'effect_size' in result['metadata']

    def test_paired_t_test_unequal_length(self):
        """Test that paired t-test rejects unequal length samples."""
        before = [1, 2, 3]
        after = [2, 3, 4, 5]

        analyzer = StatisticalAnalyzer()
        with pytest.raises(DataValidationError, match="same length"):
            analyzer.paired_t_test(before, after)

    def test_mann_whitney_test(self):
        """Test Mann-Whitney U test."""
        np.random.seed(42)
        # Two samples with different medians
        sample1 = np.random.randn(40) + 5
        sample2 = np.random.randn(40) + 6

        analyzer = StatisticalAnalyzer()
        result = analyzer.mann_whitney_test(sample1, sample2, alternative='two-sided')

        assert 'u_statistic' in result['value']
        assert 'p_value' in result['value']
        assert result['metadata']['test_type'] == 'non_parametric'
        assert 'sample1_median' in result['metadata']
        assert 'sample2_median' in result['metadata']

    def test_shapiro_test_normal(self):
        """Test Shapiro-Wilk test on normal data."""
        np.random.seed(42)
        normal_data = np.random.randn(100)

        analyzer = StatisticalAnalyzer()
        result = analyzer.shapiro_test(normal_data)

        # Should not reject normality
        assert result['metadata']['is_normal'] == True
        assert result['metadata']['conclusion'] == 'normal'

    def test_shapiro_test_non_normal(self):
        """Test Shapiro-Wilk test on non-normal data."""
        np.random.seed(42)
        # Exponential distribution (non-normal)
        non_normal_data = np.random.exponential(scale=2.0, size=100)

        analyzer = StatisticalAnalyzer()
        result = analyzer.shapiro_test(non_normal_data)

        # Should reject normality
        assert result['metadata']['is_normal'] == False
        assert result['metadata']['conclusion'] == 'non_normal'

    def test_confidence_interval_t_method(self):
        """Test confidence interval using t-distribution."""
        np.random.seed(42)
        data = np.random.randn(50) + 10

        analyzer = StatisticalAnalyzer()
        result = analyzer.calculate_confidence_interval(
            data,
            confidence_level=0.95,
            method='t'
        )

        mean = result['value']['mean']
        ci_lower, ci_upper = result['value']['confidence_interval']

        # Mean should be within CI
        assert ci_lower < mean < ci_upper

        # CI should be reasonable
        assert ci_upper - ci_lower < 2  # Not too wide

    def test_confidence_interval_bootstrap_method(self):
        """Test confidence interval using bootstrap."""
        np.random.seed(42)
        data = np.random.randn(50) + 10

        analyzer = StatisticalAnalyzer()
        result = analyzer.calculate_confidence_interval(
            data,
            confidence_level=0.95,
            method='bootstrap'
        )

        mean = result['value']['mean']
        ci_lower, ci_upper = result['value']['confidence_interval']

        # Mean should be within CI
        assert ci_lower < mean < ci_upper

    def test_effect_size_interpretation(self):
        """Test effect size interpretation."""
        analyzer = StatisticalAnalyzer()

        assert analyzer._interpret_effect_size(0.1) == 'negligible'
        assert analyzer._interpret_effect_size(0.3) == 'small'
        assert analyzer._interpret_effect_size(0.6) == 'medium'
        assert analyzer._interpret_effect_size(1.0) == 'large'
        assert analyzer._interpret_effect_size(-0.7) == 'medium'

    def test_bootstrap_insufficient_iterations(self):
        """Test that bootstrap rejects too few iterations."""
        data = np.random.randn(50)
        analyzer = StatisticalAnalyzer()

        with pytest.raises(DataValidationError, match="at least 100"):
            analyzer.bootstrap_resample(data, n_iterations=50)

    def test_t_test_insufficient_data(self):
        """Test that t-test rejects insufficient data."""
        data = [1, 2]  # Only 2 points
        analyzer = StatisticalAnalyzer()

        with pytest.raises(ValueError, match="Insufficient data"):
            analyzer.t_test(data)

    def test_invalid_alternative_hypothesis(self):
        """Test that invalid alternative hypothesis is rejected."""
        data = np.random.randn(30)
        analyzer = StatisticalAnalyzer()

        with pytest.raises(DataValidationError, match="Invalid alternative"):
            analyzer.t_test(data, alternative='invalid')

    def test_timing_metadata(self):
        """Test that timing decorator adds execution time."""
        data = np.random.randn(100)
        analyzer = StatisticalAnalyzer()
        result = analyzer.shapiro_test(data)

        assert 'execution_time_ms' in result['metadata']
        assert result['metadata']['execution_time_ms'] > 0

    def test_result_format(self):
        """Test standardized result format."""
        data = np.random.randn(50)
        analyzer = StatisticalAnalyzer()
        result = analyzer.shapiro_test(data)

        # Check standard fields
        assert 'value' in result
        assert 'method' in result
        assert 'parameters' in result
        assert 'metadata' in result
        assert 'timestamp' in result
        assert 'calculator' in result

        assert result['calculator'] == 'StatisticalAnalyzer'

    def test_bootstrap_different_statistics(self):
        """Test bootstrap with different statistics."""
        np.random.seed(42)
        data = np.random.randn(100)
        analyzer = StatisticalAnalyzer()

        # Test mean
        result_mean = analyzer.bootstrap_resample(data, statistic='mean', n_iterations=500, random_seed=42)
        assert 'statistic' in result_mean['value']

        # Test median
        result_median = analyzer.bootstrap_resample(data, statistic='median', n_iterations=500, random_seed=42)
        assert 'statistic' in result_median['value']

        # Test std
        result_std = analyzer.bootstrap_resample(data, statistic='std', n_iterations=500, random_seed=42)
        assert 'statistic' in result_std['value']

    def test_confidence_levels(self):
        """Test different confidence levels."""
        np.random.seed(42)
        data = np.random.randn(100)
        analyzer = StatisticalAnalyzer()

        # 90% CI
        result_90 = analyzer.calculate_confidence_interval(data, confidence_level=0.90)
        ci_90_width = result_90['value']['confidence_interval'][1] - result_90['value']['confidence_interval'][0]

        # 95% CI
        result_95 = analyzer.calculate_confidence_interval(data, confidence_level=0.95)
        ci_95_width = result_95['value']['confidence_interval'][1] - result_95['value']['confidence_interval'][0]

        # 95% CI should be wider than 90% CI
        assert ci_95_width > ci_90_width


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
