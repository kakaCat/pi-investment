"""Tests for strategy optimization CLI helper functions."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from quantsys.cli.strategy_optimizer import optimize_strategy


def test_optimize_strategy_rsi_uses_default_grid(tmp_path: Path) -> None:
    result = optimize_strategy(tmp_path, {"strategy": "rsi", "metric": "sharpe"})

    assert result["strategy"] == "rsi"
    assert result["metric"] == "sharpe"
    assert result["trials"] == 9
    assert result["best_params"] == {"entry_rsi": 30, "exit_rsi": 70}
    assert result["best_score"] == pytest.approx(result["results"][0]["score"])
    assert len(result["results"]) == 9
    assert result["results"] == sorted(
        result["results"],
        key=lambda item: (-item["score"], item["params"]),
    )


def test_optimize_strategy_accepts_custom_grid_json(tmp_path: Path) -> None:
    grid = {"entry_rsi": [20, 30], "exit_rsi": [65]}

    result = optimize_strategy(
        tmp_path,
        {
            "strategy": "rsi",
            "metric": "return",
            "param_grid_json": json.dumps(grid),
        },
    )

    assert result["metric"] == "return"
    assert result["trials"] == 2
    assert result["best_params"] == {"entry_rsi": 30, "exit_rsi": 65}
    assert [item["params"] for item in result["results"]] == [
        {"entry_rsi": 30, "exit_rsi": 65},
        {"entry_rsi": 20, "exit_rsi": 65},
    ]


def test_optimize_strategy_rejects_unknown_strategy(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="unsupported strategy"):
        optimize_strategy(tmp_path, {"strategy": "macd"})


def test_optimize_strategy_ma_cross_keeps_fast_less_than_slow(tmp_path: Path) -> None:
    grid = {"fast": [10, 20, 50], "slow": [20, 50]}

    result = optimize_strategy(
        tmp_path,
        {
            "strategy": "ma_cross",
            "metric": "win_rate",
            "param_grid_json": json.dumps(grid),
        },
    )

    assert result["strategy"] == "ma_cross"
    assert result["trials"] == 3
    assert result["results"]
    assert all(item["params"]["fast"] < item["params"]["slow"] for item in result["results"])
    assert {tuple(item["params"].values()) for item in result["results"]} == {
        (10, 20),
        (10, 50),
        (20, 50),
    }
