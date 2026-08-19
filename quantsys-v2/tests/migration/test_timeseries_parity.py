"""stock/factors + timeseries 域 parity 测试（agent 迁移收尾）"""
import pytest
from tests.migration.parity import assert_parity, assert_structural_parity

FACTORS = "/api/stock/600519/factors"
FACTORS_ALT = "/api/stocks/600519/factors"
ARIMA_FIT = "/api/timeseries/arima/fit"
ARIMA_FORECAST = "/api/timeseries/arima/forecast"
GARCH_FIT = "/api/timeseries/garch/fit"
GARCH_VAR = "/api/timeseries/garch/var"
KALMAN_FILTER = "/api/timeseries/kalman/filter"
KALMAN_LOCAL = "/api/timeseries/kalman/local-level"


def test_stock_factors(fastapi_client):
    assert_parity(fastapi_client, "GET", FACTORS)


def test_stock_factors_alt(fastapi_client):
    assert_parity(fastapi_client, "GET", FACTORS_ALT)


def test_arima_fit(fastapi_client):
    assert_structural_parity(fastapi_client, "POST", ARIMA_FIT,
                             json_body={"symbol": "600519"})


def test_arima_fit_missing_symbol(fastapi_client):
    assert_parity(fastapi_client, "POST", ARIMA_FIT, json_body={})


def test_arima_forecast(fastapi_client):
    assert_structural_parity(fastapi_client, "POST", ARIMA_FORECAST,
                             json_body={"symbol": "600519", "forecast_steps": 3})


def test_garch_fit(fastapi_client):
    assert_structural_parity(fastapi_client, "POST", GARCH_FIT,
                             json_body={"symbol": "600519"})


def test_garch_var(fastapi_client):
    assert_structural_parity(fastapi_client, "POST", GARCH_VAR,
                             json_body={"symbol": "600519", "confidence": 0.95})


def test_kalman_filter(fastapi_client):
    assert_structural_parity(fastapi_client, "POST", KALMAN_FILTER,
                             json_body={"symbol": "600519"})


def test_kalman_local_level(fastapi_client):
    assert_structural_parity(fastapi_client, "POST", KALMAN_LOCAL,
                             json_body={"symbol": "600519"})
