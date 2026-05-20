"""Tests for portfolio analytics CLI helper functions."""

from __future__ import annotations

from pathlib import Path

import pytest

from quantsys.cli.portfolio_analytics import compare_benchmark, optimize_portfolio


def test_compare_benchmark_calculates_alpha_and_winner_from_returns(tmp_path: Path) -> None:
    result = compare_benchmark(
        tmp_path,
        {
            "strategy_return": 0.125,
            "benchmark_return": 0.08,
            "strategy_name": "Momentum",
            "benchmark_name": "CSI300",
        },
    )

    assert result["strategy_name"] == "Momentum"
    assert result["benchmark_name"] == "CSI300"
    assert result["strategy_return"] == pytest.approx(0.125)
    assert result["benchmark_return"] == pytest.approx(0.08)
    assert result["alpha"] == pytest.approx(0.045)
    assert result["relative_performance"] == pytest.approx(0.5625)
    assert result["winner"] == "strategy"
    assert result["summary"] == "Momentum outperformed CSI300 by 4.50 percentage points."


def test_compare_benchmark_derives_returns_from_equity_arrays(tmp_path: Path) -> None:
    result = compare_benchmark(
        tmp_path,
        {
            "equity": [100, 104, 110],
            "benchmark": [100, 102, 105],
            "strategy_name": "Equity Curve",
            "benchmark_name": "Index Curve",
        },
    )

    assert result["strategy_return"] == pytest.approx(0.10)
    assert result["benchmark_return"] == pytest.approx(0.05)
    assert result["alpha"] == pytest.approx(0.05)
    assert result["relative_performance"] == pytest.approx(1.0)
    assert result["winner"] == "strategy"


def test_optimize_portfolio_falls_back_to_equal_weight_without_data(tmp_path: Path) -> None:
    result = optimize_portfolio(tmp_path, {"symbols": "AAA, BBB,CCC"})

    assert result["method"] == "equal_weight"
    assert result["symbols"] == ["AAA", "BBB", "CCC"]
    assert result["weights"] == {
        "AAA": pytest.approx(1 / 3),
        "BBB": pytest.approx(1 / 3),
        "CCC": pytest.approx(1 / 3),
    }
    assert result["expected_return"] is None
    assert result["expected_volatility"] is None
    assert result["constraints"]["sum_to_one"] is True
    assert result["constraints"]["long_only"] is True


def test_optimize_portfolio_risk_parity_weights_are_inverse_vol_and_normalized(tmp_path: Path) -> None:
    result = optimize_portfolio(
        tmp_path,
        {
            "symbols": ["LOW", "MID", "HIGH"],
            "method": "risk_parity",
            "volatilities": [0.10, 0.20, 0.40],
            "expected_returns": [0.06, 0.08, 0.12],
        },
    )

    assert result["method"] == "risk_parity"
    assert sum(result["weights"].values()) == pytest.approx(1.0)
    assert result["weights"]["LOW"] == pytest.approx(4 / 7)
    assert result["weights"]["MID"] == pytest.approx(2 / 7)
    assert result["weights"]["HIGH"] == pytest.approx(1 / 7)
    assert result["expected_return"] == pytest.approx((0.06 * 4 + 0.08 * 2 + 0.12) / 7)
    assert result["expected_volatility"] is not None


def test_optimize_portfolio_max_sharpe_weights_are_score_based_and_normalized(tmp_path: Path) -> None:
    result = optimize_portfolio(
        tmp_path,
        {
            "symbols": "A,B,C",
            "method": "max_sharpe",
            "expected_returns": [0.10, 0.05, -0.01],
            "volatilities": [0.20, 0.10, 0.30],
        },
    )

    assert result["method"] == "max_sharpe"
    assert sum(result["weights"].values()) == pytest.approx(1.0)
    assert result["weights"]["A"] == pytest.approx(0.5)
    assert result["weights"]["B"] == pytest.approx(0.5)
    assert result["weights"]["C"] == pytest.approx(0.0)
    assert result["expected_return"] == pytest.approx(0.075)
    assert result["expected_volatility"] is not None
