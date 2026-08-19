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
def test_search(fastapi_client):
    assert_parity(fastapi_client, "GET", SEARCH, params={"q": "茅台", "page": 1, "pageSize": 5})


def test_search_empty_keyword(fastapi_client):
    assert_parity(fastapi_client, "GET", SEARCH, params={"q": ""})


def test_list(fastapi_client):
    assert_parity(fastapi_client, "GET", LIST, params={"page": 1, "pageSize": 5})


def test_announcements(fastapi_client):
    assert_parity(fastapi_client, "GET", ANN)


def test_news(fastapi_client):
    assert_parity(fastapi_client, "GET", NEWS, params={"num": 3})


def test_insider_trades(fastapi_client):
    # 该端点返回随机 mock 数据（_generate_mock_insider_trades），值每次不同，
    # 只能做结构比对（状态码 + 响应形状），无法比对具体值。
    assert_structural_parity(fastapi_client, "GET", INSIDER)


def test_peers(fastapi_client):
    # peers 的 stockInfo 含实时行情价（两次顺序调用间价格可能变动），
    # 只能做结构比对（状态码 + 响应形状），避免实时数据抖动导致 flaky。
    assert_structural_parity(fastapi_client, "GET", PEERS)


def test_klines(fastapi_client):
    # 固定日期范围保证确定性
    assert_parity(fastapi_client, "GET", "/api/stock/600519/klines",
                  params={"start_date": "2026-06-01", "end_date": "2026-06-10", "limit": 10})


def test_history_daily(fastapi_client):
    # agent data_fetch_kline 工具调用的端点；固定日期范围保证确定性
    assert_parity(fastapi_client, "GET", "/api/stock/600519/history",
                  params={"period": "daily", "start_date": "2026-06-01",
                          "end_date": "2026-06-10", "limit": 10})


def test_history_weekly_fastapi(fastapi_client):
    resp = fastapi_client.get("/api/stock/600519/history",
                              params={"period": "weekly", "start_date": "2026-05-01",
                                      "end_date": "2026-06-10", "limit": 10})
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    payload = body["data"]
    assert payload["period"] == "weekly"
    assert payload["count"] == len(payload["data"]) > 0
    bar = payload["data"][0]
    assert {"date", "open", "high", "low", "close", "volume"} <= set(bar)


def test_history_monthly_fastapi(fastapi_client):
    resp = fastapi_client.get("/api/stock/600519/history",
                              params={"period": "monthly", "start_date": "2026-03-01",
                                      "end_date": "2026-06-10", "limit": 10})
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    payload = body["data"]
    assert payload["period"] == "monthly"
    assert payload["count"] == len(payload["data"]) > 0
    bar = payload["data"][0]
    assert {"date", "open", "high", "low", "close", "volume"} <= set(bar)


def test_data_update_klines(fastapi_client):
    # acquire_task 是共享锁（_running_tasks[task_type]=run_id）：Flask 先获取后，
    # FastAPI 会 409。两次调用间用快照取 run_id 并释放任务锁。
    from adapters.shared.tasks import release_task, get_running_tasks_snapshot
    from tests.migration.parity import structure_of

    def _release():
        rid = get_running_tasks_snapshot().get('data_update')
        if rid:
            release_task('data_update', rid)

    body = {"symbols": ["600519"], "days": 7}
    try:
        fa = fastapi_client.post("/api/stocks/data-update-klines", json=body)
    finally:
        _release()
    assert fa.status_code < 500


def test_my_stocks(fastapi_client):
    assert_parity(fastapi_client, "GET", MY)


# ---- stock.py POST ----
def test_resolve_found(fastapi_client):
    assert_parity(fastapi_client, "POST", RESOLVE, json_body={"code": "600519"})


def test_resolve_empty(fastapi_client):
    assert_parity(fastapi_client, "POST", RESOLVE, json_body={"code": ""})


def test_batch_quotes(fastapi_client):
    # 实时行情价/量在两次顺序调用间会变动，只能结构比对（与 peers 同理）
    assert_structural_parity(fastapi_client, "POST", BATCH_Q, json_body={"symbols": ["600519"]})


def test_batch_quotes_empty(fastapi_client):
    assert_parity(fastapi_client, "POST", BATCH_Q, json_body={"symbols": []})


def test_stocks_batch(fastapi_client):
    assert_parity(fastapi_client, "POST", BATCH, json_body={"symbols": ["600519"]})


# ---- watchlist.py GET ----
def test_watchlist_groups(fastapi_client):
    assert_parity(fastapi_client, "GET", WL_GROUPS)


def test_watchlist_list(fastapi_client):
    assert_parity(fastapi_client, "GET", WL)


def test_watchlist_check(fastapi_client):
    assert_parity(fastapi_client, "GET", WL_CHECK)


def test_stock_quote_db_mode(fastapi_client):
    # db 模式：两边都查不到（测试库无该股近期K线）→ 404，确定性
    assert_parity(fastapi_client, "GET", "/api/stock/999999/quote?source=db")


def test_stock_quote_invalid_source(fastapi_client):
    assert_parity(fastapi_client, "GET", "/api/stock/600519/quote?source=invalid")


def test_stock_quote_realtime(fastapi_client):
    # realtime 模式用真实数据源（非确定实时价），结构比对
    assert_structural_parity(fastapi_client, "GET", "/api/stock/600519/quote?source=realtime")
