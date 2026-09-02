"""Tests for PoolValidationService."""
import pytest
from unittest.mock import MagicMock, patch
from application.services.pool_validation_service import PoolValidationService


@pytest.fixture
def mock_pool_repo():
    repo = MagicMock()
    repo.get_pool.return_value = {
        'id': 1,
        'name': '测试池',
        'pool_type': 'static',
        'symbols': ['600519.SH', '000858.SZ', '000001.SZ'],
    }
    return repo


@pytest.fixture
def mock_strategy_repo():
    repo = MagicMock()
    repo.get_all.return_value = [
        {'id': 53, 'name': '多因子波段策略v9', 'is_active': True},
        {'id': 54, 'name': 'RSI策略', 'is_active': True},
    ]
    return repo


@pytest.fixture
def service(mock_pool_repo, mock_strategy_repo):
    return PoolValidationService(
        pool_repo=mock_pool_repo,
        strategy_repo=mock_strategy_repo,
    )


class TestPoolValidationService:
    def test_validate_pool_not_found(self, service, mock_pool_repo):
        mock_pool_repo.get_pool.return_value = None
        with pytest.raises(ValueError, match="Pool 999 not found"):
            service.validate_pool(999)

    def test_validate_pool_empty_symbols(self, service, mock_pool_repo):
        mock_pool_repo.get_pool.return_value = {
            'id': 1, 'name': '空池', 'symbols': [],
        }
        with pytest.raises(ValueError, match="empty"):
            service.validate_pool(1)

    @patch('application.services.pool_validation_service.requests.post')
    def test_validate_pool_builds_correct_jobs(self, mock_post, service):
        """Verify jobs = strategy × symbol cartesian product."""
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            'success': True,
            'data': {'results': [], 'errors': []},
        }
        service.validate_pool(1, strategy_ids=[53])

        call_args = mock_post.call_args
        body = call_args[1]['json']
        jobs = body['jobs']
        # 1 strategy × 3 symbols = 3 jobs
        assert len(jobs) == 3
        assert all(j['strategy_id'] == 53 for j in jobs)
        symbols_in_jobs = {j['symbol'] for j in jobs}
        assert symbols_in_jobs == {'600519.SH', '000858.SZ', '000001.SZ'}

    @patch('application.services.pool_validation_service.requests.post')
    def test_validate_pool_aggregates_by_strategy(self, mock_post, service, mock_pool_repo):
        """Test that results are aggregated per strategy and ranked."""
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            'success': True,
            'data': {
                'results': [
                    {'strategyId': 53, 'symbol': '600519.SH',
                     'annualReturn': 0.15, 'sharpeRatio': 2.0,
                     'maxDrawdown': -0.05, 'winRate': 0.7, 'profitFactor': 2.0},
                    {'strategyId': 53, 'symbol': '000858.SZ',
                     'annualReturn': 0.10, 'sharpeRatio': 1.5,
                     'maxDrawdown': -0.08, 'winRate': 0.6, 'profitFactor': 1.5},
                    {'strategyId': 53, 'symbol': '000001.SZ',
                     'annualReturn': 0.12, 'sharpeRatio': 1.8,
                     'maxDrawdown': -0.06, 'winRate': 0.65, 'profitFactor': 1.8},
                    {'strategyId': 54, 'symbol': '600519.SH',
                     'annualReturn': 0.05, 'sharpeRatio': 0.8,
                     'maxDrawdown': -0.12, 'winRate': 0.45, 'profitFactor': 0.9},
                    {'strategyId': 54, 'symbol': '000858.SZ',
                     'annualReturn': 0.03, 'sharpeRatio': 0.5,
                     'maxDrawdown': -0.15, 'winRate': 0.40, 'profitFactor': 0.7},
                    {'strategyId': 54, 'symbol': '000001.SZ',
                     'annualReturn': 0.04, 'sharpeRatio': 0.6,
                     'maxDrawdown': -0.13, 'winRate': 0.42, 'profitFactor': 0.8},
                ],
                'errors': [],
            },
        }

        result = service.validate_pool(1)

        assert result['pool_id'] == 1
        assert result['strategies_tested'] == 2
        assert result['stocks_in_pool'] == 3
        # Strategy 53 should be ranked first (better metrics)
        assert result['best_strategy']['strategy_id'] == 53
        assert len(result['rankings']) == 2
        assert result['rankings'][0]['strategy_id'] == 53
        assert result['rankings'][1]['strategy_id'] == 54
        # recommended_pairs should exist (top 5 from best strategy)
        assert len(result['recommended_pairs']) <= 5

    @patch('application.services.pool_validation_service.requests.post')
    def test_validate_pool_uses_all_strategies_when_none_specified(self, mock_post, service):
        """When strategy_ids is None, all active strategies are used."""
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            'success': True,
            'data': {'results': [], 'errors': []},
        }
        service.validate_pool(1, strategy_ids=None)

        call_args = mock_post.call_args
        body = call_args[1]['json']
        jobs = body['jobs']
        strategy_ids_used = {j['strategy_id'] for j in jobs}
        # Should use both strategies from mock_strategy_repo
        assert strategy_ids_used == {53, 54}
        # 2 strategies × 3 symbols = 6 jobs
        assert len(jobs) == 6

    @patch('application.services.pool_validation_service.requests.post')
    def test_validate_pool_saves_validation_result(self, mock_post, service, mock_pool_repo):
        """Verify last_validation is saved to the pool."""
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            'success': True,
            'data': {
                'results': [
                    {'strategyId': 53, 'symbol': '600519.SH',
                     'annualReturn': 0.15, 'sharpeRatio': 2.0,
                     'maxDrawdown': -0.05, 'winRate': 0.7, 'profitFactor': 2.0},
                ],
                'errors': [],
            },
        }
        service.validate_pool(1, strategy_ids=[53])
        mock_pool_repo.update_validation.assert_called_once()
        saved_validation = mock_pool_repo.update_validation.call_args[0][1]
        assert 'validated_at' in saved_validation
        assert 'best_strategy' in saved_validation
