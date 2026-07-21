"""Tests for L3 model layer handlers."""
import pytest
import json
from unittest.mock import AsyncMock, patch
from infrastructure.daemon.handlers.model_handlers import (
    model_train,
    model_predict,
    model_evaluate,
    model_list,
    model_monitor
)


@pytest.mark.asyncio
async def test_model_train_success():
    params = {
        "model_name": "momentum_predictor",
        "model_type": "random_forest",
        "features": ["momentum", "value"],
        "target": "returns_5d"
    }
    mock_response = {"job_id": "train_job_123", "status": "started", "model_name": "momentum_predictor"}
    with patch("daemon.handlers.model_handlers.call_api", new_callable=AsyncMock) as mock_api:
        mock_api.return_value = mock_response
        result = await model_train(params)
        parsed = json.loads(result)
        assert parsed["job_id"] == "train_job_123"


@pytest.mark.asyncio
async def test_model_train_missing_model_name():
    with pytest.raises(ValueError) as exc_info:
        await model_train({"model_type": "random_forest"})
    assert "model_name" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_model_train_missing_features():
    with pytest.raises(ValueError) as exc_info:
        await model_train({"model_name": "test", "model_type": "rf", "target": "returns"})
    assert "features" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_model_predict_success():
    params = {"model_name": "momentum_predictor", "symbols": ["AAPL", "GOOGL"], "date": "2024-01-15"}
    mock_response = {"model_name": "momentum_predictor", "predictions": {"AAPL": 0.025, "GOOGL": 0.018}}
    with patch("daemon.handlers.model_handlers.call_api", new_callable=AsyncMock) as mock_api:
        mock_api.return_value = mock_response
        result = await model_predict(params)
        parsed = json.loads(result)
        assert parsed["predictions"]["AAPL"] == 0.025


@pytest.mark.asyncio
async def test_model_predict_missing_symbols():
    with pytest.raises(ValueError) as exc_info:
        await model_predict({"model_name": "test_model"})
    assert "symbols" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_model_evaluate_success():
    params = {"model_name": "momentum_predictor", "test_start": "2024-01-01"}
    mock_response = {"model_name": "momentum_predictor", "metrics": {"accuracy": 0.68, "sharpe_ratio": 1.45}}
    with patch("daemon.handlers.model_handlers.call_api", new_callable=AsyncMock) as mock_api:
        mock_api.return_value = mock_response
        result = await model_evaluate(params)
        parsed = json.loads(result)
        assert parsed["metrics"]["accuracy"] == 0.68


@pytest.mark.asyncio
async def test_model_list_success():
    params = {}
    mock_response = {"models": [{"name": "momentum_predictor", "status": "trained"}], "total": 1}
    with patch("daemon.handlers.model_handlers.call_api", new_callable=AsyncMock) as mock_api:
        mock_api.return_value = mock_response
        result = await model_list(params)
        parsed = json.loads(result)
        assert parsed["total"] == 1


@pytest.mark.asyncio
async def test_model_list_with_status_filter():
    params = {"status": "trained"}
    mock_response = {"models": [{"name": "test"}], "total": 1}
    with patch("daemon.handlers.model_handlers.call_api", new_callable=AsyncMock) as mock_api:
        mock_api.return_value = mock_response
        result = await model_list(params)
        parsed = json.loads(result)
        assert parsed["total"] == 1


@pytest.mark.asyncio
async def test_model_monitor_success():
    params = {"model_name": "momentum_predictor", "start_date": "2024-01-01"}
    mock_response = {"model_name": "momentum_predictor", "metrics": {"prediction_count": 1250, "drift_score": 0.08}}
    with patch("daemon.handlers.model_handlers.call_api", new_callable=AsyncMock) as mock_api:
        mock_api.return_value = mock_response
        result = await model_monitor(params)
        parsed = json.loads(result)
        assert parsed["metrics"]["drift_score"] == 0.08


@pytest.mark.asyncio
async def test_model_monitor_missing_model_name():
    with pytest.raises(ValueError) as exc_info:
        await model_monitor({})
    assert "model_name" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_model_monitor_with_alerts():
    params = {"model_name": "momentum_predictor"}
    mock_response = {
        "model_name": "momentum_predictor",
        "metrics": {"drift_score": 0.25, "alerts": [{"type": "drift_warning", "severity": "medium"}]}
    }
    with patch("daemon.handlers.model_handlers.call_api", new_callable=AsyncMock) as mock_api:
        mock_api.return_value = mock_response
        result = await model_monitor(params)
        parsed = json.loads(result)
        assert len(parsed["metrics"]["alerts"]) == 1
