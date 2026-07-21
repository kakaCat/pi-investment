"""pipeline 域 parity 测试（P8）"""
import pytest
from tests.migration.parity import assert_parity

STATS = "/api/pipeline/statistics"
TASKS = "/api/pipeline/tasks/list"
RUNS = "/api/pipeline/runs/list"
RUN_DETAIL = "/api/pipeline/nonexistent-run"
RUN_LOGS = "/api/pipeline/nonexistent-run/logs"
TRIGGER = "/api/pipeline/trigger"


def test_statistics(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "GET", STATS)


def test_tasks_list(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "GET", TASKS)


def test_runs_list(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "GET", RUNS, params={"page": 1, "page_size": 5})


def test_run_detail_not_found(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "GET", RUN_DETAIL)


def test_run_logs_not_found(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "GET", RUN_LOGS)


def test_trigger_missing_body(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "POST", TRIGGER, json_body=None)
