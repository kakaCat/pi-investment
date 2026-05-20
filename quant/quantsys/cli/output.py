"""Output helpers for stable human and machine CLI responses."""

from __future__ import annotations

import json
from typing import Any

from .errors import CliError


def success_payload(
    command: str,
    data: Any = None,
    params: dict[str, Any] | None = None,
    artifacts: list[str] | None = None,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    """Build a successful command response."""
    return {
        "ok": True,
        "command": command,
        "params": params or {},
        "data": data,
        "artifacts": artifacts or [],
        "warnings": warnings or [],
        "error": None,
    }


def error_payload(command: str, error: CliError) -> dict[str, Any]:
    """Build a failed command response."""
    payload: dict[str, Any] = {
        "ok": False,
        "command": command,
        "params": {},
        "data": None,
        "artifacts": [],
        "warnings": [],
        "error": {
            "code": error.code,
            "message": error.message,
        },
    }
    if error.hint:
        payload["error"]["hint"] = error.hint
    return payload


def print_json(payload: dict[str, Any]) -> None:
    """Print compact UTF-8 JSON for agents."""
    print(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))

