"""analysis 域 parity 测试（P6）

P6 首批：backtest / compute-factors / technical（见上方既有用例）。
P6 第二批：/api/stock/{symbol}/* 10 个端点
（price-action / buy-range / exit-plan / pe-percentile / candlestick /
indicators / valuation / score / quality / data-health）。
"""
import pytest
from tests.migration.parity import assert_parity, assert_structural_parity

BACKTEST = "/api/backtest"
COMPUTE = "/api/compute/factors"
TECHNICAL = "/api/stock/600519/technical"

SYMBOL = "600519"
BAD_SYMBOL = "999999"


def test_backtest_missing_fields(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "POST", BACKTEST, json_body={"symbol": "600519"})


def test_backtest_missing_ma_params(flask_client, fastapi_client):
    body = {"strategyName": "ma_cross", "symbol": "600519", "startDate": "2024-01-01",
            "endDate": "2024-12-31", "initialCapital": 100000}
    assert_parity(flask_client, fastapi_client, "POST", BACKTEST, json_body=body)


def test_compute_missing_symbols(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "POST", COMPUTE, json_body={})


def test_technical(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "GET", TECHNICAL)


def test_technical_not_found(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "GET", "/api/stock/999999/technical")


# ============ /api/stock/{symbol}/price-action ============

# price-action / candlestick 底层服务会访问 eastmoney 实时接口（非确定性），
# 成功路径只比对结构与状态码。
def test_price_action(flask_client, fastapi_client):
    assert_structural_parity(flask_client, fastapi_client, "GET",
                             f"/api/stock/{SYMBOL}/price-action", params={"period": 60})


def test_price_action_bad_symbol(flask_client, fastapi_client):
    assert_structural_parity(flask_client, fastapi_client, "GET",
                             f"/api/stock/{BAD_SYMBOL}/price-action")


# ============ /api/stock/{symbol}/buy-range ============

def test_buy_range(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "GET",
                  f"/api/stock/{SYMBOL}/buy-range")


def test_buy_range_bad_symbol(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "GET",
                  f"/api/stock/{BAD_SYMBOL}/buy-range")


# ============ /api/stock/{symbol}/exit-plan ============

def test_exit_plan(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "GET",
                  f"/api/stock/{SYMBOL}/exit-plan",
                  params={"buy_price": 1500.0, "position_size": 100})


def test_exit_plan_bad_symbol(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "GET",
                  f"/api/stock/{BAD_SYMBOL}/exit-plan", params={"buy_price": 10.0})


# ============ /api/stock/{symbol}/pe-percentile ============

def test_pe_percentile(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "GET",
                  f"/api/stock/{SYMBOL}/pe-percentile", params={"years": 3})


def test_pe_percentile_bad_symbol(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "GET",
                  f"/api/stock/{BAD_SYMBOL}/pe-percentile")


# ============ /api/stock/{symbol}/candlestick ============

def test_candlestick(flask_client, fastapi_client):
    assert_structural_parity(flask_client, fastapi_client, "GET",
                             f"/api/stock/{SYMBOL}/candlestick")


def test_candlestick_bad_symbol(flask_client, fastapi_client):
    assert_structural_parity(flask_client, fastapi_client, "GET",
                             f"/api/stock/{BAD_SYMBOL}/candlestick")


# ============ /api/stock/{symbol}/indicators ============

def test_indicators(flask_client, fastapi_client):
    assert_structural_parity(flask_client, fastapi_client, "GET",
                             f"/api/stock/{SYMBOL}/indicators")


# ============ /api/stock/{symbol}/valuation ============

def test_valuation(flask_client, fastapi_client):
    assert_structural_parity(flask_client, fastapi_client, "GET",
                             f"/api/stock/{SYMBOL}/valuation")


# ============ /api/stock/{symbol}/score ============

def test_score(flask_client, fastapi_client):
    assert_structural_parity(flask_client, fastapi_client, "GET",
                             f"/api/stock/{SYMBOL}/score")


# ============ /api/stock/{symbol}/quality ============

def test_quality(flask_client, fastapi_client):
    assert_structural_parity(flask_client, fastapi_client, "GET",
                             f"/api/stock/{SYMBOL}/quality", params={"framework": "auto"})


# ============ /api/stock/{symbol}/data-health ============

def test_data_health(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "GET",
                  f"/api/stock/{SYMBOL}/data-health")


def test_data_health_bad_symbol(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "GET",
                  f"/api/stock/{BAD_SYMBOL}/data-health")


# ============ P6c：/api/market/sentiment ============

# 市场情绪底层走实时数据源（非确定性），只比对结构与状态码。
def test_market_sentiment(flask_client, fastapi_client):
    assert_structural_parity(flask_client, fastapi_client, "GET", "/api/market/sentiment")


# ============ P6c：/api/stocks/screen ============

def test_stocks_screen(flask_client, fastapi_client):
    assert_structural_parity(flask_client, fastapi_client, "GET",
                             "/api/stocks/screen", params={"limit": 5})


def test_stocks_screen_with_criteria(flask_client, fastapi_client):
    assert_structural_parity(flask_client, fastapi_client, "GET",
                             "/api/stocks/screen",
                             params={"min_score": 60, "max_pe": 30.5, "limit": 3})


# ============ P6c：/api/screening/quality ============

def test_screening_quality(flask_client, fastapi_client):
    assert_structural_parity(flask_client, fastapi_client, "GET",
                             "/api/screening/quality", params={"limit": 5})


def test_screening_quality_with_params(flask_client, fastapi_client):
    assert_structural_parity(flask_client, fastapi_client, "GET",
                             "/api/screening/quality",
                             params={"sector": "白酒", "min_score": 50, "max_pe": 40.0, "limit": 3})


# ============ P6c：/api/risk/stress-test（410 deprecated，确定性） ============

def test_risk_stress_test_deprecated(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "POST", "/api/risk/stress-test", json_body={})


# ============ P6c：/api/risk/price-alert（legacy quant 模块缺失 → 503，确定性） ============

def test_risk_price_alert(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "POST", "/api/risk/price-alert",
                  json_body={"symbol": "600519"})


# ============ P6c：/api/risk/trade-verify（legacy quant 模块缺失 → 503，确定性） ============

def test_risk_trade_verify(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "POST", "/api/risk/trade-verify",
                  json_body={"trades": []})


# ============ P6c：/api/risk/metrics（纯计算，确定性） ============

def test_risk_metrics_missing_returns(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "POST", "/api/risk/metrics", json_body={})


def test_risk_metrics(flask_client, fastapi_client):
    body = {"returns": [0.01, -0.02, 0.015, 0.005, -0.01, 0.02, -0.005, 0.008]}
    assert_parity(flask_client, fastapi_client, "POST", "/api/risk/metrics", json_body=body)


def test_risk_metrics_with_benchmark(flask_client, fastapi_client):
    body = {
        "returns": [0.01, -0.02, 0.015, 0.005, -0.01, 0.02, -0.005, 0.008],
        "benchmarkReturns": [0.008, -0.01, 0.012, 0.004, -0.008, 0.015, -0.004, 0.006],
        "riskFreeRate": 0.03,
    }
    assert_parity(flask_client, fastapi_client, "POST", "/api/risk/metrics", json_body=body)


# ============ P6d：/api/portfolio/* legacy quant 代理（模块缺失 → 503，确定性） ============

def test_portfolio_benchmark(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "POST", "/api/portfolio/benchmark",
                  json_body={"portfolio": []})


def test_portfolio_optimize(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "POST", "/api/portfolio/optimize",
                  json_body={"symbols": ["600519"]})


def test_portfolio_correlation(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "POST", "/api/portfolio/correlation",
                  json_body={"symbols": ["600519", "000001"]})


def test_portfolio_factor_decay(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "POST", "/api/portfolio/factor-decay",
                  json_body={"factor": "rsi"})


def test_portfolio_performance_analyze(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "POST", "/api/portfolio/performance-analyze",
                  json_body={"trades": []})


def test_portfolio_signal_arbitrate(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "POST", "/api/portfolio/signal-arbitrate",
                  json_body={"signals": []})


# ============ P6d：/api/portfolio/factor-analyze ============

def test_factor_analyze_missing_factors(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "POST", "/api/portfolio/factor-analyze",
                  json_body={})


def test_factor_analyze_missing_dates(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "POST", "/api/portfolio/factor-analyze",
                  json_body={"factors": ["rsi"]})


def test_factor_analyze(flask_client, fastapi_client):
    # 底层走 alphalens/因子计算（可能含随机 fallback），只比对结构与状态码
    body = {"factors": ["rsi"], "startDate": "2024-01-01", "endDate": "2024-03-01",
            "universe": ["600519"], "useAlphalens": False}
    assert_structural_parity(flask_client, fastapi_client, "POST",
                             "/api/portfolio/factor-analyze", json_body=body)


# ============ P6d：/api/analysis/factor-report ============

def test_factor_report_missing_factors(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "POST", "/api/analysis/factor-report",
                  json_body={})


def test_factor_report_missing_dates(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "POST", "/api/analysis/factor-report",
                  json_body={"factors": ["rsi"]})


def test_factor_report(flask_client, fastapi_client):
    # 生成 HTML 报告（文件名含时间戳、依赖 alphalens），只比对结构与状态码
    body = {"factors": ["rsi"], "startDate": "2024-01-01", "endDate": "2024-03-01",
            "universe": ["600519"]}
    assert_structural_parity(flask_client, fastapi_client, "POST",
                             "/api/analysis/factor-report", json_body=body)


# ============ P6d：/api/portfolio/sector-aggregate（DB 聚合，确定性） ============

def test_sector_aggregate(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "POST", "/api/portfolio/sector-aggregate",
                  json_body={"sector_field": "sector", "limit": 5})


def test_sector_aggregate_industry(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "POST", "/api/portfolio/sector-aggregate",
                  json_body={"sector_field": "industry", "limit": 3})


def test_sector_aggregate_bad_field(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "POST", "/api/portfolio/sector-aggregate",
                  json_body={"sector_field": "bogus"})


# ============ P6d：/api/analysis/swing-points ============

def test_swing_points_missing_symbol(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "POST", "/api/analysis/swing-points",
                  json_body={})


def test_swing_points(flask_client, fastapi_client):
    body = {"symbol": "600519", "startDate": "2025-01-01", "endDate": "2026-01-01",
            "minChange": 5.0}
    assert_parity(flask_client, fastapi_client, "POST", "/api/analysis/swing-points",
                  json_body=body)
