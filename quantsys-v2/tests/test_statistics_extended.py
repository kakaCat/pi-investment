"""
Unit Tests for Extended Statistical Analysis Methods
====================================================

Tests the new statistical methods added to StatisticalAnalyzer.
"""

import pytest
import numpy as np
import pandas as pd

from domain.quantlib.statistics import StatisticalAnalyzer
from domain.quantlib.core.exceptions import DataValidationError


class TestExtendedStatisticalMethods:
    """Test extended statistical analysis methods."""

    def test_wilcoxon_test(self):
        """Test Wilcoxon signed-rank test."""
        np.random.seed(42)
        before = np.random.randn(30) + 10
        after = before + np.random.randn(30) * 0.5 + 0.5  # Slight increase

        analyzer = StatisticalAnalyzer()
        result = analyzer.wilcoxon_test(before, after, alternative='two-sided')

        assert 'statistic' in result['value']
        assert 'p_value' in result['value']
        assert result['metadata']['test_type'] == 'non_parametric_paired'
        assert 'median_difference' in result['metadata']
        assert 'effect_size' in result['metadata']

    def test_wilcoxon_test_unequal_length(self):
        """Test that Wilcoxon test rejects unequal length samples."""
        before = [1, 2, 3]
        after = [2, 3, 4, 5]

        analyzer = StatisticalAnalyzer()
        with pytest.raises(DataValidationError, match="same length"):
            analyzer.wilcoxon_test(before, after)

    def test_ks_test_normal(self):
        """Test KS test with normal distribution."""
        np.random.seed(42)
        normal_data = np.random.randn(100)

        analyzer = StatisticalAnalyzer()
        result = analyzer.ks_test(normal_data, distribution='norm')

        assert 'ks_statistic' in result['value']
        assert 'p_value' in result['value']
        assert result['parameters']['distribution'] == 'norm'
        assert 'is_good_fit' in result['metadata']

    def test_ks_test_uniform(self):
        """Test KS test with uniform distribution."""
        np.random.seed(42)
        uniform_data = np.random.uniform(0, 1, 100)

        analyzer = StatisticalAnalyzer()
        result = analyzer.ks_test(uniform_data, distribution='uniform')

        assert result['parameters']['distribution'] == 'uniform'
        assert 'conclusion' in result['metadata']

    def test_ks_test_invalid_distribution(self):
        """Test that KS test rejects invalid distribution."""
        data = np.random.randn(50)
        analyzer = StatisticalAnalyzer()

        with pytest.raises(DataValidationError, match="Unknown distribution"):
            analyzer.ks_test(data, distribution='invalid')

    def test_chi_square_test_uniform(self):
        """Test chi-square test with uniform expected frequencies."""
        # Observed frequencies (roughly uniform)
        observed = [25, 23, 27, 25]

        analyzer = StatisticalAnalyzer()
        result = analyzer.chi_square_test(observed)

        assert 'chi_square_statistic' in result['value']
        assert 'p_value' in result['value']
        assert 'degrees_of_freedom' in result['value']
        assert result['value']['degrees_of_freedom'] == 3

    def test_chi_square_test_with_expected(self):
        """Test chi-square test with specified expected frequencies."""
        observed = [30, 20, 25, 25]
        expected = [25, 25, 25, 25]

        analyzer = StatisticalAnalyzer()
        result = analyzer.chi_square_test(observed, expected)

        assert 'is_significant' in result['metadata']
        assert 'observed' in result['metadata']
        assert 'expected' in result['metadata']

    def test_chi_square_test_negative_frequencies(self):
        """Test that chi-square test rejects negative frequencies."""
        observed = [10, -5, 15]
        analyzer = StatisticalAnalyzer()

        with pytest.raises(DataValidationError, match="non-negative"):
            analyzer.chi_square_test(observed)

    def test_f_test(self):
        """Test F-test for equality of variances."""
        np.random.seed(42)
        # Two samples with different variances
        sample1 = np.random.randn(50) * 1.0
        sample2 = np.random.randn(50) * 2.0

        analyzer = StatisticalAnalyzer()
        result = analyzer.f_test(sample1, sample2)

        assert 'f_statistic' in result['value']
        assert 'p_value' in result['value']
        assert 'df1' in result['value']
        assert 'df2' in result['value']
        assert 'sample1_variance' in result['metadata']
        assert 'sample2_variance' in result['metadata']
        assert 'variance_ratio' in result['metadata']

    def test_f_test_equal_variances(self):
        """Test F-test with equal variances."""
        np.random.seed(42)
        sample1 = np.random.randn(50)
        sample2 = np.random.randn(50)

        analyzer = StatisticalAnalyzer()
        result = analyzer.f_test(sample1, sample2)

        # Should not reject null hypothesis (equal variances)
        assert result['value']['p_value'] > 0.05

    def test_kruskal_wallis_test(self):
        """Test Kruskal-Wallis test with multiple groups."""
        np.random.seed(42)
        group1 = np.random.randn(30) + 5
        group2 = np.random.randn(30) + 5.5
        group3 = np.random.randn(30) + 6

        analyzer = StatisticalAnalyzer()
        result = analyzer.kruskal_wallis_test(group1, group2, group3)

        assert 'h_statistic' in result['value']
        assert 'p_value' in result['value']
        assert 'degrees_of_freedom' in result['value']
        assert result['value']['degrees_of_freedom'] == 2
        assert result['parameters']['n_groups'] == 3
        assert 'group_medians' in result['metadata']
        assert len(result['metadata']['group_medians']) == 3

    def test_kruskal_wallis_test_two_groups(self):
        """Test Kruskal-Wallis test with two groups."""
        np.random.seed(42)
        group1 = np.random.randn(30)
        group2 = np.random.randn(30)

        analyzer = StatisticalAnalyzer()
        result = analyzer.kruskal_wallis_test(group1, group2)

        assert result['parameters']['n_groups'] == 2
        assert result['metadata']['test_type'] == 'non_parametric_anova'

    def test_kruskal_wallis_test_insufficient_groups(self):
        """Test that Kruskal-Wallis test requires at least 2 groups."""
        group1 = np.random.randn(30)
        analyzer = StatisticalAnalyzer()

        with pytest.raises(DataValidationError, match="at least 2 samples"):
            analyzer.kruskal_wallis_test(group1)

    def test_bonferroni_correction(self):
        """Test Bonferroni correction for multiple comparisons."""
        # Simulate 5 hypothesis tests
        p_values = [0.01, 0.02, 0.03, 0.04, 0.05]

        analyzer = StatisticalAnalyzer()
        result = analyzer.bonferroni_correction(p_values, alpha=0.05)

        assert 'corrected_alpha' in result['value']
        assert result['value']['corrected_alpha'] == 0.05 / 5
        assert 'n_significant' in result['value']
        assert 'significant_indices' in result['value']
        assert result['parameters']['n_tests'] == 5

    def test_bonferroni_correction_all_significant(self):
        """Test Bonferroni correction with all significant p-values."""
        p_values = [0.001, 0.002, 0.003]
        analyzer = StatisticalAnalyzer()
        result = analyzer.bonferroni_correction(p_values, alpha=0.05)

        # All should be significant even after correction
        assert result['value']['n_significant'] == 3

    def test_bonferroni_correction_none_significant(self):
        """Test Bonferroni correction with no significant p-values."""
        p_values = [0.1, 0.2, 0.3, 0.4, 0.5]
        analyzer = StatisticalAnalyzer()
        result = analyzer.bonferroni_correction(p_values, alpha=0.05)

        # None should be significant
        assert result['value']['n_significant'] == 0

    def test_bonferroni_correction_invalid_p_values(self):
        """Test that Bonferroni correction rejects invalid p-values."""
        p_values = [0.01, 1.5, 0.03]  # 1.5 is invalid
        analyzer = StatisticalAnalyzer()

        with pytest.raises(DataValidationError, match="between 0 and 1"):
            analyzer.bonferroni_correction(p_values)

    def test_timing_metadata_extended(self):
        """Test that timing decorator works for extended methods."""
        data = np.random.randn(50)
        analyzer = StatisticalAnalyzer()
        result = analyzer.ks_test(data)

        assert 'execution_time_ms' in result['metadata']
        assert result['metadata']['execution_time_ms'] > 0

    def test_result_format_extended(self):
        """Test standardized result format for extended methods."""
        data = np.random.randn(50)
        analyzer = StatisticalAnalyzer()
        result = analyzer.ks_test(data)

        # Check standard fields
        assert 'value' in result
        assert 'method' in result
        assert 'parameters' in result
        assert 'metadata' in result
        assert 'timestamp' in result
        assert 'calculator' in result

        assert result['calculator'] == 'StatisticalAnalyzer'
        assert result['method'] == 'ks_test'


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
