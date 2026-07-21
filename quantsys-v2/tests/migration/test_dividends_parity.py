"""dividends 域 parity 测试（agent 迁移）"""
import pytest
from tests.migration.parity import assert_parity, assert_structural_parity

SINGLE = "/api/stock/601398/dividends"
SCREEN = "/api/dividends/screen"
CALENDAR = "/api/dividends/calendar"


def test_single_dividends(flask_client, fastapi_client):
    # 单股查询，确定性数据，精确比对
    assert_parity(flask_client, fastapi_client, "GET", SINGLE, params={"years": 5})


def test_screen(flask_client, fastapi_client):
    # 全池扫描 + eastmoney 网络超时 → 结果非确定，结构比对
    assert_structural_parity(flask_client, fastapi_client, "POST", SCREEN,
                             json_body={"min_yield": 3.0, "min_years": 3, "limit": 5})


def test_calendar(flask_client, fastapi_client):
    # 全池扫描 + eastmoney 网络超时 → 结果非确定（total 可能 92/93 抖动），结构比对
    assert_structural_parity(flask_client, fastapi_client, "GET", CALENDAR,
                             params={"start_date": "2026-06-01", "end_date": "2026-06-30", "event": "ex_dividend"})


def test_calendar_missing_dates(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "GET", CALENDAR)
