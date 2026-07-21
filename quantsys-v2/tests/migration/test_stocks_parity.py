"""stocks + watchlist 域 parity 测试"""
import pytest
from tests.migration.parity import assert_parity, assert_structural_parity

SEARCH = "/api/stocks/search"
LIST = "/api/stocks/list"
RESOLVE = "/api/stocks/resolve"
ANN = "/api/stock/600519/announcements"
NEWS = "/api/stock/600519/news"
BATCH_Q = "/api/stocks/batch-quotes"
INSIDER = "/api/stock/600519/insider-trades"
PEERS = "/api/stock/600519/peers"
MY = "/api/stocks/my-stocks"
BATCH = "/api/stocks/batch"
WL = "/api/stocks/watchlist"
WL_GROUPS = "/api/stocks/watchlist/groups"
WL_CHECK = "/api/stocks/watchlist/600519/check"


# ---- stock.py GET ----
def test_search(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "GET", SEARCH, params={"q": "茅台", "page": 1, "pageSize": 5})


def test_search_empty_keyword(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "GET", SEARCH, params={"q": ""})


def test_list(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "GET", LIST, params={"page": 1, "pageSize": 5})


def test_announcements(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "GET", ANN)


def test_news(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "GET", NEWS, params={"num": 3})


def test_insider_trades(flask_client, fastapi_client):
    # 该端点返回随机 mock 数据（_generate_mock_insider_trades），值每次不同，
    # 只能做结构比对（状态码 + 响应形状），无法比对具体值。
    assert_structural_parity(flask_client, fastapi_client, "GET", INSIDER)


def test_peers(flask_client, fastapi_client):
    # peers 的 stockInfo 含实时行情价（两次顺序调用间价格可能变动），
    # 只能做结构比对（状态码 + 响应形状），避免实时数据抖动导致 flaky。
    assert_structural_parity(flask_client, fastapi_client, "GET", PEERS)


def test_klines(flask_client, fastapi_client):
    # 固定日期范围保证确定性
    assert_parity(flask_client, fastapi_client, "GET", "/api/stock/600519/klines",
                  params={"start_date": "2026-06-01", "end_date": "2026-06-10", "limit": 10})


def test_data_update_klines(flask_client, fastapi_client):
    # acquire_task 是共享锁（_running_tasks[task_type]=run_id）：Flask 先获取后，
    # FastAPI 会 409。两次调用间用快照取 run_id 并释放任务锁。
    from adapters.inbound.api.shared import release_task, get_running_tasks_snapshot
    from tests.migration.parity import structure_of

    def _release():
        rid = get_running_tasks_snapshot().get('data_update')
        if rid:
            release_task('data_update', rid)

    body = {"symbols": ["600519"], "days": 7}
    try:
        fr = flask_client.open("/api/stocks/data-update-klines", method="POST", json=body)
    finally:
        _release()
    try:
        fa = fastapi_client.post("/api/stocks/data-update-klines", json=body)
    finally:
        _release()
    assert fa.status_code == fr.status_code
    assert structure_of(fa.json()) == structure_of(fr.get_json())


def test_my_stocks(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "GET", MY)


# ---- stock.py POST ----
def test_resolve_found(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "POST", RESOLVE, json_body={"code": "600519"})


def test_resolve_empty(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "POST", RESOLVE, json_body={"code": ""})


def test_batch_quotes(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "POST", BATCH_Q, json_body={"symbols": ["600519"]})


def test_batch_quotes_empty(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "POST", BATCH_Q, json_body={"symbols": []})


def test_stocks_batch(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "POST", BATCH, json_body={"symbols": ["600519"]})


# ---- watchlist.py GET ----
def test_watchlist_groups(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "GET", WL_GROUPS)


def test_watchlist_list(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "GET", WL)


def test_watchlist_check(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "GET", WL_CHECK)
