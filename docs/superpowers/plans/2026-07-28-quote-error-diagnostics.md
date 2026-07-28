# Quote 端点可行动错误诊断 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** quote 端点（`/api/stock/{symbol}/quote`）取数失败时返回结构化诊断（`provider_errors` + 分类 `suggestion`），让 agent 能自我纠正，替代笼统的"无法获取 X 的实时行情"。

**Architecture:** 路由改为直连 `DataProviderManager.get_quote()`（仿 K 线端点 `get_stock_history` 既有模式），拿到 manager 已收集的 `provider_errors`/`attempted_sources`；新增 `_quote_failure_suggestion()` 按失败原因分类生成建议；4 个 quote provider 返回 None 时设置 `self.last_error`（manager 第 116 行已会读取）。FastAPI 与 Flask 双端镜像改动，保持 parity。

**Tech Stack:** Python 3.13 / Flask / FastAPI / pytest / requests / akshare

**Spec:** `quantsys-v2/docs/superpowers/specs/2026-07-28-quote-error-diagnostics-design.md`

**Worktree:** `.claude/worktrees/quote-error-diagnostics`，分支 `feat/quote-error-diagnostics`

---

### Task 0: 基线确认

**Files:** 无改动

- [ ] **Step 1: 跑既有 parity 与路由测试确认基线绿**

Run:
```bash
cd /Users/mac/Documents/ai/pi-investment/.claude/worktrees/quote-error-diagnostics/quantsys-v2
venv/bin/python -m pytest tests/migration/test_stocks_parity.py -x -q
```
Expected: 全 PASS（若有因外网数据源不可用导致的失败，记录具体用例名，向用户报告后再继续）

---

### Task 1: Flask 端 `_quote_failure_suggestion` helper

**Files:**
- Modify: `quantsys-v2/adapters/inbound/api/routes/quote_market.py`（在 `get_stock_quote` 函数结束之后、`_kline_failure_suggestion` 之前插入）
- Test: `quantsys-v2/tests/api/test_quote_market_routes.py`（新建）

- [ ] **Step 1: 写失败测试（新文件）**

```python
"""quote_market Flask 路由诊断测试"""
import json
import pytest
from unittest.mock import patch

from adapters.inbound.api.server import create_app
from adapters.inbound.api.routes.quote_market import _quote_failure_suggestion
from adapters.outbound.datasources.models import QuoteData


@pytest.fixture
def client():
    app = create_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


class TestQuoteFailureSuggestion:
    def test_hk_5digit_bare_with_network_error(self):
        s = _quote_failure_suggestion('00836', {'sina': 'Read timed out. (read timeout=5)'})
        assert '港股' in s
        assert '00836.HK' in s
        assert '网络型失败' in s
        assert 'source=db' in s

    def test_hk_suffix(self):
        s = _quote_failure_suggestion('00700.HK', {})
        assert '港股' in s
        assert '00700.HK' in s
        assert 'source=db' in s

    def test_a_share_6digit(self):
        s = _quote_failure_suggestion('999999', {})
        assert '已上市/已退市' in s
        assert 'source=db' in s

    def test_unknown_format_fallback(self):
        s = _quote_failure_suggestion('ABC', {})
        assert '代码格式' in s
        assert 'source=db' in s
```

- [ ] **Step 2: 跑测试确认失败**

Run:
```bash
cd /Users/mac/Documents/ai/pi-investment/.claude/worktrees/quote-error-diagnostics/quantsys-v2
venv/bin/python -m pytest tests/api/test_quote_market_routes.py::TestQuoteFailureSuggestion -v
```
Expected: FAIL — `ImportError: cannot import name '_quote_failure_suggestion'`

- [ ] **Step 3: 实现 helper（插入到 `get_stock_quote` 之后、`_kline_failure_suggestion` 之前）**

```python
def _quote_failure_suggestion(symbol: str, provider_errors: dict) -> str:
    """根据各数据源的具体失败原因，生成可行动的修复建议（供 agent 自我纠正）"""
    joined = ' '.join(provider_errors.values())
    hints = []

    code = symbol.split('.')[0]
    if symbol.endswith('.HK') or (code.isdigit() and len(code) <= 5):
        hints.append(
            f"疑似港股代码：本接口主要支持 6 位 A 股代码，港股请尝试 {code.zfill(5)}.HK 格式"
        )
    if any(k in joined for k in ('timeout', 'Timeout', 'Connection', 'RemoteDisconnected', '502', 'Max retries')):
        hints.append("存在网络型失败：数据源可能临时限流/封禁，可稍后重试")
    if code.isdigit() and len(code) == 6:
        hints.append("请检查代码是否正确、是否已上市/已退市")
    if not hints:
        hints.append("请检查代码格式（A股为 6 位数字，可带 .SH/.SZ 后缀）")
    hints.append("也可用 source=db 查询本地缓存（如有）")

    return '；'.join(hints)
```

- [ ] **Step 4: 跑测试确认通过**

Run:
```bash
venv/bin/python -m pytest tests/api/test_quote_market_routes.py::TestQuoteFailureSuggestion -v
```
Expected: 4 PASS

- [ ] **Step 5: Commit**

```bash
git add quantsys-v2/adapters/inbound/api/routes/quote_market.py quantsys-v2/tests/api/test_quote_market_routes.py
git commit -m "feat(quote): Flask 端 _quote_failure_suggestion 分类建议 helper"
```

---

### Task 2: Flask 端路由直连 provider_manager + 诊断响应体

**Files:**
- Modify: `quantsys-v2/adapters/inbound/api/routes/quote_market.py`（`get_stock_quote` 的 realtime/auto 段，约 144-180 行；新增 `_build_quote_failure_body`）
- Test: `quantsys-v2/tests/api/test_quote_market_routes.py`

- [ ] **Step 1: 追加路由失败测试**

在 `test_quote_market_routes.py` 文件末尾追加：

```python
def _failed_manager_result():
    return {
        'success': False,
        'error': 'All data providers failed',
        'attempted_sources': ['tencent', 'sina', 'eastmoney', 'akshare'],
        'provider_errors': {
            'tencent': '腾讯无 sz00836 数据（代码不存在或该市场不支持）',
            'sina': 'Exception: 新浪财经查询失败: Read timed out. (read timeout=5)',
        },
    }


class TestQuoteRouteDiagnostics:
    @patch('adapters.outbound.datasources.get_data_provider_manager')
    def test_realtime_failure_returns_diagnostics(self, mock_get_manager, client):
        mock_get_manager.return_value.get_quote.return_value = _failed_manager_result()

        resp = client.get('/api/stock/00836/quote')

        assert resp.status_code == 502
        body = json.loads(resp.data)
        assert body['success'] is False
        assert 'tencent' in body['error']
        assert body['provider_errors']['tencent'].startswith('腾讯无 sz00836')
        assert '港股' in body['suggestion']
        assert '00836.HK' in body['suggestion']
        assert 'source=db' in body['suggestion']

    @patch('adapters.outbound.datasources.get_data_provider_manager')
    def test_realtime_success_unchanged(self, mock_get_manager, client):
        quote = QuoteData(
            symbol='600519', name='贵州茅台', price=1294.97, open=1308.0,
            high=1308.0, low=1279.58, prev_close=1297.41, volume=2482400,
            amount=129190000.0, change=-2.44, change_pct=-0.19,
            source='tencent', timestamp='2026-07-27T13:49:39',
        )
        mock_get_manager.return_value.get_quote.return_value = {
            'success': True, 'data': quote, 'source': 'tencent',
        }

        resp = client.get('/api/stock/600519/quote')

        assert resp.status_code == 200
        body = json.loads(resp.data)
        assert body['success'] is True
        assert body['data']['price'] == 1294.97
        assert body['data']['source'] == 'tencent'

    @patch('adapters.inbound.api.routes.quote_market._get_db_quote', return_value=None)
    @patch('adapters.outbound.datasources.get_data_provider_manager')
    def test_auto_failure_after_db_fallback(self, mock_get_manager, mock_db, client):
        mock_get_manager.return_value.get_quote.return_value = _failed_manager_result()

        resp = client.get('/api/stock/00836/quote?source=auto')

        assert resp.status_code == 502
        body = json.loads(resp.data)
        assert 'provider_errors' in body
        assert 'suggestion' in body
```

- [ ] **Step 2: 跑测试确认失败**

Run:
```bash
venv/bin/python -m pytest tests/api/test_quote_market_routes.py::TestQuoteRouteDiagnostics -v
```
Expected: FAIL — 502 响应体中无 `provider_errors`/`suggestion` 键（`test_realtime_success_unchanged` 此时可能 PASS 也可能 FAIL，因为路由还没直连 manager；FAIL 属预期）

- [ ] **Step 3: 实现路由改动**

在 `quote_market.py` 中，把 `get_stock_quote` 里从 `# realtime 或 auto 模式：使用 RealtimeQuoteService` 到函数末尾（原 144-180 行）整段替换为：

```python
    # realtime 或 auto 模式：直连 DataProviderManager（拿到各数据源失败原因，供 agent 诊断）
    quote_result = None
    try:
        from adapters.outbound.datasources import get_data_provider_manager
        quote_result = get_data_provider_manager().get_quote(clean_symbol)
    except Exception as e:
        logging.getLogger(__name__).warning(f"DataProviderManager.get_quote failed for {symbol}: {e}")

    if quote_result and quote_result.get('success'):
        quote_data = quote_result['data']
        # 转换 QuoteData 为 API 响应格式
        result = {
            "symbol": quote_data.symbol,
            "name": quote_data.name,
            "price": quote_data.price,
            "open": quote_data.open,
            "high": quote_data.high,
            "low": quote_data.low,
            "prev_close": quote_data.prev_close,
            "volume": quote_data.volume,
            "amount": quote_data.amount,
            "change": quote_data.change,
            "change_pct": quote_data.change_pct,
            "source": quote_data.source,
            "timestamp": quote_data.timestamp,
        }
        return api_response(result)

    # realtime 模式：所有数据源失败，返回 502 + 诊断信息
    if source == 'realtime':
        return jsonify(_build_quote_failure_body(symbol, quote_result)), 502

    # auto 模式：fallback 到数据库
    db_result = _get_db_quote(clean_symbol)
    if db_result:
        return api_response(db_result)

    return jsonify(_build_quote_failure_body(symbol, quote_result)), 502
```

并在 `_quote_failure_suggestion` 之前插入 `_build_quote_failure_body`：

```python
def _build_quote_failure_body(symbol: str, quote_result) -> dict:
    """组装 quote 失败的结构化诊断响应体（供 agent 自我纠正）"""
    if quote_result:
        error_msg = quote_result.get('error', 'All data providers failed')
        attempted = quote_result.get('attempted_sources', [])
        provider_errors = quote_result.get('provider_errors', {})
    else:
        error_msg, attempted, provider_errors = '行情服务异常', [], {}

    if attempted:
        error_text = f"{error_msg} (尝试数据源: {', '.join(attempted)})"
    else:
        error_text = f"无法获取 {symbol} 的实时行情：{error_msg}"

    return {
        "success": False,
        "error": error_text,
        "provider_errors": provider_errors,
        "suggestion": _quote_failure_suggestion(symbol, provider_errors),
    }
```

注意：函数 docstring 中"数据源优先级"描述（akshare → sina → …）已过时，顺手改为"tencent → sina → eastmoney → akshare（与 DataProviderManager.quote_providers 一致）"。

- [ ] **Step 4: 跑测试确认通过**

Run:
```bash
venv/bin/python -m pytest tests/api/test_quote_market_routes.py -v
```
Expected: 全部 PASS（4 个 helper 测试 + 3 个路由测试）

- [ ] **Step 5: Commit**

```bash
git add quantsys-v2/adapters/inbound/api/routes/quote_market.py quantsys-v2/tests/api/test_quote_market_routes.py
git commit -m "feat(quote): Flask 路由直连 provider_manager，502 返回 provider_errors+suggestion"
```

---

### Task 3: FastAPI 端 `_quote_failure_suggestion` + `_build_quote_failure_body` helper

**Files:**
- Modify: `quantsys-v2/adapters/inbound/fastapi_app/routes/stock_async.py`（在 `_get_db_quote` 之后、`get_stock_quote` 之前插入）
- Test: `quantsys-v2/tests/api/test_stock_quote_async.py`（新建）

- [ ] **Step 1: 写失败测试（新文件）**

```python
"""quote FastAPI 路由诊断测试"""
import pytest
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient

from adapters.inbound.fastapi_app.routes.stock_async import (
    router,
    _quote_failure_suggestion,
)
from adapters.outbound.datasources.models import QuoteData


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


class TestQuoteFailureSuggestion:
    def test_hk_5digit_bare_with_network_error(self):
        s = _quote_failure_suggestion('00836', {'sina': 'Read timed out. (read timeout=5)'})
        assert '港股' in s
        assert '00836.HK' in s
        assert '网络型失败' in s
        assert 'source=db' in s

    def test_hk_suffix(self):
        s = _quote_failure_suggestion('00700.HK', {})
        assert '港股' in s
        assert '00700.HK' in s
        assert 'source=db' in s

    def test_a_share_6digit(self):
        s = _quote_failure_suggestion('999999', {})
        assert '已上市/已退市' in s
        assert 'source=db' in s

    def test_unknown_format_fallback(self):
        s = _quote_failure_suggestion('ABC', {})
        assert '代码格式' in s
        assert 'source=db' in s
```

- [ ] **Step 2: 跑测试确认失败**

Run:
```bash
venv/bin/python -m pytest tests/api/test_stock_quote_async.py::TestQuoteFailureSuggestion -v
```
Expected: FAIL — `ImportError: cannot import name '_quote_failure_suggestion'`

- [ ] **Step 3: 实现两个 helper（在 `_get_db_quote` 之后、`@router.get('/api/stock/{symbol}/quote')` 之前插入）**

```python
def _build_quote_failure_body(symbol: str, quote_result: Optional[dict]) -> dict:
    """组装 quote 失败的结构化诊断响应体（供 agent 自我纠正）。与 Flask quote_market.py 镜像。"""
    if quote_result:
        error_msg = quote_result.get('error', 'All data providers failed')
        attempted = quote_result.get('attempted_sources', [])
        provider_errors = quote_result.get('provider_errors', {})
    else:
        error_msg, attempted, provider_errors = '行情服务异常', [], {}

    if attempted:
        error_text = f"{error_msg} (尝试数据源: {', '.join(attempted)})"
    else:
        error_text = f"无法获取 {symbol} 的实时行情：{error_msg}"

    return {
        "success": False,
        "error": error_text,
        "provider_errors": provider_errors,
        "suggestion": _quote_failure_suggestion(symbol, provider_errors),
    }


def _quote_failure_suggestion(symbol: str, provider_errors: dict) -> str:
    """根据各数据源的具体失败原因，生成可行动的修复建议（供 agent 自我纠正）。与 Flask quote_market.py 镜像。"""
    joined = ' '.join(provider_errors.values())
    hints = []

    code = symbol.split('.')[0]
    if symbol.endswith('.HK') or (code.isdigit() and len(code) <= 5):
        hints.append(
            f"疑似港股代码：本接口主要支持 6 位 A 股代码，港股请尝试 {code.zfill(5)}.HK 格式"
        )
    if any(k in joined for k in ('timeout', 'Timeout', 'Connection', 'RemoteDisconnected', '502', 'Max retries')):
        hints.append("存在网络型失败：数据源可能临时限流/封禁，可稍后重试")
    if code.isdigit() and len(code) == 6:
        hints.append("请检查代码是否正确、是否已上市/已退市")
    if not hints:
        hints.append("请检查代码格式（A股为 6 位数字，可带 .SH/.SZ 后缀）")
    hints.append("也可用 source=db 查询本地缓存（如有）")

    return '；'.join(hints)
```

- [ ] **Step 4: 跑测试确认通过**

Run:
```bash
venv/bin/python -m pytest tests/api/test_stock_quote_async.py::TestQuoteFailureSuggestion -v
```
Expected: 4 PASS

- [ ] **Step 5: Commit**

```bash
git add quantsys-v2/adapters/inbound/fastapi_app/routes/stock_async.py quantsys-v2/tests/api/test_stock_quote_async.py
git commit -m "feat(quote): FastAPI 端 quote 诊断 helper（与 Flask 镜像）"
```

---

### Task 4: FastAPI 端路由直连 provider_manager + 诊断响应体

**Files:**
- Modify: `quantsys-v2/adapters/inbound/fastapi_app/routes/stock_async.py`（`get_stock_quote` 的 realtime/auto 段，约 421-453 行）
- Test: `quantsys-v2/tests/api/test_stock_quote_async.py`

- [ ] **Step 1: 追加路由失败测试**

在 `test_stock_quote_async.py` 文件末尾追加：

```python
def _failed_manager_result():
    return {
        'success': False,
        'error': 'All data providers failed',
        'attempted_sources': ['tencent', 'sina', 'eastmoney', 'akshare'],
        'provider_errors': {
            'tencent': '腾讯无 sz00836 数据（代码不存在或该市场不支持）',
            'sina': 'Exception: 新浪财经查询失败: Read timed out. (read timeout=5)',
        },
    }


class TestQuoteRouteDiagnostics:
    @patch('adapters.outbound.datasources.get_data_provider_manager')
    def test_realtime_failure_returns_diagnostics(self, mock_get_manager, client):
        mock_get_manager.return_value.get_quote.return_value = _failed_manager_result()

        resp = client.get('/api/stock/00836/quote')

        assert resp.status_code == 502
        body = resp.json()
        assert body['success'] is False
        assert 'tencent' in body['error']
        assert body['provider_errors']['tencent'].startswith('腾讯无 sz00836')
        assert '港股' in body['suggestion']
        assert '00836.HK' in body['suggestion']
        assert 'source=db' in body['suggestion']

    @patch('adapters.outbound.datasources.get_data_provider_manager')
    def test_realtime_success_unchanged(self, mock_get_manager, client):
        quote = QuoteData(
            symbol='600519', name='贵州茅台', price=1294.97, open=1308.0,
            high=1308.0, low=1279.58, prev_close=1297.41, volume=2482400,
            amount=129190000.0, change=-2.44, change_pct=-0.19,
            source='tencent', timestamp='2026-07-27T13:49:39',
        )
        mock_get_manager.return_value.get_quote.return_value = {
            'success': True, 'data': quote, 'source': 'tencent',
        }

        resp = client.get('/api/stock/600519/quote')

        assert resp.status_code == 200
        body = resp.json()
        assert body['success'] is True
        assert body['data']['price'] == 1294.97
        assert body['data']['source'] == 'tencent'

    @patch('adapters.inbound.fastapi_app.routes.stock_async._get_db_quote', return_value=None)
    @patch('adapters.outbound.datasources.get_data_provider_manager')
    def test_auto_failure_after_db_fallback(self, mock_get_manager, mock_db, client):
        mock_get_manager.return_value.get_quote.return_value = _failed_manager_result()

        resp = client.get('/api/stock/00836/quote?source=auto')

        assert resp.status_code == 502
        body = resp.json()
        assert 'provider_errors' in body
        assert 'suggestion' in body
```

- [ ] **Step 2: 跑测试确认失败**

Run:
```bash
venv/bin/python -m pytest tests/api/test_stock_quote_async.py::TestQuoteRouteDiagnostics -v
```
Expected: FAIL — 502 响应体无 `provider_errors`/`suggestion` 键

- [ ] **Step 3: 实现路由改动**

在 `stock_async.py` 的 `get_stock_quote` 中，把 `# realtime 或 auto 模式：使用 RealtimeQuoteService` 到函数末尾（原 421-453 行）整段替换为：

```python
    # realtime 或 auto 模式：直连 DataProviderManager（拿到各数据源失败原因，供 agent 诊断）
    quote_result = None
    try:
        from adapters.outbound.datasources import get_data_provider_manager
        quote_result = get_data_provider_manager().get_quote(clean_symbol)
    except Exception as e:
        logger.warning(f"DataProviderManager.get_quote failed for {symbol}: {e}")

    if quote_result and quote_result.get('success'):
        quote_data = quote_result['data']
        result = {
            "symbol": quote_data.symbol,
            "name": quote_data.name,
            "price": quote_data.price,
            "open": quote_data.open,
            "high": quote_data.high,
            "low": quote_data.low,
            "prev_close": quote_data.prev_close,
            "volume": quote_data.volume,
            "amount": quote_data.amount,
            "change": quote_data.change,
            "change_pct": quote_data.change_pct,
            "source": quote_data.source,
            "timestamp": quote_data.timestamp,
        }
        return api_response(result)

    if source == 'realtime':
        return error_response(_build_quote_failure_body(symbol, quote_result), 502)

    # auto 模式：fallback 到数据库
    db_result = _get_db_quote(clean_symbol)
    if db_result:
        return api_response(db_result)
    return error_response(_build_quote_failure_body(symbol, quote_result), 502)
```

- [ ] **Step 4: 跑测试确认通过**

Run:
```bash
venv/bin/python -m pytest tests/api/test_stock_quote_async.py -v
```
Expected: 全部 PASS（4 个 helper 测试 + 3 个路由测试）

- [ ] **Step 5: Commit**

```bash
git add quantsys-v2/adapters/inbound/fastapi_app/routes/stock_async.py quantsys-v2/tests/api/test_stock_quote_async.py
git commit -m "feat(quote): FastAPI 路由直连 provider_manager，502 返回 provider_errors+suggestion"
```

---

### Task 5: tencent quote provider `last_error`

**Files:**
- Modify: `quantsys-v2/adapters/outbound/datasources/providers/quote/tencent.py`（`get_quote` 方法）
- Test: `quantsys-v2/tests/test_quote_providers_last_error.py`（新建）

- [ ] **Step 1: 写失败测试（新文件）**

```python
"""quote providers last_error 诊断测试"""
import pandas as pd
from unittest.mock import patch, MagicMock

from adapters.outbound.datasources.providers.quote.tencent import TencentQuoteProvider
from adapters.outbound.datasources.providers.quote.sina import SinaQuoteProvider
from adapters.outbound.datasources.providers.quote.eastmoney import EastmoneyQuoteProvider
from adapters.outbound.datasources.providers.quote.akshare import AkshareQuoteProvider


def _mock_response(text='', json_data=None):
    resp = MagicMock()
    resp.text = text
    resp.json.return_value = json_data if json_data is not None else {}
    return resp


class TestTencentLastError:
    def test_no_match_sets_last_error(self):
        """腾讯 v_pv_none_match（代码无匹配）走解析分支返回 None，需设置 last_error"""
        provider = TencentQuoteProvider()
        resp = _mock_response(text='v_pv_none_match="1";')
        with patch(
            'adapters.outbound.datasources.providers.quote.tencent.requests.get',
            return_value=resp,
        ):
            assert provider.get_quote('00836') is None
        assert provider.last_error is not None
        assert 'sz00836' in provider.last_error

    def test_empty_quote_sets_last_error(self):
        """腾讯返回空串（v_xxx=""）需设置 last_error"""
        provider = TencentQuoteProvider()
        resp = _mock_response(text='v_sh600519="";')
        with patch(
            'adapters.outbound.datasources.providers.quote.tencent.requests.get',
            return_value=resp,
        ):
            assert provider.get_quote('600519') is None
        assert provider.last_error is not None
        assert 'sh600519' in provider.last_error
```

- [ ] **Step 2: 跑测试确认失败**

Run:
```bash
venv/bin/python -m pytest tests/test_quote_providers_last_error.py::TestTencentLastError -v
```
Expected: FAIL — `AssertionError: assert None is not None`（`provider.last_error` 不存在，`AttributeError` 也算预期失败）

- [ ] **Step 3: 实现 `last_error`（替换 tencent.py 的 `get_quote` 整个方法）**

```python
    def get_quote(self, symbol: str) -> Optional[QuoteData]:
        """
        获取实时行情数据

        Args:
            symbol: 股票代码 (e.g., "600519.SH", "000001.SZ")

        Returns:
            QuoteData if successful, None if empty response

        Raises:
            Exception: 网络错误或解析失败
        """
        self.last_error = None
        try:
            # Convert symbol to Tencent format
            tencent_code = self._convert_to_tencent_code(symbol)

            # Call Tencent API
            url = f"http://qt.gtimg.cn/q={tencent_code}"
            response = requests.get(
                url,
                timeout=self.timeout,
                proxies={'http': None, 'https': None}
            )
            response.encoding = 'gbk'

            # Check for empty response
            if not response.text or '""' in response.text:
                self.last_error = f"腾讯无 {tencent_code} 数据（代码不存在或该市场不支持）"
                return None

            quote = self._parse_quote(symbol, response.text)
            if quote is None:
                self.last_error = f"腾讯返回数据无法解析或代码无匹配 ({tencent_code})"
            return quote

        except Exception as e:
            raise Exception(f"腾讯财经查询失败: {e}") from e
```

- [ ] **Step 4: 跑测试确认通过**

Run:
```bash
venv/bin/python -m pytest tests/test_quote_providers_last_error.py::TestTencentLastError -v
```
Expected: 2 PASS

- [ ] **Step 5: Commit**

```bash
git add quantsys-v2/adapters/outbound/datasources/providers/quote/tencent.py quantsys-v2/tests/test_quote_providers_last_error.py
git commit -m "feat(quote): tencent provider 返回 None 时设置 last_error"
```

---

### Task 6: sina quote provider `last_error`

**Files:**
- Modify: `quantsys-v2/adapters/outbound/datasources/providers/quote/sina.py`（`get_quote` 方法）
- Test: `quantsys-v2/tests/test_quote_providers_last_error.py`

- [ ] **Step 1: 追加失败测试**

在 `test_quote_providers_last_error.py` 末尾追加：

```python
class TestSinaLastError:
    def test_empty_response_sets_last_error(self):
        """新浪空响应需设置 last_error（裸 00836 会被映射为 A 股 000836）"""
        provider = SinaQuoteProvider()
        resp = _mock_response(text='')
        with patch(
            'adapters.outbound.datasources.providers.quote.sina.requests.get',
            return_value=resp,
        ):
            assert provider.get_quote('00836') is None
        assert provider.last_error is not None
        assert '000836' in provider.last_error

    def test_incomplete_data_sets_last_error(self):
        """新浪返回字段不足（解析返回 None）需设置 last_error"""
        provider = SinaQuoteProvider()
        resp = _mock_response(text='var hq_str_1600519="贵州茅台,1308.0";')
        with patch(
            'adapters.outbound.datasources.providers.quote.sina.requests.get',
            return_value=resp,
        ):
            assert provider.get_quote('600519') is None
        assert provider.last_error is not None
        assert '1600519' in provider.last_error
```

- [ ] **Step 2: 跑测试确认失败**

Run:
```bash
venv/bin/python -m pytest tests/test_quote_providers_last_error.py::TestSinaLastError -v
```
Expected: FAIL — `provider.last_error` 为 None/不存在

- [ ] **Step 3: 实现 `last_error`（替换 sina.py 的 `get_quote` 整个方法）**

```python
    def get_quote(self, symbol: str) -> Optional[QuoteData]:
        """
        获取实时行情数据

        Args:
            symbol: 股票代码 (e.g., "600000.SH", "00700.HK")

        Returns:
            QuoteData if successful, None if empty response

        Raises:
            Exception: 网络错误或解析失败
        """
        self.last_error = None
        try:
            # Convert symbol to Sina format
            sina_code = self._convert_to_sina_code(symbol)

            # Call Sina API (disable proxy for domestic data sources)
            url = f"https://hq.sinajs.cn/list={sina_code}"
            response = requests.get(url, timeout=self.timeout, proxies={'http': None, 'https': None})
            response.encoding = 'gbk'

            # Check for empty response
            if not response.text or '""' in response.text:
                self.last_error = f"新浪无 {sina_code} 数据（代码不存在或该市场不支持）"
                return None

            # Parse based on market
            if symbol.endswith('.HK'):
                quote = self._parse_sina_hk_quote(symbol, response.text)
            else:
                quote = self._parse_sina_a_quote(symbol, response.text)
            if quote is None:
                self.last_error = f"新浪返回数据不完整 ({sina_code})"
            return quote

        except Exception as e:
            raise Exception(f"新浪财经查询失败: {e}") from e
```

- [ ] **Step 4: 跑测试确认通过**

Run:
```bash
venv/bin/python -m pytest tests/test_quote_providers_last_error.py::TestSinaLastError -v
```
Expected: 2 PASS

- [ ] **Step 5: Commit**

```bash
git add quantsys-v2/adapters/outbound/datasources/providers/quote/sina.py quantsys-v2/tests/test_quote_providers_last_error.py
git commit -m "feat(quote): sina provider 返回 None 时设置 last_error"
```

---

### Task 7: eastmoney quote provider `last_error`

**Files:**
- Modify: `quantsys-v2/adapters/outbound/datasources/providers/quote/eastmoney.py`（`get_quote` 方法）
- Test: `quantsys-v2/tests/test_quote_providers_last_error.py`

- [ ] **Step 1: 追加失败测试**

在 `test_quote_providers_last_error.py` 末尾追加：

```python
class TestEastmoneyLastError:
    def test_no_data_sets_last_error(self):
        """东方财富 data 为空需设置 last_error（裸 00836 映射为深市 0.00836）"""
        provider = EastmoneyQuoteProvider()
        resp = _mock_response(json_data={'data': None})
        with patch(
            'adapters.outbound.datasources.providers.quote.eastmoney.requests.get',
            return_value=resp,
        ):
            assert provider.get_quote('00836') is None
        assert provider.last_error is not None
        assert '0.00836' in provider.last_error

    def test_invalid_price_sets_last_error(self):
        """东方财富价格字段为 0（解析返回 None）需设置 last_error"""
        provider = EastmoneyQuoteProvider()
        resp = _mock_response(json_data={'data': {'f43': 0, 'f58': 'X'}})
        with patch(
            'adapters.outbound.datasources.providers.quote.eastmoney.requests.get',
            return_value=resp,
        ):
            assert provider.get_quote('600519') is None
        assert provider.last_error is not None
        assert '1.600519' in provider.last_error
```

- [ ] **Step 2: 跑测试确认失败**

Run:
```bash
venv/bin/python -m pytest tests/test_quote_providers_last_error.py::TestEastmoneyLastError -v
```
Expected: FAIL — `provider.last_error` 为 None/不存在

- [ ] **Step 3: 实现 `last_error`（替换 eastmoney.py `get_quote` 中 `data = response.json()` 之后到 `except` 之前的部分）**

替换后 `get_quote` 完整方法：

```python
    def get_quote(self, symbol: str) -> Optional[QuoteData]:
        """
        获取实时行情数据

        Args:
            symbol: 股票代码 (e.g., "600519.SH", "000001.SZ")

        Returns:
            QuoteData if successful, None if empty response

        Raises:
            Exception: 网络错误或解析失败
        """
        self.last_error = None
        try:
            # Convert symbol to Eastmoney secid format
            secid = self._convert_to_secid(symbol)

            # Call Eastmoney API
            url = "http://push2.eastmoney.com/api/qt/stock/get"
            params = {
                'secid': secid,
                'fields': 'f43,f44,f45,f46,f47,f48,f57,f58,f60,f152,f168,f169,f170,f171'
            }

            response = requests.get(
                url,
                params=params,
                timeout=self.timeout,
                proxies={'http': None, 'https': None}
            )
            response.raise_for_status()

            data = response.json()

            # Check if data exists
            if not data or 'data' not in data or not data['data']:
                self.last_error = f"东方财富无 {secid} 数据（代码不存在或该市场不支持）"
                return None

            quote = self._parse_quote(symbol, data['data'])
            if quote is None:
                self.last_error = f"东方财富返回价格无效 ({secid})"
            return quote

        except Exception as e:
            raise Exception(f"东方财富查询失败: {e}") from e
```

- [ ] **Step 4: 跑测试确认通过**

Run:
```bash
venv/bin/python -m pytest tests/test_quote_providers_last_error.py::TestEastmoneyLastError -v
```
Expected: 2 PASS

- [ ] **Step 5: Commit**

```bash
git add quantsys-v2/adapters/outbound/datasources/providers/quote/eastmoney.py quantsys-v2/tests/test_quote_providers_last_error.py
git commit -m "feat(quote): eastmoney provider 返回 None 时设置 last_error"
```

---

### Task 8: akshare quote provider `last_error`

**Files:**
- Modify: `quantsys-v2/adapters/outbound/datasources/providers/quote/akshare.py`（`get_quote`、`_get_a_quote`、`_get_hk_quote`）
- Test: `quantsys-v2/tests/test_quote_providers_last_error.py`

- [ ] **Step 1: 追加失败测试**

在 `test_quote_providers_last_error.py` 末尾追加：

```python
class TestAkshareLastError:
    def test_a_share_not_found_sets_last_error(self):
        """akshare A 股全表无该代码需设置 last_error"""
        provider = AkshareQuoteProvider()
        df = pd.DataFrame({'代码': ['600519'], '名称': ['贵州茅台']})
        with patch(
            'adapters.outbound.datasources.providers.quote.akshare.ak.stock_zh_a_spot_em',
            return_value=df,
        ):
            assert provider.get_quote('999999') is None
        assert provider.last_error is not None
        assert '999999' in provider.last_error

    def test_hk_not_found_sets_last_error(self):
        """akshare 港股全表无该代码需设置 last_error（裸 00836 走港股分支）"""
        provider = AkshareQuoteProvider()
        df = pd.DataFrame({'代码': ['00700'], '名称': ['腾讯控股']})
        with patch(
            'adapters.outbound.datasources.providers.quote.akshare.ak.stock_hk_spot_em',
            return_value=df,
        ):
            assert provider.get_quote('00836') is None
        assert provider.last_error is not None
        assert '00836' in provider.last_error
```

- [ ] **Step 2: 跑测试确认失败**

Run:
```bash
venv/bin/python -m pytest tests/test_quote_providers_last_error.py::TestAkshareLastError -v
```
Expected: FAIL — `provider.last_error` 为 None/不存在

- [ ] **Step 3: 实现 `last_error`（akshare.py 三处小改）**

1. `get_quote` 方法体开头（`env_patch` 赋值之前）加一行：

```python
        self.last_error = None
```

2. `_get_a_quote` 中 `if row.empty:` 分支改为：

```python
        if row.empty:
            self.last_error = f"akshare A股无 {clean_symbol} 数据（代码不存在或已退市）"
            return None
```

3. `_get_hk_quote` 中 `if row.empty:` 分支改为：

```python
        if row.empty:
            self.last_error = f"akshare 港股无 {clean_symbol} 数据（代码不存在或未上市）"
            return None
```

- [ ] **Step 4: 跑测试确认通过**

Run:
```bash
venv/bin/python -m pytest tests/test_quote_providers_last_error.py -v
```
Expected: 全部 PASS（tencent 2 + sina 2 + eastmoney 2 + akshare 2）

- [ ] **Step 5: Commit**

```bash
git add quantsys-v2/adapters/outbound/datasources/providers/quote/akshare.py quantsys-v2/tests/test_quote_providers_last_error.py
git commit -m "feat(quote): akshare provider 返回 None 时设置 last_error"
```

---

### Task 9: 全量回归 + 实测验证

**Files:** 无改动

- [ ] **Step 1: 跑 parity 测试**

Run:
```bash
cd /Users/mac/Documents/ai/pi-investment/.claude/worktrees/quote-error-diagnostics/quantsys-v2
venv/bin/python -m pytest tests/migration/test_stocks_parity.py -v
```
Expected: 全 PASS（`test_stock_quote_realtime` 依赖外网，若因数据源不可用失败需确认是否与 Task 0 基线一致——基线就失败的用例不算回归）

- [ ] **Step 2: 跑相关测试文件全量**

Run:
```bash
venv/bin/python -m pytest tests/api/test_quote_market_routes.py tests/api/test_stock_quote_async.py tests/test_quote_providers_last_error.py tests/migration/test_stocks_parity.py -q
```
Expected: 全 PASS

- [ ] **Step 3: 实测失败路径诊断（真实 manager + 真实网络）**

Run:
```bash
venv/bin/python -c "
from fastapi import FastAPI
from fastapi.testclient import TestClient
from adapters.inbound.fastapi_app.routes.stock_async import router
app = FastAPI()
app.include_router(router)
c = TestClient(app)
r = c.get('/api/stock/00836/quote')
import json; print(r.status_code); print(json.dumps(r.json(), ensure_ascii=False, indent=2))
"
```
Expected: 502，body 含 `provider_errors`（4 个数据源各自的具体原因）与 `suggestion`（含"港股"、"00836.HK"、"source=db"）

- [ ] **Step 4: 实测成功路径不变（600519）**

Run:
```bash
venv/bin/python -c "
from fastapi import FastAPI
from fastapi.testclient import TestClient
from adapters.inbound.fastapi_app.routes.stock_async import router
app = FastAPI()
app.include_router(router)
c = TestClient(app)
r = c.get('/api/stock/600519/quote')
import json; print(r.status_code); print(json.dumps(r.json(), ensure_ascii=False)[:300])
"
```
Expected: 200，`success: true`，含 price/source 字段（与改动前形状一致）

- [ ] **Step 5: 向用户报告验证结果，准备合并回 main**

---

## Self-Review 记录

- **Spec 覆盖**：spec 第 1 节（路由直连）→ Task 2/4；第 2 节（响应体）→ Task 2/4；第 3 节（suggestion 规则）→ Task 1/3；第 4 节（last_error）→ Task 5/6/7/8；第 5 节（parity）→ Task 0/9。验证节 → Task 9。✅
- **Placeholder 扫描**：无 TBD/TODO，所有代码步骤含完整代码。✅
- **类型一致性**：`_quote_failure_suggestion(symbol: str, provider_errors: dict) -> str`、`_build_quote_failure_body(symbol: str, quote_result) -> dict`（FastAPI 侧注解 `Optional[dict]`，该文件已 import Optional）在所有任务中一致；mock 目标 `adapters.outbound.datasources.get_data_provider_manager`（函数内 import，调用时才解析，patch 源模块属性有效）。✅
