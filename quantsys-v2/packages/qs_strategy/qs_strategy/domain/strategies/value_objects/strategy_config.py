from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class StrategyConfig:
    """Immutable value object holding all parameters for a strategy template.

    StrategyConfig centralizes every tunable aspect of a strategy -- rebalance
    cadence, position limits, risk controls, model paths, and extra parameters --
    so that strategy templates can be constructed, versioned, and validated
    independently of execution code.
    """

    name: str
    version: str
    description: str = ""
    rebalance_days: int = 1
    max_positions: int = 10
    max_position_pct: float = 0.2
    stop_loss_pct: float = 0.05
    trailing_stop_pct: float = 0.05
    portfolio_stop_loss_pct: float = 0.1
    model_path: str = ""
    factors_path: str = ""
    params: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("name must be a non-empty string")
        if not isinstance(self.version, str) or not self.version.strip():
            raise ValueError("version must be a non-empty string")
        if not isinstance(self.rebalance_days, int) or self.rebalance_days <= 0:
            raise ValueError("rebalance_days must be a positive integer")
        if not isinstance(self.max_positions, int) or self.max_positions <= 0:
            raise ValueError("max_positions must be a positive integer")
        if (
            not isinstance(self.max_position_pct, (int, float))
            or self.max_position_pct <= 0
            or self.max_position_pct > 1
        ):
            raise ValueError("max_position_pct must be in (0, 1]")
        if not isinstance(self.params, dict):
            raise TypeError("params must be a dict")

    def get(self, key: str, default: Any = None) -> Any:
        """Provide dict-like access to fields for backward compatibility."""
        return getattr(self, key, default)
