"""Service基类 - 统一错误处理和日志"""
from abc import ABC
from typing import Any
import structlog

class ServiceBase(ABC):
    def __init__(self, logger: structlog.BoundLogger = None):
        self.logger = logger or structlog.get_logger(self.__class__.__name__)

    def _validate_required(self, value: Any, name: str):
        if value is None or (isinstance(value, str) and value == ""):
            raise ValueError(f"{name} is required")

    def _validate_symbol(self, symbol: str):
        """Validate stock symbol format.

        Supports:
        - A-shares: 6-digit code (e.g., 600519) or with suffix (600519.SH)
        - HK stocks: 1-5 digit code (e.g., 00700) or with suffix (0700.HK)
        """
        self._validate_required(symbol, "symbol")
        # Remove suffix for validation
        clean = symbol.split('.')[0]
        if not clean.isdigit() or len(clean) < 4 or len(clean) > 6:
            raise ValueError(f"Invalid symbol: {symbol}")

    def _validate_date(self, date_str: str, name: str = "date"):
        """Validate date string format (YYYY-MM-DD)."""
        self._validate_required(date_str, name)
        from datetime import datetime
        try:
            datetime.strptime(date_str, '%Y-%m-%d')
        except ValueError:
            raise ValueError(f"Invalid {name} format: {date_str}, expected YYYY-MM-DD")

    def _log_operation(self, operation: str, **kwargs):
        self.logger.info(f"{operation}: {kwargs}")

    def _handle_error(self, exc: Exception, operation: str):
        self.logger.error(f"{operation} failed: {exc}")
        raise RuntimeError(f"{operation} failed") from exc
