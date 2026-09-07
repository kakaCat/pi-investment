"""Abstract base for indicator adapters."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class IndicatorAdapter(ABC):
    """Base class for indicator library adapters."""

    @abstractmethod
    def calculate(self, klines: list[dict], indicator: str, **params) -> Any:
        """Calculate a single indicator. Returns the indicator values list."""

    @abstractmethod
    def is_available(self) -> bool:
        """Check whether the underlying library is installed and usable."""

    @abstractmethod
    def list_indicators(self) -> list[str]:
        """List all indicators supported by this adapter."""
