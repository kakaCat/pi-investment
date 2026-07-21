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
        self._validate_required(symbol, "symbol")
        if not symbol.isdigit() or len(symbol) != 6:
            raise ValueError(f"Invalid symbol: {symbol}")

    def _log_operation(self, operation: str, **kwargs):
        self.logger.info(f"{operation}: {kwargs}")

    def _handle_error(self, exc: Exception, operation: str):
        self.logger.error(f"{operation} failed: {exc}")
        raise RuntimeError(f"{operation} failed") from exc
