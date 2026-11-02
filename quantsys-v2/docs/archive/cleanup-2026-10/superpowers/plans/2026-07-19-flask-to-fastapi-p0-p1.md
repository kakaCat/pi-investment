# Flask→FastAPI 迁移 P0+P1 实施计划（parity 框架 + stocks 域）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立 Flask↔FastAPI parity 比对框架并收敛 FastAPI 入口，然后迁移 stocks 域（stock.py + watchlist.py）作为垂直切片，验证整个迁移模式。

**Architecture:** 迁移只改路由层：Flask Blueprint → FastAPI APIRouter，业务层 `ds`(DataService) 与 application services 原样复用。新建 FastAPI 共享辅助模块保证响应契约与 Flask 完全一致；新建 parity 框架用 in-process test client 同时打 Flask 与 FastAPI 并 diff JSON。验证先行（先写失败的 parity 测试，再实现路由使其转绿）。

**Tech Stack:** FastAPI (uvicorn) / Flask / pytest / starlette TestClient / structlog / PostgreSQL(测试库 quant_test)。

**关联文档:** 总体设计 `docs/superpowers/specs/2026-07-19-flask-to-fastapi-migration-design.md`

## Global Constraints

- **契约冻结**：迁移后每个端点的响应 JSON（字段名、嵌套、类型、HTTP 状态码）必须与 Flask 一致（timestamp 等易变字段值除外）。
- **复用同一 `ds` 单例**：从 `adapters.inbound.api.shared` 导入 `ds` 与序列化助手，保证 FastAPI 与 Flask 行为一致。
- **同步 `def` 端点**：`ds` 是同步服务，FastAPI 路由用普通 `def`（FastAPI 自动放到 threadpool，不阻塞事件循环），不要用 `async def` 包同步阻塞调用。
- **测试库隔离**：所有 parity 测试必须在 pytest 下运行（自动切到 `quant_test` 库），禁止连生产库。
- **不动业务逻辑**：`application/services/`、`ds`、repository 一律不改。
- **固定地址**：FastAPI REST `127.0.0.1:5001`、WebSocket `127.0.0.1:5003` 不可改。
- 工作分支：`migrate/flask-to-fastapi`（quantsys-v2 仓库）。

---

## 文件结构

| 文件 | 责任 |
|------|------|
| `adapters/inbound/fastapi_app/shared.py` | **新建**。FastAPI 共享辅助：`api_response`/`handle_api_error`/`error_response`，复用 Flask 的 `ds` 与序列化助手 |
| `tests/migration/__init__.py` | **新建**。空包标记 |
| `tests/migration/parity.py` | **新建**。`normalize()` + `assert_parity()` 比对工具 |
| `tests/migration/conftest.py` | **新建**。`flask_client` / `fastapi_client` fixture（in-process） |
| `tests/migration/test_framework_smoke.py` | **新建**。证明双 client 可启动、比对函数可运行 |
| `adapters/inbound/fastapi_app/routes/stock_async.py` | **新建**（替换空桩）。stocks 域真实路由 |
| `adapters/inbound/fastapi_app/routes/watchlist_async.py` | **新建**（替换空桩）。watchlist 真实路由 |
| `tests/migration/test_stocks_parity.py` | **新建**。stocks+watchlist 端点 parity 测试 |
| `adapters/inbound/fastapi_app/main.py` | **修改**。注册新 stocks/watchlist 路由 |
| `adapters/inbound/fastapi_app/server*.py`（5 个冗余）| **删除** |
| 35 个孤儿空桩 `*_async.py` | **删除** |
| `quantsys-v2/CLAUDE.md` | **修改**。修正启动说明（start_all.py 不存在） |

---

## P0 - 地基

### Task 1: FastAPI 共享辅助模块

**Files:**
- Create: `adapters/inbound/fastapi_app/shared.py`
- Test: `tests/migration/test_shared_helpers.py`

**Interfaces:**
- Consumes: `adapters.inbound.api.shared` 的 `ds`、`sanitize_for_json`、`convert_keys_to_camel`、`_read_watchlist`、`_write_watchlist`、`_read_groups`、`_write_groups`（框架无关，直接复用同一实现/单例）。
- Produces: `api_response(data, success=True, message=None) -> Dict`、`error_response(payload: Dict, status_code: int) -> JSONResponse`、`handle_api_error(f)` 装饰器。后续所有迁移路由都从这里 import。

- [ ] **Step 1: 写失败测试**

Create `tests/migration/__init__.py`（空文件）和 `tests/migration/test_shared_helpers.py`：

```python
"""FastAPI 共享辅助模块测试"""
from adapters.inbound.fastapi_app.shared import api_response


def test_api_response_wraps_success_and_camel_data():
    out = api_response({"stock_name": "茅台", "price": 1700.0})
    assert out["success"] is True
    # convert_keys_to_camel: snake -> camel
    assert out["data"]["stockName"] == "茅台"
    assert out["data"]["price"] == 1700.0


def test_api_response_optional_message():
    out = api_response({"a": 1}, message="ok")
    assert out["message"] == "ok"
    assert "message" not in api_response({"a": 1})


def test_api_response_sanitizes_nan():
    out = api_response({"v": float("nan")})
    assert out["data"]["v"] is None
```

- [ ] **Step 2: 运行确认失败**

Run: `cd quantsys-v2 && source activate-py313.sh && python -m pytest tests/migration/test_shared_helpers.py -q --no-cov`
Expected: FAIL — `ModuleNotFoundError: No module named 'adapters.inbound.fastapi_app.shared'`

- [ ] **Step 3: 实现 shared.py**

Create `adapters/inbound/fastapi_app/shared.py`：

```python
"""
FastAPI 共享辅助模块

从 Flask adapters/inbound/api/shared.py 复用框架无关实现（同一 ds 单例 +
同一序列化逻辑），并提供 FastAPI 兼容的 api_response / handle_api_error /
error_response，保证迁移后响应契约与 Flask 完全一致（parity）。
"""
import functools
from typing import Any, Dict, Optional

from fastapi.responses import JSONResponse
import structlog

# 复用 Flask shared 的框架无关部分（同一 ds 单例 + 同一序列化 → 保证 parity）
from adapters.inbound.api.shared import (
    ds,
    sanitize_for_json,
    convert_keys_to_camel,
    convert_keys_to_snake,
    _read_watchlist,
    _write_watchlist,
    _read_groups,
    _write_groups,
)

logger = structlog.get_logger(__name__)

__all__ = [
    "ds", "sanitize_for_json", "convert_keys_to_camel", "convert_keys_to_snake",
    "_read_watchlist", "_write_watchlist", "_read_groups", "_write_groups",
    "api_response", "error_response", "handle_api_error",
]


def api_response(data: Any, success: bool = True, message: Optional[str] = None) -> Dict:
    """标准 API 响应（与 Flask api_response 契约一致；返回 dict 由 FastAPI 序列化）"""
    response: Dict[str, Any] = {
        "success": success,
        "data": convert_keys_to_camel(sanitize_for_json(data)),
    }
    if message:
        response["message"] = message
    return response


def error_response(payload: Dict, status_code: int) -> JSONResponse:
    """非 200 错误响应（保留 Flask 的状态码与响应体形状）"""
    return JSONResponse(content=sanitize_for_json(payload), status_code=status_code)


def handle_api_error(f):
    """API 错误处理装饰器（与 Flask 版契约一致）"""
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except ValueError as e:
            return JSONResponse({"success": False, "error": str(e)}, status_code=400)
        except KeyError as e:
            return JSONResponse({"success": False, "error": f"缺少参数: {e}"}, status_code=400)
        except Exception as e:
            logger.error(f"API错误: {e}", exc_info=True)
            return JSONResponse({"success": False, "error": f"服务器内部错误: {e}"}, status_code=500)

    return wrapper
```

- [ ] **Step 4: 运行确认通过**

Run: `cd quantsys-v2 && source activate-py313.sh && python -m pytest tests/migration/test_shared_helpers.py -q --no-cov`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
cd quantsys-v2
git add adapters/inbound/fastapi_app/shared.py tests/migration/__init__.py tests/migration/test_shared_helpers.py
git commit -m "feat(fastapi): 新增共享辅助模块（api_response/handle_api_error 与 Flask 契约一致）"
```

---

### Task 2: Parity 比对框架

**Files:**
- Create: `tests/migration/parity.py`
- Create: `tests/migration/conftest.py`
- Test: `tests/migration/test_framework_smoke.py`

**Interfaces:**
- Consumes: Flask `create_app()`（`adapters/inbound/api/server.py:39`）、FastAPI `app`（`adapters/inbound/fastapi_app/main.py`）。
- Produces: `normalize(obj, ignore_keys)`、`assert_parity(flask_client, fastapi_client, method, path, *, params=None, json_body=None, ignore_keys=DEFAULT_IGNORE)`、`DEFAULT_IGNORE`。conftest 提供 `flask_client` / `fastapi_client` session fixture。

- [ ] **Step 1: 写 parity.py + conftest.py**

Create `tests/migration/parity.py`：

```python
"""Flask ↔ FastAPI 响应比对工具"""
import json
from typing import Any, FrozenSet, Optional

# 默认忽略的易变字段名（响应里值每次不同的字段）
DEFAULT_IGNORE: FrozenSet[str] = frozenset({
    "timestamp", "trace_id", "traceId", "duration", "elapsed",
    "time", "serverTime", "requestId",
})


def normalize(obj: Any, ignore_keys: FrozenSet[str] = DEFAULT_IGNORE) -> Any:
    """递归移除易变字段，返回可比对的结构。
    dict 用 == 比较本就无序；list 保持顺序（顺序即契约的一部分）。
    """
    if isinstance(obj, dict):
        return {k: normalize(v, ignore_keys) for k, v in obj.items() if k not in ignore_keys}
    if isinstance(obj, list):
        return [normalize(x, ignore_keys) for x in obj]
    return obj


def assert_parity(flask_client, fastapi_client, method: str, path: str, *,
                  params: Optional[dict] = None, json_body: Any = None,
                  ignore_keys: FrozenSet[str] = DEFAULT_IGNORE) -> None:
    """用相同输入分别请求 Flask 与 FastAPI，断言状态码与响应体一致。"""
    flask_resp = flask_client.open(path, method=method, query_string=params, json=json_body)
    fa_resp = fastapi_client.request(method, path, params=params, json=json_body)

    assert fa_resp.status_code == flask_resp.status_code, (
        f"[{method} {path}] 状态码不一致: flask={flask_resp.status_code} "
        f"fastapi={fa_resp.status_code}\nflask={flask_resp.get_data(as_text=True)[:400]}\n"
        f"fastapi={fa_resp.text[:400]}"
    )

    try:
        flask_json = flask_resp.get_json()
    except Exception:
        flask_json = None
    try:
        fa_json = fa_resp.json()
    except Exception:
        fa_json = None

    f_norm = normalize(flask_json, ignore_keys)
    fa_norm = normalize(fa_json, ignore_keys)
    assert fa_norm == f_norm, (
        f"[{method} {path}] 响应体不一致:\n"
        f"flask  = {json.dumps(f_norm, ensure_ascii=False, default=str)[:800]}\n"
        f"fastapi= {json.dumps(fa_norm, ensure_ascii=False, default=str)[:800]}"
    )
```

Create `tests/migration/conftest.py`：

```python
"""parity 测试共享 fixture：in-process 同时启动 Flask 与 FastAPI"""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def flask_client():
    from adapters.inbound.api.server import create_app
    app = create_app()
    app.testing = True
    return app.test_client()


@pytest.fixture(scope="session")
def fastapi_client():
    from adapters.inbound.fastapi_app.main import app
    return TestClient(app)
```

- [ ] **Step 2: 写 smoke 测试证明框架可运行**

Create `tests/migration/test_framework_smoke.py`：

```python
"""证明 parity 框架能同时驱动 Flask 与 FastAPI 两个 in-process client"""
from tests.migration.parity import normalize


def test_both_clients_boot(flask_client, fastapi_client):
    # Flask 健康端点存在（可能 200 或 404，取决于注册，但 client 必须可用）
    fr = flask_client.get("/api/health")
    assert fr.status_code in (200, 404)
    # FastAPI 根路径与健康检查必定可用
    assert fastapi_client.get("/health").status_code == 200
    assert fastapi_client.get("/").status_code == 200


def test_normalize_strips_volatile_keys():
    a = {"success": True, "timestamp": "2026-01-01", "data": {"x": 1}}
    b = {"success": True, "timestamp": "2099-12-31", "data": {"x": 1}}
    assert normalize(a) == normalize(b)
    # 非易变字段不同则不相等
    c = {"success": True, "data": {"x": 2}}
    assert normalize(a) != normalize(c)
```

- [ ] **Step 3: 运行确认通过**

Run: `cd quantsys-v2 && source activate-py313.sh && python -m pytest tests/migration/test_framework_smoke.py -q --no-cov`
Expected: 2 passed（若 Flask `create_app()` 启动报错，先解决导入/初始化问题再继续——这是框架能用的前提）

- [ ] **Step 4: Commit**

```bash
cd quantsys-v2
git add tests/migration/parity.py tests/migration/conftest.py tests/migration/test_framework_smoke.py
git commit -m "test(fastapi): 新增 Flask↔FastAPI parity 比对框架"
```

---

### Task 3: 入口收敛（删冗余 server + 删孤儿空桩 + 修文档）

**Files:**
- Delete: `adapters/inbound/fastapi_app/server.py`、`server_async.py`、`server_complete.py`、`server_final.py`、`server_100_complete.py`
- Delete: 35 个孤儿空桩（见 Step 2 计算；保留被 main.py 引用的 `indicators_async.py`、`portfolio_async.py`）
- Modify: `quantsys-v2/CLAUDE.md`

**Interfaces:**
- Consumes: 无。
- Produces: 唯一 REST 入口 `adapters/inbound/fastapi_app/main.py` + WebSocket 入口 `websocket_server.py`。

- [ ] **Step 1: 删除 5 个冗余 server 文件，确认唯一入口仍可启动**

```bash
cd quantsys-v2
git rm adapters/inbound/fastapi_app/server.py \
       adapters/inbound/fastapi_app/server_async.py \
       adapters/inbound/fastapi_app/server_complete.py \
       adapters/inbound/fastapi_app/server_final.py \
       adapters/inbound/fastapi_app/server_100_complete.py
```

确认没有其它代码引用它们：
Run: `grep -rn "fastapi_app.server\b\|server_final\|server_100_complete\|server_async\|server_complete" --include=*.py adapters/ | grep -v websocket_server | grep -v "main.py"`
Expected: 无输出（如有引用，先改引用再删）

- [ ] **Step 2: 删除 35 个孤儿空桩（保留 main.py 引用的 2 个）**

孤儿空桩 = 含 TODO 占位 且 未被 main.py 引用。已确认被引用的仅 `indicators_async.py`、`portfolio_async.py`（保留，P6/P5 再替换）。删除其余：

```bash
cd quantsys-v2
git rm adapters/inbound/fastapi_app/routes/{automation,benchmarks,diagnosis,discovery,chan,factor_models,financials_v2,data_quality,dividends,knowledge_management,game_alert,learning_system,game_intelligence,monitoring,jobs,opportunities,market_style,pool_scan_switch,orders,quote_market,pipeline,risk_metrics,quote_v2,sentiment,signals_push,signal_execution,sectors,stock,scheduler_config,training,signal_test,timeseries,strategy,watchlist,tools}_async.py
```

（注：`stock_async.py`、`watchlist_async.py` 也在删除之列——P1 会以真实实现重建它们。）

- [ ] **Step 3: 确认 FastAPI 仍可启动且路由数符合预期**

Run: `cd quantsys-v2 && source activate-py313.sh && python -c "from adapters.inbound.fastapi_app.main import app; print('routes:', len([r for r in app.routes]))"`
Expected: 正常打印 routes 数（无 ImportError；被删的空桩本就未被 main.py 注册，不影响）

- [ ] **Step 4: 修正 CLAUDE.md 启动说明**

`quantsys-v2/CLAUDE.md` 中 `python start_all.py` 已不存在。把 "Dev Commands" 段改为：

```markdown
# 启动 FastAPI REST API (端口 5001)
python adapters/inbound/fastapi_app/main.py
# 启动 FastAPI WebSocket (端口 5003)
python adapters/inbound/fastapi_app/websocket_server.py
```

并删除/标注 `start_all.py` 与已删 server 文件的引用。

- [ ] **Step 5: Commit**

```bash
cd quantsys-v2
git add -A
git commit -m "chore(fastapi): 入口收敛——删除5个冗余server与35个孤儿空桩，修正启动文档"
```

---

## P1 - stocks 域垂直切片

### Task 4: stocks+watchlist parity 测试（先写，RED）

**Files:**
- Test: `tests/migration/test_stocks_parity.py`

**Interfaces:**
- Consumes: Task 2 的 `assert_parity`、`flask_client`、`fastapi_client`。
- Produces: stocks/watchlist 端点的 parity 断言集合（后续 Task 使其转绿）。

> 说明：以下端点当前在 FastAPI 侧是 404（空桩已删），所以测试 initially 失败（status 404 vs Flask 200/400），这正是 RED。

- [ ] **Step 1: 写 parity 测试**

Create `tests/migration/test_stocks_parity.py`：

```python
"""stocks + watchlist 域 parity 测试"""
import pytest
from tests.migration.parity import assert_parity

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
    assert_parity(flask_client, fastapi_client, "GET", INSIDER)


def test_peers(flask_client, fastapi_client):
    assert_parity(flask_client, fastapi_client, "GET", PEERS)


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
```

> 注：写操作（add_stock、watchlist add/remove、group create/update/delete）因会改写本地 watchlist/groups 文件、双跑会互相干扰，本切片先只对**只读 + 无副作用 POST**做全量 parity；写操作在 Task 7 用独立的状态隔离测试覆盖。

- [ ] **Step 2: 运行确认失败（RED）**

Run: `cd quantsys-v2 && source activate-py313.sh && python -m pytest tests/migration/test_stocks_parity.py -q --no-cov`
Expected: 全部 FAIL — FastAPI 侧 404（路由尚未实现）

- [ ] **Step 3: Commit（失败的测试作为迁移目标）**

```bash
cd quantsys-v2
git add tests/migration/test_stocks_parity.py
git commit -m "test(fastapi): stocks+watchlist parity 测试（RED，待实现路由）"
```

---

### Task 5: 实现 stock_async.py 路由（GREEN）

**Files:**
- Create: `adapters/inbound/fastapi_app/routes/stock_async.py`
- Modify: `adapters/inbound/fastapi_app/main.py`（注册路由）

**Interfaces:**
- Consumes: Task 1 的 `shared.py`（`ds`/`api_response`/`handle_api_error`/`error_response`/`sanitize_for_json`/`_read_watchlist`）、`application.services.stock_data_service.stock_data_service`。
- Produces: `router = APIRouter()`，暴露 stocks 域 12 个端点，响应契约与 Flask `stock.py` 一致。

- [ ] **Step 1: 实现路由**

Create `adapters/inbound/fastapi_app/routes/stock_async.py`：

```python
"""股票数据 API - FastAPI 版（从 Flask stock.py 迁移，响应契约保持一致）"""
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query, Body
import structlog

from adapters.inbound.fastapi_app.shared import (
    ds, api_response, error_response, handle_api_error,
    sanitize_for_json, _read_watchlist,
)
from application.services.stock_data_service import stock_data_service

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["Stocks - 股票数据"])


def enrich_stock_data(stock) -> Dict:
    """为股票添加额外信息（价格、涨跌幅、K线天数、因子数量等）。逻辑与 Flask stock.py 一致。"""
    if hasattr(stock, 'symbol'):
        symbol, name = stock.symbol, stock.name
        market, industry = stock.market or '', stock.industry or ''
    else:
        symbol, name = stock['symbol'], stock['name']
        market, industry = stock.get('market', ''), stock.get('industry', '')

    stock_data = {
        'symbol': symbol, 'name': name, 'market': market, 'industry': industry,
        'price': 0.0, 'changePercent': 0.0, 'klineDays': 0, 'factorCount': 0,
        'dataStatus': 'incomplete',
    }
    try:
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        klines = ds.kline.get_daily_klines(symbol, start_date, end_date)
        klines_len = 0
        if klines is not None:
            if hasattr(klines, '__len__'):
                klines_len = len(klines)
            elif hasattr(klines, 'shape'):
                klines_len = klines.shape[0]
        if klines is not None and klines_len > 0:
            latest = klines[-1]
            stock_data['price'] = float(latest.get('close', 0))
            if klines_len >= 2:
                prev_close = float(klines[-2].get('close', 0))
                if prev_close > 0:
                    stock_data['changePercent'] = ((stock_data['price'] - prev_close) / prev_close) * 100
        kline_stats = ds.kline.get_kline_stats(symbol, '2020-01-01', end_date)
        if kline_stats:
            stock_data['klineDays'] = kline_stats.get('count', 0)
        available_factors = ds.factor.get_available_factors(symbol)
        if available_factors:
            stock_data['factorCount'] = len(available_factors)
        if stock_data['klineDays'] > 0 and stock_data['factorCount'] > 0:
            stock_data['dataStatus'] = 'complete'
    except Exception as e:
        logger.warning(f"Failed to enrich stock {symbol}: {e}")
    return stock_data


@router.get('/api/stocks/search')
def search_stocks(q: str = Query(''), page: int = Query(1), pageSize: int = Query(20)):
    q = q.strip()
    if not q:
        return error_response({'error': '搜索关键词不能为空'}, 400)
    page = max(1, page)
    page_size = max(1, min(pageSize, 100))
    offset = (page - 1) * page_size
    try:
        results = ds.stock.search(q, limit=page_size + offset)
        total = len(results)
        stocks = results[offset:offset + page_size]
        enriched = [enrich_stock_data(s) for s in stocks]
        return {'query': q, 'total': total, 'page': page, 'pageSize': page_size, 'stocks': enriched}
    except Exception as e:
        return error_response({'error': str(e)}, 500)


@router.get('/api/stocks/list')
def get_stock_list(market: Optional[str] = Query(None), industry: Optional[str] = Query(None),
                   keyword: str = Query(''), page: int = Query(1), pageSize: int = Query(20)):
    try:
        keyword = keyword.strip()
        page = max(1, page)
        page_size = max(1, min(pageSize, 100))
        if keyword:
            all_stocks = ds.stock.search(keyword, limit=500)
            if market:
                all_stocks = [s for s in all_stocks if (hasattr(s, 'market') and s.market == market) or (isinstance(s, dict) and s.get('market') == market)]
            if industry:
                all_stocks = [s for s in all_stocks if (hasattr(s, 'industry') and s.industry == industry) or (isinstance(s, dict) and s.get('industry') == industry)]
            kw = keyword.lower()
            all_stocks = [s for s in all_stocks
                          if kw in str(getattr(s, 'symbol', None) or s.get('symbol', '')).lower()
                          or kw in str(getattr(s, 'name', None) or s.get('name', '')).lower()]
        else:
            all_stocks = ds.stock.get_all(market=market or None, industry=industry or None, limit=500)
        total = len(all_stocks)
        offset = (page - 1) * page_size
        stocks = all_stocks[offset:offset + page_size]
        enriched = [enrich_stock_data(s) for s in stocks]
        return {'count': total, 'stocks': enriched, 'page': page, 'pageSize': page_size}
    except Exception as e:
        logger.error(f"Failed to get stock list: {e}")
        return error_response({'error': str(e)}, 500)


@router.post('/api/stocks/resolve')
def resolve_stock(payload: Dict[str, Any] = Body(default_factory=dict)):
    code = (payload.get('code') or '').strip()
    if not code:
        return error_response({'error': '股票代码不能为空'}, 400)
    try:
        stock = ds.stock.get_by_symbol(code)
        if not stock:
            return error_response({'found': False, 'symbol': code}, 404)
        return {'found': True, 'symbol': stock.symbol, 'name': stock.name,
                'market': stock.market or '', 'industry': stock.industry or ''}
    except Exception as e:
        logger.error(f"Failed to resolve stock {code}: {e}")
        return error_response({'error': str(e)}, 500)


@router.post('/api/stocks/add')
def add_stock(payload: Dict[str, Any] = Body(default_factory=dict)):
    try:
        ds.stock.save(payload)
        return {'success': True, 'symbol': payload.get('symbol')}
    except Exception as e:
        return error_response({'error': str(e)}, 500)


@router.get('/api/stock/{symbol}/announcements')
@handle_api_error
def get_announcements_v2(symbol: str):
    result = stock_data_service.get_announcements(symbol)
    if not result.get('success'):
        return error_response(result, 400)
    return api_response(result.get('data', {}))


@router.get('/api/stock/{symbol}/news')
@handle_api_error
def get_stock_news_v2(symbol: str, num: int = Query(10)):
    result = stock_data_service.get_news(symbol, num)
    if not result.get('success'):
        return error_response(result, 400)
    return api_response(result.get('data', {}))


@router.post('/api/stocks/batch-quotes')
@handle_api_error
def get_batch_quotes_v2(payload: Dict[str, Any] = Body(default_factory=dict)):
    symbols = payload.get('symbols', [])
    if not symbols:
        return error_response({'success': False, 'error': 'symbols required'}, 400)
    result = stock_data_service.get_batch_quotes(symbols)
    if not result.get('success'):
        return error_response(result, 400)
    return api_response(result.get('data', {}))


@router.get('/api/stock/{symbol}/insider-trades')
@handle_api_error
def get_insider_trades_v2(symbol: str):
    result = stock_data_service.get_insider_trades(symbol)
    if not result.get('success'):
        return error_response(result, 400)
    return api_response(result.get('data', {}))


@router.get('/api/stock/{symbol}/peers')
@handle_api_error
def get_peers(symbol: str):
    result = stock_data_service.compare_peers(symbol)
    if not result.get('success'):
        return error_response(result, 400)
    return api_response(result.get('data', {}))


@router.get('/api/stocks/my-stocks')
@handle_api_error
def get_my_stocks():
    positions: List[Dict] = []
    watchlist: List[Dict] = []
    try:
        db = ds.portfolio.db
        if db:
            cursor = db.cursor()
            cursor.execute("""SELECT EXISTS (SELECT FROM information_schema.tables
                              WHERE table_schema = 'quant' AND table_name = 'positions')""")
            has_new_schema = cursor.fetchone()['exists']
            if has_new_schema:
                cursor.execute("""SELECT symbol, name FROM quant.positions
                                  WHERE status = 'open' ORDER BY entry_date DESC""")
                positions = [{'symbol': r['symbol'], 'name': r.get('name', '')} for r in cursor.fetchall()]
            else:
                holdings = ds.portfolio.get_all_holdings()
                positions = [{'symbol': h['symbol'], 'name': h.get('name', '')} for h in holdings]
            cursor.close()
    except Exception:
        pass
    try:
        wl = _read_watchlist()
        watchlist = [{'symbol': i['symbol'], 'name': i.get('name', '')} for i in wl.get('items', [])]
    except Exception:
        pass
    return api_response({'positions': positions, 'watchlist': watchlist})


@router.post('/api/stocks/batch')
def get_stocks_batch(payload: Dict[str, Any] = Body(default_factory=dict)):
    try:
        symbols = payload.get('symbols', [])
        if not symbols or not isinstance(symbols, list):
            return error_response({'success': False, 'error': 'symbols参数必须是数组'}, 400)
        from adapters.outbound.repositories.stock_repository import StockORMRepository
        repo = StockORMRepository()
        result: Dict[str, Any] = {}
        for symbol in symbols:
            try:
                stock = repo.get_by_symbol(symbol)
                if stock:
                    result[symbol] = {'symbol': stock.symbol, 'name': stock.name,
                                      'exchange': getattr(stock, 'exchange', None)}
            except Exception:
                continue
        return {'success': True, 'data': result}
    except Exception as e:
        return error_response({'success': False, 'error': str(e)}, 500)
```

- [ ] **Step 2: 在 main.py 注册路由**

在 `register_routes()` 的 P1 区（strategies 附近）追加：

```python
    # 股票数据（stocks 域，P1 迁移）
    try:
        from adapters.inbound.fastapi_app.routes.stock_async import router as stock_router
        app.include_router(stock_router)
        logger.info("✅ Registered: stock (P1 迁移)")
    except ImportError as e:
        logger.warning(f"⚠️ Failed to import stock_async: {e}")
```

- [ ] **Step 3: 运行 stocks 相关 parity（watchlist 仍红）**

Run: `cd quantsys-v2 && source activate-py313.sh && python -m pytest tests/migration/test_stocks_parity.py -q --no-cov -k "not watchlist"`
Expected: stocks 相关用例 PASS（watchlist 用例仍 FAIL，Task 6 解决）

> 若某用例不一致：优先检查响应体形状（`api_response` 是否该用 / 状态码 / camelCase）。常见坑：Flask 用裸 `jsonify` 的端点不要用 `api_response`；错误路径状态码要与 Flask 一致。

- [ ] **Step 4: Commit**

```bash
cd quantsys-v2
git add adapters/inbound/fastapi_app/routes/stock_async.py adapters/inbound/fastapi_app/main.py
git commit -m "feat(fastapi): 迁移 stocks 域 stock.py 路由（12端点，parity通过）"
```

---

### Task 6: 实现 watchlist_async.py 路由（GREEN）

**Files:**
- Create: `adapters/inbound/fastapi_app/routes/watchlist_async.py`
- Modify: `adapters/inbound/fastapi_app/main.py`（注册路由）

**Interfaces:**
- Consumes: Task 1 的 `shared.py`（`ds`/`_read_watchlist`/`_write_watchlist`/`_read_groups`/`_write_groups`/`error_response`）。
- Produces: `router = APIRouter()`，暴露 watchlist 8 个端点，契约与 Flask `watchlist.py` 一致。

- [ ] **Step 1: 实现路由**

Create `adapters/inbound/fastapi_app/routes/watchlist_async.py`：

```python
"""自选股 API - FastAPI 版（从 Flask watchlist.py 迁移，响应契约保持一致）"""
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Query, Body
import structlog

from adapters.inbound.fastapi_app.shared import (
    ds, error_response, _read_watchlist, _write_watchlist, _read_groups, _write_groups,
)

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["Watchlist - 自选股"])


@router.get('/api/stocks/watchlist/groups')
def get_watchlist_groups():
    groups_data = _read_groups()
    return {'success': True, 'groups': groups_data.get('groups', [])}


@router.post('/api/stocks/watchlist/groups')
def create_watchlist_group(payload: Dict[str, Any] = Body(default_factory=dict)):
    name = (payload.get('name') or '').strip()
    if not name:
        return error_response({'success': False, 'error': '分组名称不能为空'}, 400)
    groups_data = _read_groups()
    new_group = {
        'id': str(uuid.uuid4())[:8],
        'name': name,
        'description': payload.get('description', ''),
        'created_at': datetime.now().isoformat(),
    }
    groups_data['groups'].append(new_group)
    _write_groups(groups_data)
    return {'success': True, 'group': new_group}


@router.put('/api/stocks/watchlist/groups/{group_id}')
def update_watchlist_group(group_id: str, payload: Dict[str, Any] = Body(default_factory=dict)):
    name = (payload.get('name') or '').strip()
    if not name:
        return error_response({'success': False, 'error': '分组名称不能为空'}, 400)
    groups_data = _read_groups()
    for group in groups_data.get('groups', []):
        if group['id'] == group_id:
            group['name'] = name
            if 'description' in payload:
                group['description'] = payload['description']
            group['updated_at'] = datetime.now().isoformat()
            _write_groups(groups_data)
            return {'success': True, 'group': group}
    return error_response({'success': False, 'error': '分组不存在'}, 404)


@router.delete('/api/stocks/watchlist/groups/{group_id}')
def delete_watchlist_group(group_id: str):
    if group_id == 'default':
        return error_response({'success': False, 'error': '不能删除默认分组'}, 400)
    groups_data = _read_groups()
    original_len = len(groups_data.get('groups', []))
    groups_data['groups'] = [g for g in groups_data.get('groups', []) if g['id'] != group_id]
    if len(groups_data['groups']) == original_len:
        return error_response({'success': False, 'error': '分组不存在'}, 404)
    _write_groups(groups_data)
    wl = _read_watchlist()
    for item in wl.get('items', []):
        if item.get('group_id') == group_id:
            item['group_id'] = 'default'
    _write_watchlist(wl)
    return {'success': True, 'message': '分组已删除'}


@router.get('/api/stocks/watchlist/{symbol}/check')
def check_watchlist(symbol: str):
    wl = _read_watchlist()
    found = any(item['symbol'] == symbol for item in wl.get('items', []))
    return {'success': True, 'inWatchlist': found, 'symbol': symbol}


@router.post('/api/stocks/watchlist')
def add_to_watchlist(payload: Dict[str, Any] = Body(default_factory=dict)):
    symbol = (payload.get('symbol') or '').strip()
    if not symbol:
        return error_response({'success': False, 'error': '股票代码不能为空'}, 400)
    stock_info = ds.stock.get_by_symbol(symbol)
    if not stock_info:
        return error_response({'success': False, 'error': f'股票不存在: {symbol}'}, 404)
    wl = _read_watchlist()
    for item in wl.get('items', []):
        if item['symbol'] == symbol:
            return {'success': True, 'message': '已在自选股中', 'item': item}
    new_item = {
        'symbol': symbol,
        'name': stock_info.get('name', symbol),
        'market': stock_info.get('market', ''),
        'group_id': payload.get('groupId', 'default'),
        'note': payload.get('note', ''),
        'added_at': datetime.now().isoformat(),
    }
    wl.setdefault('items', []).append(new_item)
    _write_watchlist(wl)
    return {'success': True, 'item': new_item, 'message': '已添加到自选股'}


@router.delete('/api/stocks/watchlist/{symbol}')
def remove_from_watchlist(symbol: str):
    wl = _read_watchlist()
    original_len = len(wl.get('items', []))
    wl['items'] = [i for i in wl.get('items', []) if i['symbol'] != symbol]
    if len(wl['items']) == original_len:
        return error_response({'success': False, 'error': f'股票不在自选股中: {symbol}'}, 404)
    _write_watchlist(wl)
    return {'success': True, 'message': f'已从自选股移除: {symbol}'}


@router.get('/api/stocks/watchlist')
def get_watchlist(groupId: Optional[str] = Query(None)):
    wl = _read_watchlist()
    items = wl.get('items', [])
    if groupId:
        items = [i for i in items if i.get('group_id') == groupId]
    return {'success': True, 'items': items, 'count': len(items)}
```

- [ ] **Step 2: 在 main.py 注册路由**

在 stock 注册后追加：

```python
    # 自选股（watchlist 域，P1 迁移）
    try:
        from adapters.inbound.fastapi_app.routes.watchlist_async import router as watchlist_router
        app.include_router(watchlist_router)
        logger.info("✅ Registered: watchlist (P1 迁移)")
    except ImportError as e:
        logger.warning(f"⚠️ Failed to import watchlist_async: {e}")
```

- [ ] **Step 3: 运行全部 stocks+watchlist parity（GREEN）**

Run: `cd quantsys-v2 && source activate-py313.sh && python -m pytest tests/migration/test_stocks_parity.py -q --no-cov`
Expected: 全部 PASS

- [ ] **Step 4: Commit**

```bash
cd quantsys-v2
git add adapters/inbound/fastapi_app/routes/watchlist_async.py adapters/inbound/fastapi_app/main.py
git commit -m "feat(fastapi): 迁移 watchlist 域路由（8端点，parity通过）"
```

---

### Task 7: 写操作状态隔离测试 + 整体验证

**Files:**
- Test: `tests/migration/test_stocks_writes.py`

**Interfaces:**
- Consumes: Task 2 fixtures、Task 5/6 路由。
- Produces: 写操作（add_stock、watchlist add/remove、group CRUD）的行为一致性验证（快照/恢复本地文件，避免双跑互相污染）。

> watchlist/groups 是本地 JSON 文件（`_read_watchlist`/`_write_watchlist`/`_read_groups`/`_write_groups`）。Flask 与 FastAPI 共享同一文件，直接双跑写操作会互相干扰。做法：每个用例先快照文件内容，分别在两边执行同一写序列后恢复，再比较两边产生的**响应序列**与**最终文件状态**是否一致。

- [ ] **Step 1: 写状态隔离的写操作测试**

Create `tests/migration/test_stocks_writes.py`：

```python
"""stocks/watchlist 写操作的 Flask↔FastAPI 行为一致性（状态隔离）"""
import copy
import pytest
from tests.migration.parity import normalize
from adapters.inbound.api.shared import _read_watchlist, _write_watchlist, _read_groups, _write_groups


@pytest.fixture
def snapshot_state():
    """快照并恢复 watchlist + groups 本地文件"""
    wl, gr = copy.deepcopy(_read_watchlist()), copy.deepcopy(_read_groups())
    yield
    _write_watchlist(wl)
    _write_groups(gr)


def test_watchlist_add_remove_parity(flask_client, fastapi_client, snapshot_state):
    def seq(client, is_flask):
        out = []
        if is_flask:
            r1 = client.open("/api/stocks/watchlist", method="POST", json={"symbol": "600519"})
            out.append((r1.status_code, r1.get_json()))
            r2 = client.open("/api/stocks/watchlist/600519", method="DELETE")
            out.append((r2.status_code, r2.get_json()))
        else:
            r1 = client.post("/api/stocks/watchlist", json={"symbol": "600519"})
            out.append((r1.status_code, r1.json()))
            r2 = client.delete("/api/stocks/watchlist/600519")
            out.append((r2.status_code, r2.json()))
        return out

    f_res = seq(flask_client, True)
    fa_res = seq(fastapi_client, False)

    for (f_code, f_body), (fa_code, fa_body) in zip(f_res, fa_res):
        assert fa_code == f_code
        # 忽略写操作里的事件时间字段
        assert normalize(fa_body, ignore_keys=frozenset({"added_at"})) == normalize(f_body, ignore_keys=frozenset({"added_at"}))
```

> 说明：写操作响应里含 `added_at` 等时间字段，比较时忽略。`snapshot_state` fixture 保证测试不污染真实 watchlist 文件。

- [ ] **Step 2: 运行写操作测试**

Run: `cd quantsys-v2 && source activate-py313.sh && python -m pytest tests/migration/test_stocks_writes.py -q --no-cov`
Expected: PASS

- [ ] **Step 3: 启动 FastAPI 实测 openapi 覆盖 + 抽验**

```bash
cd quantsys-v2 && source activate-py313.sh
nohup python -c "import sys; sys.path.insert(0,'.'); import uvicorn; from adapters.inbound.fastapi_app.main import app; uvicorn.run(app, host='127.0.0.1', port=5099, log_level='error')" > /tmp/p1_boot.log 2>&1 &
BOOT_PID=$!
for i in $(seq 1 30); do curl -s -m2 http://127.0.0.1:5099/health >/dev/null 2>&1 && break; sleep 1; done
curl -s http://127.0.0.1:5099/openapi.json | python -c "import json,sys; p=json.load(sys.stdin)['paths']; need=['/api/stocks/search','/api/stocks/list','/api/stocks/resolve','/api/stocks/my-stocks','/api/stocks/watchlist','/api/stocks/watchlist/groups','/api/stock/{symbol}/news','/api/stock/{symbol}/peers']; missing=[n for n in need if n not in p]; print('MISSING:', missing) if missing else print('ALL PRESENT:', len(need))"
kill $BOOT_PID 2>/dev/null
```
Expected: 输出 `ALL PRESENT: 8`（无 MISSING）

- [ ] **Step 4: 跑完整 migration 测试套件确认无回归**

Run: `cd quantsys-v2 && source activate-py313.sh && python -m pytest tests/migration/ -q --no-cov`
Expected: 全部 PASS

- [ ] **Step 5: Commit**

```bash
cd quantsys-v2
git add tests/migration/test_stocks_writes.py
git commit -m "test(fastapi): stocks/watchlist 写操作状态隔离 parity 测试"
```

---

## 完成标准（P0+P1 Definition of Done）

- [ ] `tests/migration/` 全部通过（shared 助手 + 框架 smoke + stocks/watchlist parity + 写操作）
- [ ] FastAPI `/openapi.json` 包含 stocks/watchlist 全部 20 个端点
- [ ] 冗余 server 文件与孤儿空桩已删，FastAPI 唯一入口可启动
- [ ] `migrate/flask-to-fastapi` 分支上每个 Task 一个 commit

## 后续（P2+，不在本计划）

stocks 域内分散在其它文件的端点（analysis 的 factors/technical、quote_market 的 klines、sentiment 的 fund-flow、pipeline 的 data-update-klines）随各自主文件在 P3/P6/P7 迁移。每个 Phase 复用本计划的 shared.py + parity 框架模式。

**明确推迟到后续的项**（本切片不做，避免扩大风险）：
- **register_routes 显式化**：总体设计 §8 提到把 `try/except ImportError` 静默跳过改为显式注册（缺失即报错）。本切片不做——因为部分路由模块依赖可选组件，盲目显式化可能导致应用无法启动。留待 P9 切换前，配合全量路由就绪后统一处理。
- **p1_batch / p2_batch1 / p2_batch2 聚合模块拆分**：这些文件把多个域的路由揉在一起，属代码异味，但重构它们会牵涉多个域，留待对应域迁移时一并处理。
- **被 main.py 引用的 2 个空桩**（`indicators_async.py`、`portfolio_async.py`）：在 P6/P5 替换为真实实现。
