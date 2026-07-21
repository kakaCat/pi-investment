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
    try:
        proc.wait(timeout=2)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()


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
