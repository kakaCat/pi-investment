"""scheduler 域 parity 测试（P4）"""
import pytest
from tests.migration.parity import assert_parity

TASKS = "/api/scheduler/tasks"
RUNS = "/api/scheduler/runs"
RUNS_FAILED = "/api/scheduler/runs/failed"
TASK_ENABLE = "/api/scheduler/tasks/999999/enable"
TASK_RUNS = "/api/scheduler/tasks/999999/runs"
TASK_TRIGGER = "/api/scheduler/tasks/999999/trigger"


def test_list_tasks(fastapi_client):
    assert_parity(fastapi_client, "GET", TASKS, params={"page": 1, "pageSize": 5})


def test_create_task_missing_body(fastapi_client):
    assert_parity(fastapi_client, "POST", TASKS, json_body={})


def test_list_runs(fastapi_client):
    assert_parity(fastapi_client, "GET", RUNS, params={"page": 1, "pageSize": 5})


def test_list_runs_failed(fastapi_client):
    assert_parity(fastapi_client, "GET", RUNS_FAILED, params={"page": 1, "pageSize": 5})


def test_enable_task_not_found(fastapi_client):
    assert_parity(fastapi_client, "POST", TASK_ENABLE, json_body={})


def test_task_runs_not_found(fastapi_client):
    assert_parity(fastapi_client, "GET", TASK_RUNS, params={"page": 1, "pageSize": 5})


def test_trigger_task_not_found(fastapi_client):
    assert_parity(fastapi_client, "POST", TASK_TRIGGER, json_body={})
