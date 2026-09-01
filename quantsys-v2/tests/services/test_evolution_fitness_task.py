"""evolution_fitness_daily 调度任务 handler 测试"""
from unittest.mock import patch

from application.services.scheduler_tasks import (
    handle_evolution_fitness_daily, get_task_handler,
)


class TestEvolutionFitnessHandler:
    @patch('application.services.evolution.evolution_fitness_service.EvolutionFitnessService')
    def test_handler_returns_success_summary(self, mock_svc):
        mock_svc.return_value.compute_all_accounts.return_value = {
            'computed': 5, 'skipped': 0, 'window_end': '2026-08-05',
        }
        result = handle_evolution_fitness_daily({'window_days': 20})
        mock_svc.return_value.compute_all_accounts.assert_called_once_with(window_days=20)
        assert result['action'] == 'evolution_fitness_daily'
        assert result['status'] == 'success'
        assert result['computed'] == 5

    @patch('application.services.evolution.evolution_fitness_service.EvolutionFitnessService')
    def test_handler_default_params(self, mock_svc):
        mock_svc.return_value.compute_all_accounts.return_value = {
            'computed': 3, 'skipped': 0, 'window_end': '2026-08-05',
        }
        handle_evolution_fitness_daily()
        mock_svc.return_value.compute_all_accounts.assert_called_once_with(window_days=20)

    @patch('application.services.evolution.evolution_fitness_service.EvolutionFitnessService')
    def test_handler_failure_returns_failed(self, mock_svc):
        mock_svc.return_value.compute_all_accounts.side_effect = RuntimeError('db down')
        result = handle_evolution_fitness_daily({})
        assert result['status'] == 'failed'
        assert 'db down' in result['error']

    def test_registered_in_task_handlers(self):
        handler = get_task_handler('evolution_fitness_daily')
        assert handler is handle_evolution_fitness_daily
