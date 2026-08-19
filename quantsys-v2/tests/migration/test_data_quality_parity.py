"""data_quality 域 parity 测试（agent 迁移）"""
import pytest
from tests.migration.parity import assert_parity

REPORT = "/api/data/quality-report"
STATS = "/api/data/quality-stats"
SUMMARY = "/api/data/quality-summary"
TREND = "/api/data/quality-trend"
SUBMIT = "/api/data/quality-submit"
CHECK = "/api/data/check"
DETECT = "/api/data/detect-gaps"
VALIDATE = "/api/data/validate"


def test_report(fastapi_client):
    assert_parity(fastapi_client, "GET", REPORT, params={"limit": 5})


def test_stats(fastapi_client):
    assert_parity(fastapi_client, "GET", STATS, params={"limit": 5})


def test_summary(fastapi_client):
    assert_parity(fastapi_client, "GET", SUMMARY, params={"days": 7})


def test_trend(fastapi_client):
    assert_parity(fastapi_client, "GET", TREND, params={"days": 7})


def test_submit_missing_fields(fastapi_client):
    assert_parity(fastapi_client, "POST", SUBMIT, json_body={"symbol": "600519"})


def test_check(fastapi_client):
    assert_parity(fastapi_client, "GET", CHECK, params={"symbols": "600519"})


def test_detect_gaps(fastapi_client):
    assert_parity(fastapi_client, "POST", DETECT, json_body={"symbols": ["600519"]})


def test_validate(fastapi_client):
    assert_parity(fastapi_client, "POST", VALIDATE, json_body={"symbols": ["600519"]})
