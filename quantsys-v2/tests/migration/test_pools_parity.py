"""pools 域 parity 测试（P3a）"""
import pytest
from tests.migration.parity import assert_parity

POOLS = "/api/pools"
POOL_BY_ID = "/api/pools/999999"            # 不存在 → 404
SCAN_AND_CREATE = "/api/pools/scan-and-create"
SCAN_STATUS = "/api/pools/scan-status"
SCAN_RESULTS = "/api/pools/scan-results"
VALIDATE = "/api/pools/999999/validate"


def test_list_pools(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "GET", POOLS)


def test_get_pool_not_found(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "GET", POOL_BY_ID)


def test_create_pool_missing_body(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "POST", POOLS, json_body={})


def test_create_pool_missing_type(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "POST", POOLS, json_body={"name": "测试池"})


def test_create_pool_invalid_filter(flask_client, fastapi_client):
    body = {"name": "x", "poolType": "dynamic",
            "filterTemplate": {"conditions": [{"field": "bogus", "operator": ">=", "value": 1}]}}
    assert_parity(flask_client, fastapi_client, "POST", POOLS, json_body=body)


def test_scan_and_create_missing_fields(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "POST", SCAN_AND_CREATE, json_body={"name": "x"})


def test_scan_status(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "GET", SCAN_STATUS)


def test_scan_results(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "GET", SCAN_RESULTS)


def test_validate_pool_not_found(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "POST", VALIDATE, json_body={})
