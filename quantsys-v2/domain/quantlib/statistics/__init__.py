"""
Statistical Analysis Module
===========================

Advanced statistical analysis tools including hypothesis testing,
bootstrap resampling, and confidence interval estimation.

Inspired by FinceptTerminal's statistical analysis capabilities.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Union, Literal
from scipy import stats
import warnings

from infrastructure.quantlib.core.base_calculator import (
    BaseCalculator,
    validate_inputs,
    timing_decorator,
    handle_calculation_error
)
from infrastructure.quantlib.core.exceptions import (
    DataValidationError,
    InsufficientDataError,
    CalculationError
)


class StatisticalAnalyzer(BaseCalculator):
    """
    Statistical analysis calculator.

    Provides hypothesis testing, bootstrap resampling, and confidence intervals.
    """

    def get_supported_methods(self) -> List[str]:
        return [
            'bootstrap_resample',
            't_test',
            'paired_t_test',
            'mann_whitney_test',
            'wilcoxon_test',
            'shapiro_test',
            'calculate_confidence_interval',
            'ks_test',
            'chi_square_test',
            'f_test',
            'kruskal_wallis_test',
            'bonferroni_correction'
        ]

    @validate_inputs
    @timing_decorator
    @handle_calculation_error
    def bootstrap_resample(
        self,
        data: Union[List, np.ndarray, pd.Series],
        statistic: Literal['mean', 'median', 'std', 'sharpe'] = 'mean',
        n_iterations: int = 10000,
        confidence_level: float = 0.95,
        random_seed: Optional[int] = None
    ) -> Dict:
        """
        Perform bootstrap resampling to estimate sampling distribution.

        Args:
            data: Sample data
            statistic: Statistic to compute ('mean', 'median', 'std', 'sharpe')
            n_iterations: Number of bootstrap iterations
            confidence_level: Confidence level for interval (0-1)
            random_seed: Random seed for reproducibility

        Returns:
            Result dict with bootstrap distribution and confidence interval
        """
        # Validate
        data = self._validate_returns(data, "data")
        self._check_data_length(data, min_length=10)
        confidence_level = self._validate_probability(confidence_level, "confidence_level")

        if n_iterations < 100:
            raise DataValidationError(
                "n_iterations must be at least 100",
                "n_iterations"
            )

        if random_seed is not None:
            np.random.seed(random_seed)

        # Define statistic function
        stat_func = self._get_statistic_function(statistic)

        # Bootstrap resampling
        n = len(data)
        bootstrap_stats = np.zeros(n_iterations)

        for i in range(n_iterations):
            # Resample with replacement
            sample = np.random.choice(data, size=n, replace=True)
            bootstrap_stats[i] = stat_func(sample)

        # Calculate confidence interval
        alpha = 1 - confidence_level
        lower_percentile = (alpha / 2) * 100
        upper_percentile = (1 - alpha / 2) * 100

        ci_lower = np.percentile(bootstrap_stats, lower_percentile)
        ci_upper = np.percentile(bootstrap_stats, upper_percentile)

        # Original statistic
        original_stat = stat_func(data)

        # Standard error
        bootstrap_se = np.std(bootstrap_stats)

        return self._create_result_dict(
            value={
                'statistic': round(original_stat, self.precision),
                'confidence_interval': [
                    round(ci_lower, self.precision),
                    round(ci_upper, self.precision)
                ],
                'standard_error': round(bootstrap_se, self.precision)
            },
            method='bootstrap_resample',
            parameters={
                'data_length': n,
                'statistic': statistic,
                'n_iterations': n_iterations,
                'confidence_level': confidence_level
            },
            metadata={
                'bootstrap_distribution': bootstrap_stats.tolist(),
                'bootstrap_mean': round(np.mean(bootstrap_stats), self.precision),
                'bootstrap_std': round(np.std(bootstrap_stats), self.precision),
                'bias': round(np.mean(bootstrap_stats) - original_stat, self.precision)
            }
        )

    @validate_inputs
    @timing_decorator
    @handle_calculation_error
    def t_test(
        self,
        sample1: Union[List, np.ndarray, pd.Series],
        sample2: Optional[Union[List, np.ndarray, pd.Series]] = None,
        mu: float = 0.0,
        alternative: Literal['two-sided', 'less', 'greater'] = 'two-sided'
    ) -> Dict:
        """
        Perform t-test (one-sample or two-sample).

        Args:
            sample1: First sample
            sample2: Second sample (None for one-sample test)
            mu: Hypothesized mean (for one-sample test)
            alternative: Alternative hypothesis

        Returns:
            Result dict with t-statistic and p-value
        """
        # Validate
        sample1 = self._validate_returns(sample1, "sample1")
        self._check_data_length(sample1, min_length=3)

        if alternative not in ['two-sided', 'less', 'greater']:
            raise DataValidationError(
                f"Invalid alternative: {alternative}",
                "alternative"
            )

        if sample2 is None:
            # One-sample t-test
            t_stat, p_value = stats.ttest_1samp(sample1, mu, alternative=alternative)
            test_type = 'one_sample'
            df = len(sample1) - 1

            effect_size = (np.mean(sample1) - mu) / np.std(sample1, ddof=1)

        else:
            # Two-sample t-test
            sample2 = self._validate_returns(sample2, "sample2")
            self._check_data_length(sample2, min_length=3)

            t_stat, p_value = stats.ttest_ind(sample1, sample2, alternative=alternative)
            test_type = 'two_sample'
            df = len(sample1) + len(sample2) - 2

            # Cohen's d effect size
            pooled_std = np.sqrt(
                ((len(sample1) - 1) * np.var(sample1, ddof=1) +
                 (len(sample2) - 1) * np.var(sample2, ddof=1)) / df
            )
            effect_size = (np.mean(sample1) - np.mean(sample2)) / pooled_std

        # Determine significance
        alpha = 0.05
        is_significant = p_value < alpha

        return self._create_result_dict(
            value={
                't_statistic': round(float(t_stat), self.precision),
                'p_value': round(float(p_value), self.precision),
                'degrees_of_freedom': int(df)
            },
            method='t_test',
            parameters={
                'sample1_size': len(sample1),
                'sample2_size': len(sample2) if sample2 is not None else None,
                'mu': mu,
                'alternative': alternative,
                'test_type': test_type
            },
            metadata={
                'is_significant': is_significant,
                'alpha': alpha,
                'effect_size': round(effect_size, 4),
                'sample1_mean': round(np.mean(sample1), self.precision),
                'sample2_mean': round(np.mean(sample2), self.precision) if sample2 is not None else None,
                'interpretation': self._interpret_effect_size(effect_size)
            }
        )

    @validate_inputs
    @timing_decorator
    @handle_calculation_error
    def paired_t_test(
        self,
        before: Union[List, np.ndarray, pd.Series],
        after: Union[List, np.ndarray, pd.Series],
        alternative: Literal['two-sided', 'less', 'greater'] = 'two-sided'
    ) -> Dict:
        """
        Perform paired t-test.

        Args:
            before: Measurements before treatment
            after: Measurements after treatment
            alternative: Alternative hypothesis

        Returns:
            Result dict with t-statistic and p-value
        """
        # Validate
        before = self._validate_returns(before, "before")
        after = self._validate_returns(after, "after")

        if len(before) != len(after):
            raise DataValidationError(
                f"Samples must have same length: {len(before)} vs {len(after)}",
                "sample_length"
            )

        self._check_data_length(before, min_length=3)

        # Perform paired t-test
        t_stat, p_value = stats.ttest_rel(before, after, alternative=alternative)

        # Calculate differences
        differences = after - before
        mean_diff = np.mean(differences)
        std_diff = np.std(differences, ddof=1)

        # Effect size (Cohen's d for paired samples)
        effect_size = mean_diff / std_diff

        # Determine significance
        alpha = 0.05
        is_significant = p_value < alpha

        return self._create_result_dict(
            value={
                't_statistic': round(float(t_stat), self.precision),
                'p_value': round(float(p_value), self.precision),
                'degrees_of_freedom': len(before) - 1
            },
            method='paired_t_test',
            parameters={
                'n_pairs': len(before),
                'alternative': alternative
            },
            metadata={
                'is_significant': is_significant,
                'alpha': alpha,
                'mean_difference': round(mean_diff, self.precision),
                'std_difference': round(std_diff, self.precision),
                'effect_size': round(effect_size, 4),
                'interpretation': self._interpret_effect_size(effect_size),
                'before_mean': round(np.mean(before), self.precision),
                'after_mean': round(np.mean(after), self.precision)
            }
        )

    @validate_inputs
    @timing_decorator
    @handle_calculation_error
    def mann_whitney_test(
        self,
        sample1: Union[List, np.ndarray, pd.Series],
        sample2: Union[List, np.ndarray, pd.Series],
        alternative: Literal['two-sided', 'less', 'greater'] = 'two-sided'
    ) -> Dict:
        """
        Perform Mann-Whitney U test (non-parametric alternative to t-test).

        Args:
            sample1: First sample
            sample2: Second sample
            alternative: Alternative hypothesis

        Returns:
            Result dict with U-statistic and p-value
        """
        # Validate
        sample1 = self._validate_returns(sample1, "sample1")
        sample2 = self._validate_returns(sample2, "sample2")
        self._check_data_length(sample1, min_length=3)
        self._check_data_length(sample2, min_length=3)

        # Perform Mann-Whitney U test
        u_stat, p_value = stats.mannwhitneyu(
            sample1, sample2,
            alternative=alternative
        )

        # Determine significance
        alpha = 0.05
        is_significant = p_value < alpha

        # Rank-biserial correlation (effect size)
        n1, n2 = len(sample1), len(sample2)
        r = 1 - (2 * u_stat) / (n1 * n2)

        return self._create_result_dict(
            value={
                'u_statistic': round(float(u_stat), self.precision),
                'p_value': round(float(p_value), self.precision)
            },
            method='mann_whitney_test',
            parameters={
                'sample1_size': n1,
                'sample2_size': n2,
                'alternative': alternative
            },
            metadata={
                'is_significant': is_significant,
                'alpha': alpha,
                'effect_size': round(r, 4),
                'sample1_median': round(np.median(sample1), self.precision),
                'sample2_median': round(np.median(sample2), self.precision),
                'test_type': 'non_parametric'
            }
        )

    @validate_inputs
    @timing_decorator
    @handle_calculation_error
    def shapiro_test(
        self,
        data: Union[List, np.ndarray, pd.Series]
    ) -> Dict:
        """
        Perform Shapiro-Wilk test for normality.

        Args:
            data: Sample data

        Returns:
            Result dict with test statistic and p-value
        """
        # Validate
        data = self._validate_returns(data, "data")
        self._check_data_length(data, min_length=3)

        if len(data) > 5000:
            warnings.warn(
                "Shapiro-Wilk test may be unreliable for large samples (>5000). "
                "Consider using Kolmogorov-Smirnov test instead."
            )

        # Perform Shapiro-Wilk test
        w_stat, p_value = stats.shapiro(data)

        # Determine normality
        alpha = 0.05
        is_normal = p_value > alpha

        return self._create_result_dict(
            value={
                'w_statistic': round(float(w_stat), self.precision),
                'p_value': round(float(p_value), self.precision)
            },
            method='shapiro_test',
            parameters={
                'data_length': len(data)
            },
            metadata={
                'is_normal': is_normal,
                'alpha': alpha,
                'conclusion': 'normal' if is_normal else 'non_normal',
                'recommendation': self._get_normality_recommendation(is_normal)
            }
        )

    @validate_inputs
    @timing_decorator
    @handle_calculation_error
    def calculate_confidence_interval(
        self,
        data: Union[List, np.ndarray, pd.Series],
        confidence_level: float = 0.95,
        method: Literal['t', 'bootstrap'] = 't'
    ) -> Dict:
        """
        Calculate confidence interval for the mean.

        Args:
            data: Sample data
            confidence_level: Confidence level (0-1)
            method: 't' for t-distribution, 'bootstrap' for bootstrap

        Returns:
            Result dict with confidence interval
        """
        # Validate
        data = self._validate_returns(data, "data")
        self._check_data_length(data, min_length=3)
        confidence_level = self._validate_probability(confidence_level, "confidence_level")

        n = len(data)
        mean = np.mean(data)
        std = np.std(data, ddof=1)
        se = std / np.sqrt(n)

        if method == 't':
            # t-distribution method
            alpha = 1 - confidence_level
            t_critical = stats.t.ppf(1 - alpha / 2, df=n - 1)
            margin_of_error = t_critical * se
            ci_lower = mean - margin_of_error
            ci_upper = mean + margin_of_error

        elif method == 'bootstrap':
            # Bootstrap method
            result = self.bootstrap_resample(
                data,
                statistic='mean',
                confidence_level=confidence_level
            )
            ci_lower, ci_upper = result['value']['confidence_interval']
            margin_of_error = (ci_upper - ci_lower) / 2

        else:
            raise DataValidationError(
                f"Invalid method: {method}",
                "method"
            )

        return self._create_result_dict(
            value={
                'mean': round(mean, self.precision),
                'confidence_interval': [
                    round(ci_lower, self.precision),
                    round(ci_upper, self.precision)
                ],
                'margin_of_error': round(margin_of_error, self.precision)
            },
            method='calculate_confidence_interval',
            parameters={
                'data_length': n,
                'confidence_level': confidence_level,
                'method': method
            },
            metadata={
                'standard_error': round(se, self.precision),
                'standard_deviation': round(std, self.precision),
                'interval_width': round(ci_upper - ci_lower, self.precision)
            }
        )

    # Helper methods

    def _get_statistic_function(self, statistic: str):
        """Get statistic function by name."""
        if statistic == 'mean':
            return np.mean
        elif statistic == 'median':
            return np.median
        elif statistic == 'std':
            return lambda x: np.std(x, ddof=1)
        elif statistic == 'sharpe':
            return lambda x: np.mean(x) / np.std(x, ddof=1) if np.std(x, ddof=1) > 0 else 0
        else:
            raise DataValidationError(
                f"Unknown statistic: {statistic}",
                "statistic"
            )

    def _interpret_effect_size(self, effect_size: float) -> str:
        """Interpret Cohen's d effect size."""
        abs_effect = abs(effect_size)
        if abs_effect < 0.2:
            return 'negligible'
        elif abs_effect < 0.5:
            return 'small'
        elif abs_effect < 0.8:
            return 'medium'
        else:
            return 'large'

    def _get_normality_recommendation(self, is_normal: bool) -> str:
        """Get recommendation based on normality test."""
        if is_normal:
            return "Data appears normally distributed. Parametric tests (t-test) are appropriate."
        else:
            return "Data may not be normally distributed. Consider non-parametric tests (Mann-Whitney, Wilcoxon)."

    @validate_inputs
    @timing_decorator
    @handle_calculation_error
    def wilcoxon_test(
        self,
        sample1: Union[List, np.ndarray, pd.Series],
        sample2: Union[List, np.ndarray, pd.Series],
        alternative: Literal['two-sided', 'less', 'greater'] = 'two-sided'
    ) -> Dict:
        """
        Perform Wilcoxon signed-rank test (paired non-parametric test).

        Args:
            sample1: First sample (before)
            sample2: Second sample (after)
            alternative: Alternative hypothesis

        Returns:
            Result dict with test statistic and p-value
        """
        # Validate
        sample1 = self._validate_returns(sample1, "sample1")
        sample2 = self._validate_returns(sample2, "sample2")

        if len(sample1) != len(sample2):
            raise DataValidationError(
                f"Samples must have same length: {len(sample1)} vs {len(sample2)}",
                "sample_length"
            )

        self._check_data_length(sample1, min_length=3)

        # Perform Wilcoxon signed-rank test
        statistic, p_value = stats.wilcoxon(
            sample1, sample2,
            alternative=alternative
        )

        # Calculate differences
        differences = np.array(sample2) - np.array(sample1)
        median_diff = np.median(differences)

        # Determine significance
        alpha = 0.05
        is_significant = p_value < alpha

        # Effect size (r = Z / sqrt(N))
        n = len(sample1)
        z_score = stats.norm.ppf(1 - p_value / 2) if alternative == 'two-sided' else stats.norm.ppf(1 - p_value)
        effect_size = abs(z_score) / np.sqrt(n)

        return self._create_result_dict(
            value={
                'statistic': round(float(statistic), self.precision),
                'p_value': round(float(p_value), self.precision)
            },
            method='wilcoxon_test',
            parameters={
                'n_pairs': n,
                'alternative': alternative
            },
            metadata={
                'is_significant': is_significant,
                'alpha': alpha,
                'median_difference': round(median_diff, self.precision),
                'effect_size': round(effect_size, 4),
                'test_type': 'non_parametric_paired'
            }
        )

    @validate_inputs
    @timing_decorator
    @handle_calculation_error
    def ks_test(
        self,
        data: Union[List, np.ndarray, pd.Series],
        distribution: Literal['norm', 'uniform', 'expon'] = 'norm'
    ) -> Dict:
        """
        Perform Kolmogorov-Smirnov test for goodness of fit.

        Args:
            data: Sample data
            distribution: Distribution to test against ('norm', 'uniform', 'expon')

        Returns:
            Result dict with test statistic and p-value
        """
        # Validate
        data = self._validate_returns(data, "data")
        self._check_data_length(data, min_length=3)

        # Perform KS test
        if distribution == 'norm':
            # Test against normal distribution with sample mean and std
            statistic, p_value = stats.kstest(
                data,
                'norm',
                args=(np.mean(data), np.std(data, ddof=1))
            )
        elif distribution == 'uniform':
            statistic, p_value = stats.kstest(data, 'uniform')
        elif distribution == 'expon':
            statistic, p_value = stats.kstest(data, 'expon')
        else:
            raise DataValidationError(
                f"Unknown distribution: {distribution}",
                "distribution"
            )

        # Determine goodness of fit
        alpha = 0.05
        is_good_fit = p_value > alpha

        return self._create_result_dict(
            value={
                'ks_statistic': round(float(statistic), self.precision),
                'p_value': round(float(p_value), self.precision)
            },
            method='ks_test',
            parameters={
                'data_length': len(data),
                'distribution': distribution
            },
            metadata={
                'is_good_fit': is_good_fit,
                'alpha': alpha,
                'conclusion': 'good_fit' if is_good_fit else 'poor_fit',
                'recommendation': f"Data {'fits' if is_good_fit else 'does not fit'} {distribution} distribution"
            }
        )

    @validate_inputs
    @timing_decorator
    @handle_calculation_error
    def chi_square_test(
        self,
        observed: Union[List, np.ndarray, pd.Series],
        expected: Optional[Union[List, np.ndarray, pd.Series]] = None
    ) -> Dict:
        """
        Perform chi-square goodness of fit test.

        Args:
            observed: Observed frequencies
            expected: Expected frequencies (None for uniform distribution)

        Returns:
            Result dict with chi-square statistic and p-value
        """
        # Validate
        observed = np.array(observed)

        if len(observed) < 2:
            raise DataValidationError(
                "Need at least 2 categories",
                "observed"
            )

        if np.any(observed < 0):
            raise DataValidationError(
                "Observed frequencies must be non-negative",
                "observed"
            )

        # Set expected frequencies
        if expected is None:
            # Uniform distribution
            expected = np.ones_like(observed) * np.sum(observed) / len(observed)
        else:
            expected = np.array(expected)
            if len(expected) != len(observed):
                raise DataValidationError(
                    f"Expected and observed must have same length: {len(expected)} vs {len(observed)}",
                    "expected"
                )

        # Perform chi-square test
        chi2_stat, p_value = stats.chisquare(observed, expected)

        # Degrees of freedom
        df = len(observed) - 1

        # Determine significance
        alpha = 0.05
        is_significant = p_value < alpha

        return self._create_result_dict(
            value={
                'chi_square_statistic': round(float(chi2_stat), self.precision),
                'p_value': round(float(p_value), self.precision),
                'degrees_of_freedom': int(df)
            },
            method='chi_square_test',
            parameters={
                'n_categories': len(observed),
                'total_observations': int(np.sum(observed))
            },
            metadata={
                'is_significant': is_significant,
                'alpha': alpha,
                'conclusion': 'reject_null' if is_significant else 'fail_to_reject',
                'observed': observed.tolist(),
                'expected': expected.tolist()
            }
        )

    @validate_inputs
    @timing_decorator
    @handle_calculation_error
    def f_test(
        self,
        sample1: Union[List, np.ndarray, pd.Series],
        sample2: Union[List, np.ndarray, pd.Series]
    ) -> Dict:
        """
        Perform F-test for equality of variances.

        Args:
            sample1: First sample
            sample2: Second sample

        Returns:
            Result dict with F-statistic and p-value
        """
        # Validate
        sample1 = self._validate_returns(sample1, "sample1")
        sample2 = self._validate_returns(sample2, "sample2")
        self._check_data_length(sample1, min_length=3)
        self._check_data_length(sample2, min_length=3)

        # Calculate variances
        var1 = np.var(sample1, ddof=1)
        var2 = np.var(sample2, ddof=1)

        # F-statistic (larger variance / smaller variance)
        if var1 >= var2:
            f_stat = var1 / var2
            df1 = len(sample1) - 1
            df2 = len(sample2) - 1
        else:
            f_stat = var2 / var1
            df1 = len(sample2) - 1
            df2 = len(sample1) - 1

        # Calculate p-value (two-tailed)
        p_value = 2 * min(
            stats.f.cdf(f_stat, df1, df2),
            1 - stats.f.cdf(f_stat, df1, df2)
        )

        # Determine significance
        alpha = 0.05
        is_significant = p_value < alpha

        return self._create_result_dict(
            value={
                'f_statistic': round(float(f_stat), self.precision),
                'p_value': round(float(p_value), self.precision),
                'df1': int(df1),
                'df2': int(df2)
            },
            method='f_test',
            parameters={
                'sample1_size': len(sample1),
                'sample2_size': len(sample2)
            },
            metadata={
                'is_significant': is_significant,
                'alpha': alpha,
                'sample1_variance': round(var1, self.precision),
                'sample2_variance': round(var2, self.precision),
                'variance_ratio': round(max(var1, var2) / min(var1, var2), self.precision),
                'conclusion': 'unequal_variances' if is_significant else 'equal_variances'
            }
        )

    @validate_inputs
    @timing_decorator
    @handle_calculation_error
    def kruskal_wallis_test(
        self,
        *samples: Union[List, np.ndarray, pd.Series]
    ) -> Dict:
        """
        Perform Kruskal-Wallis H-test (non-parametric one-way ANOVA).

        Args:
            *samples: Multiple samples to compare

        Returns:
            Result dict with H-statistic and p-value
        """
        if len(samples) < 2:
            raise DataValidationError(
                "Need at least 2 samples",
                "samples"
            )

        # Validate all samples
        validated_samples = []
        for i, sample in enumerate(samples):
            validated = self._validate_returns(sample, f"sample{i+1}")
            self._check_data_length(validated, min_length=3)
            validated_samples.append(validated)

        # Perform Kruskal-Wallis test
        h_stat, p_value = stats.kruskal(*validated_samples)

        # Degrees of freedom
        df = len(samples) - 1

        # Determine significance
        alpha = 0.05
        is_significant = p_value < alpha

        # Calculate medians
        medians = [np.median(s) for s in validated_samples]

        return self._create_result_dict(
            value={
                'h_statistic': round(float(h_stat), self.precision),
                'p_value': round(float(p_value), self.precision),
                'degrees_of_freedom': int(df)
            },
            method='kruskal_wallis_test',
            parameters={
                'n_groups': len(samples),
                'group_sizes': [len(s) for s in validated_samples]
            },
            metadata={
                'is_significant': is_significant,
                'alpha': alpha,
                'group_medians': [round(m, self.precision) for m in medians],
                'test_type': 'non_parametric_anova',
                'conclusion': 'groups_differ' if is_significant else 'groups_similar'
            }
        )

    @validate_inputs
    @timing_decorator
    @handle_calculation_error
    def bonferroni_correction(
        self,
        p_values: Union[List, np.ndarray],
        alpha: float = 0.05
    ) -> Dict:
        """
        Apply Bonferroni correction for multiple comparisons.

        Args:
            p_values: List of p-values from multiple tests
            alpha: Family-wise error rate

        Returns:
            Result dict with corrected alpha and significance decisions
        """
        p_values = np.array(p_values)

        if len(p_values) < 1:
            raise DataValidationError(
                "Need at least 1 p-value",
                "p_values"
            )

        if np.any((p_values < 0) | (p_values > 1)):
            raise DataValidationError(
                "P-values must be between 0 and 1",
                "p_values"
            )

        alpha = self._validate_probability(alpha, "alpha")

        # Bonferroni correction
        n_tests = len(p_values)
        corrected_alpha = alpha / n_tests

        # Determine significance
        is_significant = p_values < corrected_alpha
        n_significant = np.sum(is_significant)

        return self._create_result_dict(
            value={
                'corrected_alpha': round(corrected_alpha, 6),
                'n_significant': int(n_significant),
                'significant_indices': np.where(is_significant)[0].tolist()
            },
            method='bonferroni_correction',
            parameters={
                'n_tests': n_tests,
                'original_alpha': alpha
            },
            metadata={
                'p_values': [round(p, 6) for p in p_values],
                'is_significant': is_significant.tolist(),
                'correction_factor': n_tests,
                'recommendation': f"Use α = {corrected_alpha:.6f} for each test to maintain family-wise error rate of {alpha}"
            }
        )
