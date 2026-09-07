"""Tests for StrategyValidationService"""
import pytest
from unittest.mock import Mock, patch
from application.services.strategy_validation_service import StrategyValidationService


@pytest.fixture
def validation_service():
    return StrategyValidationService()


def test_normalize_basic(validation_service):
    """Test basic normalization"""
    # Value at midpoint
    result = validation_service.normalize(0.0, -0.5, 0.5)
    assert result == pytest.approx(50.0, rel=0.01)

    # Value at max
    result = validation_service.normalize(0.5, -0.5, 0.5)
    assert result == pytest.approx(100.0, rel=0.01)

    # Value at min
    result = validation_service.normalize(-0.5, -0.5, 0.5)
    assert result == pytest.approx(0.0, rel=0.01)


def test_normalize_reverse(validation_service):
    """Test reverse normalization (for max_drawdown)"""
    # For drawdown range [-0.5, 0.0], reverse=True means:
    # - Value at 0.0 (best, no drawdown) → 100.0
    # - Value at -0.5 (worst, max drawdown) → 0.0

    # -0.1 is 80% toward 0.0, so reversed it's 20.0
    result = validation_service.normalize(-0.1, -0.5, 0.0, reverse=True)
    assert result == pytest.approx(20.0, rel=0.01)

    # -0.4 is 20% toward 0.0, so reversed it's 80.0
    result = validation_service.normalize(-0.4, -0.5, 0.0, reverse=True)
    assert result == pytest.approx(80.0, rel=0.01)


def test_normalize_clipping(validation_service):
    """Test value clipping at boundaries"""
    # Value above max should clip to 100
    result = validation_service.normalize(1.0, -0.5, 0.5)
    assert result == 100.0

    # Value below min should clip to 0
    result = validation_service.normalize(-1.0, -0.5, 0.5)
    assert result == 0.0


def test_calculate_comprehensive_score_passing(validation_service):
    """Test comprehensive score calculation for passing strategy"""
    # Strategy A from spec: 年化15%, Sharpe 1.5, 回撤-20%, 胜率60%, 盈亏比2.0 → 61.67分
    score = validation_service.calculate_comprehensive_score(
        annual_return=0.15,
        sharpe_ratio=1.5,
        max_drawdown=-0.20,
        win_rate=0.60,
        profit_factor=2.0
    )

    # Should be around 61.67 points
    assert 60.0 <= score <= 63.0


def test_calculate_comprehensive_score_failing(validation_service):
    """Test comprehensive score calculation for failing strategy"""
    # Strategy B from spec: 年化-5%, Sharpe 0.3, 回撤-30%, 胜率40%, 盈亏比0.8 → 42分
    score = validation_service.calculate_comprehensive_score(
        annual_return=-0.05,
        sharpe_ratio=0.3,
        max_drawdown=-0.30,
        win_rate=0.40,
        profit_factor=0.8
    )

    # Should be around 42 points
    assert 39.0 <= score <= 45.0


def test_calculate_comprehensive_score_edge_case(validation_service):
    """Test comprehensive score calculation at threshold"""
    # Strategy C from spec: 年化5%, Sharpe 0.8, 回撤-15%, 胜率55%, 盈亏比1.5 → 50.95分
    score = validation_service.calculate_comprehensive_score(
        annual_return=0.05,
        sharpe_ratio=0.8,
        max_drawdown=-0.15,
        win_rate=0.55,
        profit_factor=1.5
    )

    # Should be around 50.95 points
    assert 49.0 <= score <= 52.0


def test_aggregate_by_strategy(validation_service):
    """Test aggregating backtest results by strategy"""
    # Arrange - mock backtest results for 2 strategies across 3 stocks each
    results = [
        # Strategy 1
        {'strategy_id': 1, 'symbol': '000001.SH', 'annual_return': 0.15, 'sharpe_ratio': 1.5,
         'max_drawdown': -0.20, 'win_rate': 0.60, 'profit_factor': 2.0},
        {'strategy_id': 1, 'symbol': '000001.SZ', 'annual_return': 0.12, 'sharpe_ratio': 1.3,
         'max_drawdown': -0.18, 'win_rate': 0.58, 'profit_factor': 1.8},
        {'strategy_id': 1, 'symbol': '000858.SZ', 'annual_return': 0.18, 'sharpe_ratio': 1.7,
         'max_drawdown': -0.22, 'win_rate': 0.62, 'profit_factor': 2.2},
        # Strategy 2
        {'strategy_id': 2, 'symbol': '000001.SH', 'annual_return': -0.05, 'sharpe_ratio': 0.3,
         'max_drawdown': -0.30, 'win_rate': 0.40, 'profit_factor': 0.8},
        {'strategy_id': 2, 'symbol': '000001.SZ', 'annual_return': -0.03, 'sharpe_ratio': 0.5,
         'max_drawdown': -0.28, 'win_rate': 0.42, 'profit_factor': 0.9},
        {'strategy_id': 2, 'symbol': '000858.SZ', 'annual_return': -0.07, 'sharpe_ratio': 0.2,
         'max_drawdown': -0.32, 'win_rate': 0.38, 'profit_factor': 0.7},
    ]

    # Act
    aggregated = validation_service._aggregate_by_strategy(results)

    # Assert
    assert len(aggregated) == 2
    assert 1 in aggregated
    assert 2 in aggregated

    # Strategy 1 averages
    s1 = aggregated[1]
    assert s1['annual_return'] == pytest.approx(0.15, rel=0.01)  # (0.15+0.12+0.18)/3
    assert s1['sharpe_ratio'] == pytest.approx(1.5, rel=0.01)
    assert s1['backtest_count'] == 3
    assert s1['error_count'] == 0

    # Strategy 2 averages
    s2 = aggregated[2]
    assert s2['annual_return'] == pytest.approx(-0.05, rel=0.01)
    assert s2['backtest_count'] == 3


def test_validate_all_strategies_dry_run(validation_service):
    """Test validate_all_strategies in dry-run mode"""
    from unittest.mock import Mock, patch

    # Mock dependencies
    with patch.object(validation_service.strategy_repo, 'get_all') as mock_get_all, \
         patch.object(validation_service.stock_pool_service, 'get_hot_stocks') as mock_get_stocks, \
         patch.object(validation_service, '_call_batch_backtest') as mock_batch_backtest:

        # Arrange
        mock_get_all.return_value = [
            {'id': 1, 'strategy_name': 'Strategy A'},
            {'id': 2, 'strategy_name': 'Strategy B'}
        ]
        mock_get_stocks.return_value = ['000001.SH', '000001.SZ']
        mock_batch_backtest.return_value = {
            'results': [
                # Strategy 1 - should pass with higher metrics
                {'strategy_id': 1, 'symbol': '000001.SH', 'annual_return': 0.18,
                 'sharpe_ratio': 1.6, 'max_drawdown': -0.18, 'win_rate': 0.62, 'profit_factor': 2.1},
                {'strategy_id': 1, 'symbol': '000001.SZ', 'annual_return': 0.16,
                 'sharpe_ratio': 1.5, 'max_drawdown': -0.16, 'win_rate': 0.60, 'profit_factor': 2.0},
                # Strategy 2 - should fail with low metrics
                {'strategy_id': 2, 'symbol': '000001.SH', 'annual_return': -0.05,
                 'sharpe_ratio': 0.3, 'max_drawdown': -0.30, 'win_rate': 0.40, 'profit_factor': 0.8},
                {'strategy_id': 2, 'symbol': '000001.SZ', 'annual_return': -0.03,
                 'sharpe_ratio': 0.5, 'max_drawdown': -0.28, 'win_rate': 0.42, 'profit_factor': 0.9},
            ],
            'errors': []
        }

        # Act
        result = validation_service.validate_all_strategies(
            start_date='2024-05-27',
            end_date='2026-05-27',
            threshold=60.0,
            dry_run=True
        )

        # Assert
        assert result['total'] == 2
        assert result['passed'] == 1  # Strategy 1 should pass
        assert result['failed'] == 1  # Strategy 2 should fail
        assert len(result['details']) == 2
