"""JSON-RPC 2.0 protocol handler."""
import json
from typing import Any, Dict, Optional


# JSON-RPC 2.0 Error Codes
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603


def parse_request(raw: str) -> Dict[str, Any]:
    """
    Parse JSON-RPC 2.0 request.
    
    Args:
        raw: Raw JSON string
        
    Returns:
        Parsed request dict with keys: jsonrpc, id, method, params
        
    Raises:
        ValueError: If request is invalid
    """
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"Parse error: {e}")
    
    # Validate required fields
    if not isinstance(data, dict):
        raise ValueError("Invalid Request: must be JSON object")
    
    if data.get("jsonrpc") != "2.0":
        raise ValueError("Invalid Request: jsonrpc must be '2.0'")
    
    if "method" not in data:
        raise ValueError("Invalid Request: method is required")
    
    if not isinstance(data["method"], str):
        raise ValueError("Invalid Request: method must be string")
    
    # id is optional for notifications, but we require it
    if "id" not in data:
        raise ValueError("Invalid Request: id is required")

    # Validate params type (must be object or array per JSON-RPC 2.0 spec)
    params = data.get("params", {})
    if params is not None and not isinstance(params, (dict, list)):
        raise ValueError("Invalid Request: params must be object or array")

    return {
        "jsonrpc": data["jsonrpc"],
        "id": data["id"],
        "method": data["method"],
        "params": params
    }


def create_response(request_id: Any, result: Any) -> str:
    """
    Create JSON-RPC 2.0 success response.

    Args:
        request_id: Request ID from original request
        result: Result data (will be JSON-encoded)

    Returns:
        JSON-RPC response as string
    """
    response = {
        "jsonrpc": "2.0",
        "id": request_id,
        "result": result
    }
    return json.dumps(response, ensure_ascii=False)


def create_error_response(
    request_id: Optional[Any],
    code: int,
    message: str,
    data: Optional[Any] = None
) -> str:
    """
    Create JSON-RPC 2.0 error response.
    
    Args:
        request_id: Request ID (None if parse error)
        code: Error code (use constants above)
        message: Error message
        data: Optional additional error data
        
    Returns:
        JSON-RPC error response as string
    """
    error = {
        "code": code,
        "message": message
    }
    if data is not None:
        error["data"] = data
    
    response = {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": error
    }
    return json.dumps(response, ensure_ascii=False)
