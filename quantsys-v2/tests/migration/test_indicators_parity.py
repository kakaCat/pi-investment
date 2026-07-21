"""indicators 域 parity 测试（P6）"""
import pytest
from tests.migration.parity import assert_parity

LIST = "/api/indicators/list"
DETAIL = "/api/indicators/detail/999999"
CREATE = "/api/indicators/create"
RUN = "/api/indicators/run/999999"
BACKTEST = "/api/indicators/backtest"


def test_list(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "GET", LIST, params={"page": 1, "pageSize": 5})


def test_list_my(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "GET", LIST, params={"type": "my"})


def test_list_system(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "GET", LIST, params={"type": "system"})


def test_detail_not_found(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "GET", DETAIL)


def test_create_missing_name(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "POST", CREATE, json_body={"code": "MA5"})


def test_create_missing_code(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "POST", CREATE, json_body={"name": "x"})


def test_run_missing_symbol(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "POST", RUN, json_body={})


def test_run_not_found(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "POST", RUN, json_body={"symbol": "600519"})


def test_backtest_missing_fields(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "POST", BACKTEST, json_body={"symbol": "600519"})
