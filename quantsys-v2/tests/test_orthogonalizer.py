"""
Tests for FactorOrthogonalizer - factor orthogonalization methods
"""

import numpy as np
import pandas as pd
import pytest
from unittest.mock import patch, MagicMock

from domain.quantlib.factor_analysis.orthogonalizer import FactorOrthogonalizer


@pytest.fixture
def sample_factor_data():
    """Create sample factor data with some correlation"""
    np.random.seed(42)
    n_samples = 200

    # Create correlated factors
    base = np.random.randn(n_samples, 3)
    factors = np.column_stack([
        base,
        base[:, 0:1] + np.random.randn(n_samples, 1) * 0.3,  # Correlated with factor 1
        base[:, 1:2] + np.random.randn(n_samples, 1) * 0.3,  # Correlated with factor 2
        np.random.randn(n_samples, 3)  # Independent factors
    ])

    factor_names = [f'factor_{i+1}' for i in range(8)]
    return pd.DataFrame(factors, columns=factor_names)


@pytest.fixture
def highly_correlated_data():
    """Create factor data with high correlation"""
    np.random.seed(100)
    n_samples = 150

    base = np.random.randn(n_samples, 1)
    factors = np.column_stack([
        base,
        base + np.random.randn(n_samples, 1) * 0.1,  # Very high correlation
        base + np.random.randn(n_samples, 1) * 0.1,
        np.random.randn(n_samples, 2)
    ])

    factor_names = [f'factor_{i+1}' for i in range(5)]
    return pd.DataFrame(factors, columns=factor_names)


@pytest.fixture
def orthogonal_data():
    """Create already orthogonal factor data"""
    np.random.seed(200)
    n_samples = 100

    # Independent factors
    factors = np.random.randn(n_samples, 5)
    factor_names = [f'factor_{i+1}' for i in range(5)]
    return pd.DataFrame(factors, columns=factor_names)


class TestFactorOrthogonalizer:
    """Test suite for FactorOrthogonalizer"""

    def test_initialization(self):
        """Test FactorOrthogonalizer initialization"""
        orthogonalizer = FactorOrthogonalizer()
        assert orthogonalizer.correlation_matrix is None
        assert orthogonalizer.orthogonal_factors is None

    def test_calculate_correlation_matrix(self, sample_factor_data):
        """Test correlation matrix calculation"""
        orthogonalizer = FactorOrthogonalizer()

        corr_matrix = orthogonalizer.calculate_correlation_matrix(sample_factor_data)

        assert isinstance(corr_matrix, pd.DataFrame)
        assert corr_matrix.shape == (8, 8)
        assert np.allclose(np.diag(corr_matrix), 1.0)  # Diagonal should be 1
        assert orthogonalizer.correlation_matrix is not None

    def test_correlation_matrix_symmetry(self, sample_factor_data):
        """Test correlation matrix is symmetric"""
        orthogonalizer = FactorOrthogonalizer()

        corr_matrix = orthogonalizer.calculate_correlation_matrix(sample_factor_data)

        assert np.allclose(corr_matrix, corr_matrix.T)

    def test_correlation_matrix_values(self, sample_factor_data):
        """Test correlation matrix values are in valid range"""
        orthogonalizer = FactorOrthogonalizer()

        corr_matrix = orthogonalizer.calculate_correlation_matrix(sample_factor_data)

        assert (corr_matrix >= -1).all().all()
        assert (corr_matrix <= 1).all().all()

    def test_find_highly_correlated_pairs(self, highly_correlated_data):
        """Test finding highly correlated factor pairs"""
        orthogonalizer = FactorOrthogonalizer()

        orthogonalizer.calculate_correlation_matrix(highly_correlated_data)
        pairs = orthogonalizer.find_highly_correlated_pairs(threshold=0.8)

        assert isinstance(pairs, list)
        assert len(pairs) > 0

        for pair in pairs:
            assert 'factor1' in pair
            assert 'factor2' in pair
            assert 'correlation' in pair
            assert abs(pair['correlation']) > 0.8

    def test_find_highly_correlated_pairs_no_correlation(self, orthogonal_data):
        """Test finding pairs with orthogonal data"""
        orthogonalizer = FactorOrthogonalizer()

        orthogonalizer.calculate_correlation_matrix(orthogonal_data)
        pairs = orthogonalizer.find_highly_correlated_pairs(threshold=0.8)

        assert len(pairs) == 0

    def test_find_highly_correlated_pairs_no_matrix(self):
        """Test finding pairs without correlation matrix"""
        orthogonalizer = FactorOrthogonalizer()

        with pytest.raises(ValueError, match="Correlation matrix not calculated"):
            orthogonalizer.find_highly_correlated_pairs()

    @pytest.mark.parametrize("threshold", [0.5, 0.7, 0.9])
    def test_find_highly_correlated_pairs_thresholds(self, highly_correlated_data, threshold):
        """Test different correlation thresholds"""
        orthogonalizer = FactorOrthogonalizer()

        orthogonalizer.calculate_correlation_matrix(highly_correlated_data)
        pairs = orthogonalizer.find_highly_correlated_pairs(threshold=threshold)

        for pair in pairs:
            assert abs(pair['correlation']) > threshold

    def test_schmidt_orthogonalization(self, sample_factor_data):
        """Test Schmidt orthogonalization"""
        orthogonalizer = FactorOrthogonalizer()

        base_factors = ['factor_1', 'factor_2', 'factor_3']
        orthogonal = orthogonalizer.schmidt_orthogonalization(
            sample_factor_data,
            base_factors
        )

        assert isinstance(orthogonal, pd.DataFrame)
        assert orthogonal.shape == sample_factor_data.shape
        assert list(orthogonal.columns) == list(sample_factor_data.columns)
        assert orthogonalizer.orthogonal_factors is not None

    def test_schmidt_orthogonalization_base_factors_unchanged(self, sample_factor_data):
        """Test base factors remain unchanged in Schmidt orthogonalization"""
        orthogonalizer = FactorOrthogonalizer()

        base_factors = ['factor_1', 'factor_2']
        orthogonal = orthogonalizer.schmidt_orthogonalization(
            sample_factor_data,
            base_factors
        )

        # Base factors should be unchanged
        for factor in base_factors:
            pd.testing.assert_series_equal(
                orthogonal[factor],
                sample_factor_data[factor]
            )

    def test_schmidt_orthogonalization_reduces_correlation(self, sample_factor_data):
        """Test Schmidt orthogonalization reduces correlation"""
        orthogonalizer = FactorOrthogonalizer()

        base_factors = ['factor_1', 'factor_2', 'factor_3']
        orthogonal = orthogonalizer.schmidt_orthogonalization(
            sample_factor_data,
            base_factors
        )

        # Calculate correlations
        original_corr = sample_factor_data.corr()
        orthogonal_corr = orthogonal.corr()

        # Check correlation between base and other factors is reduced
        for base in base_factors:
            for other in sample_factor_data.columns:
                if other not in base_factors:
                    assert abs(orthogonal_corr.loc[base, other]) <= abs(original_corr.loc[base, other]) + 0.1

    def test_schmidt_orthogonalization_with_nan(self):
        """Test Schmidt orthogonalization handles NaN values"""
        orthogonalizer = FactorOrthogonalizer()

        np.random.seed(42)
        data = pd.DataFrame(np.random.randn(100, 5), columns=[f'f{i}' for i in range(5)])
        data.iloc[10:20, 2] = np.nan

        base_factors = ['f0', 'f1']
        orthogonal = orthogonalizer.schmidt_orthogonalization(data, base_factors)

        assert isinstance(orthogonal, pd.DataFrame)

    def test_schmidt_orthogonalization_insufficient_samples(self):
        """Test Schmidt orthogonalization with insufficient samples"""
        orthogonalizer = FactorOrthogonalizer()

        # Very small dataset
        data = pd.DataFrame(np.random.randn(5, 3), columns=['f1', 'f2', 'f3'])

        base_factors = ['f1']
        orthogonal = orthogonalizer.schmidt_orthogonalization(data, base_factors)

        # Should complete but may not orthogonalize well
        assert isinstance(orthogonal, pd.DataFrame)

    def test_pca_orthogonalization(self, sample_factor_data):
        """Test PCA orthogonalization"""
        orthogonalizer = FactorOrthogonalizer()

        pc_df, variance_ratio = orthogonalizer.pca_orthogonalization(
            sample_factor_data,
            n_components=5
        )

        assert isinstance(pc_df, pd.DataFrame)
        assert pc_df.shape[1] == 5
        assert len(variance_ratio) == 5
        assert np.sum(variance_ratio) <= 1.0
        assert orthogonalizer.orthogonal_factors is not None

    def test_pca_orthogonalization_auto_components(self, sample_factor_data):
        """Test PCA with automatic component selection"""
        orthogonalizer = FactorOrthogonalizer()

        pc_df, variance_ratio = orthogonalizer.pca_orthogonalization(
            sample_factor_data,
            n_components=None,
            variance_threshold=0.95
        )

        assert isinstance(pc_df, pd.DataFrame)
        assert np.sum(variance_ratio) >= 0.95

    def test_pca_orthogonalization_components_orthogonal(self, sample_factor_data):
        """Test PCA components are orthogonal"""
        orthogonalizer = FactorOrthogonalizer()

        pc_df, _ = orthogonalizer.pca_orthogonalization(
            sample_factor_data,
            n_components=5
        )

        # Check orthogonality
        corr_matrix = pc_df.corr()
        off_diagonal = corr_matrix.values[~np.eye(5, dtype=bool)]

        assert np.allclose(off_diagonal, 0, atol=1e-10)

    def test_pca_orthogonalization_variance_explained(self, sample_factor_data):
        """Test PCA variance explained is reasonable"""
        orthogonalizer = FactorOrthogonalizer()

        _, variance_ratio = orthogonalizer.pca_orthogonalization(
            sample_factor_data,
            n_components=3
        )

        # Variance should be positive and sum <= 1
        assert all(v > 0 for v in variance_ratio)
        assert np.sum(variance_ratio) <= 1.0

    def test_pca_orthogonalization_column_names(self, sample_factor_data):
        """Test PCA component column names"""
        orthogonalizer = FactorOrthogonalizer()

        pc_df, _ = orthogonalizer.pca_orthogonalization(
            sample_factor_data,
            n_components=4
        )

        expected_names = ['PC1', 'PC2', 'PC3', 'PC4']
        assert list(pc_df.columns) == expected_names

    def test_symmetric_orthogonalization(self, sample_factor_data):
        """Test symmetric orthogonalization"""
        orthogonalizer = FactorOrthogonalizer()

        orthogonal = orthogonalizer.symmetric_orthogonalization(sample_factor_data)

        assert isinstance(orthogonal, pd.DataFrame)
        assert orthogonal.shape == sample_factor_data.shape
        assert list(orthogonal.columns) == list(sample_factor_data.columns)
        assert orthogonalizer.orthogonal_factors is not None

    def test_symmetric_orthogonalization_orthogonality(self, sample_factor_data):
        """Test symmetric orthogonalization produces orthogonal factors"""
        orthogonalizer = FactorOrthogonalizer()

        orthogonal = orthogonalizer.symmetric_orthogonalization(sample_factor_data)

        # Check orthogonality: Q^T Q = I
        Q = orthogonal.values
        product = Q.T @ Q
        identity = np.eye(Q.shape[1])

        assert np.allclose(product, identity, atol=1e-10)

    def test_symmetric_orthogonalization_with_nan(self):
        """Test symmetric orthogonalization handles NaN"""
        orthogonalizer = FactorOrthogonalizer()

        np.random.seed(42)
        data = pd.DataFrame(np.random.randn(100, 5), columns=[f'f{i}' for i in range(5)])
        data.iloc[10:20, 2] = np.nan

        # Should drop NaN rows
        orthogonal = orthogonalizer.symmetric_orthogonalization(data)

        assert isinstance(orthogonal, pd.DataFrame)
        assert not orthogonal.isnull().any().any()

    def test_compare_before_after(self, sample_factor_data):
        """Test comparison of correlation before and after orthogonalization"""
        orthogonalizer = FactorOrthogonalizer()

        base_factors = ['factor_1', 'factor_2']
        orthogonal = orthogonalizer.schmidt_orthogonalization(
            sample_factor_data,
            base_factors
        )

        stats = orthogonalizer.compare_before_after(sample_factor_data, orthogonal)

        assert isinstance(stats, dict)
        assert 'original' in stats
        assert 'orthogonal' in stats

        for key in ['mean_abs_corr', 'max_abs_corr', 'high_corr_count']:
            assert key in stats['original']
            assert key in stats['orthogonal']

    def test_compare_before_after_correlation_reduction(self, highly_correlated_data):
        """Test correlation is reduced after orthogonalization"""
        orthogonalizer = FactorOrthogonalizer()

        base_factors = ['factor_1']
        orthogonal = orthogonalizer.schmidt_orthogonalization(
            highly_correlated_data,
            base_factors
        )

        stats = orthogonalizer.compare_before_after(highly_correlated_data, orthogonal)

        # Mean correlation should be reduced
        assert stats['orthogonal']['mean_abs_corr'] <= stats['original']['mean_abs_corr']

    def test_compare_before_after_high_corr_count(self, highly_correlated_data):
        """Test high correlation count is reduced"""
        orthogonalizer = FactorOrthogonalizer()

        base_factors = ['factor_1']
        orthogonal = orthogonalizer.schmidt_orthogonalization(
            highly_correlated_data,
            base_factors
        )

        stats = orthogonalizer.compare_before_after(highly_correlated_data, orthogonal)

        # High correlation count should be reduced
        assert stats['orthogonal']['high_corr_count'] <= stats['original']['high_corr_count']

    @patch('matplotlib.pyplot.savefig')
    @patch('matplotlib.pyplot.show')
    def test_plot_correlation_heatmap(self, mock_show, mock_savefig, sample_factor_data):
        """Test correlation heatmap plotting"""
        orthogonalizer = FactorOrthogonalizer()

        orthogonalizer.calculate_correlation_matrix(sample_factor_data)

        # Test show
        orthogonalizer.plot_correlation_heatmap()
        mock_show.assert_called_once()

        # Test save
        orthogonalizer.plot_correlation_heatmap(save_path='/tmp/test_corr.png')
        mock_savefig.assert_called_once_with('/tmp/test_corr.png')

    @patch('matplotlib.pyplot.show')
    def test_plot_correlation_heatmap_with_data(self, mock_show, sample_factor_data):
        """Test plotting with provided data"""
        orthogonalizer = FactorOrthogonalizer()

        orthogonalizer.plot_correlation_heatmap(factor_data=sample_factor_data)
        mock_show.assert_called_once()

    @patch('matplotlib.pyplot.show')
    def test_plot_correlation_heatmap_no_data(self, mock_show):
        """Test plotting raises error without data"""
        orthogonalizer = FactorOrthogonalizer()

        with pytest.raises(ValueError, match="No correlation matrix available"):
            orthogonalizer.plot_correlation_heatmap()

    def test_orthogonal_factors_persistence_schmidt(self, sample_factor_data):
        """Test orthogonal factors are stored after Schmidt"""
        orthogonalizer = FactorOrthogonalizer()

        base_factors = ['factor_1']
        orthogonal = orthogonalizer.schmidt_orthogonalization(
            sample_factor_data,
            base_factors
        )

        assert orthogonalizer.orthogonal_factors is not None
        pd.testing.assert_frame_equal(orthogonalizer.orthogonal_factors, orthogonal)

    def test_orthogonal_factors_persistence_pca(self, sample_factor_data):
        """Test orthogonal factors are stored after PCA"""
        orthogonalizer = FactorOrthogonalizer()

        pc_df, _ = orthogonalizer.pca_orthogonalization(sample_factor_data, n_components=3)

        assert orthogonalizer.orthogonal_factors is not None
        pd.testing.assert_frame_equal(orthogonalizer.orthogonal_factors, pc_df)

    def test_orthogonal_factors_persistence_symmetric(self, sample_factor_data):
        """Test orthogonal factors are stored after symmetric"""
        orthogonalizer = FactorOrthogonalizer()

        orthogonal = orthogonalizer.symmetric_orthogonalization(sample_factor_data)

        assert orthogonalizer.orthogonal_factors is not None
        pd.testing.assert_frame_equal(orthogonalizer.orthogonal_factors, orthogonal)

    def test_empty_factor_data(self):
        """Test handling of empty factor data"""
        orthogonalizer = FactorOrthogonalizer()

        empty_df = pd.DataFrame()

        # Empty dataframe should return empty correlation matrix
        corr_matrix = orthogonalizer.calculate_correlation_matrix(empty_df)
        assert corr_matrix.empty

    def test_single_factor(self):
        """Test handling of single factor"""
        orthogonalizer = FactorOrthogonalizer()

        data = pd.DataFrame({'factor_1': np.random.randn(100)})

        corr_matrix = orthogonalizer.calculate_correlation_matrix(data)

        assert corr_matrix.shape == (1, 1)
        assert corr_matrix.iloc[0, 0] == 1.0

    def test_all_nan_factor(self):
        """Test handling of all NaN factor"""
        orthogonalizer = FactorOrthogonalizer()

        data = pd.DataFrame({
            'factor_1': np.random.randn(100),
            'factor_2': [np.nan] * 100
        })

        corr_matrix = orthogonalizer.calculate_correlation_matrix(data)

        # Should handle NaN gracefully
        assert isinstance(corr_matrix, pd.DataFrame)

    def test_constant_factor(self):
        """Test handling of constant factor"""
        orthogonalizer = FactorOrthogonalizer()

        data = pd.DataFrame({
            'factor_1': np.random.randn(100),
            'factor_2': [1.0] * 100  # Constant
        })

        # Should handle constant factor (std=0)
        corr_matrix = orthogonalizer.calculate_correlation_matrix(data)
        assert isinstance(corr_matrix, pd.DataFrame)

    def test_pca_more_components_than_features(self, sample_factor_data):
        """Test PCA with more components than features"""
        orthogonalizer = FactorOrthogonalizer()

        n_features = sample_factor_data.shape[1]

        # Request more components than features
        pc_df, variance_ratio = orthogonalizer.pca_orthogonalization(
            sample_factor_data,
            n_components=n_features + 5
        )

        # Should cap at number of features
        assert pc_df.shape[1] <= n_features

    def test_schmidt_empty_base_factors(self, sample_factor_data):
        """Test Schmidt orthogonalization with empty base factors"""
        orthogonalizer = FactorOrthogonalizer()

        orthogonal = orthogonalizer.schmidt_orthogonalization(
            sample_factor_data,
            base_factors=[]
        )

        # All factors should remain unchanged
        pd.testing.assert_frame_equal(orthogonal, sample_factor_data)

    def test_schmidt_all_base_factors(self, sample_factor_data):
        """Test Schmidt orthogonalization with all factors as base"""
        orthogonalizer = FactorOrthogonalizer()

        all_factors = list(sample_factor_data.columns)
        orthogonal = orthogonalizer.schmidt_orthogonalization(
            sample_factor_data,
            base_factors=all_factors
        )

        # All factors should remain unchanged
        pd.testing.assert_frame_equal(orthogonal, sample_factor_data)

    def test_pca_variance_threshold_edge_cases(self, sample_factor_data):
        """Test PCA with edge case variance thresholds"""
        orthogonalizer = FactorOrthogonalizer()

        # Very low threshold
        pc_df_low, _ = orthogonalizer.pca_orthogonalization(
            sample_factor_data,
            variance_threshold=0.5
        )

        # Very high threshold
        pc_df_high, _ = orthogonalizer.pca_orthogonalization(
            sample_factor_data,
            variance_threshold=0.99
        )

        # High threshold should require more components
        assert pc_df_high.shape[1] >= pc_df_low.shape[1]
