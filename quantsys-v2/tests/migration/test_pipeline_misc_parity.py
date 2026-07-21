"""pipeline_misc + tools + training 域 parity 测试（agent 迁移）

覆盖端点：
- POST /api/cli/calibrate
- POST /api/cli/signal-generate
- GET  /api/stocks/data-full-status
- GET  /api/stocks/data-status
- GET  /api/tools/list
- GET  /api/tools/describe
- GET  /api/training/reports
- GET  /api/training/history

说明：
- /api/tools/list 与命中路由的 /api/tools/describe 为服务自省端点，
  Flask 与 FastAPI 路由集合/endpoint 命名不同属预期，用结构比对。
- /api/cli/calibrate 202 分支含随机 run_id 且会启动后台线程，
  测试用 fake 执行器替换两边线程目标（立即释放任务锁），再做结构比对。
- /api/stocks/data-full-status 依赖运行记录文件与缓存统计（易变），用结构比对。
"""
import json

import pytest

from tests.migration.parity import assert_parity, assert_structural_parity, DEFAULT_IGNORE

# check_data_integrity 响应含请求时生成的 checked_at 时间戳，比对时忽略
IGNORE_CHECKED_AT = DEFAULT_IGNORE | {'checked_at'}

CALIBRATE = "/api/cli/calibrate"
SIGNAL_GENERATE = "/api/cli/signal-generate"
DATA_FULL_STATUS = "/api/stocks/data-full-status"
DATA_STATUS = "/api/stocks/data-status"
TOOLS_LIST = "/api/tools/list"
TOOLS_DESCRIBE = "/api/tools/describe"
TRAINING_REPORTS = "/api/training/reports"
TRAINING_HISTORY = "/api/training/history"


# ---- /api/cli/calibrate ----

def test_cli_calibrate_conflict(flask_client, fastapi_client):
    """任务锁已被占用时两边均返回 409（确定性错误路径）"""
    from adapters.inbound.api.shared import acquire_task, release_task
    assert acquire_task('calibrate', '#C-PARITYTEST')
    try:
        assert_parity(flask_client, fastapi_client, "POST", CALIBRATE, json_body={})
    finally:
        release_task('calibrate', '#C-PARITYTEST')


def test_cli_calibrate_accepted(flask_client, fastapi_client, monkeypatch):
    """202 分支：fake 后台执行器（立即释放锁），结构比对"""
    from adapters.inbound.api.shared import release_task
    import adapters.inbound.api.routes.pipeline as flask_pipeline
    import adapters.inbound.fastapi_app.routes.pipeline_misc_async as fa_misc

    def fake_execute(run_id, **kwargs):
        release_task('calibrate', run_id)

    monkeypatch.setattr(flask_pipeline, '_execute_calibration', fake_execute)
    monkeypatch.setattr(fa_misc, '_execute_calibration', fake_execute)
    assert_structural_parity(flask_client, fastapi_client, "POST", CALIBRATE, json_body={})


# ---- /api/cli/signal-generate ----

def test_signal_generate_missing_strategy_id(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "POST", SIGNAL_GENERATE, json_body={})


def test_signal_generate_invalid_strategy_id(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "POST", SIGNAL_GENERATE,
                  json_body={"strategy_id": "no_such_builtin_zzz", "symbols": ["600000"]})


def test_signal_generate_sync_json(flask_client, fastapi_client):
    """同步 JSON 分支（Accept: application/json）：状态码 + 逐字段比对（剔除 generated_at）"""
    body = {"strategy_id": 1, "symbols": ["600000"]}
    headers = {"Accept": "application/json"}
    fr = flask_client.open(SIGNAL_GENERATE, method="POST", json=body, headers=headers)
    fa = fastapi_client.post(SIGNAL_GENERATE, json=body, headers=headers)
    assert fr.status_code == fa.status_code, (
        f"状态码不一致: flask={fr.status_code} fastapi={fa.status_code}")
    f_json = fr.get_json()
    fa_json = fa.json()
    assert (f_json is not None) == (fa_json is not None)
    if f_json is None:
        return
    for payload in (f_json, fa_json):
        payload.get('summary', {}).pop('generated_at', None)
        for entry in payload.get('signals', []):
            if entry.get('type') == 'signal':
                entry['data'] = '<signal>'  # 信号体可能含易变字段，只比对类型
    assert f_json == fa_json, f"响应体不一致:\nflask={f_json}\nfastapi={fa_json}"


def test_signal_generate_sync_ndjson(flask_client, fastapi_client):
    """同步 NDJSON 分支（默认 Accept）：状态码 + 行类型序列 + summary 比对"""
    body = {"strategy_id": 1, "symbols": ["600000"]}

    def parse(text):
        lines = [json.loads(l) for l in text.strip().splitlines() if l.strip()]
        for l in lines:
            if l.get('type') == 'summary':
                l['data'].pop('generated_at', None)
            elif l.get('type') == 'signal':
                l['data'] = '<signal>'
        return lines

    fr = flask_client.open(SIGNAL_GENERATE, method="POST", json=body)
    fa = fastapi_client.post(SIGNAL_GENERATE, json=body)
    assert fr.status_code == fa.status_code, (
        f"状态码不一致: flask={fr.status_code} fastapi={fa.status_code}")
    assert parse(fr.get_data(as_text=True)) == parse(fa.text)


# ---- /api/stocks/data-full-status ----

def test_data_full_status(flask_client, fastapi_client):
    assert_structural_parity(flask_client, fastapi_client, "GET", DATA_FULL_STATUS)


# ---- /api/stocks/data-status ----

def test_data_status(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "GET", DATA_STATUS,
                  params={"symbol": "600519"}, ignore_keys=IGNORE_CHECKED_AT)


def test_data_status_default_symbol(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "GET", DATA_STATUS,
                  ignore_keys=IGNORE_CHECKED_AT)


# ---- /api/tools/list ----

def test_tools_list(flask_client, fastapi_client):
    # 服务自省端点：两边路由集合不同属预期，仅结构比对
    assert_structural_parity(flask_client, fastapi_client, "GET", TOOLS_LIST)


# ---- /api/tools/describe ----

def test_tools_describe_missing_params(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "GET", TOOLS_DESCRIBE)


def test_tools_describe_unknown_name(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "GET", TOOLS_DESCRIBE,
                  params={"name": "no.such.command"})


def test_tools_describe_unknown_path(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "GET", TOOLS_DESCRIBE,
                  params={"path": "/api/nonexistent-zzz"})


def test_tools_describe_hit(flask_client, fastapi_client):
    # 命中路由时 endpoint 命名两边不同，结构比对
    assert_structural_parity(flask_client, fastapi_client, "GET", TOOLS_DESCRIBE,
                             params={"path": "/api/tools/list"})


def test_tools_describe_by_name(flask_client, fastapi_client):
    assert_structural_parity(flask_client, fastapi_client, "GET", TOOLS_DESCRIBE,
                             params={"name": "strategy.list"})


# ---- /api/training/reports & /api/training/history ----

def test_training_reports(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "GET", TRAINING_REPORTS)


def test_training_history(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "GET", TRAINING_HISTORY)
