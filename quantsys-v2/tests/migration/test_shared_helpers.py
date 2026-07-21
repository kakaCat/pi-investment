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
