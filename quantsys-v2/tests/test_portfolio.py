"""
Portfolio Optimization Test Suite (adapted for quantlib API)

Tests:
- Markowitz Min Variance/Max Sharpe/Target Return
- Risk Parity
- Black-Litterman
- Efficient Frontier
"""
import pytest
import numpy as np
import pandas as pd

from domain.quantlib.portfolio import (
    MarkowitzOptimizer,
    RiskParityOptimizer,
    BlackLittermanOptimizer,
    EfficientFrontierCalculator,
)
from domain.quantlib.exceptions import (
    DataValidationError,
    InsufficientDataError,
    ConvergenceError
)


@pytest.fixture
def expected_returns():
    return np.array([0.001, 0.0008, 0.0012, 0.0009])


@pytest.fixture
def cov_matrix():
    return np.array([
        [0.0004, 0.0001, 0.0002, 0.0001],
        [0.0001, 0.0003, 0.0001, 0.0001],
        [0.0002, 0.0001, 0.0005, 0.0002],
        [0.0001, 0.0001, 0.0002, 0.0003]
    ])


@pytest.fixture
def market_caps():
    return np.array([100.0, 80.0, 60.0, 40.0])


class TestMarkowitzMinVariance:

    def test_basic_optimization(self, expected_returns, cov_matrix):
        optimizer = MarkowitzOptimizer()
        result = optimizer.calculate(expected_returns, cov_matrix, objective='min_variance')

        assert 'value' in result
        weights = result['value']['weights']
        assert len(weights) == 4
        assert np.isclose(np.sum(weights), 1.0, atol=1e-6)
        assert np.all(weights >= -1e-6)

    def test_allow_short(self, expected_returns, cov_matrix):
        optimizer = MarkowitzOptimizer()
        result = optimizer.calculate(expected_returns, cov_matrix, objective='min_variance', allow_short=True)
        weights = result['value']['weights']
        assert np.isclose(np.sum(weights), 1.0, atol=1e-6)

    def test_weight_bounds(self, expected_returns, cov_matrix):
        optimizer = MarkowitzOptimizer()
        result = optimizer.calculate(
            expected_returns, cov_matrix,
            objective='min_variance',
            lower_bound=0.1, upper_bound=0.4
        )
        weights = result['value']['weights']
        assert np.all(weights >= 0.1 - 1e-6)
        assert np.all(weights <= 0.4 + 1e-6)

    def test_insufficient_assets(self):
        optimizer = MarkowitzOptimizer()
        with pytest.raises(DataValidationError):
            optimizer.calculate(np.array([0.001]), np.array([[0.0004]]))

    def test_mismatched_dimensions(self, expected_returns):
        optimizer = MarkowitzOptimizer()
        bad_cov = np.eye(3)
        with pytest.raises(DataValidationError):
            optimizer.calculate(expected_returns, bad_cov)


class TestMarkowitzMaxSharpe:

    def test_basic_optimization(self, expected_returns, cov_matrix):
        optimizer = MarkowitzOptimizer(risk_free_rate=0.0002)
        result = optimizer.calculate(expected_returns, cov_matrix, objective='max_sharpe')
        weights = result['value']['weights']
        assert len(weights) == 4
        assert np.isclose(np.sum(weights), 1.0, atol=1e-6)

    def test_sharpe_positive(self, expected_returns, cov_matrix):
        optimizer = MarkowitzOptimizer(risk_free_rate=0.0002)
        result = optimizer.calculate(expected_returns, cov_matrix, objective='max_sharpe')
        assert result['value']['sharpe_ratio'] > 0

    def test_returns_structure(self, expected_returns, cov_matrix):
        optimizer = MarkowitzOptimizer()
        result = optimizer.calculate(expected_returns, cov_matrix, objective='max_sharpe')
        assert 'weights' in result['value']
        assert 'expected_return' in result['value']
        assert 'risk' in result['value']


class TestMarkowitzTargetReturn:

    def test_basic_optimization(self, expected_returns, cov_matrix):
        optimizer = MarkowitzOptimizer()
        result = optimizer.calculate(
            expected_returns, cov_matrix,
            objective='target_return', target_return=0.001
        )
        weights = result['value']['weights']
        assert len(weights) == 4
        assert np.isclose(np.sum(weights), 1.0, atol=1e-6)

    def test_missing_target_return(self, expected_returns, cov_matrix):
        optimizer = MarkowitzOptimizer()
        with pytest.raises((DataValidationError, Exception)):
            optimizer.calculate(expected_returns, cov_matrix, objective='target_return')


class TestRiskParityOptimizer:

    def test_basic_optimization(self, cov_matrix):
        optimizer = RiskParityOptimizer()
        result = optimizer.calculate(cov_matrix)
        assert 'value' in result


class TestBlackLittermanOptimizer:

    def test_basic_optimization(self, cov_matrix, market_caps):
        optimizer = BlackLittermanOptimizer()
        market_weights = market_caps / market_caps.sum()
        result = optimizer.calculate(market_weights, cov_matrix)
        assert 'value' in result


class TestEfficientFrontier:

    def test_basic_calculation(self, expected_returns, cov_matrix):
        calc = EfficientFrontierCalculator()
        result = calc.calculate(expected_returns, cov_matrix)
        assert 'value' in result


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
