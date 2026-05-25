"""Strategy parameter optimization helpers for CLI command handlers."""

from __future__ import annotations

import itertools
import json
from pathlib import Path
from typing import Any


SUPPORTED_STRATEGIES = {"rsi", "ma_cross", "bollinger"}
SUPPORTED_METRICS = {"sharpe", "return", "win_rate"}
DEFAULT_GRIDS: dict[str, dict[str, list[int | float]]] = {
    "rsi": {"entry_rsi": [25, 30, 35], "exit_rsi": [60, 70, 80]},
    "ma_cross": {"fast": [5, 10, 20], "slow": [20, 50, 60]},
    "bollinger": {"period": [20, 30], "stddev": [2, 2.5]},
}
TOP_RESULT_LIMIT = 10


def optimize_strategy(quant_root: Path, params: dict[str, Any]) -> dict[str, Any]:
    """Search a strategy parameter grid with a deterministic fallback scorer."""
    del quant_root

    strategy = str(params.get("strategy") or "rsi")
    if strategy not in SUPPORTED_STRATEGIES:
        raise ValueError(f"unsupported strategy: {strategy}")

    metric = str(params.get("metric") or "sharpe")
    if metric not in SUPPORTED_METRICS:
        raise ValueError(f"unsupported metric: {metric}")

    requested_trials = _as_positive_int(params.get("trials"))
    grid = _param_grid(strategy, params.get("param_grid_json"))
    candidates = _candidate_params(strategy, grid)
    if requested_trials is not None:
        candidates = candidates[:requested_trials]

    scored = [
        {
            "params": candidate,
            "score": _round_score(_score_params(strategy, metric, candidate)),
        }
        for candidate in candidates
    ]
    scored.sort(key=lambda item: (-item["score"], item["params"]))

    best = scored[0] if scored else {"params": {}, "score": None}
    return {
        "strategy": strategy,
        "metric": metric,
        "trials": len(scored),
        "best_params": best["params"],
        "best_score": best["score"],
        "results": scored[:TOP_RESULT_LIMIT],
    }


def _param_grid(strategy: str, param_grid_json: Any) -> dict[str, list[int | float]]:
    if param_grid_json in (None, ""):
        return {key: values[:] for key, values in DEFAULT_GRIDS[strategy].items()}

    try:
        payload = json.loads(str(param_grid_json))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid param_grid_json: {exc.msg}") from exc

    if not isinstance(payload, dict):
        raise ValueError("param_grid_json must decode to an object")

    grid: dict[str, list[int | float]] = {}
    for key, values in payload.items():
        if not isinstance(values, list) or not values:
            raise ValueError(f"grid field {key} must be a non-empty list")
        grid[str(key)] = [_number(value, f"grid field {key}") for value in values]
    return grid


def _candidate_params(strategy: str, grid: dict[str, list[int | float]]) -> list[dict[str, int | float]]:
    keys = list(DEFAULT_GRIDS[strategy])
    missing = [key for key in keys if key not in grid]
    if missing:
        raise ValueError(f"missing grid fields for {strategy}: {', '.join(missing)}")

    candidates = [
        dict(zip(keys, values, strict=True))
        for values in itertools.product(*(grid[key] for key in keys))
    ]
    if strategy == "ma_cross":
        candidates = [
            candidate
            for candidate in candidates
            if candidate["fast"] < candidate["slow"]
        ]
    return candidates


def _score_params(strategy: str, metric: str, params: dict[str, int | float]) -> float:
    if strategy == "rsi":
        entry = float(params["entry_rsi"])
        exit_ = float(params["exit_rsi"])
        base = 100.0 - abs(entry - 30.0) * 1.8 - abs(exit_ - 70.0) * 1.2
        spread_bonus = min(max(exit_ - entry, 0.0), 50.0) * 0.08
    elif strategy == "ma_cross":
        fast = float(params["fast"])
        slow = float(params["slow"])
        ratio = fast / slow
        base = 100.0 - abs(ratio - 0.25) * 90.0 - abs(slow - 50.0) * 0.12
        spread_bonus = min(slow - fast, 60.0) * 0.03
    else:
        period = float(params["period"])
        stddev = float(params["stddev"])
        base = 100.0 - abs(period - 20.0) * 0.45 - abs(stddev - 2.0) * 9.0
        spread_bonus = (period / 20.0) + stddev

    return (base + spread_bonus) * _metric_multiplier(metric)


def _metric_multiplier(metric: str) -> float:
    return {
        "sharpe": 1.0,
        "return": 0.92,
        "win_rate": 0.01,
    }[metric]


def _as_positive_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    parsed = int(value)
    if parsed <= 0:
        raise ValueError("trials must be a positive integer")
    return parsed


def _number(value: Any, label: str) -> int | float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"{label} values must be numbers")
    return value


def _round_score(value: float) -> float:
    return round(value, 6)
