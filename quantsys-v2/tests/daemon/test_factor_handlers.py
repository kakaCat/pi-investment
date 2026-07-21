"""Tests for L2 factor layer handlers."""
import pytest
import json
from unittest.mock import AsyncMock, patch
from infrastructure.daemon.handlers.factor_handlers import (
    calculate_factor,
    batch_calculate_factors,
    get_factor_values,
    list_available_factors,
    validate_factor_expression
)


@pytest.mark.asyncio
async def test_calculate_factor_success():
    params = {"factor_name": "momentum", "symbols": ["AAPL", "GOOGL"], "date": "2024-01-15"}
    mock_response = {"factor_name": "momentum", "date": "2024-01-15", "values": {"AAPL": 0.15, "GOOGL": 0.08}}
    with patch("daemon.handlers.factor_handlers.call_api", new_callable=AsyncMock) as mock_api:
        mock_api.return_value = mock_response
        result = await calculate_factor(params)
        parsed = json.loads(result)
        assert parsed["factor_name"] == "momentum"
        assert parsed["values"]["AAPL"] == 0.15


@pytest.mark.asyncio
async def test_calculate_factor_missing_factor_name():
    with pytest.raises(ValueError) as exc_info:
        await calculate_factor({"symbols": ["AAPL"]})
    assert "factor_name" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_calculate_factor_missing_symbols():
    with pytest.raises(ValueError) as exc_info:
        await calculate_factor({"factor_name": "momentum"})
    assert "symbols" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_batch_calculate_factors_success():
    params = {"factor_names": ["momentum", "value"], "symbols": ["AAPL"], "date": "2024-01-15"}
    mock_response = {"date": "2024-01-15", "factors": {"momentum": {"AAPL": 0.15}, "value": {"AAPL": -0.05}}}
    with patch("daemon.handlers.factor_handlers.call_api", new_callable=AsyncMock) as mock_api:
        mock_api.return_value = mock_response
        result = await batch_calculate_factors(params)
        parsed = json.loads(result)
        assert len(parsed["factors"]) == 2


@pytest.mark.asyncio
async def test_batch_calculate_factors_missing_factor_names():
    with pytest.raises(ValueError) as exc_info:
        await batch_calculate_factors({"symbols": ["AAPL"]})
    assert "factor_names" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_get_factor_values_success():
    params = {"factor_name": "momentum", "symbol": "AAPL", "start_date": "2024-01-01"}
    mock_response = {"factor_name": "momentum", "symbol": "AAPL", "values": [{"date": "2024-01-02", "value": 0.12}]}
    with patch("daemon.handlers.factor_handlers.call_api", new_callable=AsyncMock) as mock_api:
        mock_api.return_value = mock_response
        result = await get_factor_values(params)
        parsed = json.loads(result)
        assert parsed["factor_name"] == "momentum"


@pytest.mark.asyncio
async def test_list_available_factors_success():
    params = {}
    mock_response = {"factors": [{"name": "momentum", "description": "Price momentum", "category": "technical"}], "total": 1}
    with patch("daemon.handlers.factor_handlers.call_api", new_callable=AsyncMock) as mock_api:
        mock_api.return_value = mock_response
        result = await list_available_factors(params)
        parsed = json.loads(result)
        assert parsed["total"] == 1


@pytest.mark.asyncio
async def test_list_available_factors_with_category():
    params = {"category": "technical"}
    mock_response = {"factors": [{"name": "momentum"}], "total": 1}
    with patch("daemon.handlers.factor_handlers.call_api", new_callable=AsyncMock) as mock_api:
        mock_api.return_value = mock_response
        result = await list_available_factors(params)
        parsed = json.loads(result)
        assert parsed["total"] == 1


@pytest.mark.asyncio
async def test_validate_factor_expression_valid():
    params = {"expression": "close / sma(close, 20) - 1"}
    mock_response = {"valid": True, "message": "Expression is valid"}
    with patch("daemon.handlers.factor_handlers.call_api", new_callable=AsyncMock) as mock_api:
        mock_api.return_value = mock_response
        result = await validate_factor_expression(params)
        parsed = json.loads(result)
        assert parsed["valid"] is True


@pytest.mark.asyncio
async def test_validate_factor_expression_invalid():
    params = {"expression": "close / 0"}
    mock_response = {"valid": False, "message": "Division by zero", "errors": ["Division by zero at position 8"]}
    with patch("daemon.handlers.factor_handlers.call_api", new_callable=AsyncMock) as mock_api:
        mock_api.return_value = mock_response
        result = await validate_factor_expression(params)
        parsed = json.loads(result)
        assert parsed["valid"] is False


@pytest.mark.asyncio
async def test_validate_factor_expression_missing_expression():
    with pytest.raises(ValueError) as exc_info:
        await validate_factor_expression({})
    assert "expression" in str(exc_info.value).lower()
