"""L2 Factor Layer handlers."""
import json
from typing import Any, Dict
from infrastructure.daemon.registry import register_method
from infrastructure.daemon.handlers.api_client import call_api


@register_method("calculate_factor")
async def calculate_factor(params: dict) -> str:
    """Calculate a specific factor for stocks."""
    factor_name = params.get("factor_name")
    if not factor_name:
        raise ValueError("Parameter 'factor_name' is required")

    symbols = params.get("symbols")
    if not symbols:
        raise ValueError("Parameter 'symbols' is required")

    if not isinstance(symbols, list):
        raise ValueError("Parameter 'symbols' must be a list")

    request_data = {"factor_name": factor_name, "symbols": symbols}
    if params.get("date"):
        request_data["date"] = params["date"]

    data = await call_api("POST", "/api/factors/calculate", data=request_data)
    return json.dumps(data, ensure_ascii=False)


@register_method("batch_calculate_factors")
async def batch_calculate_factors(params: dict) -> str:
    """Calculate multiple factors in batch."""
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

    request_data = {"factor_names": factor_names, "symbols": symbols}
    if params.get("date"):
        request_data["date"] = params["date"]

    data = await call_api("POST", "/api/factors/batch-calculate", data=request_data)
    return json.dumps(data, ensure_ascii=False)


@register_method("get_factor_values")
async def get_factor_values(params: dict) -> str:
    """Get historical factor values."""
    factor_name = params.get("factor_name")
    if not factor_name:
        raise ValueError("Parameter 'factor_name' is required")

    symbol = params.get("symbol")
    if not symbol:
        raise ValueError("Parameter 'symbol' is required")

    query_params = []
    if params.get("start_date"):
        query_params.append(f"start_date={params['start_date']}")
    if params.get("end_date"):
        query_params.append(f"end_date={params['end_date']}")

    query_string = "?" + "&".join(query_params) if query_params else ""

    data = await call_api("GET", f"/api/factors/{factor_name}/values/{symbol}{query_string}")
    return json.dumps(data, ensure_ascii=False)


@register_method("list_available_factors")
async def list_available_factors(params: dict) -> str:
    """List all available factor definitions."""
    query_params = []
    if params.get("category"):
        query_params.append(f"category={params['category']}")

    query_string = "?" + "&".join(query_params) if query_params else ""

    data = await call_api("GET", f"/api/factors/list{query_string}")
    return json.dumps(data, ensure_ascii=False)


@register_method("validate_factor_expression")
async def validate_factor_expression(params: dict) -> str:
    """Validate factor calculation expression."""
    expression = params.get("expression")
    if not expression:
        raise ValueError("Parameter 'expression' is required")

    request_data = {"expression": expression}

    data = await call_api("POST", "/api/factors/validate", data=request_data)
    return json.dumps(data, ensure_ascii=False)
