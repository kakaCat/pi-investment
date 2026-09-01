"""misc 域 parity 测试（agent 迁移批次）

覆盖：
- risk:      /api/stock/{symbol}/risk/trade-check|position-size|stop-loss
- signal-test: record / verify / stats / run-strategy
- indicators: compare / sandbox-columns
- discovery: /api/discovery/result/{id}
- market:    /api/market/style
- orders:    /api/orders/algo-execute
"""
from tests.migration.parity import assert_parity, assert_structural_parity

SYM = "600519"

# ---- risk ----
TRADE_CHECK = f"/api/stock/{SYM}/risk/trade-check"
POSITION_SIZE = f"/api/stock/{SYM}/risk/position-size"
STOP_LOSS = f"/api/stock/{SYM}/risk/stop-loss"


def test_trade_check_missing_params(fastapi_client):
    assert_parity(fastapi_client, "POST", TRADE_CHECK, json_body={})


def test_trade_check_ok(fastapi_client):
    assert_parity(fastapi_client, "POST", TRADE_CHECK,
                  json_body={"action": "BUY", "price": 100, "shares": 200})


def test_position_size_missing_price(fastapi_client):
    assert_parity(fastapi_client, "POST", POSITION_SIZE, json_body={})


def test_position_size_ok(fastapi_client):
    assert_parity(fastapi_client, "POST", POSITION_SIZE,
                  json_body={"price": 100, "account_value": 200000, "risk_percent": 2.0})


def test_stop_loss_missing_entry(fastapi_client):
    assert_parity(fastapi_client, "POST", STOP_LOSS, json_body={})


def test_stop_loss_ok(fastapi_client):
    assert_parity(fastapi_client, "POST", STOP_LOSS,
                  json_body={"entry_price": 100, "method": "percentage"})


# ---- signal-test ----
ST_RECORD = "/api/signal-test/record"
ST_VERIFY = "/api/signal-test/verify"
ST_STATS = "/api/signal-test/stats"
ST_RUN = "/api/signal-test/run-strategy"


def test_signal_record_missing_fields(fastapi_client):
    assert_parity(fastapi_client, "POST", ST_RECORD, json_body={"symbol": SYM})


def test_signal_verify(fastapi_client):
    # days_after 极大 → 不会实际改动 pending 记录，两次调用结果确定
    assert_parity(fastapi_client, "POST", ST_VERIFY, json_body={"days_after": 999999})


def test_signal_stats(fastapi_client):
    assert_parity(fastapi_client, "GET", ST_STATS)


def test_signal_run_missing_symbol(fastapi_client):
    assert_parity(fastapi_client, "POST", ST_RUN, json_body={})


def test_signal_run_no_klines(fastapi_client):
    assert_parity(fastapi_client, "POST", ST_RUN,
                  json_body={"symbol": "NOEXIST999"})


# ---- indicators ----
IND_COMPARE = "/api/indicators/compare"
IND_SANDBOX = "/api/indicators/sandbox-columns"


def test_indicators_compare_missing_fields(fastapi_client):
    assert_parity(fastapi_client, "POST", IND_COMPARE, json_body={})


def test_indicators_compare_bad_ids(fastapi_client):
    assert_parity(fastapi_client, "POST", IND_COMPARE, json_body={
        "indicator_id_a": "abc", "indicator_id_b": 2, "symbol": SYM,
        "start_date": "2024-01-01", "end_date": "2024-12-31"})


def test_indicators_compare_not_found(fastapi_client):
    assert_parity(fastapi_client, "POST", IND_COMPARE, json_body={
        "indicator_id_a": 99999991, "indicator_id_b": 99999992, "symbol": SYM,
        "start_date": "2024-01-01", "end_date": "2024-12-31"})


def test_sandbox_columns_missing_symbol(fastapi_client):
    assert_parity(fastapi_client, "GET", IND_SANDBOX)


def test_sandbox_columns_no_data(fastapi_client):
    assert_parity(fastapi_client, "GET", IND_SANDBOX, params={"symbol": "NOEXIST999"})


# ---- discovery ----
def test_discovery_result_not_found(fastapi_client):
    assert_parity(fastapi_client, "GET", "/api/discovery/result/nonexistent_run_id")


# ---- market style ----
def test_market_style(fastapi_client):
    assert_parity(fastapi_client, "GET", "/api/market/style", params={"lookback_days": 60})


# ---- orders algo-execute ----
ALGO = "/api/orders/algo-execute"


def test_algo_execute_missing_params(fastapi_client):
    assert_parity(fastapi_client, "POST", ALGO, json_body={})


def test_algo_execute_bad_side(fastapi_client):
    assert_parity(fastapi_client, "POST", ALGO, json_body={
        "symbol": SYM, "side": "hold", "quantity": 1000, "algo": "TWAP"})


def test_algo_execute_bad_algo(fastapi_client):
    assert_parity(fastapi_client, "POST", ALGO, json_body={
        "symbol": SYM, "side": "buy", "quantity": 1000, "algo": "ABC"})


def test_algo_execute_bad_quantity(fastapi_client):
    assert_parity(fastapi_client, "POST", ALGO, json_body={
        "symbol": SYM, "side": "buy", "quantity": 0, "algo": "TWAP"})


def test_algo_execute_bad_start_time(fastapi_client):
    assert_parity(fastapi_client, "POST", ALGO, json_body={
        "symbol": SYM, "side": "buy", "quantity": 1000, "algo": "TWAP", "start_time": "9点30"})


def test_algo_execute_twap_ok(fastapi_client):
    assert_structural_parity(fastapi_client, "POST", ALGO, json_body={
        "symbol": SYM, "side": "buy", "quantity": 10000, "algo": "TWAP", "duration_minutes": 30})


def test_algo_execute_vwap_ok(fastapi_client):
    assert_structural_parity(fastapi_client, "POST", ALGO, json_body={
        "symbol": SYM, "side": "sell", "quantity": 9000, "algo": "VWAP", "duration_minutes": 20})
