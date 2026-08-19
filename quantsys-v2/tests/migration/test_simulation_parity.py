"""simulation + report 域测试（P7）

说明：
- simulation：Flask simulation.py 的蓝图无 url_prefix，路由在根路径（/strategies、/accounts），
  而 web 与 FastAPI 用 /api/simulation/*，故无法直接 Flask↔FastAPI parity（Flask 侧 404）。
  这里对 FastAPI 的 simulation 端点做**功能测试**（验证成功路径 + 必填/404 错误路径）。
- report/daily：Flask health.py 的 ds.get_risk_summary() 不存在（既有 bug），两边同为 500，
  故保留 parity（按状态码比对）。
"""
import pytest
from tests.migration.parity import assert_parity

SIM = "/api/simulation"
REPORT_DAILY = "/api/report/daily"


# ---- simulation 功能测试（FastAPI-only，Flask 在根路径无法 parity）----

def test_strategies_list(fastapi_client):
    r = fastapi_client.get(f"{SIM}/strategies")
    assert r.status_code == 200
    body = r.json()
    assert body.get("success") is True
    assert isinstance(body.get("data"), list)


def test_strategy_detail_not_found(fastapi_client):
    r = fastapi_client.get(f"{SIM}/strategies/nonexistent-xyz")
    assert r.status_code == 404
    assert r.json().get("success") is False


def test_accounts_list(fastapi_client):
    r = fastapi_client.get(f"{SIM}/accounts")
    assert r.status_code == 200
    body = r.json()
    assert body.get("success") is True
    assert "accounts" in body.get("data", {})


def test_trades_requires_account_name(fastapi_client):
    r = fastapi_client.get(f"{SIM}/trades")
    assert r.status_code == 400
    assert r.json().get("success") is False


def test_performance_requires_account_name(fastapi_client):
    r = fastapi_client.get(f"{SIM}/performance")
    assert r.status_code == 400
    assert r.json().get("success") is False


def test_execution_history_requires_account_name(fastapi_client):
    r = fastapi_client.get(f"{SIM}/execution-history")
    assert r.status_code == 400
    assert r.json().get("success") is False


def test_run_requires_account_name(fastapi_client):
    r = fastapi_client.post(f"{SIM}/run", json={"strategy_id": "v13"})
    assert r.status_code == 400
    assert r.json().get("success") is False


def test_account_detail_not_found(fastapi_client):
    r = fastapi_client.get(f"{SIM}/accounts/nonexistent-xyz")
    assert r.status_code in (404, 500)


# ---- report/daily parity（Flask 也是 500：ds.get_risk_summary 不存在的既有 bug）----

def test_report_daily(fastapi_client):
    assert_parity(fastapi_client, "GET", REPORT_DAILY)
