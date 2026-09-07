"""L3 Model Layer handlers."""
import json
from typing import Any, Dict
from infrastructure.daemon.registry import register_method
from infrastructure.daemon.handlers.api_client import call_api


@register_method("model_train")
async def model_train(params: dict) -> str:
    """Train a new model."""
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

    request_data = {
        "model_name": model_name,
        "model_type": model_type,
        "features": features,
        "target": target
    }

    if params.get("train_start"):
        request_data["train_start"] = params["train_start"]
    if params.get("train_end"):
        request_data["train_end"] = params["train_end"]
    if params.get("hyperparameters"):
        request_data["hyperparameters"] = params["hyperparameters"]

    data = await call_api("POST", "/api/models/train", data=request_data)
    return json.dumps(data, ensure_ascii=False)


@register_method("model_predict")
async def model_predict(params: dict) -> str:
    """Make predictions with a trained model."""
    model_name = params.get("model_name")
    if not model_name:
        raise ValueError("Parameter 'model_name' is required")

    symbols = params.get("symbols")
    if not symbols:
        raise ValueError("Parameter 'symbols' is required")

    if not isinstance(symbols, list):
        raise ValueError("Parameter 'symbols' must be a list")

    request_data = {"model_name": model_name, "symbols": symbols}
    if params.get("date"):
        request_data["date"] = params["date"]

    data = await call_api("POST", "/api/models/predict", data=request_data)
    return json.dumps(data, ensure_ascii=False)


@register_method("model_evaluate")
async def model_evaluate(params: dict) -> str:
    """Evaluate model performance."""
    model_name = params.get("model_name")
    if not model_name:
        raise ValueError("Parameter 'model_name' is required")

    request_data = {"model_name": model_name}
    if params.get("test_start"):
        request_data["test_start"] = params["test_start"]
    if params.get("test_end"):
        request_data["test_end"] = params["test_end"]

    data = await call_api("POST", "/api/models/evaluate", data=request_data)
    return json.dumps(data, ensure_ascii=False)


@register_method("model_list")
async def model_list(params: dict) -> str:
    """List available models."""
    query_params = []
    if params.get("status"):
        query_params.append(f"status={params['status']}")
    if params.get("model_type"):
        query_params.append(f"model_type={params['model_type']}")

    query_string = "?" + "&".join(query_params) if query_params else ""

    data = await call_api("GET", f"/api/models/list{query_string}")
    return json.dumps(data, ensure_ascii=False)


@register_method("model_monitor")
async def model_monitor(params: dict) -> str:
    """Get model monitoring metrics."""
    model_name = params.get("model_name")
    if not model_name:
        raise ValueError("Parameter 'model_name' is required")

    query_params = []
    if params.get("start_date"):
        query_params.append(f"start_date={params['start_date']}")
    if params.get("end_date"):
        query_params.append(f"end_date={params['end_date']}")

    query_string = "?" + "&".join(query_params) if query_params else ""

    data = await call_api("GET", f"/api/models/{model_name}/monitor{query_string}")
    return json.dumps(data, ensure_ascii=False)
