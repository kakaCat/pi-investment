"""Tests for trade verification and portfolio correlation CLI helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from quantsys.cli.trade_portfolio_analytics import correlate_portfolio, verify_trades


def test_verify_trades_matches_backtest_and_calculates_slippage(tmp_path: Path) -> None:
    result = verify_trades(
        tmp_path,
        {
            "trades": [
                {"symbol": "AAA", "action": "BUY", "price": 101},
                {"symbol": "BBB", "action": "SELL", "price": 49},
            ],
            "backtest": [
                {"symbol": "AAA", "action": "BUY", "price": 100},
                {"symbol": "CCC", "action": "BUY", "price": 20},
            ],
        },
    )

    assert result["matched_count"] == 1
    assert result["missing_in_backtest"] == [{"symbol": "BBB", "action": "SELL", "price": 49}]
    assert result["extra_backtest"] == [{"symbol": "CCC", "action": "BUY", "price": 20}]
    assert result["avg_slippage_pct"] == pytest.approx(0.01)
    assert result["matched"][0]["slippage_pct"] == pytest.approx(0.01)


def test_verify_trades_accepts_json_inputs(tmp_path: Path) -> None:
    result = verify_trades(
        tmp_path,
        {
            "trades_json": '[{"symbol":"AAA","action":"BUY","price":100}]',
            "backtest_json": '[{"symbol":"AAA","action":"BUY","price":100}]',
        },
    )

    assert result["matched_count"] == 1
    assert result["avg_slippage_pct"] == pytest.approx(0.0)


def test_correlate_portfolio_returns_matrix_and_high_pairs(tmp_path: Path) -> None:
    result = correlate_portfolio(
        tmp_path,
        {
            "prices": {
                "AAA": [1, 2, 3, 4],
                "BBB": [2, 4, 6, 8],
                "CCC": [4, 3, 2, 1],
            },
            "threshold": 0.7,
        },
    )

    assert result["correlation_matrix"]["AAA"]["BBB"] == pytest.approx(1.0)
    assert result["correlation_matrix"]["AAA"]["CCC"] == pytest.approx(-1.0)
    assert {"symbols": ["AAA", "BBB"], "correlation": pytest.approx(1.0)} in result["high_correlation_pairs"]
    assert {"symbols": ["AAA", "CCC"], "correlation": pytest.approx(-1.0)} in result["high_correlation_pairs"]


def test_correlate_portfolio_handles_insufficient_data(tmp_path: Path) -> None:
    result = correlate_portfolio(
        tmp_path,
        {"prices_json": '{"AAA":[1],"BBB":[2,3]}'},
    )

    assert result["correlation_matrix"]["AAA"]["BBB"] is None
    assert result["high_correlation_pairs"] == []
