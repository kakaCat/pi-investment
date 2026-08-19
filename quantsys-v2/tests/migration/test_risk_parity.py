"""risk 域 parity 测试（P6）"""
import pytest
from tests.migration.parity import assert_parity

CHECK = "/api/risk/check"
RULES = "/api/risk/stop-loss/rules"
RULE_CREATE = "/api/risk/stop-loss/rules"
RULE_BATCH = "/api/risk/stop-loss/rules/batch"
RULE_UPDATE = "/api/risk/stop-loss/rules/nonexistent"
RULE_DELETE = "/api/risk/stop-loss/rules/nonexistent"


def test_risk_check(fastapi_client):
    assert_parity(fastapi_client, "POST", CHECK, json_body={})


def test_get_rules(fastapi_client):
    assert_parity(fastapi_client, "GET", RULES)


def test_create_rule_missing_symbol(fastapi_client):
    assert_parity(fastapi_client, "POST", RULE_CREATE, json_body={})


def test_batch_create_missing_rules(fastapi_client):
    assert_parity(fastapi_client, "POST", RULE_BATCH, json_body={})


def test_update_rule_not_found(fastapi_client):
    assert_parity(fastapi_client, "PUT", RULE_UPDATE, json_body={"name": "x"})


def test_delete_rule_not_found(fastapi_client):
    assert_parity(fastapi_client, "DELETE", RULE_DELETE)
