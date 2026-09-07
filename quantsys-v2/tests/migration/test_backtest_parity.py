"""backtest 域 parity 测试（Flask backtest.py 迁移）

覆盖端点：
- GET  /api/backtest/results
- POST /api/backtest/run
- GET  /api/performance/strategy/{id}
- GET  /api/performance/comparison
- POST /api/backtest/strategy
- POST /api/backtest/combo

说明：
- 真实回测运行依赖测试库数据且 /api/backtest/run 会写库（_backtest_id 每次不同），
  成功路径只比对结构与状态码（assert_structural_parity）。
- /api/backtest/combo 的 Flask 处理器首行
  `from adapters.inbound.api.shared import combo_backtest_service` 当前必抛
  ImportError（shared 中无此名），Flask 返回 500（非 JSON），FastAPI 全局异常
  处理器同样返回 500，只能按状态码比对（契约冻结，不修复既有 bug）。
"""
import pytest
from tests.migration.parity import assert_parity, assert_structural_parity

RESULTS = "/api/backtest/results"
RUN = "/api/backtest/run"
PERF_STRATEGY = "/api/performance/strategy/1"
PERF_COMPARISON = "/api/performance/comparison"
STRATEGY = "/api/backtest/strategy"
COMBO = "/api/backtest/combo"


# ============ GET /api/backtest/results（DB 查询，确定性） ============

def test_results_default(fastapi_client):
    assert_parity(fastapi_client, "GET", RESULTS)


def test_results_with_limit(fastapi_client):
    assert_parity(fastapi_client, "GET", RESULTS, params={"limit": 5})


def test_results_with_strategy(fastapi_client):
    assert_parity(fastapi_client, "GET", RESULTS,
                  params={"strategy": "nonexistent_strategy"})


def test_results_with_strategy_and_symbol(fastapi_client):
    assert_parity(fastapi_client, "GET", RESULTS,
                  params={"strategy": "nonexistent_strategy", "symbol": "600519"})


# ============ GET /api/performance/strategy/{id}（DB 查询，确定性） ============

def test_performance_strategy(fastapi_client):
    assert_parity(fastapi_client, "GET", PERF_STRATEGY)


def test_performance_strategy_nonexistent(fastapi_client):
    assert_parity(fastapi_client, "GET", "/api/performance/strategy/999999")


# ============ GET /api/performance/comparison（DB 聚合，确定性） ============

def test_performance_comparison(fastapi_client):
    assert_parity(fastapi_client, "GET", PERF_COMPARISON)


def test_performance_comparison_with_days(fastapi_client):
    assert_parity(fastapi_client, "GET", PERF_COMPARISON, params={"days": 7})


# ============ POST /api/backtest/run ============

def test_run_empty_body(fastapi_client):
    assert_parity(fastapi_client, "POST", RUN, json_body={})


def test_run_missing_fields(fastapi_client):
    assert_parity(fastapi_client, "POST", RUN,
                  json_body={"strategy_id": 1})


def test_run_invalid_strategy_id(fastapi_client):
    body = {"strategy_id": "abc", "symbol": "600519",
            "start_date": "2025-01-01", "end_date": "2025-06-01"}
    assert_parity(fastapi_client, "POST", RUN, json_body=body)


def test_run_nonexistent_strategy(fastapi_client):
    # 策略不存在 → 底层服务确定性报错（两侧同一代码路径）
    body = {"strategy_id": 999999, "symbol": "600519",
            "start_date": "2025-01-01", "end_date": "2025-06-01"}
    assert_parity(fastapi_client, "POST", RUN, json_body=body)


# ============ POST /api/backtest/strategy ============

def test_strategy_empty_body(fastapi_client):
    assert_parity(fastapi_client, "POST", STRATEGY, json_body={})


def test_strategy_missing_fields(fastapi_client):
    assert_parity(fastapi_client, "POST", STRATEGY,
                  json_body={"strategy_id": 1})


def test_strategy_invalid_strategy_id(fastapi_client):
    body = {"strategy_id": "abc", "symbol": "600519",
            "start_date": "2025-01-01", "end_date": "2025-06-01"}
    assert_parity(fastapi_client, "POST", STRATEGY, json_body=body)


def test_strategy_nonexistent_strategy(fastapi_client):
    body = {"strategy_id": 999999, "symbol": "600519",
            "start_date": "2025-01-01", "end_date": "2025-06-01"}
    assert_parity(fastapi_client, "POST", STRATEGY, json_body=body)


# ============ POST /api/backtest/combo（Flask 既有 ImportError → 500，按状态码比对） ============

def test_combo_empty_body(fastapi_client):
    assert_parity(fastapi_client, "POST", COMBO, json_body={})


def test_combo_invalid_mode(fastapi_client):
    body = {"mode": "bogus", "strategies": [1], "symbols": ["600519"]}
    assert_parity(fastapi_client, "POST", COMBO, json_body=body)
