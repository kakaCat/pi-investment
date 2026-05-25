"""Tests for strategy analytics CLI helper functions."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from quantsys.cli.strategy_analytics import analyze_performance, arbitrate_signals


def write_signal_file(signals_dir: Path, filename: str, signals: list[dict]) -> None:
    signals_dir.mkdir(parents=True, exist_ok=True)
    payload = {"date": filename.removesuffix(".json"), "signals": signals}
    (signals_dir / filename).write_text(json.dumps(payload), encoding="utf-8")


def test_analyze_performance_calculates_metrics_from_signal_returns(tmp_path: Path) -> None:
    signals_dir = tmp_path / "signals"
    write_signal_file(
        signals_dir,
        "2026-05-18.json",
        [
            {
                "symbol": "000001",
                "strategy_id": "ma_cross",
                "signal": "BUY",
                "date": "2026-05-18",
                "profit_pct": 5.0,
            },
            {
                "symbol": "000002",
                "strategy": "ma_cross",
                "signal": "SELL",
                "date": "2026-05-18",
                "return_pct": -2.0,
            },
            {
                "symbol": "000003",
                "strategy_id": "rsi",
                "signal": "BUY",
                "date": "2026-05-18",
                "profit_pct": 8.0,
            },
        ],
    )
    write_signal_file(
        signals_dir,
        "2026-05-19.json",
        [
            {
                "symbol": "000004",
                "strategy_id": "ma_cross",
                "signal_type": "BUY",
                "date": "2026-05-19",
                "profit_pct": 1.0,
            }
        ],
    )

    result = analyze_performance(
        tmp_path,
        {"strategy_id": "ma_cross", "days": 30, "signals_dir": str(signals_dir)},
    )

    assert result["strategy_id"] == "ma_cross"
    assert result["period_days"] == 30
    assert result["total_signals"] == 3
    assert result["buy_signals"] == 2
    assert result["sell_signals"] == 1
    assert result["win_rate"] == pytest.approx(2 / 3)
    assert result["avg_profit_pct"] == pytest.approx(4 / 3)
    assert result["max_drawdown_pct"] == pytest.approx(2.0)
    assert result["sharpe_ratio"] is not None
    assert result["first_signal_date"] == "2026-05-18"
    assert result["last_signal_date"] == "2026-05-19"


def test_analyze_performance_returns_predictable_empty_metrics(tmp_path: Path) -> None:
    result = analyze_performance(
        tmp_path,
        {"strategy_id": "missing", "days": 7, "signals_dir": str(tmp_path / "missing")},
    )

    assert result == {
        "strategy_id": "missing",
        "period_days": 7,
        "total_signals": 0,
        "buy_signals": 0,
        "sell_signals": 0,
        "win_rate": None,
        "avg_profit_pct": None,
        "max_drawdown_pct": 0.0,
        "sharpe_ratio": None,
        "first_signal_date": None,
        "last_signal_date": None,
    }


def test_arbitrate_signals_holds_when_conflicting_scores_are_close(tmp_path: Path) -> None:
    result = arbitrate_signals(
        tmp_path,
        {
            "signals": [
                {"symbol": "000001", "signal": "BUY", "confidence": 0.62, "reason": "trend"},
                {"symbol": "000001", "signal": "SELL", "confidence": 0.58, "reason": "overbought"},
                {"symbol": "000002", "signal": "BUY", "confidence": 0.7, "reason": "breakout"},
            ]
        },
    )

    decisions = {item["symbol"]: item for item in result["decisions"]}

    assert result["total_symbols"] == 2
    assert decisions["000001"]["decision"] == "HOLD"
    assert decisions["000001"]["confidence"] == pytest.approx(0.04)
    assert decisions["000001"]["buy_score"] == pytest.approx(0.62)
    assert decisions["000001"]["sell_score"] == pytest.approx(0.58)
    assert decisions["000001"]["conflicts"] is True
    assert "Conflict" in decisions["000001"]["reason"]
    assert decisions["000002"]["decision"] == "BUY"
    assert decisions["000002"]["confidence"] == pytest.approx(0.7)
    assert decisions["000002"]["conflicts"] is False


def test_arbitrate_signals_reads_dated_file_from_signals_dir(tmp_path: Path) -> None:
    signals_dir = tmp_path / "signals"
    write_signal_file(
        signals_dir,
        "2026-05-20.json",
        [
            {"symbol": "000001", "signal": "BUY", "confidence": 0.8, "reason": "ma"},
            {"symbol": "000001", "signal": "SELL", "confidence": 0.2, "reason": "rsi"},
            {"symbol": "000002", "signal_type": "SELL", "confidence": 0.9, "reason": "weak"},
        ],
    )

    result = arbitrate_signals(
        tmp_path,
        {"date": "2026-05-20", "signals_dir": str(signals_dir)},
    )

    decisions = {item["symbol"]: item for item in result["decisions"]}

    assert result["date"] == "2026-05-20"
    assert decisions["000001"]["decision"] == "BUY"
    assert decisions["000001"]["confidence"] == pytest.approx(0.6)
    assert decisions["000001"]["conflicts"] is True
    assert decisions["000002"]["decision"] == "SELL"
    assert decisions["000002"]["sell_score"] == pytest.approx(0.9)
