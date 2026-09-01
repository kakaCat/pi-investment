"""daily_equity_snapshot 调度任务 handler 测试"""
from unittest.mock import patch

from application.services.task_handlers import (
    handle_daily_equity_snapshot, get_task_handler,
)


class TestDailyEquitySnapshotHandler:
    @patch('application.services.evolution.daily_snapshot_service.DailySnapshotService')
    def test_handler_returns_success_summary(self, mock_svc):
        mock_svc.return_value.snapshot_all_accounts.return_value = {
            'written': 5, 'skipped': 0, 'date': '2026-08-05',
        }
        result = handle_daily_equity_snapshot({})
        assert result['action'] == 'daily_equity_snapshot'
        assert result['status'] == 'success'
        assert result['written'] == 5

    @patch('application.services.evolution.daily_snapshot_service.DailySnapshotService')
    def test_handler_failure_returns_failed(self, mock_svc):
        mock_svc.return_value.snapshot_all_accounts.side_effect = RuntimeError('kline down')
        result = handle_daily_equity_snapshot({})
        assert result['status'] == 'failed'

    def test_registered_in_task_handlers(self):
        handler = get_task_handler('daily_equity_snapshot')
        assert handler is handle_daily_equity_snapshot
