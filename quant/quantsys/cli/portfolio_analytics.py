"""Portfolio analytics helpers for CLI command handlers."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any


SUPPORTED_METHODS = {"equal_weight", "risk_parity", "max_sharpe"}


def compare_benchmark(quant_root: Path, params: dict[str, Any]) -> dict[str, Any]:
    """Compare strategy performance against a benchmark."""
    del quant_root

    strategy_name = str(params.get("strategy_name") or "strategy")
    benchmark_name = str(params.get("benchmark_name") or "benchmark")
    strategy_return = _resolve_return(params, "strategy_return", ("equity", "strategy_equity"))
    benchmark_return = _resolve_return(params, "benchmark_return", ("benchmark", "benchmark_equity"))

    alpha = strategy_return - benchmark_return
    relative_performance = _relative_performance(alpha, benchmark_return)
    winner = _winner(alpha)

    return {
        "strategy_name": strategy_name,
        "benchmark_name": benchmark_name,
        "strategy_return": _round_metric(strategy_return),
        "benchmark_return": _round_metric(benchmark_return),
        "alpha": _round_metric(alpha),
        "relative_performance": _round_metric(relative_performance),
        "winner": winner,
        "summary": _benchmark_summary(strategy_name, benchmark_name, alpha, winner),
    }


def optimize_portfolio(quant_root: Path, params: dict[str, Any]) -> dict[str, Any]:
    """Optimize portfolio weights using simple deterministic methods."""
    del quant_root

    symbols = _parse_symbols(params.get("symbols"))
    method = str(params.get("method") or "equal_weight").lower()
    if method not in SUPPORTED_METHODS:
        method = "equal_weight"

    expected_returns = _parse_metric_list(params.get("expected_returns"), len(symbols))
    volatilities = _parse_metric_list(params.get("volatilities"), len(symbols))

    if method == "risk_parity" and volatilities:
        raw_weights = [1.0 / value if value > 0 else 0.0 for value in volatilities]
    elif method == "max_sharpe" and expected_returns and volatilities:
        raw_weights = [
            max(return_value, 0.0) / volatility if volatility > 0 else 0.0
            for return_value, volatility in zip(expected_returns, volatilities)
        ]
    else:
        method = "equal_weight"
        raw_weights = [1.0 for _ in symbols]

    normalized = _normalize_weights(raw_weights, len(symbols))
    weights = {
        symbol: _round_metric(weight)
        for symbol, weight in zip(symbols, normalized)
    }

    return {
        "method": method,
        "symbols": symbols,
        "weights": weights,
        "expected_return": _portfolio_return(normalized, expected_returns),
        "expected_volatility": _portfolio_volatility(normalized, volatilities),
        "constraints": {
            "sum_to_one": True,
            "long_only": True,
        },
    }


def _resolve_return(params: dict[str, Any], return_key: str, array_keys: tuple[str, ...]) -> float:
    direct = _to_float(params.get(return_key))
    if direct is not None:
        return direct

    for key in array_keys:
        values = _parse_metric_list(params.get(key))
        if len(values) >= 2 and values[0] != 0:
            return values[-1] / values[0] - 1.0
    return 0.0


def _relative_performance(alpha: float, benchmark_return: float) -> float:
    if benchmark_return == 0:
        return 0.0 if alpha == 0 else alpha
    return alpha / abs(benchmark_return)


def _winner(alpha: float) -> str:
    if alpha > 0:
        return "strategy"
    if alpha < 0:
        return "benchmark"
    return "tie"


def _benchmark_summary(strategy_name: str, benchmark_name: str, alpha: float, winner: str) -> str:
    spread = abs(alpha) * 100.0
    if winner == "strategy":
        return f"{strategy_name} outperformed {benchmark_name} by {spread:.2f} percentage points."
    if winner == "benchmark":
        return f"{benchmark_name} outperformed {strategy_name} by {spread:.2f} percentage points."
    return f"{strategy_name} matched {benchmark_name}."


def _parse_symbols(value: Any) -> list[str]:
    if isinstance(value, str):
        symbols = [item.strip() for item in value.split(",")]
    elif isinstance(value, list):
        symbols = [str(item).strip() for item in value]
    else:
        symbols = []
    return [symbol for symbol in symbols if symbol]


def _parse_metric_list(value: Any, expected_len: int | None = None) -> list[float]:
    if value is None:
        return []
    if isinstance(value, str):
        raw_values = [item.strip() for item in value.split(",")]
    elif isinstance(value, list | tuple):
        raw_values = list(value)
    else:
        raw_values = [value]

    parsed = [_to_float(item) for item in raw_values]
    values = [item for item in parsed if item is not None]
    if expected_len is not None and len(values) != expected_len:
        return []
    return values


def _normalize_weights(values: list[float], count: int) -> list[float]:
    if count <= 0:
        return []
    total = sum(value for value in values if value > 0)
    if total <= 0:
        return [1.0 / count for _ in range(count)]
    return [max(value, 0.0) / total for value in values]


def _portfolio_return(weights: list[float], expected_returns: list[float]) -> float | None:
    if not weights or not expected_returns:
        return None
    return sum(weight * return_value for weight, return_value in zip(weights, expected_returns))


def _portfolio_volatility(weights: list[float], volatilities: list[float]) -> float | None:
    if not weights or not volatilities:
        return None
    variance = sum((weight * volatility) ** 2 for weight, volatility in zip(weights, volatilities))
    return math.sqrt(variance)


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _round_metric(value: float) -> float:
    return round(float(value), 6)
