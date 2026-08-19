"""signals 域 parity 测试（P3b）

注：web 的 signal.ts 用 /api/signals/{id}/approve 形式，Flask 只有 /api/signals/approve/{id}，
这里按 Flask 实际路由做 parity（web 路径不匹配是既有 bug，不在迁移范围）。
"""
import pytest
from tests.migration.parity import assert_parity

SIGNALS = "/api/signals"
HISTORY = "/api/signals/history"
STATS = "/api/signals/statistics"
DETAIL = "/api/signals/detail/999999"
BY_ID = "/api/signals/999999"
APPROVE = "/api/signals/approve/999999"
REJECT = "/api/signals/reject/999999"
MARK_ERR = "/api/signals/mark-error/999999"
AGENT_LOGS = "/api/agent/logs"


def test_get_signals(fastapi_client):
    assert_parity(fastapi_client, "GET", SIGNALS, params={"page": 1, "page_size": 5})


def test_get_signals_camel_params(fastapi_client):
    # camelCase 参数（get_query_params_snake_case 应统一转 snake）
    assert_parity(fastapi_client, "GET", SIGNALS, params={"pageSize": 5, "minConfidence": 0})


def test_history(fastapi_client):
    assert_parity(fastapi_client, "GET", HISTORY)


def test_statistics(fastapi_client):
    assert_parity(fastapi_client, "GET", STATS)


def test_detail_not_found(fastapi_client):
    assert_parity(fastapi_client, "GET", DETAIL)


def test_by_id_not_found(fastapi_client):
    assert_parity(fastapi_client, "GET", BY_ID)


def test_approve_not_found(fastapi_client):
    assert_parity(fastapi_client, "POST", APPROVE, json_body={})


def test_reject_not_found(fastapi_client):
    assert_parity(fastapi_client, "POST", REJECT, json_body={"reason": "x"})


def test_mark_error_not_found(fastapi_client):
    assert_parity(fastapi_client, "POST", MARK_ERR, json_body={"errorType": "bad"})


def test_agent_logs(fastapi_client):
    assert_parity(fastapi_client, "GET", AGENT_LOGS, params={"page": 1, "page_size": 5})
