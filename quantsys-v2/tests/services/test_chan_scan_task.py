"""chan_scan 调度任务 handler 测试"""
from unittest.mock import patch

from application.services.scheduler_tasks import (
    handle_chan_scan, handle_chan_knowledge_distill, get_task_handler,
)


class TestChanScanHandler:
    @patch('application.services.chan_scan_service.ChanScanService')
    def test_handler_returns_success_summary(self, mock_svc):
        mock_svc.return_value.scan.return_value = {
            'scanned': 10, 'signals_written': 2, 'duplicates': 1,
            'skipped': 3, 'errors': 0,
        }
        result = handle_chan_scan()
        assert result['action'] == 'chan_scan'
        assert result['status'] == 'success'
        assert result['signals_written'] == 2

    def test_registered_in_task_handlers(self):
        handler = get_task_handler('chan_scan')
        assert handler is handle_chan_scan


class TestChanKnowledgeDistillHandler:
    @patch('application.services.chan_knowledge_distiller.ChanKnowledgeDistiller')
    def test_handler_passes_params(self, mock_distiller):
        mock_distiller.return_value.distill.return_value = {
            'strategies_distilled': 3, 'signals_total': 50, 'signals_excluded': 2,
        }
        result = handle_chan_knowledge_distill({'window_days': 20, 'lookback_days': 90})
        mock_distiller.assert_called_once_with(window_days=20, lookback_days=90)
        assert result['action'] == 'chan_knowledge_distill'
        assert result['status'] == 'success'
        assert result['strategies_distilled'] == 3

    def test_registered_in_task_handlers(self):
        handler = get_task_handler('chan_knowledge_distill')
        assert handler is handle_chan_knowledge_distill
