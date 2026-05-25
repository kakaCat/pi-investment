# QuantSys V2 Daemon Migration - Phase 3: L2 Factor Layer

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement L2 Factor Layer handlers (5 methods) for factor calculation and analysis

**Dependencies:** Phase 1 and Phase 2 must be complete

**Architecture:** Each handler calls quantsys-v2 REST API endpoints for factor operations

---

## Methods to Implement

1. `calculate_factor` - Calculate a specific factor for stocks
2. `batch_calculate_factors` - Calculate multiple factors in batch
3. `get_factor_values` - Get historical factor values
4. `list_available_factors` - List all available factor definitions
5. `validate_factor_expression` - Validate factor calculation expression

---

## Task 1: Implement calculate_factor Handler

**Files:**
- Create: `quantsys-v2/daemon/handlers/factor_handlers.py`
- Create: `quantsys-v2/tests/daemon/test_factor_handlers.py`

- [ ] **Step 1: Write failing test**

Create `tests/daemon/test_factor_handlers.py`:

```python
"""Tests for L2 factor layer handlers."""
import pytest
import json
from unittest.mock import AsyncMock, patch
from daemon.handlers.factor_handlers import calculate_factor


@pytest.mark.asyncio
async def test_calculate_factor_success():
    """Test calculate_factor returns factor values."""
    params = {
        "factor_name": "momentum",
        "symbols": ["AAPL", "GOOGL"],
        "date": "2024-01-15"
    }
    
    mock_response = {
        "factor_name": "momentum",
        "date": "2024-01-15",
        "values": {
            "AAPL": 0.15,
            "GOOGL": 0.08
        }
    }
    
    with patch("daemon.handlers.factor_handlers.call_api", new_callable=AsyncMock) as mock_api:
        mock_api.return_value = mock_response
        
        result = await calculate_factor(params)
        parsed = json.loads(result)
        
        assert parsed["factor_name"] == "momentum"
        assert "AAPL" in parsed["values"]
        assert parsed["values"]["AAPL"] == 0.15


@pytest.mark.asyncio
async def test_calculate_factor_missing_factor_name():
    """Test calculate_factor requires factor_name."""
    params = {"symbols": ["AAPL"]}
    
    with pytest.raises(ValueError) as exc_info:
        await calculate_factor(params)
    
    assert "factor_name" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_calculate_factor_missing_symbols():
    """Test calculate_factor requires symbols."""
    params = {"factor_name": "momentum"}
    
    with pytest.raises(ValueError) as exc_info:
        await calculate_factor(params)
    
    assert "symbols" in str(exc_info.value).lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd quantsys-v2 && pytest tests/daemon/test_factor_handlers.py::test_calculate_factor_success -v`
Expected: FAIL with "ModuleNotFoundError"

- [ ] **Step 3: Implement factor handlers**

Create `daemon/handlers/factor_handlers.py`:

```python
"""L2 Factor Layer handlers."""
import json
from typing import Any, Dict
from daemon.registry import register_method

# Import API client from data_handlers
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from data_handlers import call_api


@register_method("calculate_factor")
async def calculate_factor(params: dict) -> str:
    """
    Calculate a specific factor for stocks.
    
    Params:
        factor_name: Factor name (required)
        symbols: List of stock symbols (required)
        date: Calculation date (optional, default: latest)
        
    Returns:
        JSON string with factor values
    """
    factor_name = params.get("factor_name")
    if not factor_name:
        raise ValueError("Parameter 'factor_name' is required")
    
    symbols = params.get("symbols")
    if not symbols:
        raise ValueError("Parameter 'symbols' is required")
    
    if not isinstance(symbols, list):
        raise ValueError("Parameter 'symbols' must be a list")
    
    # Build request body
    request_data = {
        "factor_name": factor_name,
        "symbols": symbols
    }
    
    if params.get("date"):
        request_data["date"] = params["date"]
    
    # Call API
    data = await call_api("POST", "/api/factors/calculate", data=request_data)
    
    return json.dumps(data, ensure_ascii=False)
```

- [ ] **Step 4: Run tests**

Run: `cd quantsys-v2 && pytest tests/daemon/test_factor_handlers.py -k calculate_factor -v`
Expected: All 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add daemon/handlers/factor_handlers.py tests/daemon/test_factor_handlers.py
git commit -m "feat(daemon): implement calculate_factor handler (L2)"
```

---

## Task 2: Implement batch_calculate_factors Handler

- [ ] **Step 1: Write failing test**

Append to `tests/daemon/test_factor_handlers.py`:

```python
from daemon.handlers.factor_handlers import batch_calculate_factors


@pytest.mark.asyncio
async def test_batch_calculate_factors_success():
    """Test batch_calculate_factors returns multiple factor values."""
    params = {
        "factor_names": ["momentum", "value", "quality"],
        "symbols": ["AAPL", "GOOGL"],
        "date": "2024-01-15"
    }
    
    mock_response = {
        "date": "2024-01-15",
        "factors": {
            "momentum": {"AAPL": 0.15, "GOOGL": 0.08},
            "value": {"AAPL": -0.05, "GOOGL": 0.12},
            "quality": {"AAPL": 0.22, "GOOGL": 0.18}
        }
    }
    
    with patch("daemon.handlers.factor_handlers.call_api", new_callable=AsyncMock) as mock_api:
        mock_api.return_value = mock_response
        
        result = await batch_calculate_factors(params)
        parsed = json.loads(result)
        
        assert "factors" in parsed
        assert len(parsed["factors"]) == 3
        assert "momentum" in parsed["factors"]


@pytest.mark.asyncio
async def test_batch_calculate_factors_missing_factor_names():
    """Test batch_calculate_factors requires factor_names."""
    params = {"symbols": ["AAPL"]}
    
    with pytest.raises(ValueError) as exc_info:
        await batch_calculate_factors(params)
    
    assert "factor_names" in str(exc_info.value).lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd quantsys-v2 && pytest tests/daemon/test_factor_handlers.py::test_batch_calculate_factors_success -v`
Expected: FAIL

- [ ] **Step 3: Implement handler**

Append to `daemon/handlers/factor_handlers.py`:

```python
@register_method("batch_calculate_factors")
async def batch_calculate_factors(params: dict) -> str:
    """
    Calculate multiple factors in batch.
    
    Params:
        factor_names: List of factor names (required)
        symbols: List of stock symbols (required)
        date: Calculation date (optional, default: latest)
        
    Returns:
        JSON string with all factor values
    """
    factor_names = params.get("factor_names")
    if not factor_names:
        raise ValueError("Parameter 'factor_names' is required")
    
    if not isinstance(factor_names, list):
        raise ValueError("Parameter 'factor_names' must be a list")
    
    symbols = params.get("symbols")
    if not symbols:
        raise ValueError("Parameter 'symbols' is required")
    
    if not isinstance(symbols, list):
        raise ValueError("Parameter 'symbols' must be a list")
    
    # Build request body
    request_data = {
        "factor_names": factor_names,
        "symbols": symbols
    }
    
    if params.get("date"):
        request_data["date"] = params["date"]
    
    # Call API
    data = await call_api("POST", "/api/factors/batch-calculate", data=request_data)
    
    return json.dumps(data, ensure_ascii=False)
```

- [ ] **Step 4: Run tests**

Run: `cd quantsys-v2 && pytest tests/daemon/test_factor_handlers.py -k batch_calculate_factors -v`
Expected: All 2 tests PASS

- [ ] **Step 5: Commit**

```bash
git add daemon/handlers/factor_handlers.py tests/daemon/test_factor_handlers.py
git commit -m "feat(daemon): implement batch_calculate_factors handler (L2)"
```

---

## Task 3: Implement get_factor_values Handler

- [ ] **Step 1: Write test and implement**

Append to `tests/daemon/test_factor_handlers.py`:

```python
from daemon.handlers.factor_handlers import get_factor_values


@pytest.mark.asyncio
async def test_get_factor_values_success():
    """Test get_factor_values returns historical factor data."""
    params = {
        "factor_name": "momentum",
        "symbol": "AAPL",
        "start_date": "2024-01-01",
        "end_date": "2024-01-31"
    }
    
    mock_response = {
        "factor_name": "momentum",
        "symbol": "AAPL",
        "values": [
            {"date": "2024-01-02", "value": 0.12},
            {"date": "2024-01-03", "value": 0.15}
        ]
    }
    
    with patch("daemon.handlers.factor_handlers.call_api", new_callable=AsyncMock) as mock_api:
        mock_api.return_value = mock_response
        
        result = await get_factor_values(params)
        parsed = json.loads(result)
        
        assert parsed["factor_name"] == "momentum"
        assert len(parsed["values"]) == 2
```

Append to `daemon/handlers/factor_handlers.py`:

```python
@register_method("get_factor_values")
async def get_factor_values(params: dict) -> str:
    """
    Get historical factor values.
    
    Params:
        factor_name: Factor name (required)
        symbol: Stock symbol (required)
        start_date: Start date (optional, format: YYYY-MM-DD)
        end_date: End date (optional, format: YYYY-MM-DD)
        
    Returns:
        JSON string with historical factor values
    """
    factor_name = params.get("factor_name")
    if not factor_name:
        raise ValueError("Parameter 'factor_name' is required")
    
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
    data = await call_api("GET", f"/api/factors/{factor_name}/values/{symbol}{query_string}")
    
    return json.dumps(data, ensure_ascii=False)
```

- [ ] **Step 2: Run test and commit**

Run: `cd quantsys-v2 && pytest tests/daemon/test_factor_handlers.py::test_get_factor_values_success -v`

```bash
git add daemon/handlers/factor_handlers.py tests/daemon/test_factor_handlers.py
git commit -m "feat(daemon): implement get_factor_values handler (L2)"
```

---

## Task 4: Implement list_available_factors Handler

- [ ] **Step 1: Write test and implement**

Append to `tests/daemon/test_factor_handlers.py`:

```python
from daemon.handlers.factor_handlers import list_available_factors


@pytest.mark.asyncio
async def test_list_available_factors_success():
    """Test list_available_factors returns factor definitions."""
    params = {}
    
    mock_response = {
        "factors": [
            {
                "name": "momentum",
                "description": "Price momentum factor",
                "category": "technical"
            },
            {
                "name": "value",
                "description": "Value factor based on P/E ratio",
                "category": "fundamental"
            }
        ],
        "total": 2
    }
    
    with patch("daemon.handlers.factor_handlers.call_api", new_callable=AsyncMock) as mock_api:
        mock_api.return_value = mock_response
        
        result = await list_available_factors(params)
        parsed = json.loads(result)
        
        assert parsed["total"] == 2
        assert len(parsed["factors"]) == 2
        assert parsed["factors"][0]["name"] == "momentum"


@pytest.mark.asyncio
async def test_list_available_factors_with_category():
    """Test list_available_factors filters by category."""
    params = {"category": "technical"}
    
    mock_response = {
        "factors": [
            {"name": "momentum", "description": "Price momentum", "category": "technical"}
        ],
        "total": 1
    }
    
    with patch("daemon.handlers.factor_handlers.call_api", new_callable=AsyncMock) as mock_api:
        mock_api.return_value = mock_response
        
        result = await list_available_factors(params)
        parsed = json.loads(result)
        
        assert parsed["total"] == 1
        mock_api.assert_called_once()
```

Append to `daemon/handlers/factor_handlers.py`:

```python
@register_method("list_available_factors")
async def list_available_factors(params: dict) -> str:
    """
    List all available factor definitions.
    
    Params:
        category: Filter by category (optional)
        
    Returns:
        JSON string with factor definitions
    """
    # Build query params
    query_params = []
    if params.get("category"):
        query_params.append(f"category={params['category']}")
    
    query_string = "?" + "&".join(query_params) if query_params else ""
    
    # Call API
    data = await call_api("GET", f"/api/factors/list{query_string}")
    
    return json.dumps(data, ensure_ascii=False)
```

- [ ] **Step 2: Run tests and commit**

Run: `cd quantsys-v2 && pytest tests/daemon/test_factor_handlers.py -k list_available_factors -v`

```bash
git add daemon/handlers/factor_handlers.py tests/daemon/test_factor_handlers.py
git commit -m "feat(daemon): implement list_available_factors handler (L2)"
```

---

## Task 5: Implement validate_factor_expression Handler

- [ ] **Step 1: Write test and implement**

Append to `tests/daemon/test_factor_handlers.py`:

```python
from daemon.handlers.factor_handlers import validate_factor_expression


@pytest.mark.asyncio
async def test_validate_factor_expression_valid():
    """Test validate_factor_expression returns valid for correct expression."""
    params = {
        "expression": "close / sma(close, 20) - 1"
    }
    
    mock_response = {
        "valid": True,
        "message": "Expression is valid"
    }
    
    with patch("daemon.handlers.factor_handlers.call_api", new_callable=AsyncMock) as mock_api:
        mock_api.return_value = mock_response
        
        result = await validate_factor_expression(params)
        parsed = json.loads(result)
        
        assert parsed["valid"] is True


@pytest.mark.asyncio
async def test_validate_factor_expression_invalid():
    """Test validate_factor_expression returns error for invalid expression."""
    params = {
        "expression": "close / 0"
    }
    
    mock_response = {
        "valid": False,
        "message": "Division by zero",
        "errors": ["Division by zero at position 8"]
    }
    
    with patch("daemon.handlers.factor_handlers.call_api", new_callable=AsyncMock) as mock_api:
        mock_api.return_value = mock_response
        
        result = await validate_factor_expression(params)
        parsed = json.loads(result)
        
        assert parsed["valid"] is False
        assert "errors" in parsed


@pytest.mark.asyncio
async def test_validate_factor_expression_missing_expression():
    """Test validate_factor_expression requires expression."""
    params = {}
    
    with pytest.raises(ValueError) as exc_info:
        await validate_factor_expression(params)
    
    assert "expression" in str(exc_info.value).lower()
```

Append to `daemon/handlers/factor_handlers.py`:

```python
@register_method("validate_factor_expression")
async def validate_factor_expression(params: dict) -> str:
    """
    Validate factor calculation expression.
    
    Params:
        expression: Factor expression to validate (required)
        
    Returns:
        JSON string with validation result
    """
    expression = params.get("expression")
    if not expression:
        raise ValueError("Parameter 'expression' is required")
    
    # Build request body
    request_data = {
        "expression": expression
    }
    
    # Call API
    data = await call_api("POST", "/api/factors/validate", data=request_data)
    
    return json.dumps(data, ensure_ascii=False)
```

- [ ] **Step 2: Run tests and commit**

Run: `cd quantsys-v2 && pytest tests/daemon/test_factor_handlers.py -k validate_factor_expression -v`

```bash
git add daemon/handlers/factor_handlers.py tests/daemon/test_factor_handlers.py
git commit -m "feat(daemon): implement validate_factor_expression handler (L2)"
```

---

## Task 6: Register Factor Handlers in Server

- [ ] **Step 1: Import handlers in server**

Update `daemon/server.py`, add after data_handlers import:

```python
from daemon.handlers import factor_handlers
```

- [ ] **Step 2: Run full test suite**

Run: `cd quantsys-v2 && pytest tests/daemon/ -v`
Expected: All tests PASS

- [ ] **Step 3: Test with real daemon**

```bash
cd quantsys-v2
echo '{"jsonrpc": "2.0", "id": 1, "method": "list_available_factors", "params": {}}' | python -m daemon.server
```

Expected: JSON-RPC response with factor list (or error if API not running)

- [ ] **Step 4: Commit**

```bash
git add daemon/server.py
git commit -m "feat(daemon): register L2 factor handlers in server"
```

---

## Phase 3 Complete

**Deliverables:**
✅ 5 L2 Factor Layer handlers implemented and tested
✅ All handlers registered in daemon server
✅ Unit tests with mocked API calls passing
✅ Integration tests passing

**Methods Implemented:**
1. ✅ calculate_factor
2. ✅ batch_calculate_factors
3. ✅ get_factor_values
4. ✅ list_available_factors
5. ✅ validate_factor_expression

**Next Steps:**
- Phase 4: Implement L3 Model Layer handlers (5 methods)
- Phase 5: Documentation and cleanup
