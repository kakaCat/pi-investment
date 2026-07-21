"""Tests for JSON-RPC 2.0 protocol handler."""
import pytest
import json
from infrastructure.daemon.protocol import parse_request, create_response, create_error_response


def test_parse_request_valid():
    """Test parsing valid JSON-RPC request."""
    raw = "{\"jsonrpc\": \"2.0\", \"id\": 1, \"method\": \"test_method\", \"params\": {\"key\": \"value\"}}"
    result = parse_request(raw)
    
    assert result["jsonrpc"] == "2.0"
    assert result["id"] == 1
    assert result["method"] == "test_method"
    assert result["params"] == {"key": "value"}


def test_parse_request_invalid_json():
    """Test parsing invalid JSON."""
    raw = "{\"invalid json"
    
    with pytest.raises(ValueError) as exc_info:
        parse_request(raw)
    
    assert "Parse error" in str(exc_info.value)


def test_parse_request_missing_jsonrpc():
    """Test request missing jsonrpc field."""
    raw = "{\"id\": 1, \"method\": \"test\"}"
    
    with pytest.raises(ValueError) as exc_info:
        parse_request(raw)
    
    assert "Invalid Request" in str(exc_info.value)


def test_parse_request_missing_method():
    """Test request missing method field."""
    raw = "{\"jsonrpc\": \"2.0\", \"id\": 1}"

    with pytest.raises(ValueError) as exc_info:
        parse_request(raw)

    assert "Invalid Request" in str(exc_info.value)


def test_parse_request_missing_id():
    """Test request missing id field."""
    raw = "{\"jsonrpc\": \"2.0\", \"method\": \"test\"}"

    with pytest.raises(ValueError) as exc_info:
        parse_request(raw)

    assert "id is required" in str(exc_info.value)


def test_create_response():
    """Test creating success response."""
    result = create_response(1, {"data": "test"})
    parsed = json.loads(result)

    assert parsed["jsonrpc"] == "2.0"
    assert parsed["id"] == 1
    assert parsed["result"] == {"data": "test"}


def test_create_error_response():
    """Test creating error response."""
    from infrastructure.daemon.protocol import INTERNAL_ERROR
    result = create_error_response(1, INTERNAL_ERROR, "Test error")
    parsed = json.loads(result)
    
    assert parsed["jsonrpc"] == "2.0"
    assert parsed["id"] == 1
    assert parsed["error"]["code"] == INTERNAL_ERROR
    assert parsed["error"]["message"] == "Test error"


def test_create_error_response_with_data():
    """Test creating error response with additional data."""
    from infrastructure.daemon.protocol import INVALID_PARAMS
    result = create_error_response(1, INVALID_PARAMS, "Bad param", data={"field": "symbol"})
    parsed = json.loads(result)
    
    assert parsed["error"]["data"] == {"field": "symbol"}
