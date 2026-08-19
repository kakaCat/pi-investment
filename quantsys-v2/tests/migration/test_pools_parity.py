"""pools 域 parity 测试（P3a）"""
import pytest
from tests.migration.parity import assert_parity

POOLS = "/api/pools"
POOL_BY_ID = "/api/pools/999999"            # 不存在 → 404
SCAN_AND_CREATE = "/api/pools/scan-and-create"
SCAN_STATUS = "/api/pools/scan-status"
SCAN_RESULTS = "/api/pools/scan-results"
VALIDATE = "/api/pools/999999/validate"


def test_list_pools(fastapi_client):
    assert_parity(fastapi_client, "GET", POOLS)


def test_get_pool_not_found(fastapi_client):
    assert_parity(fastapi_client, "GET", POOL_BY_ID)


def test_create_pool_missing_body(fastapi_client):
    assert_parity(fastapi_client, "POST", POOLS, json_body={})


def test_create_pool_missing_type(fastapi_client):
    assert_parity(fastapi_client, "POST", POOLS, json_body={"name": "测试池"})


def test_create_pool_invalid_filter(fastapi_client):
    body = {"name": "x", "poolType": "dynamic",
            "filterTemplate": {"conditions": [{"field": "bogus", "operator": ">=", "value": 1}]}}
    assert_parity(fastapi_client, "POST", POOLS, json_body=body)


def test_scan_and_create_missing_fields(fastapi_client):
    assert_parity(fastapi_client, "POST", SCAN_AND_CREATE, json_body={"name": "x"})


def test_scan_status(fastapi_client):
    assert_parity(fastapi_client, "GET", SCAN_STATUS)


def test_scan_results(fastapi_client):
    assert_parity(fastapi_client, "GET", SCAN_RESULTS)


def test_validate_pool_not_found(fastapi_client):
    assert_parity(fastapi_client, "POST", VALIDATE, json_body={})


ADD_MEMBERS_NF = "/api/pools/999999/members"   # 不存在 → 404


def test_add_members_not_found(fastapi_client):
    assert_parity(fastapi_client, "POST", ADD_MEMBERS_NF,
                  json_body={"symbols": ["600519.SH"]})


def test_add_members_missing_symbols(fastapi_client):
    assert_parity(fastapi_client, "POST", ADD_MEMBERS_NF,
                  json_body={})


def test_remove_members_not_found(fastapi_client):
    assert_parity(fastapi_client, "DELETE", ADD_MEMBERS_NF,
                  json_body={"symbols": ["600519.SH"]})
