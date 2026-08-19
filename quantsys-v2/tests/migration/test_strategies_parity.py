"""strategies + strategy 域 parity 测试（P2a）

注：测试库 strategy_configs 表结构偏旧（缺 is_public 列），strategy_service
会捕获该错误并返回空列表——Flask 与 FastAPI 调用同一 service 得到相同结果，
因此 parity 仍能有效验证路由层的响应塑形是否一致。
"""
import pytest
from tests.migration.parity import assert_parity

LIST = "/api/strategies/list"
DETAIL = "/api/strategies/detail/999999"      # 不存在 → 两边都 404
PERF = "/api/strategies/performance/999999"   # 不存在 → 两边都 404
CREATE = "/api/strategies/create"
OPTIMIZE = "/api/strategies/optimize"
STRATEGY_STATUS = "/api/strategy/status"


# ---- strategies.py GET（只读）----
def test_list_user(fastapi_client):
    assert_parity(fastapi_client, "GET", LIST, params={"page": 1, "pageSize": 5})


def test_list_builtin(fastapi_client):
    # builtin 模式走 StrategyFactory（不依赖 DB），是真实数据的 parity 验证
    assert_parity(fastapi_client, "GET", LIST, params={"source": "builtin"})


def test_list_invalid_code_type(fastapi_client):
    assert_parity(fastapi_client, "GET", LIST, params={"codeType": "bogus"})


def test_detail_not_found(fastapi_client):
    assert_parity(fastapi_client, "GET", DETAIL)


def test_performance_not_found(fastapi_client):
    assert_parity(fastapi_client, "GET", PERF)


# ---- strategies.py POST 校验路径（不产生真实写入）----
def test_create_missing_body(fastapi_client):
    # 空 JSON body（web 前端总是发 JSON）。注：完全不带 content-type 的裸 POST，
    # Flask get_json() 会 415→500，FastAPI Body(None)→400，属框架对畸形请求的
    # 固有差异，不在正常 API 契约内，故这里用 {} 测试真实空 body。
    assert_parity(fastapi_client, "POST", CREATE, json_body={})


def test_create_missing_name(fastapi_client):
    assert_parity(fastapi_client, "POST", CREATE, json_body={"code": "MA5"})


def test_create_invalid_code_type(fastapi_client):
    assert_parity(fastapi_client, "POST", CREATE,
                  json_body={"name": "x", "code": "y", "codeType": "bogus"})


def test_optimize_missing_params(fastapi_client):
    assert_parity(fastapi_client, "POST", OPTIMIZE, json_body={"strategyId": 1})


# ---- strategy.py GET ----
def test_strategy_status(fastapi_client):
    assert_parity(fastapi_client, "GET", STRATEGY_STATUS)
