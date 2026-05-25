# QuantSys V2 Daemon Migration - Phase 4: L3 Model Layer

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement L3 Model Layer handlers (5 methods) for ML model operations

**Dependencies:** Phase 1, 2, and 3 must be complete

**Architecture:** Each handler calls quantsys-v2 REST API endpoints for model training, prediction, and monitoring

---

## Methods to Implement

1. `model_train` - Train a new model
2. `model_predict` - Make predictions with a trained model
3. `model_evaluate` - Evaluate model performance
4. `model_list` - List available models
5. `model_monitor` - Get model monitoring metrics

---

## Task 1: Implement model_train Handler

**Files:**
- Create: `quantsys-v2/daemon/handlers/model_handlers.py`
- Create: `quantsys-v2/tests/daemon/test_model_handlers.py`

- [ ] **Step 1: Write failing test**

Create `tests/daemon/test_model_handlers.py`:

```python
"""Tests for L3 model layer handlers."""
import pytest
import json
from unittest.mock import AsyncMock, patch
from daemon.handlers.model_handlers import model_train


@pytest.mark.asyncio
async def test_model_train_success():
    """Test model_train starts training job."""
    params = {
        "model_name": "momentum_predictor",
        "model_type": "random_forest",
        "features": ["momentum", "value", "quality"],
        "target": "returns_5d",
        "train_start": "2023-01-01",
        "train_end": "2023-12-31"
    }
    
    mock_response = {
        "job_id": "train_job_123",
        "status": "started",
        "model_name": "momentum_predictor",
        "message": "Training job started"
    }
    
    with patch("daemon.handlers.model_handlers.call_api", new_callable=AsyncMock) as mock_api:
        mock_api.return_value = mock_response
        
        result = await model_train(params)
        parsed = json.loads(result)
        
        assert parsed["job_id"] == "train_job_123"
        assert parsed["status"] == "started"
        mock_api.assert_called_once_with("POST", "/api/models/train", data=params)


@pytest.mark.asyncio
async def test_model_train_missing_model_name():
    """Test model_train requires model_name."""
    params = {"model_type": "random_forest"}
    
    with pytest.raises(ValueError) as exc_info:
        await model_train(params)
    
    assert "model_name" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_model_train_missing_model_type():
    """Test model_train requires model_type."""
    params = {"model_name": "test_model"}
    
    with pytest.raises(ValueError) as exc_info:
        await model_train(params)
    
    assert "model_type" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_model_train_missing_features():
    """Test model_train requires features."""
    params = {
        "model_name": "test_model",
        "model_type": "random_forest"
    }
    
    with pytest.raises(ValueError) as exc_info:
        await model_train(params)
    
    assert "features" in str(exc_info.value).lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd quantsys-v2 && pytest tests/daemon/test_model_handlers.py::test_model_train_success -v`
Expected: FAIL with "ModuleNotFoundError"

- [ ] **Step 3: Implement model handlers**

Create `daemon/handlers/model_handlers.py`:

```python
"""L3 Model Layer handlers."""
import json
from typing import Any, Dict
from daemon.registry import register_method

# Import API client from data_handlers
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from data_handlers import call_api


@register_method("model_train")
async def model_train(params: dict) -> str:
    """
    Train a new model.
    
    Params:
        model_name: Model name (required)
        model_type: Model type (required, e.g., "random_forest", "xgboost", "neural_network")
        features: List of feature names (required)
        target: Target variable name (required)
        train_start: Training start date (optional)
        train_end: Training end date (optional)
        hyperparameters: Model hyperparameters (optional)
        
    Returns:
        JSON string with training job info
    """
    model_name = params.get("model_name")
    if not model_name:
        raise ValueError("Parameter 'model_name' is required")
    
    model_type = params.get("model_type")
    if not model_type:
        raise ValueError("Parameter 'model_type' is required")
    
    features = params.get("features")
    if not features:
        raise ValueError("Parameter 'features' is required")
    
    if not isinstance(features, list):
        raise ValueError("Parameter 'features' must be a list")
    
    target = params.get("target")
    if not target:
        raise ValueError("Parameter 'target' is required")
    
    # Build request body (pass all params)
    request_data = {
        "model_name": model_name,
        "model_type": model_type,
        "features": features,
        "target": target
    }
    
    # Add optional params
    if params.get("train_start"):
        request_data["train_start"] = params["train_start"]
    if params.get("train_end"):
        request_data["train_end"] = params["train_end"]
    if params.get("hyperparameters"):
        request_data["hyperparameters"] = params["hyperparameters"]
    
    # Call API
    data = await call_api("POST", "/api/models/train", data=request_data)
    
    return json.dumps(data, ensure_ascii=False)
```

- [ ] **Step 4: Run tests**

Run: `cd quantsys-v2 && pytest tests/daemon/test_model_handlers.py -k model_train -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add daemon/handlers/model_handlers.py tests/daemon/test_model_handlers.py
git commit -m "feat(daemon): implement model_train handler (L3)"
```

---

## Task 2: Implement model_predict Handler

- [ ] **Step 1: Write failing test**

Append to `tests/daemon/test_model_handlers.py`:

```python
from daemon.handlers.model_handlers import model_predict


@pytest.mark.asyncio
async def test_model_predict_success():
    """Test model_predict returns predictions."""
    params = {
        "model_name": "momentum_predictor",
        "symbols": ["AAPL", "GOOGL"],
        "date": "2024-01-15"
    }
    
    mock_response = {
        "model_name": "momentum_predictor",
        "date": "2024-01-15",
        "predictions": {
            "AAPL": 0.025,
            "GOOGL": 0.018
        }
    }
    
    with patch("daemon.handlers.model_handlers.call_api", new_callable=AsyncMock) as mock_api:
        mock_api.return_value = mock_response
        
        result = await model_predict(params)
        parsed = json.loads(result)
        
        assert parsed["model_name"] == "momentum_predictor"
        assert "AAPL" in parsed["predictions"]
        assert parsed["predictions"]["AAPL"] == 0.025


@pytest.mark.asyncio
async def test_model_predict_missing_model_name():
    """Test model_predict requires model_name."""
    params = {"symbols": ["AAPL"]}
    
    with pytest.raises(ValueError) as exc_info:
        await model_predict(params)
    
    assert "model_name" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_model_predict_missing_symbols():
    """Test model_predict requires symbols."""
    params = {"model_name": "test_model"}
    
    with pytest.raises(ValueError) as exc_info:
        await model_predict(params)
    
    assert "symbols" in str(exc_info.value).lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd quantsys-v2 && pytest tests/daemon/test_model_handlers.py::test_model_predict_success -v`
Expected: FAIL

- [ ] **Step 3: Implement handler**

Append to `daemon/handlers/model_handlers.py`:

```python
@register_method("model_predict")
async def model_predict(params: dict) -> str:
    """
    Make predictions with a trained model.
    
    Params:
        model_name: Model name (required)
        symbols: List of stock symbols (required)
        date: Prediction date (optional, default: latest)
        
    Returns:
        JSON string with predictions
    """
    model_name = params.get("model_name")
    if not model_name:
        raise ValueError("Parameter 'model_name' is required")
    
    symbols = params.get("symbols")
    if not symbols:
        raise ValueError("Parameter 'symbols' is required")
    
    if not isinstance(symbols, list):
        raise ValueError("Parameter 'symbols' must be a list")
    
    # Build request body
    request_data = {
        "model_name": model_name,
        "symbols": symbols
    }
    
    if params.get("date"):
        request_data["date"] = params["date"]
    
    # Call API
    data = await call_api("POST", "/api/models/predict", data=request_data)
    
    return json.dumps(data, ensure_ascii=False)
```

- [ ] **Step 4: Run tests**

Run: `cd quantsys-v2 && pytest tests/daemon/test_model_handlers.py -k model_predict -v`
Expected: All 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add daemon/handlers/model_handlers.py tests/daemon/test_model_handlers.py
git commit -m "feat(daemon): implement model_predict handler (L3)"
```

---

## Task 3: Implement model_evaluate Handler

- [ ] **Step 1: Write test and implement**

Append to `tests/daemon/test_model_handlers.py`:

```python
from daemon.handlers.model_handlers import model_evaluate


@pytest.mark.asyncio
async def test_model_evaluate_success():
    """Test model_evaluate returns performance metrics."""
    params = {
        "model_name": "momentum_predictor",
        "test_start": "2024-01-01",
        "test_end": "2024-01-31"
    }
    
    mock_response = {
        "model_name": "momentum_predictor",
        "metrics": {
            "accuracy": 0.68,
            "precision": 0.72,
            "recall": 0.65,
            "f1_score": 0.68,
            "sharpe_ratio": 1.45
        },
        "test_period": {
            "start": "2024-01-01",
            "end": "2024-01-31"
        }
    }
    
    with patch("daemon.handlers.model_handlers.call_api", new_callable=AsyncMock) as mock_api:
        mock_api.return_value = mock_response
        
        result = await model_evaluate(params)
        parsed = json.loads(result)
        
        assert parsed["model_name"] == "momentum_predictor"
        assert parsed["metrics"]["accuracy"] == 0.68
        assert "sharpe_ratio" in parsed["metrics"]


@pytest.mark.asyncio
async def test_model_evaluate_missing_model_name():
    """Test model_evaluate requires model_name."""
    params = {}
    
    with pytest.raises(ValueError) as exc_info:
        await model_evaluate(params)
    
    assert "model_name" in str(exc_info.value).lower()
```

Append to `daemon/handlers/model_handlers.py`:

```python
@register_method("model_evaluate")
async def model_evaluate(params: dict) -> str:
    """
    Evaluate model performance.
    
    Params:
        model_name: Model name (required)
        test_start: Test period start date (optional)
        test_end: Test period end date (optional)
        
    Returns:
        JSON string with evaluation metrics
    """
    model_name = params.get("model_name")
    if not model_name:
        raise ValueError("Parameter 'model_name' is required")
    
    # Build request body
    request_data = {
        "model_name": model_name
    }
    
    if params.get("test_start"):
        request_data["test_start"] = params["test_start"]
    if params.get("test_end"):
        request_data["test_end"] = params["test_end"]
    
    # Call API
    data = await call_api("POST", "/api/models/evaluate", data=request_data)
    
    return json.dumps(data, ensure_ascii=False)
```

- [ ] **Step 2: Run tests and commit**

Run: `cd quantsys-v2 && pytest tests/daemon/test_model_handlers.py -k model_evaluate -v`

```bash
git add daemon/handlers/model_handlers.py tests/daemon/test_model_handlers.py
git commit -m "feat(daemon): implement model_evaluate handler (L3)"
```

---

## Task 4: Implement model_list Handler

- [ ] **Step 1: Write test and implement**

Append to `tests/daemon/test_model_handlers.py`:

```python
from daemon.handlers.model_handlers import model_list


@pytest.mark.asyncio
async def test_model_list_success():
    """Test model_list returns available models."""
    params = {}
    
    mock_response = {
        "models": [
            {
                "name": "momentum_predictor",
                "type": "random_forest",
                "status": "trained",
                "created_at": "2024-01-10T10:00:00Z",
                "metrics": {"accuracy": 0.68}
            },
            {
                "name": "value_predictor",
                "type": "xgboost",
                "status": "training",
                "created_at": "2024-01-15T14:30:00Z"
            }
        ],
        "total": 2
    }
    
    with patch("daemon.handlers.model_handlers.call_api", new_callable=AsyncMock) as mock_api:
        mock_api.return_value = mock_response
        
        result = await model_list(params)
        parsed = json.loads(result)
        
        assert parsed["total"] == 2
        assert len(parsed["models"]) == 2
        assert parsed["models"][0]["name"] == "momentum_predictor"


@pytest.mark.asyncio
async def test_model_list_with_status_filter():
    """Test model_list filters by status."""
    params = {"status": "trained"}
    
    mock_response = {
        "models": [
            {"name": "momentum_predictor", "status": "trained"}
        ],
        "total": 1
    }
    
    with patch("daemon.handlers.model_handlers.call_api", new_callable=AsyncMock) as mock_api:
        mock_api.return_value = mock_response
        
        result = await model_list(params)
        parsed = json.loads(result)
        
        assert parsed["total"] == 1
        mock_api.assert_called_once()
```

Append to `daemon/handlers/model_handlers.py`:

```python
@register_method("model_list")
async def model_list(params: dict) -> str:
    """
    List available models.
    
    Params:
        status: Filter by status (optional, e.g., "trained", "training", "failed")
        model_type: Filter by model type (optional)
        
    Returns:
        JSON string with model list
    """
    # Build query params
    query_params = []
    if params.get("status"):
        query_params.append(f"status={params['status']}")
    if params.get("model_type"):
        query_params.append(f"model_type={params['model_type']}")
    
    query_string = "?" + "&".join(query_params) if query_params else ""
    
    # Call API
    data = await call_api("GET", f"/api/models/list{query_string}")
    
    return json.dumps(data, ensure_ascii=False)
```

- [ ] **Step 2: Run tests and commit**

Run: `cd quantsys-v2 && pytest tests/daemon/test_model_handlers.py -k model_list -v`

```bash
git add daemon/handlers/model_handlers.py tests/daemon/test_model_handlers.py
git commit -m "feat(daemon): implement model_list handler (L3)"
```

---

## Task 5: Implement model_monitor Handler

- [ ] **Step 1: Write test and implement**

Append to `tests/daemon/test_model_handlers.py`:

```python
from daemon.handlers.model_handlers import model_monitor


@pytest.mark.asyncio
async def test_model_monitor_success():
    """Test model_monitor returns monitoring metrics."""
    params = {
        "model_name": "momentum_predictor",
        "start_date": "2024-01-01",
        "end_date": "2024-01-31"
    }
    
    mock_response = {
        "model_name": "momentum_predictor",
        "period": {
            "start": "2024-01-01",
            "end": "2024-01-31"
        },
        "metrics": {
            "prediction_count": 1250,
            "avg_confidence": 0.72,
            "accuracy": 0.65,
            "drift_score": 0.08,
            "alerts": []
        }
    }
    
    with patch("daemon.handlers.model_handlers.call_api", new_callable=AsyncMock) as mock_api:
        mock_api.return_value = mock_response
        
        result = await model_monitor(params)
        parsed = json.loads(result)
        
        assert parsed["model_name"] == "momentum_predictor"
        assert parsed["metrics"]["prediction_count"] == 1250
        assert parsed["metrics"]["drift_score"] == 0.08


@pytest.mark.asyncio
async def test_model_monitor_missing_model_name():
    """Test model_monitor requires model_name."""
    params = {}
    
    with pytest.raises(ValueError) as exc_info:
        await model_monitor(params)
    
    assert "model_name" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_model_monitor_with_alerts():
    """Test model_monitor returns alerts when drift detected."""
    params = {"model_name": "momentum_predictor"}
    
    mock_response = {
        "model_name": "momentum_predictor",
        "metrics": {
            "drift_score": 0.25,
            "alerts": [
                {
                    "type": "drift_warning",
                    "message": "Feature drift detected",
                    "severity": "medium"
                }
            ]
        }
    }
    
    with patch("daemon.handlers.model_handlers.call_api", new_callable=AsyncMock) as mock_api:
        mock_api.return_value = mock_response
        
        result = await model_monitor(params)
        parsed = json.loads(result)
        
        assert len(parsed["metrics"]["alerts"]) == 1
        assert parsed["metrics"]["alerts"][0]["type"] == "drift_warning"
```

Append to `daemon/handlers/model_handlers.py`:

```python
@register_method("model_monitor")
async def model_monitor(params: dict) -> str:
    """
    Get model monitoring metrics.
    
    Params:
        model_name: Model name (required)
        start_date: Monitoring period start (optional)
        end_date: Monitoring period end (optional)
        
    Returns:
        JSON string with monitoring metrics
    """
    model_name = params.get("model_name")
    if not model_name:
        raise ValueError("Parameter 'model_name' is required")
    
    # Build query params
    query_params = []
    if params.get("start_date"):
        query_params.append(f"start_date={params['start_date']}")
    if params.get("end_date"):
        query_params.append(f"end_date={params['end_date']}")
    
    query_string = "?" + "&".join(query_params) if query_params else ""
    
    # Call API
    data = await call_api("GET", f"/api/models/{model_name}/monitor{query_string}")
    
    return json.dumps(data, ensure_ascii=False)
```

- [ ] **Step 2: Run tests and commit**

Run: `cd quantsys-v2 && pytest tests/daemon/test_model_handlers.py -k model_monitor -v`

```bash
git add daemon/handlers/model_handlers.py tests/daemon/test_model_handlers.py
git commit -m "feat(daemon): implement model_monitor handler (L3)"
```

---

## Task 6: Register Model Handlers in Server

- [ ] **Step 1: Import handlers in server**

Update `daemon/server.py`, add after factor_handlers import:

```python
from daemon.handlers import model_handlers
```

- [ ] **Step 2: Run full test suite**

Run: `cd quantsys-v2 && pytest tests/daemon/ -v`
Expected: All tests PASS

- [ ] **Step 3: Test with real daemon**

```bash
cd quantsys-v2
echo '{"jsonrpc": "2.0", "id": 1, "method": "model_list", "params": {}}' | python -m daemon.server
```

Expected: JSON-RPC response with model list (or error if API not running)

- [ ] **Step 4: Commit**

```bash
git add daemon/server.py
git commit -m "feat(daemon): register L3 model handlers in server"
```

---

## Phase 4 Complete

**Deliverables:**
✅ 5 L3 Model Layer handlers implemented and tested
✅ All handlers registered in daemon server
✅ Unit tests with mocked API calls passing
✅ Integration tests passing

**Methods Implemented:**
1. ✅ model_train
2. ✅ model_predict
3. ✅ model_evaluate
4. ✅ model_list
5. ✅ model_monitor

**Next Steps:**
- Phase 5: Documentation and cleanup
