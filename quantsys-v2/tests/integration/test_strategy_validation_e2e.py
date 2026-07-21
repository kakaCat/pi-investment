"""End-to-end integration test for strategy validation"""
import pytest
from application.services.strategy_validation_service import StrategyValidationService
from adapters.outbound.repositories import StrategyORMRepository


@pytest.mark.integration
def test_strategy_validation_e2e():
    """
    End-to-end test: validate strategies with real database

    This test requires:
    - PostgreSQL running with test database
    - At least 2 strategies in quant.strategy_configs
    - K-line data for at least 2 stocks
    """
    # Arrange
    validation_service = StrategyValidationService()
    strategy_repo = StrategyORMRepository()

    # Get existing strategies
    strategies = strategy_repo.get_all(active_only=False)
    if len(strategies) < 2:
        pytest.skip("Need at least 2 strategies for integration test")

    # Act - dry run mode to avoid modifying database
    result = validation_service.validate_all_strategies(
        start_date='2025-05-01',
        end_date='2025-06-01',
        threshold=60.0,
        dry_run=True
    )

    # Assert
    assert result['total'] >= 2
    assert result['passed'] + result['failed'] == result['total']
    assert result['duration'] > 0
    assert len(result['details']) == result['total']

    # Verify detail structure
    for detail in result['details']:
        assert 'strategy_id' in detail
        assert 'strategy_name' in detail
        assert 'score' in detail
        assert 'status' in detail
        assert detail['status'] in ['passed', 'failed']
        assert 0 <= detail['score'] <= 100
        assert 'metrics' in detail
        assert 'backtest_count' in detail
        assert 'error_count' in detail


@pytest.mark.integration
def test_validation_report_persistence():
    """Test that validation reports are saved correctly"""
    # Arrange
    validation_service = StrategyValidationService()
    strategy_repo = StrategyORMRepository()

    strategies = strategy_repo.get_all(active_only=False)
    if len(strategies) < 1:
        pytest.skip("Need at least 1 strategy for integration test")

    # Act - run validation without dry_run
    result = validation_service.validate_all_strategies(
        start_date='2025-05-01',
        end_date='2025-06-01',
        threshold=60.0,
        dry_run=False
    )

    # Assert - verify reports were saved
    # Note: This test modifies the database, so it should clean up after itself
    # or run in a transaction that gets rolled back
    assert result['total'] > 0

    # Verify at least one strategy has validation_status set
    for detail in result['details']:
        strategy = strategy_repo.get_by_id(detail['strategy_id'])
        assert strategy is not None
        assert 'validation_status' in strategy
