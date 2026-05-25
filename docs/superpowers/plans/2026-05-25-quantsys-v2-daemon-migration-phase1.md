# QuantSys V2 Daemon Migration - Phase 1: Infrastructure

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the JSON-RPC 2.0 daemon infrastructure in quantsys-v2

**Architecture:** Independent daemon service that listens on stdin/stdout, parses JSON-RPC requests, routes to handlers via registry, and returns JSON-RPC responses.

**Tech Stack:** Python 3.9+, asyncio, JSON-RPC 2.0 protocol

---

## File Structure

**New Files:**
- `quantsys-v2/daemon/__init__.py` - Package marker
- `quantsys-v2/daemon/server.py` - Main daemon entry point
- `quantsys-v2/daemon/protocol.py` - JSON-RPC 2.0 protocol handler
- `quantsys-v2/daemon/registry.py` - Method registration system
- `quantsys-v2/daemon/handlers/__init__.py` - Handlers package marker
- `quantsys-v2/tests/daemon/__init__.py` - Tests package marker
- `quantsys-v2/tests/daemon/test_protocol.py` - Protocol unit tests
- `quantsys-v2/tests/daemon/test_registry.py` - Registry unit tests
- `quantsys-v2/tests/daemon/test_integration.py` - Integration tests

**Modified Files:**
- `src/infrastructure/quant/quantsys-daemon-adapter.ts:20` - Update QUANT_ROOT path
- `src/infrastructure/quant/quantsys-daemon-adapter.ts:74` - Update spawn command

---

## Task 1: Create Daemon Package Structure

**Files:**
- Create: `quantsys-v2/daemon/__init__.py`
- Create: `quantsys-v2/daemon/handlers/__init__.py`
- Create: `quantsys-v2/tests/daemon/__init__.py`

- [ ] **Step 1: Create daemon package**

```bash
cd quantsys-v2
mkdir -p daemon/handlers
touch daemon/__init__.py
touch daemon/handlers/__init__.py
```

- [ ] **Step 2: Create tests package**

```bash
mkdir -p tests/daemon
touch tests/daemon/__init__.py
```

- [ ] **Step 3: Verify structure**

Run: `ls -la daemon/ daemon/handlers/ tests/daemon/`
Expected: All __init__.py files exist

- [ ] **Step 4: Commit**

```bash
git add daemon/ tests/daemon/
git commit -m "feat(daemon): create daemon package structure"
```

---

## Task 2: Implement JSON-RPC 2.0 Protocol Handler

**Files:**
- Create: `quantsys-v2/daemon/protocol.py`
- Create: `quantsys-v2/tests/daemon/test_protocol.py`

- [ ] **Step 1: Write failing test for request parsing**

Create `tests/daemon/test_protocol.py`:

```python
"""Tests for JSON-RPC 2.0 protocol handler."""
import pytest
import json
from daemon.protocol import parse_request, create_response, create_error_response


def test_parse_request_valid():
    """Test parsing valid JSON-RPC request."""
    raw = '{"jsonrpc": "2.0", "id": 1, "method": "test_method", "params": {"key": "value"}}'
    result = parse_request(raw)
    
    assert result["jsonrpc"] == "2.0"
    assert result["id"] == 1
    assert result["method"] == "test_method"
    assert result["params"] == {"key": "value"}


def test_parse_request_invalid_json():
    """Test parsing invalid JSON."""
    raw = '{"invalid json'
    
    with pytest.raises(ValueError) as exc_info:
        parse_request(raw)
    
    assert "Parse error" in str(exc_info.value)


def test_parse_request_missing_jsonrpc():
    """Test request missing jsonrpc field."""
    raw = '{"id": 1, "method": "test"}'
    
    with pytest.raises(ValueError) as exc_info:
        parse_request(raw)
    
    assert "Invalid Request" in str(exc_info.value)


def test_parse_request_missing_method():
    """Test request missing method field."""
    raw = '{"jsonrpc": "2.0", "id": 1}'
    
    with pytest.raises(ValueError) as exc_info:
        parse_request(raw)
    
    assert "Invalid Request" in str(exc_info.value)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd quantsys-v2 && pytest tests/daemon/test_protocol.py::test_parse_request_valid -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'daemon.protocol'"

- [ ] **Step 3: Implement protocol parser**

Create `daemon/protocol.py`:

```python
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
    
    return {
        "jsonrpc": data["jsonrpc"],
        "id": data["id"],
        "method": data["method"],
        "params": data.get("params", {})
    }


def create_response(request_id: Any, result: str) -> str:
    """
    Create JSON-RPC 2.0 success response.
    
    Args:
        request_id: Request ID from original request
        result: Result string (JSON-encoded data)
        
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd quantsys-v2 && pytest tests/daemon/test_protocol.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Add tests for response creation**

Append to `tests/daemon/test_protocol.py`:

```python
def test_create_response():
    """Test creating success response."""
    result = create_response(1, '{"data": "test"}')
    parsed = json.loads(result)
    
    assert parsed["jsonrpc"] == "2.0"
    assert parsed["id"] == 1
    assert parsed["result"] == '{"data": "test"}'


def test_create_error_response():
    """Test creating error response."""
    result = create_error_response(1, INTERNAL_ERROR, "Test error")
    parsed = json.loads(result)
    
    assert parsed["jsonrpc"] == "2.0"
    assert parsed["id"] == 1
    assert parsed["error"]["code"] == INTERNAL_ERROR
    assert parsed["error"]["message"] == "Test error"


def test_create_error_response_with_data():
    """Test creating error response with additional data."""
    result = create_error_response(1, INVALID_PARAMS, "Bad param", data={"field": "symbol"})
    parsed = json.loads(result)
    
    assert parsed["error"]["data"] == {"field": "symbol"}
```

- [ ] **Step 6: Run new tests**

Run: `cd quantsys-v2 && pytest tests/daemon/test_protocol.py::test_create_response -v`
Expected: All 3 new tests PASS

- [ ] **Step 7: Commit**

```bash
git add daemon/protocol.py tests/daemon/test_protocol.py
git commit -m "feat(daemon): implement JSON-RPC 2.0 protocol handler"
```

---

## Task 3: Implement Method Registry

**Files:**
- Create: `quantsys-v2/daemon/registry.py`
- Create: `quantsys-v2/tests/daemon/test_registry.py`

- [ ] **Step 1: Write failing test for method registration**

Create `tests/daemon/test_registry.py`:

```python
"""Tests for method registry."""
import pytest
from daemon.registry import MethodRegistry, register_method


@pytest.fixture
def registry():
    """Create fresh registry for each test."""
    return MethodRegistry()


def test_register_method_decorator(registry):
    """Test registering method with decorator."""
    @register_method("test_method", registry=registry)
    async def test_handler(params: dict) -> str:
        return "test_result"
    
    assert registry.has_method("test_method")
    handler = registry.get_handler("test_method")
    assert handler is not None


def test_get_handler_not_found(registry):
    """Test getting non-existent handler."""
    handler = registry.get_handler("nonexistent")
    assert handler is None


def test_register_duplicate_method(registry):
    """Test registering duplicate method raises error."""
    @register_method("duplicate", registry=registry)
    async def handler1(params: dict) -> str:
        return "first"
    
    with pytest.raises(ValueError) as exc_info:
        @register_method("duplicate", registry=registry)
        async def handler2(params: dict) -> str:
            return "second"
    
    assert "already registered" in str(exc_info.value)


@pytest.mark.asyncio
async def test_call_handler(registry):
    """Test calling registered handler."""
    @register_method("echo", registry=registry)
    async def echo_handler(params: dict) -> str:
        return params.get("message", "")
    
    handler = registry.get_handler("echo")
    result = await handler({"message": "hello"})
    assert result == "hello"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd quantsys-v2 && pytest tests/daemon/test_registry.py::test_register_method_decorator -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'daemon.registry'"

- [ ] **Step 3: Implement method registry**

Create `daemon/registry.py`:

```python
"""Method registry for daemon handlers."""
from typing import Callable, Dict, Optional, Any
import inspect


class MethodRegistry:
    """Registry for JSON-RPC method handlers."""
    
    def __init__(self):
        """Initialize empty registry."""
        self._handlers: Dict[str, Callable] = {}
    
    def register(self, method_name: str, handler: Callable) -> None:
        """
        Register a method handler.
        
        Args:
            method_name: JSON-RPC method name
            handler: Async function that takes params dict and returns JSON string
            
        Raises:
            ValueError: If method already registered or handler invalid
        """
        if method_name in self._handlers:
            raise ValueError(f"Method '{method_name}' already registered")
        
        if not inspect.iscoroutinefunction(handler):
            raise ValueError(f"Handler for '{method_name}' must be async function")
        
        self._handlers[method_name] = handler
    
    def has_method(self, method_name: str) -> bool:
        """Check if method is registered."""
        return method_name in self._handlers
    
    def get_handler(self, method_name: str) -> Optional[Callable]:
        """Get handler for method, or None if not found."""
        return self._handlers.get(method_name)
    
    def list_methods(self) -> list[str]:
        """List all registered method names."""
        return list(self._handlers.keys())


# Global registry instance
_global_registry = MethodRegistry()


def register_method(method_name: str, registry: Optional[MethodRegistry] = None):
    """
    Decorator to register a method handler.
    
    Args:
        method_name: JSON-RPC method name
        registry: Registry instance (uses global if None)
        
    Example:
        @register_method("get_stock_info")
        async def get_stock_info(params: dict) -> str:
            return json.dumps({"result": "data"})
    """
    target_registry = registry if registry is not None else _global_registry
    
    def decorator(func: Callable) -> Callable:
        target_registry.register(method_name, func)
        return func
    
    return decorator


def get_global_registry() -> MethodRegistry:
    """Get the global registry instance."""
    return _global_registry
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd quantsys-v2 && pytest tests/daemon/test_registry.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add daemon/registry.py tests/daemon/test_registry.py
git commit -m "feat(daemon): implement method registry with decorator"
```

---

## Task 4: Implement Daemon Server

**Files:**
- Create: `quantsys-v2/daemon/server.py`
- Create: `quantsys-v2/tests/daemon/test_integration.py`

- [ ] **Step 1: Write integration test**

Create `tests/daemon/test_integration.py`:

```python
"""Integration tests for daemon server."""
import subprocess
import json
import time
import pytest
from pathlib import Path


@pytest.fixture
def daemon_process():
    """Start daemon process for testing."""
    # Start daemon
    proc = subprocess.Popen(
        ["python", "-m", "daemon.server"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=Path(__file__).parent.parent.parent,
        text=True,
        bufsize=1
    )
    
    # Give it time to start
    time.sleep(0.5)
    
    yield proc
    
    # Cleanup
    proc.terminate()
    proc.wait(timeout=2)


def test_daemon_ping(daemon_process):
    """Test daemon responds to ping request."""
    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "ping",
        "params": {}
    }
    
    # Send request
    daemon_process.stdin.write(json.dumps(request) + "\n")
    daemon_process.stdin.flush()
    
    # Read response
    response_line = daemon_process.stdout.readline()
    response = json.loads(response_line)
    
    assert response["jsonrpc"] == "2.0"
    assert response["id"] == 1
    assert "result" in response
    assert json.loads(response["result"])["status"] == "ok"


def test_daemon_method_not_found(daemon_process):
    """Test daemon returns error for unknown method."""
    request = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "nonexistent_method",
        "params": {}
    }
    
    daemon_process.stdin.write(json.dumps(request) + "\n")
    daemon_process.stdin.flush()
    
    response_line = daemon_process.stdout.readline()
    response = json.loads(response_line)
    
    assert response["jsonrpc"] == "2.0"
    assert response["id"] == 2
    assert "error" in response
    assert response["error"]["code"] == -32601  # METHOD_NOT_FOUND


def test_daemon_invalid_json(daemon_process):
    """Test daemon handles invalid JSON."""
    daemon_process.stdin.write("{invalid json\n")
    daemon_process.stdin.flush()
    
    response_line = daemon_process.stdout.readline()
    response = json.loads(response_line)
    
    assert response["jsonrpc"] == "2.0"
    assert response["id"] is None
    assert "error" in response
    assert response["error"]["code"] == -32700  # PARSE_ERROR
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd quantsys-v2 && pytest tests/daemon/test_integration.py::test_daemon_ping -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'daemon.server'" or daemon doesn't start

- [ ] **Step 3: Implement daemon server**

Create `daemon/server.py`:

```python
"""Daemon server main entry point."""
import sys
import asyncio
import json
import signal
from typing import Optional

from daemon.protocol import (
    parse_request,
    create_response,
    create_error_response,
    PARSE_ERROR,
    INVALID_REQUEST,
    METHOD_NOT_FOUND,
    INVALID_PARAMS,
    INTERNAL_ERROR
)
from daemon.registry import get_global_registry, register_method


# Built-in ping handler
@register_method("ping")
async def ping_handler(params: dict) -> str:
    """Built-in ping handler for health checks."""
    return json.dumps({"status": "ok", "message": "pong"}, ensure_ascii=False)


class DaemonServer:
    """JSON-RPC 2.0 daemon server."""
    
    def __init__(self):
        """Initialize daemon server."""
        self.registry = get_global_registry()
        self.running = True
        self.setup_signal_handlers()
    
    def setup_signal_handlers(self):
        """Setup graceful shutdown on SIGTERM/SIGINT."""
        def shutdown_handler(signum, frame):
            self.running = False
            sys.stderr.write("[daemon] Received shutdown signal\n")
            sys.stderr.flush()
        
        signal.signal(signal.SIGTERM, shutdown_handler)
        signal.signal(signal.SIGINT, shutdown_handler)
    
    async def handle_request(self, line: str) -> str:
        """
        Handle a single JSON-RPC request.
        
        Args:
            line: Raw request line
            
        Returns:
            JSON-RPC response string
        """
        request_id = None
        
        try:
            # Parse request
            try:
                request = parse_request(line)
                request_id = request["id"]
                method = request["method"]
                params = request["params"]
            except ValueError as e:
                error_msg = str(e)
                if "Parse error" in error_msg:
                    return create_error_response(None, PARSE_ERROR, error_msg)
                else:
                    return create_error_response(None, INVALID_REQUEST, error_msg)
            
            # Get handler
            handler = self.registry.get_handler(method)
            if handler is None:
                return create_error_response(
                    request_id,
                    METHOD_NOT_FOUND,
                    f"Method '{method}' not found"
                )
            
            # Call handler
            try:
                result = await handler(params)
                return create_response(request_id, result)
            except ValueError as e:
                return create_error_response(
                    request_id,
                    INVALID_PARAMS,
                    f"Invalid params: {e}"
                )
            except Exception as e:
                return create_error_response(
                    request_id,
                    INTERNAL_ERROR,
                    f"Internal error: {e}"
                )
        
        except Exception as e:
            # Catch-all for unexpected errors
            return create_error_response(
                request_id,
                INTERNAL_ERROR,
                f"Unexpected error: {e}"
            )
    
    async def run(self):
        """Main server loop - read from stdin, write to stdout."""
        sys.stderr.write("[daemon] QuantSys daemon started\n")
        sys.stderr.flush()
        
        while self.running:
            try:
                # Read line from stdin (blocking)
                line = await asyncio.get_event_loop().run_in_executor(
                    None,
                    sys.stdin.readline
                )
                
                if not line:
                    # EOF reached
                    break
                
                line = line.strip()
                if not line:
                    continue
                
                # Handle request
                response = await self.handle_request(line)
                
                # Write response to stdout
                sys.stdout.write(response + "\n")
                sys.stdout.flush()
            
            except KeyboardInterrupt:
                break
            except Exception as e:
                sys.stderr.write(f"[daemon] Error in main loop: {e}\n")
                sys.stderr.flush()
        
        sys.stderr.write("[daemon] Shutting down\n")
        sys.stderr.flush()


def main():
    """Main entry point."""
    server = DaemonServer()
    asyncio.run(server.run())


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Make daemon runnable as module**

Update `daemon/__init__.py`:

```python
"""QuantSys V2 Daemon - JSON-RPC 2.0 service for TypeScript agent tools."""

__version__ = "1.0.0"
```

Create `daemon/__main__.py`:

```python
"""Allow running daemon as: python -m daemon.server"""
from daemon.server import main

if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run integration tests**

Run: `cd quantsys-v2 && pytest tests/daemon/test_integration.py -v -s`
Expected: All 3 tests PASS

- [ ] **Step 6: Test daemon manually**

```bash
cd quantsys-v2
echo '{"jsonrpc": "2.0", "id": 1, "method": "ping", "params": {}}' | python -m daemon.server
```

Expected output: `{"jsonrpc": "2.0", "id": 1, "result": "{\"status\": \"ok\", \"message\": \"pong\"}"}`

- [ ] **Step 7: Commit**

```bash
git add daemon/server.py daemon/__init__.py daemon/__main__.py tests/daemon/test_integration.py
git commit -m "feat(daemon): implement daemon server with stdin/stdout communication"
```

---

## Task 5: Update TypeScript Adapter Configuration

**Files:**
- Modify: `src/infrastructure/quant/quantsys-daemon-adapter.ts:20`
- Modify: `src/infrastructure/quant/quantsys-daemon-adapter.ts:74`

- [ ] **Step 1: Read current adapter code**

Run: `cat src/infrastructure/quant/quantsys-daemon-adapter.ts | head -80`
Expected: See current QUANT_ROOT and spawn command

- [ ] **Step 2: Update QUANT_ROOT path**

In `src/infrastructure/quant/quantsys-daemon-adapter.ts`, change line 20:

```typescript
// OLD:
const QUANT_ROOT = join(PROJECT_ROOT, "quant");

// NEW:
const QUANT_ROOT = join(PROJECT_ROOT, "quantsys-v2");
```

- [ ] **Step 3: Update spawn command**

In `src/infrastructure/quant/quantsys-daemon-adapter.ts`, change line 74:

```typescript
// OLD:
this.process = spawn(pythonCmd, ["-m", "quantsys.cli", "--daemon"], {

// NEW:
this.process = spawn(pythonCmd, ["-m", "daemon.server"], {
```

- [ ] **Step 4: Verify TypeScript compiles**

Run: `npm run build`
Expected: No TypeScript errors

- [ ] **Step 5: Test daemon startup from TypeScript**

Create test file `src/infrastructure/quant/test-daemon-startup.ts`:

```typescript
import { callQuantSysDaemon } from './quantsys-daemon-adapter.js';

async function test() {
  try {
    const result = await callQuantSysDaemon('ping', {});
    console.log('Daemon response:', result);
    const parsed = JSON.parse(result);
    if (parsed.status === 'ok') {
      console.log('✅ Daemon startup successful');
      process.exit(0);
    } else {
      console.error('❌ Unexpected response');
      process.exit(1);
    }
  } catch (error) {
    console.error('❌ Daemon startup failed:', error);
    process.exit(1);
  }
}

test();
```

Run: `tsx src/infrastructure/quant/test-daemon-startup.ts`
Expected: "✅ Daemon startup successful"

- [ ] **Step 6: Clean up test file**

```bash
rm src/infrastructure/quant/test-daemon-startup.ts
```

- [ ] **Step 7: Commit**

```bash
git add src/infrastructure/quant/quantsys-daemon-adapter.ts
git commit -m "fix(adapter): update daemon path to quantsys-v2"
```

---

## Phase 1 Complete

**Deliverables:**
✅ Daemon package structure created
✅ JSON-RPC 2.0 protocol handler implemented and tested
✅ Method registry with decorator implemented and tested
✅ Daemon server with stdin/stdout communication implemented and tested
✅ TypeScript adapter updated to use quantsys-v2 daemon
✅ Integration tests passing

**Next Steps:**
- Phase 2: Implement L1 Data Layer handlers (6 methods)
- Phase 3: Implement L2 Factor Layer handlers (5 methods)
- Phase 4: Implement L3 Model Layer handlers (5 methods)
- Phase 5: Documentation and cleanup
