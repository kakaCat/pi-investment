"""executions 域 parity 测试（P5 收尾）"""
import pytest
from tests.migration.parity import assert_parity

LIST = "/api/executions"
STATS = "/api/executions/stats"
PENDING = "/api/executions/pending"
SUMMARY = "/api/executions/summary"
BY_ID = "/api/executions/999999"
CLOSE = "/api/executions/999999/close"
CANCEL = "/api/executions/999999/cancel"


def test_list(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "GET", LIST, params={"limit": 5})


def test_stats(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "GET", STATS)


def test_pending(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "GET", PENDING, params={"limit": 5})


def test_summary(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "GET", SUMMARY)


def test_get_not_found(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "GET", BY_ID)


def test_close_missing_params(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "PUT", CLOSE, json_body={})


def test_cancel_not_found(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "PUT", CANCEL, json_body={})
