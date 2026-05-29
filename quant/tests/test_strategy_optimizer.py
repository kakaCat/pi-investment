"""Tests for strategy parameter optimization."""

from pathlib import Path
import pytest
from quantsys.cli.strategy_optimizer import optimize_strategy


def test_optimize_strategy_bollinger():
    """Test bollinger strategy optimization completes without error."""
    result = optimize_strategy(
        Path("/tmp"),
        {"strategy": "bollinger", "metric": "sharpe", "trials": 10}
    )

    assert result["strategy"] == "bollinger"
    assert result["metric"] == "sharpe"
    assert result["trials"] == 4  # bollinger has 4 combinations (2 periods × 2 stddevs)
    assert "best_params" in result
    assert "best_score" in result
    assert isinstance(result["best_score"], float)
    assert len(result["results"]) == 4


def test_optimize_strategy_rsi():
    """Test RSI strategy optimization completes without error."""
    result = optimize_strategy(
        Path("/tmp"),
        {"strategy": "rsi", "metric": "sharpe", "trials": 20}
    )

    assert result["strategy"] == "rsi"
    assert result["metric"] == "sharpe"
    assert result["trials"] == 9  # rsi has 9 combinations (3 entry × 3 exit)
    assert "best_params" in result
    assert "best_score" in result
    assert isinstance(result["best_score"], float)


def test_optimize_strategy_handles_duplicate_scores():
    """Test that sorting works even when multiple params have identical scores.

    This is a regression test for the bug where sorting by (-score, params_dict)
    would fail with TypeError when scores were equal, because dicts can't be compared.
    """
    result = optimize_strategy(
        Path("/tmp"),
        {"strategy": "ma_cross", "metric": "win_rate", "trials": 50}
    )

    # Verify it completes without TypeError
    assert result["strategy"] == "ma_cross"
    assert "results" in result

    # Verify results are sorted by score descending
    scores = [item["score"] for item in result["results"]]
    assert scores == sorted(scores, reverse=True)


def test_optimize_strategy_invalid_strategy():
    """Test that invalid strategy raises ValueError."""
    with pytest.raises(ValueError, match="unsupported strategy"):
        optimize_strategy(Path("/tmp"), {"strategy": "invalid"})


def test_optimize_strategy_invalid_metric():
    """Test that invalid metric raises ValueError."""
    with pytest.raises(ValueError, match="unsupported metric"):
        optimize_strategy(Path("/tmp"), {"strategy": "rsi", "metric": "invalid"})
