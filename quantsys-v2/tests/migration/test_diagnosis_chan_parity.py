"""diagnosis + chan 域 parity 测试（P8）"""
import pytest
from tests.migration.parity import assert_parity

DIAG_RUN = "/api/diagnosis/run"
DIAG_HEALTH = "/api/diagnosis/health"
CHAN_ANALYZE = "/api/chan/analyze"
CHAN_BUYPOINTS = "/api/chan/buypoints/latest"
CHAN_HEALTH = "/api/chan/health"


def test_diagnosis_health(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "GET", DIAG_HEALTH)


def test_diagnosis_run_missing_params(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "POST", DIAG_RUN, json_body={"symbol": "600519"})


def test_chan_health(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "GET", CHAN_HEALTH)


def test_chan_buypoints(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "GET", CHAN_BUYPOINTS)


def test_chan_analyze_missing_symbol(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "POST", CHAN_ANALYZE, json_body={})
