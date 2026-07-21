# data-health endpoint Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose a new backend endpoint `GET /api/stock/<symbol>/data-health`, optimize `StockCodeValidator` for lightweight queries, and register `analysis.data_health` in agent-ts `V2_ROUTES` so the example health-check integration actually works.

**Architecture:** A thin Flask route delegates to the existing `StockCodeValidator.validate(symbol)`. The validator is refactored to use `count_daily_klines()` and `get_date_range()` instead of loading all historical K-lines. The route returns snake_case JSON so the existing agent-ts `DataHealthResult` interface remains valid.

**Tech Stack:** Python 3.13, Flask, pytest, polars/SQLAlchemy, TypeScript, tsc

---

## File Structure

| File | Responsibility |
|---|---|
| `quantsys-v2/tests/api/test_data_health_route.py` | New route tests (mocked validator) |
| `quantsys-v2/adapters/inbound/api/routes/analysis.py` | Add `GET /api/stock/<symbol>/data-health` route |
| `quantsys-v2/tests/services/test_stock_code_validator.py` | New unit tests for optimized validator |
| `quantsys-v2/application/services/stock_code_validator.py` | Optimize `validate()` to use aggregate queries |
| `agent-ts/src/infrastructure/adapters/quant/quant-v2-client.ts` | Register `analysis.data_health` in `V2_ROUTES` |
| `docs/superpowers/specs/2026-07-19-data-health-endpoint-design.md` | Already-written spec (reference) |

---

## Task 1: Write failing route test

**Files:**
- Create: `quantsys-v2/tests/api/test_data_health_route.py`

- [ ] **Step 1: Add the test file**

```python
"""
Tests for GET /api/stock/<symbol>/data-health
"""
import json
from unittest.mock import patch
import pytest

from adapters.inbound.api.server import create_app


@pytest.fixture
def client():
    app = create_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


class TestDataHealthAPI:
    def test_data_health_valid_symbol(self, client):
        with patch('application.services.stock_code_validator.StockCodeValidator') as MockValidator:
            MockValidator.return_value.validate.return_value = {
                'valid': True,
                'exists': True,
                'has_recent_data': True,
                'data_summary': {
                    'first_date': '2020-01-02',
                    'last_date': '2026-07-18',
                    'total_records': 1200,
                    'days_since_update': 1
                },
                'suggestions': [],
                'similar_codes': []
            }

            response = client.get('/api/stock/600519/data-health')

            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['success'] is True
            assert data['data']['valid'] is True
            assert data['data']['exists'] is True
            assert data['data']['has_recent_data'] is True
            assert data['data']['data_summary']['total_records'] == 1200

    def test_data_health_invalid_symbol(self, client):
        with patch('application.services.stock_code_validator.StockCodeValidator') as MockValidator:
            MockValidator.return_value.validate.return_value = {
                'valid': False,
                'exists': False,
                'has_recent_data': False,
                'data_summary': {
                    'first_date': None,
                    'last_date': None,
                    'total_records': 0,
                    'days_since_update': 999
                },
                'suggestions': ['该股票代码不存在或尚未录入数据'],
                'similar_codes': []
            }

            response = client.get('/api/stock/999999/data-health')

            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['success'] is True
            assert data['data']['valid'] is False
            assert data['data']['exists'] is False
```

- [ ] **Step 2: Run the test to confirm it fails**

Run:
```bash
cd /Users/mac/Documents/ai/pi-investment/quantsys-v2
source activate-py313.sh
python -m pytest tests/api/test_data_health_route.py -v
```

Expected: FAIL with 404 because the route does not exist yet.

---

## Task 2: Add the data-health route

**Files:**
- Modify: `quantsys-v2/adapters/inbound/api/routes/analysis.py` (near other `/api/stock/<symbol>/...` routes)

- [ ] **Step 1: Add the import if not already present**

Ensure the file already imports:
```python
from flask import Blueprint, request, jsonify
```

- [ ] **Step 2: Add the route function**

Insert near the end of the blueprint route definitions (after `get_quality_score_v2` is fine):

```python
@analysis_bp.route('/api/stock/<symbol>/data-health', methods=['GET'])
@handle_api_error
def get_data_health(symbol):
    """
    单票数据健康检查

    Returns:
        {
          "success": true,
          "data": {
            "valid": bool,
            "exists": bool,
            "has_recent_data": bool,
            "data_summary": {
              "first_date": str | null,
              "last_date": str | null,
              "total_records": int,
              "days_since_update": int
            },
            "suggestions": List[str],
            "similar_codes": List[str]
          }
        }
    """
    from application.services.stock_code_validator import StockCodeValidator

    validator = StockCodeValidator()
    result = validator.validate(symbol)

    # validate() 内部异常时会在结果里带 error 字段
    if result.get('error'):
        return jsonify({'success': False, 'error': result['error']}), 500

    # 保持 snake_case，绕过 api_response() 的驼峰转换
    return jsonify({'success': True, 'data': result}), 200
```

> **Why not `api_response()`?** `api_response()` recursively converts keys to camelCase, which would break the agent-ts `DataHealthResult` contract (`has_recent_data` → `hasRecentData`).

---

## Task 3: Run route test to verify it passes

- [ ] **Step 1: Run the route tests**

Run:
```bash
cd /Users/mac/Documents/ai/pi-investment/quantsys-v2
source activate-py313.sh
python -m pytest tests/api/test_data_health_route.py -v
```

Expected: 2 tests PASS.

---

## Task 4: Write failing validator optimization test

**Files:**
- Create: `quantsys-v2/tests/services/test_stock_code_validator.py`

- [ ] **Step 1: Add the test file**

```python
"""
Tests for StockCodeValidator optimization
"""
from datetime import datetime, timedelta
from unittest.mock import Mock

import pytest

from application.services.stock_code_validator import StockCodeValidator


class TestStockCodeValidatorOptimized:
    def test_validate_uses_lightweight_queries(self):
        validator = StockCodeValidator()
        validator.kline_repo.count_daily_klines = Mock(return_value=1200)

        last_date = (datetime.now() - timedelta(days=2)).strftime('%Y-%m-%d')
        validator.kline_repo.get_date_range = Mock(return_value=('2020-01-02', last_date))

        result = validator.validate('600519')

        validator.kline_repo.count_daily_klines.assert_called_once_with('600519')
        validator.kline_repo.get_date_range.assert_called_once_with('600519')

        assert result['valid'] is True
        assert result['exists'] is True
        assert result['has_recent_data'] is True
        assert result['data_summary']['total_records'] == 1200
        assert result['data_summary']['first_date'] == '2020-01-02'
        assert result['data_summary']['last_date'] == last_date
        assert isinstance(result['data_summary']['days_since_update'], int)
        assert result['data_summary']['days_since_update'] >= 2

    def test_validate_returns_invalid_when_no_records(self):
        validator = StockCodeValidator()
        validator.kline_repo.count_daily_klines = Mock(return_value=0)
        validator.kline_repo.get_date_range = Mock(return_value=None)

        result = validator.validate('999999')

        assert result['valid'] is False
        assert result['exists'] is False
        assert result['has_recent_data'] is False

    def test_validate_returns_invalid_when_date_range_missing(self):
        validator = StockCodeValidator()
        validator.kline_repo.count_daily_klines = Mock(return_value=5)
        validator.kline_repo.get_date_range = Mock(return_value=None)

        result = validator.validate('000001')

        assert result['valid'] is False
        assert result['exists'] is False
```

- [ ] **Step 2: Run the test to confirm it fails**

Run:
```bash
cd /Users/mac/Documents/ai/pi-investment/quantsys-v2
source activate-py313.sh
python -m pytest tests/services/test_stock_code_validator.py -v
```

Expected: FAIL because `validate()` currently calls `get_daily_klines()` instead of `count_daily_klines()` / `get_date_range()`.

---

## Task 5: Optimize StockCodeValidator

**Files:**
- Modify: `quantsys-v2/application/services/stock_code_validator.py`

- [ ] **Step 1: Refactor `validate()` to use aggregate queries**

Replace the body of `validate()`:

```python
    def validate(self, symbol: str) -> Dict:
        """
        验证股票代码

        Args:
            symbol: 股票代码（如 600519 或 000001）

        Returns:
            {
                'valid': bool,
                'exists': bool,
                'has_recent_data': bool,
                'data_summary': {...},
                'suggestions': List[str],
                'similar_codes': List[str]
            }
        """
        # 检查缓存
        if symbol in self._cache:
            cached = self._cache[symbol]
            if datetime.now().timestamp() - cached['timestamp'] < self._cache_ttl:
                logger.debug(f"使用缓存的验证结果: {symbol}")
                return cached['result']

        # 规范化股票代码
        normalized_symbol = self._normalize_symbol(symbol)

        try:
            # 使用轻量聚合查询，避免加载全部历史 K 线
            total_records = self.kline_repo.count_daily_klines(normalized_symbol)

            if total_records == 0:
                result = self._build_invalid_result(normalized_symbol)
            else:
                date_range = self.kline_repo.get_date_range(normalized_symbol)
                if date_range is None:
                    result = self._build_invalid_result(normalized_symbol)
                else:
                    result = self._build_valid_result_from_range(
                        normalized_symbol, total_records, date_range
                    )

            # 缓存结果
            self._cache[symbol] = {
                'result': result,
                'timestamp': datetime.now().timestamp()
            }

            return result

        except Exception as e:
            logger.error(f"验证股票代码失败: {symbol}", error=str(e))
            return {
                'valid': False,
                'exists': False,
                'error': f'验证失败: {str(e)}',
                'suggestions': ['请稍后重试或联系管理员']
            }
```

- [ ] **Step 2: Add the new helper method**

Add after `_build_valid_result` (or replace it):

```python
    def _build_valid_result_from_range(
        self, symbol: str, total_records: int, date_range: tuple
    ) -> Dict:
        """基于日期范围构建有效股票的验证结果（轻量版）"""
        first_date, last_date = date_range

        # 统一转换为 ISO 字符串
        first_date_str = first_date.isoformat() if hasattr(first_date, 'isoformat') else str(first_date)
        last_date_str = last_date.isoformat() if hasattr(last_date, 'isoformat') else str(last_date)

        # 计算数据新鲜度
        if isinstance(last_date_str, str):
            last_dt = datetime.strptime(last_date_str, '%Y-%m-%d')
        else:
            last_dt = last_date
        days_since_update = (datetime.now() - last_dt).days

        # 判断是否有最近数据（30天内）
        has_recent_data = days_since_update <= 30

        return {
            'valid': True,
            'exists': True,
            'has_recent_data': has_recent_data,
            'data_summary': {
                'first_date': first_date_str,
                'last_date': last_date_str,
                'total_records': total_records,
                'days_since_update': days_since_update
            },
            'suggestions': [] if has_recent_data else [
                f'该股票数据已 {days_since_update} 天未更新，可能已退市或停牌'
            ],
            'similar_codes': []
        }
```

- [ ] **Step 3: Remove the now-unused `_build_valid_result` helper**

Delete the old `_build_valid_result(self, symbol, klines_df)` method to avoid dead code. The only previous caller was `validate()`.

---

## Task 6: Run validator test to verify it passes

- [ ] **Step 1: Run the validator tests**

Run:
```bash
cd /Users/mac/Documents/ai/pi-investment/quantsys-v2
source activate-py313.sh
python -m pytest tests/services/test_stock_code_validator.py -v
```

Expected: 3 tests PASS.

- [ ] **Step 2: Run existing swing-point tests to ensure no regression**

Run:
```bash
python -m pytest tests/ -k "swing" -v
```

Expected: Existing tests still PASS (return shape unchanged).

---

## Task 7: Register analysis.data_health in V2_ROUTES

**Files:**
- Modify: `agent-ts/src/infrastructure/adapters/quant/quant-v2-client.ts`

- [ ] **Step 1: Add the route registration**

Locate the line:
```typescript
"analysis.swing_points": { path: "/api/analysis/swing-points",       method: "POST" },
```

Add immediately after it:
```typescript
"analysis.data_health":  { path: "/api/stock/{symbol}/data-health",   method: "GET"  },
```

---

## Task 8: Run agent-ts build

- [ ] **Step 1: Build agent-ts**

Run:
```bash
cd /Users/mac/Documents/ai/pi-investment/agent-ts
npm run build
```

Expected:
```
> pi-investment@0.1.0 build
> tsc -p tsconfig.build.json
```

No errors.

---

## Task 9: Manual integration verification

- [ ] **Step 1: Start quantsys-v2 backend**

Run:
```bash
cd /Users/mac/Documents/ai/pi-investment/quantsys-v2
source activate-py313.sh
python api/server.py
```

Wait until you see Flask listening on `127.0.0.1:5001`.

- [ ] **Step 2: Curl the new endpoint with a known symbol**

Run:
```bash
curl -s "http://127.0.0.1:5001/api/stock/600519/data-health" | python -m json.tool
```

Expected shape (values depend on DB state):
```json
{
    "success": true,
    "data": {
        "valid": true,
        "exists": true,
        "has_recent_data": true,
        "data_summary": {
            "first_date": "2020-01-02",
            "last_date": "2026-07-18",
            "total_records": 1200,
            "days_since_update": 1
        },
        "suggestions": [],
        "similar_codes": []
    }
}
```

Keys must be snake_case.

- [ ] **Step 3: Curl with an invalid symbol**

Run:
```bash
curl -s "http://127.0.0.1:5001/api/stock/999999/data-health" | python -m json.tool
```

Expected:
```json
{
    "success": true,
    "data": {
        "valid": false,
        "exists": false,
        "has_recent_data": false,
        "data_summary": {...},
        "suggestions": ["该股票代码不存在或尚未录入数据", ...],
        "similar_codes": []
    }
}
```

- [ ] **Step 4: Verify agent-ts can call it**

Create a small ad-hoc script in `agent-ts/` (do not commit):

```typescript
// /tmp/verify-data-health.ts
import { runQuantV2 } from "./src/infrastructure/adapters/quant/quant-v2-client.js";

async function main() {
  const result = await runQuantV2("analysis.data_health", { symbol: "600519" });
  console.log(JSON.stringify(result, null, 2));
}
main();
```

Run with tsx:
```bash
cd /Users/mac/Documents/ai/pi-investment/agent-ts
npx tsx /tmp/verify-data-health.ts
```

Expected:
```json
{
  "ok": true,
  "command": "analysis.data_health",
  "params": { "symbol": "600519" },
  "data": {
    "valid": true,
    "exists": true,
    "has_recent_data": true,
    ...
  },
  "warnings": [],
  "error": null
}
```

Clean up the temp file afterward:
```bash
rm /tmp/verify-data-health.ts
```

---

## Task 10: Commit changes

- [ ] **Step 1: Stage and commit**

Run:
```bash
cd /Users/mac/Documents/ai/pi-investment
git add quantsys-v2/adapters/inbound/api/routes/analysis.py
git add quantsys-v2/application/services/stock_code_validator.py
git add quantsys-v2/tests/api/test_data_health_route.py
git add quantsys-v2/tests/services/test_stock_code_validator.py
git add agent-ts/src/infrastructure/adapters/quant/quant-v2-client.ts
git add docs/superpowers/plans/2026-07-19-data-health-endpoint.md

git commit -m "feat: expose /api/stock/<symbol>/data-health and register analysis.data_health

- Add GET /api/stock/<symbol>/data-health route in analysis.py
- Optimize StockCodeValidator to use count_daily_klines/get_date_range
- Add route and validator unit tests
- Register analysis.data_health in agent-ts V2_ROUTES"
```

---

## Self-Review

- **Spec coverage:** Every spec requirement maps to a task:
  - New backend endpoint → Task 2
  - Snake_case contract → Task 2 (bypass `api_response`)
  - Validator performance fix → Task 5
  - Agent route registration → Task 7
  - Tests → Tasks 1, 4
  - Integration verification → Task 9
- **Placeholder scan:** No TBD/TODO/"implement later"/vague instructions. All code blocks contain complete code.
- **Type consistency:**
  - `DataHealthResult` fields in agent example match route response keys (`valid`, `exists`, `has_recent_data`, `data_summary`, `suggestions`, `similar_codes`).
  - `runQuantV2('analysis.data_health', { symbol })` matches `V2_ROUTES` path `/api/stock/{symbol}/data-health`.
  - `StockCodeValidator.validate()` return shape unchanged; only implementation changed.
- **Gaps:** None identified.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-07-19-data-health-endpoint.md`.

Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
