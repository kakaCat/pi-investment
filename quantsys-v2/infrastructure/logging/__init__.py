"""
Logging Infrastructure

Provides structured logging with JSON format, trace ID tracking, and sensitive data filtering.
"""

from infrastructure.logging.config import (
    configure_structured_logging,
    get_trace_id,
    set_trace_id,
    log_execution,
)

__all__ = [
    "configure_structured_logging",
    "get_trace_id",
    "set_trace_id",
    "log_execution",
]
