"""portfolio / charts / factor-models 域 parity 测试（agent 迁移）"""
from tests.migration.parity import assert_parity, assert_structural_parity

# ---- portfolio 组合优化 ----
MARKOWITZ = "/api/portfolio/markowitz/optimize"
BLACK_LITTERMAN = "/api/portfolio/black-litterman/optimize"
RISK_PARITY_OPT = "/api/portfolio/risk-parity/optimize"
RISK_PARITY_DECOMP = "/api/portfolio/risk-parity/risk-decomposition"

# ---- charts 图表 ----
CHART_ACCURACY = "/api/charts/accuracy"
CHART_EQUITY = "/api/charts/equity"
CHART_COMPARISON = "/api/charts/comparison"
CHART_IMPORTANCE = "/api/charts/importance"

# ---- factor-models 因子模型 ----
FF3 = "/api/factor-models/fama-french-3/calculate"
FF5 = "/api/factor-models/fama-french-5/calculate"
CARHART = "/api/factor-models/carhart/calculate"
BARRA = "/api/factor-models/barra/calculate"

_COV_3 = [
    [0.04, 0.006, 0.003],
    [0.006, 0.09, 0.004],
    [0.003, 0.004, 0.01],
]


# ============ portfolio ============

def test_markowitz_optimize(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "POST", MARKOWITZ, json_body={
        "expected_returns": [0.10, 0.15, 0.08],
        "covariance_matrix": _COV_3,
        "method": "max_sharpe",
        "risk_free_rate": 0.02,
    })


def test_markowitz_optimize_missing_params(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "POST", MARKOWITZ, json_body={})


def test_black_litterman_optimize(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "POST", BLACK_LITTERMAN, json_body={
        "market_weights": [0.5, 0.3, 0.2],
        "covariance_matrix": _COV_3,
        "views": [
            {"weights": [1.0, 0.0, 0.0], "return": 0.12, "confidence": 0.5}
        ],
    })


def test_black_litterman_optimize_missing_params(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "POST", BLACK_LITTERMAN, json_body={})


def test_risk_parity_optimize(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "POST", RISK_PARITY_OPT, json_body={
        "covariance_matrix": _COV_3,
    })


def test_risk_parity_optimize_missing_params(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "POST", RISK_PARITY_OPT, json_body={})


def test_risk_parity_decomposition(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "POST", RISK_PARITY_DECOMP, json_body={
        "weights": [0.4, 0.35, 0.25],
        "covariance_matrix": _COV_3,
    })


def test_risk_parity_decomposition_missing_params(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "POST", RISK_PARITY_DECOMP, json_body={})


# ============ charts ============

def test_chart_accuracy(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "GET", CHART_ACCURACY, params={"days": 30})


def test_chart_equity(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "GET", CHART_EQUITY)


def test_chart_comparison(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "GET", CHART_COMPARISON)


def test_chart_importance(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "GET", CHART_IMPORTANCE, params={"top_n": 10})


# ============ factor-models ============

def test_ff3_missing_symbol(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "POST", FF3, json_body={})


def test_ff3_with_symbol(flask_client, fastapi_client):
    # 数据是否充足取决于测试库；两侧共享同一 ds/DB，结果必然一致
    assert_parity(flask_client, fastapi_client, "POST", FF3, json_body={
        "symbol": "600519.SH",
        "start_date": "2024-01-01",
        "end_date": "2024-12-31",
    })


def test_ff5_missing_symbol(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "POST", FF5, json_body={})


def test_ff5_with_symbol(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "POST", FF5, json_body={
        "symbol": "600519.SH",
        "start_date": "2024-01-01",
        "end_date": "2024-12-31",
    })


def test_carhart_missing_symbol(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "POST", CARHART, json_body={})


def test_carhart_with_symbol(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "POST", CARHART, json_body={
        "symbol": "600519.SH",
        "start_date": "2024-01-01",
        "end_date": "2024-12-31",
    })


def test_barra_stub(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "POST", BARRA, json_body={"symbol": "600519.SH"})
