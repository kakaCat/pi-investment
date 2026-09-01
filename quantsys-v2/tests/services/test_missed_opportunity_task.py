"""missed_opportunity_daily 调度 handler 测试（P0b）。"""
from unittest.mock import patch

from application.services.task_handlers import (
    get_task_handler, handle_missed_opportunity_daily,
)


@patch('application.services.evolution.missed_opportunity_service.MissedOpportunityService')
def test_handler_success(mock_cls):
    mock_cls.return_value.capture.return_value = {
        'scanned': 5, 'captured': 3, 'skipped_acted': 1, 'skipped_duplicate': 1,
        'skipped_in_grace': 0, 'skipped_invalid': 0, 'errors': 0,
    }
    r = handle_missed_opportunity_daily()
    assert r['action'] == 'missed_opportunity_daily'
    assert r['status'] == 'success'
    assert r['captured'] == 3


@patch('application.services.evolution.missed_opportunity_service.MissedOpportunityService')
def test_handler_failure_swallowed(mock_cls):
    mock_cls.return_value.capture.side_effect = RuntimeError('db down')
    r = handle_missed_opportunity_daily()
    assert r['status'] == 'failed'
    assert 'db down' in r['error']


def test_handler_registered():
    assert get_task_handler('missed_opportunity_daily') is handle_missed_opportunity_daily
