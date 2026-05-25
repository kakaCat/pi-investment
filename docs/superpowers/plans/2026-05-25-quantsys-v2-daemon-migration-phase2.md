# QuantSys V2 Daemon Migration - Phase 2: L1 Data Layer

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement L1 Data Layer handlers (6 methods) for stock data operations

**Dependencies:** Phase 1 must be complete (daemon infrastructure ready)

**Architecture:** Each handler calls quantsys-v2 REST API endpoints, formats results as JSON strings

---

## Methods to Implement

1. `get_stock_info` - Get basic stock information
2. `get_stock_price` - Get current/historical price data
3. `get_stock_fundamentals` - Get fundamental data
4. `search_stocks` - Search stocks by criteria
5. `get_market_data` - Get market overview data
6. `update_stock_data` - Trigger data update

---

## Task 1: Implement get_stock_info Handler

**Files:**
- Create: `quantsys-v2/daemon/handlers/data_handlers.py`
- Create: `quantsys-v2/tests/daemon/test_data_handlers.py`

- [ ] **Step 1: Write failing test**

Create `tests/daemon/test_data_handlers.py`:

```python
"""Tests for L1 data layer handlers."""
import pytest
import json
from unittest.mock import AsyncMock, patch
from daemon.handlers.data_handlers import get_stock_info


@pytest.mark.asyncio
async def test_get_stock_info_success():
    """Test get_stock_info returns stock data."""
    params = {"symbol": "AAPL"}
    
    # Mock API response
    mock_response = {
        "symbol": "AAPL",
        "name": "Apple Inc.",
        "exchange": "NASDAQ",
        "sector": "Technology"
    }
    
    with patch("daemon.handlers.data_handlers.call_api", new_callable=AsyncMock) as mock_api:
        mock_api.return_value = mock_response
        
        result = await get_stock_info(params)
        parsed = json.loads(result)
        
        assert parsed["symbol"] == "AAPL"
        assert parsed["name"] == "Apple Inc."
        mock_api.assert_called_once_with("GET", "/api/stocks/AAPL")


@pytest.mark.asyncio
async def test_get_stock_info_missing_symbol():
    """Test get_stock_info raises error for missing symbol."""
    params = {}
    
    with pytest.raises(ValueError) as exc_info:
        await get_stock_info(params)
    
    assert "symbol" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_get_stock_info_api_error():
    """Test get_stock_info handles API errors."""
    params = {"symbol": "INVALID"}
    
    with patch("daemon.handlers.data_handlers.call_api", new_callable=AsyncMock) as mock_api:
        mock_api.side_effect = Exception("Stock not found")
        
        with pytest.raises(Exception) as exc_info:
            await get_stock_info(params)
        
        assert "Stock not found" in str(exc_info.value)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd quantsys-v2 && pytest tests/daemon/test_data_handlers.py::test_get_stock_info_success -v`
Expected: FAIL with "ModuleNotFoundError"

- [ ] **Step 3: Implement data handlers with API client**

Create `daemon/handlers/data_handlers.py`:

```python
"""L1 Data Layer handlers."""
import json
import aiohttp
from typing import Any, Dict
from daemon.registry import register_method


# API Configuration
API_BASE_URL = "http://127.0.0.1:5001"


async def call_api(method: str, path: str, data: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Call quantsys-v2 REST API.
    
    Args:
        method: HTTP method (GET, POST, etc.)
        path: API path (e.g., "/api/stocks/AAPL")
        data: Optional request body
        
    Returns:
        API response as dict
        
    Raises:
        Exception: If API call fails
    """
    url = f"{API_BASE_URL}{path}"
    
    async with aiohttp.ClientSession() as session:
        if method == "GET":
            async with session.get(url) as response:
                if response.status != 200:
                    text = await response.text()
                    raise Exception(f"API error {response.status}: {text}")
                return await response.json()
        
        elif method == "POST":
            async with session.post(url, json=data) as response:
                if response.status not in (200, 201):
                    text = await response.text()
                    raise Exception(f"API error {response.status}: {text}")
                return await response.json()
        
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")


@register_method("get_stock_info")
async def get_stock_info(params: dict) -> str:
    """
    Get basic stock information.
    
    Params:
        symbol: Stock symbol (required)
        
    Returns:
        JSON string with stock info
    """
    symbol = params.get("symbol")
    if not symbol:
        raise ValueError("Parameter 'symbol' is required")
    
    # Call API
    data = await call_api("GET", f"/api/stocks/{symbol}")
    
    return json.dumps(data, ensure_ascii=False)
```

- [ ] **Step 4: Add aiohttp dependency**

Update `quantsys-v2/requirements.txt`:

```bash
echo "aiohttp>=3.9.0" >> requirements.txt
pip install aiohttp
```

- [ ] **Step 5: Run tests**

Run: `cd quantsys-v2 && pytest tests/daemon/test_data_handlers.py::test_get_stock_info_success -v`
Expected: PASS

- [ ] **Step 6: Run all get_stock_info tests**

Run: `cd quantsys-v2 && pytest tests/daemon/test_data_handlers.py -k get_stock_info -v`
Expected: All 3 tests PASS

- [ ] **Step 7: Commit**

```bash
git add daemon/handlers/data_handlers.py tests/daemon/test_data_handlers.py requirements.txt
git commit -m "feat(daemon): implement get_stock_info handler (L1)"
```

---

## Task 2: Implement get_stock_price Handler

- [ ] **Step 1: Write failing test**

Append to `tests/daemon/test_data_handlers.py`:

```python
from daemon.handlers.data_handlers import get_stock_price


@pytest.mark.asyncio
async def test_get_stock_price_success():
    """Test get_stock_price returns price data."""
    params = {
        "symbol": "AAPL",
        "start_date": "2024-01-01",
        "end_date": "2024-01-31"
    }
    
    mock_response = {
        "symbol": "AAPL",
        "prices": [
            {"date": "2024-01-02", "close": 185.64},
            {"date": "2024-01-03", "close": 184.25}
        ]
    }
    
    with patch("daemon.handlers.data_handlers.call_api", new_callable=AsyncMock) as mock_api:
        mock_api.return_value = mock_response
        
        result = await get_stock_price(params)
        parsed = json.loads(result)
        
        assert parsed["symbol"] == "AAPL"
        assert len(parsed["prices"]) == 2


@pytest.mark.asyncio
async def test_get_stock_price_missing_symbol():
    """Test get_stock_price requires symbol."""
    params = {"start_date": "2024-01-01"}
    
    with pytest.raises(ValueError) as exc_info:
        await get_stock_price(params)
    
    assert "symbol" in str(exc_info.value).lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd quantsys-v2 && pytest tests/daemon/test_data_handlers.py::test_get_stock_price_success -v`
Expected: FAIL

- [ ] **Step 3: Implement handler**

Append to `daemon/handlers/data_handlers.py`:

```python
@register_method("get_stock_price")
async def get_stock_price(params: dict) -> str:
    """
    Get stock price data.
    
    Params:
        symbol: Stock symbol (required)
        start_date: Start date (optional, format: YYYY-MM-DD)
        end_date: End date (optional, format: YYYY-MM-DD)
        
    Returns:
        JSON string with price data
    """
    symbol = params.get("symbol")
    if not symbol:
        raise ValueError("Parameter 'symbol' is required")
    
    # Build query params
    query_params = []
    if params.get("start_date"):
        query_params.append(f"start_date={params['start_date']}")
    if params.get("end_date"):
        query_params.append(f"end_date={params['end_date']}")
    
    query_string = "?" + "&".join(query_params) if query_params else ""
    
    # Call API
    data = await call_api("GET", f"/api/stocks/{symbol}/prices{query_string}")
    
    return json.dumps(data, ensure_ascii=False)
```

- [ ] **Step 4: Run tests**

Run: `cd quantsys-v2 && pytest tests/daemon/test_data_handlers.py -k get_stock_price -v`
Expected: All 2 tests PASS

- [ ] **Step 5: Commit**

```bash
git add daemon/handlers/data_handlers.py tests/daemon/test_data_handlers.py
git commit -m "feat(daemon): implement get_stock_price handler (L1)"
```

---

## Task 3: Implement get_stock_fundamentals Handler

- [ ] **Step 1: Write test and implement**

Append to `tests/daemon/test_data_handlers.py`:

```python
from daemon.handlers.data_handlers import get_stock_fundamentals


@pytest.mark.asyncio
async def test_get_stock_fundamentals_success():
    """Test get_stock_fundamentals returns fundamental data."""
    params = {"symbol": "AAPL"}
    
    mock_response = {
        "symbol": "AAPL",
        "market_cap": 2800000000000,
        "pe_ratio": 28.5,
        "eps": 6.42
    }
    
    with patch("daemon.handlers.data_handlers.call_api", new_callable=AsyncMock) as mock_api:
        mock_api.return_value = mock_response
        
        result = await get_stock_fundamentals(params)
        parsed = json.loads(result)
        
        assert parsed["symbol"] == "AAPL"
        assert parsed["pe_ratio"] == 28.5
```

Append to `daemon/handlers/data_handlers.py`:

```python
@register_method("get_stock_fundamentals")
async def get_stock_fundamentals(params: dict) -> str:
    """
    Get stock fundamental data.
    
    Params:
        symbol: Stock symbol (required)
        
    Returns:
        JSON string with fundamental data
    """
    symbol = params.get("symbol")
    if not symbol:
        raise ValueError("Parameter 'symbol' is required")
    
    data = await call_api("GET", f"/api/stocks/{symbol}/fundamentals")
    
    return json.dumps(data, ensure_ascii=False)
```

- [ ] **Step 2: Run test and commit**

Run: `cd quantsys-v2 && pytest tests/daemon/test_data_handlers.py::test_get_stock_fundamentals_success -v`

```bash
git add daemon/handlers/data_handlers.py tests/daemon/test_data_handlers.py
git commit -m "feat(daemon): implement get_stock_fundamentals handler (L1)"
```

---

## Task 4: Implement search_stocks Handler

- [ ] **Step 1: Write test and implement**

Append to `tests/daemon/test_data_handlers.py`:

```python
from daemon.handlers.data_handlers import search_stocks


@pytest.mark.asyncio
async def test_search_stocks_success():
    """Test search_stocks returns matching stocks."""
    params = {
        "query": "Apple",
        "limit": 10
    }
    
    mock_response = {
        "results": [
            {"symbol": "AAPL", "name": "Apple Inc."},
            {"symbol": "APLE", "name": "Apple Hospitality REIT"}
        ],
        "total": 2
    }
    
    with patch("daemon.handlers.data_handlers.call_api", new_callable=AsyncMock) as mock_api:
        mock_api.return_value = mock_response
        
        result = await search_stocks(params)
        parsed = json.loads(result)
        
        assert parsed["total"] == 2
        assert len(parsed["results"]) == 2
```

Append to `daemon/handlers/data_handlers.py`:

```python
@register_method("search_stocks")
async def search_stocks(params: dict) -> str:
    """
    Search stocks by query.
    
    Params:
        query: Search query (required)
        limit: Max results (optional, default: 20)
        
    Returns:
        JSON string with search results
    """
    query = params.get("query")
    if not query:
        raise ValueError("Parameter 'query' is required")
    
    limit = params.get("limit", 20)
    
    data = await call_api("GET", f"/api/stocks/search?q={query}&limit={limit}")
    
    return json.dumps(data, ensure_ascii=False)
```

- [ ] **Step 2: Run test and commit**

Run: `cd quantsys-v2 && pytest tests/daemon/test_data_handlers.py::test_search_stocks_success -v`

```bash
git add daemon/handlers/data_handlers.py tests/daemon/test_data_handlers.py
git commit -m "feat(daemon): implement search_stocks handler (L1)"
```

---

## Task 5: Implement get_market_data Handler

- [ ] **Step 1: Write test and implement**

Append to `tests/daemon/test_data_handlers.py`:

```python
from daemon.handlers.data_handlers import get_market_data


@pytest.mark.asyncio
async def test_get_market_data_success():
    """Test get_market_data returns market overview."""
    params = {}
    
    mock_response = {
        "indices": {
            "SPX": {"value": 4783.45, "change": 0.52},
            "DJI": {"value": 37440.34, "change": 0.35}
        },
        "timestamp": "2024-01-15T16:00:00Z"
    }
    
    with patch("daemon.handlers.data_handlers.call_api", new_callable=AsyncMock) as mock_api:
        mock_api.return_value = mock_response
        
        result = await get_market_data(params)
        parsed = json.loads(result)
        
        assert "indices" in parsed
        assert "SPX" in parsed["indices"]
```

Append to `daemon/handlers/data_handlers.py`:

```python
@register_method("get_market_data")
async def get_market_data(params: dict) -> str:
    """
    Get market overview data.
    
    Params:
        None required
        
    Returns:
        JSON string with market data
    """
    data = await call_api("GET", "/api/market/overview")
    
    return json.dumps(data, ensure_ascii=False)
```

- [ ] **Step 2: Run test and commit**

Run: `cd quantsys-v2 && pytest tests/daemon/test_data_handlers.py::test_get_market_data_success -v`

```bash
git add daemon/handlers/data_handlers.py tests/daemon/test_data_handlers.py
git commit -m "feat(daemon): implement get_market_data handler (L1)"
```

---

## Task 6: Implement update_stock_data Handler

- [ ] **Step 1: Write test and implement**

Append to `tests/daemon/test_data_handlers.py`:

```python
from daemon.handlers.data_handlers import update_stock_data


@pytest.mark.asyncio
async def test_update_stock_data_success():
    """Test update_stock_data triggers data refresh."""
    params = {"symbol": "AAPL"}
    
    mock_response = {
        "status": "success",
        "message": "Data update triggered for AAPL"
    }
    
    with patch("daemon.handlers.data_handlers.call_api", new_callable=AsyncMock) as mock_api:
        mock_api.return_value = mock_response
        
        result = await update_stock_data(params)
        parsed = json.loads(result)
        
        assert parsed["status"] == "success"
        mock_api.assert_called_once_with("POST", "/api/stocks/AAPL/update", data={})
```

Append to `daemon/handlers/data_handlers.py`:

```python
@register_method("update_stock_data")
async def update_stock_data(params: dict) -> str:
    """
    Trigger stock data update.
    
    Params:
        symbol: Stock symbol (required)
        
    Returns:
        JSON string with update status
    """
    symbol = params.get("symbol")
    if not symbol:
        raise ValueError("Parameter 'symbol' is required")
    
    data = await call_api("POST", f"/api/stocks/{symbol}/update", data={})
    
    return json.dumps(data, ensure_ascii=False)
```

- [ ] **Step 2: Run test and commit**

Run: `cd quantsys-v2 && pytest tests/daemon/test_data_handlers.py::test_update_stock_data_success -v`

```bash
git add daemon/handlers/data_handlers.py tests/daemon/test_data_handlers.py
git commit -m "feat(daemon): implement update_stock_data handler (L1)"
```

---

## Task 7: Register Data Handlers in Server

- [ ] **Step 1: Import handlers in server**

Update `daemon/server.py`, add after imports:

```python
# Import handlers to register them
from daemon.handlers import data_handlers
```

- [ ] **Step 2: Run full integration test**

Run: `cd quantsys-v2 && pytest tests/daemon/ -v`
Expected: All tests PASS

- [ ] **Step 3: Test with real daemon**

```bash
cd quantsys-v2
echo '{"jsonrpc": "2.0", "id": 1, "method": "get_stock_info", "params": {"symbol": "AAPL"}}' | python -m daemon.server
```

Expected: JSON-RPC response with stock info (or error if API not running)

- [ ] **Step 4: Commit**

```bash
git add daemon/server.py
git commit -m "feat(daemon): register L1 data handlers in server"
```

---

## Phase 2 Complete

**Deliverables:**
✅ 6 L1 Data Layer handlers implemented and tested
✅ API client with aiohttp implemented
✅ All handlers registered in daemon server
✅ Unit tests with mocked API calls passing
✅ Integration tests passing

**Methods Implemented:**
1. ✅ get_stock_info
2. ✅ get_stock_price
3. ✅ get_stock_fundamentals
4. ✅ search_stocks
5. ✅ get_market_data
6. ✅ update_stock_data

**Next Steps:**
- Phase 3: Implement L2 Factor Layer handlers (5 methods)
- Phase 4: Implement L3 Model Layer handlers (5 methods)
- Phase 5: Documentation and cleanup
