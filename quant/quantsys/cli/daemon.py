"""
QuantSys CLI Daemon — JSON-RPC 2.0 server over stdin/stdout.

Usage: python -m quantsys.cli --daemon

Receives JSON-RPC requests line-by-line on stdin, dispatches to registered
handler functions via the DAEMON_METHOD_MAP, and writes JSON-RPC responses
to stdout.
"""

from __future__ import annotations

import json
import sys
import traceback
from typing import Any, Callable, Dict

DaemonHandler = Callable[[Dict[str, Any]], Any]

DAEMON_METHOD_MAP: Dict[str, DaemonHandler] = {}


def register_daemon_method(method: str, handler: DaemonHandler) -> None:
    """Register a handler for a JSON-RPC method name."""
    DAEMON_METHOD_MAP[method] = handler


def _resolve_handler(method: str) -> DaemonHandler | None:
    """Look up handler by method name."""
    return DAEMON_METHOD_MAP.get(method)


def handle_request(request: dict) -> dict:
    """Process a single JSON-RPC request and return the response dict."""
    method = request.get("method", "")
    params = request.get("params", {})
    request_id = request.get("id")

    handler = _resolve_handler(method)
    if handler is None:
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {
                "code": -32601,
                "message": f"Method not found: {method}",
            },
        }

    try:
        result = handler(params)
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": json.dumps(result, default=str, ensure_ascii=False),
        }
    except Exception:
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {
                "code": -32000,
                "message": traceback.format_exc(),
            },
        }


def run_daemon() -> None:
    """Main loop: read stdin, dispatch, write stdout."""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            error_response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": "Parse error"},
            }
            print(json.dumps(error_response, ensure_ascii=False), flush=True)
            continue

        response = handle_request(request)
        print(json.dumps(response, ensure_ascii=False), flush=True)
