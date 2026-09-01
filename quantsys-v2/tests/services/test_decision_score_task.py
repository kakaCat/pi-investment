"""decision_score_daily 调度 handler 测试（P0a）。"""
from unittest.mock import patch

from application.services.scheduler_tasks import (
    get_task_handler, handle_decision_score_daily,
)


@patch('application.services.evolution.decision_score_service.DecisionScoreService')
def test_handler_success(mock_cls):
    mock_cls.return_value.score_mature_decisions.return_value = {
        'scanned': 3, 'scored': 2, 'skipped_unmature': 1,
        'skipped_invalid': 0, 'errors': 0,
    }
    r = handle_decision_score_daily()
    assert r['action'] == 'decision_score_daily'
    assert r['status'] == 'success'
    assert r['scored'] == 2


@patch('application.services.evolution.decision_score_service.DecisionScoreService')
def test_handler_failure_swallowed(mock_cls):
    mock_cls.return_value.score_mature_decisions.side_effect = RuntimeError('db down')
    r = handle_decision_score_daily()
    assert r['status'] == 'failed'
    assert 'db down' in r['error']


def test_handler_registered():
    assert get_task_handler('decision_score_daily') is handle_decision_score_daily
