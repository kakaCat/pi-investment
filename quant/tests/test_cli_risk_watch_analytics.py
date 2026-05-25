"""Tests for risk watch analytics CLI helper functions."""

from __future__ import annotations

from pathlib import Path

import pytest

from quantsys.cli.risk_watch_analytics import price_alert, stress_test


def test_price_alert_triggers_above_threshold(tmp_path: Path) -> None:
    result = price_alert(tmp_path, {"symbol": "AAA", "price": 105, "above": 100})

    assert result["symbol"] == "AAA"
    assert result["price"] == pytest.approx(105)
    assert result["triggered"] is True
    assert result["alerts"] == [
        {
            "type": "above",
            "threshold": pytest.approx(100),
            "price": pytest.approx(105),
        }
    ]


def test_price_alert_triggers_below_threshold(tmp_path: Path) -> None:
    result = price_alert(tmp_path, {"symbol": "BBB", "price": 88, "below": 90})

    assert result["symbol"] == "BBB"
    assert result["price"] == pytest.approx(88)
    assert result["triggered"] is True
    assert result["alerts"] == [
        {
            "type": "below",
            "threshold": pytest.approx(90),
            "price": pytest.approx(88),
        }
    ]


def test_price_alert_triggers_positive_change_pct(tmp_path: Path) -> None:
    result = price_alert(
        tmp_path,
        {"symbol": "CCC", "price": 112, "last_price": 100, "change_pct": 0.10},
    )

    assert result["triggered"] is True
    assert result["alerts"] == [
        {
            "type": "change_pct",
            "threshold": pytest.approx(0.10),
            "change_pct": pytest.approx(0.12),
            "last_price": pytest.approx(100),
            "price": pytest.approx(112),
        }
    ]


def test_price_alert_triggers_negative_change_pct(tmp_path: Path) -> None:
    result = price_alert(
        tmp_path,
        {"symbol": "DDD", "price": 84, "last_price": 100, "change_pct": -0.15},
    )

    assert result["triggered"] is True
    assert result["alerts"] == [
        {
            "type": "change_pct",
            "threshold": pytest.approx(-0.15),
            "change_pct": pytest.approx(-0.16),
            "last_price": pytest.approx(100),
            "price": pytest.approx(84),
        }
    ]


def test_price_alert_returns_not_triggered_without_crossing_thresholds(tmp_path: Path) -> None:
    result = price_alert(
        tmp_path,
        {
            "symbol": "EEE",
            "price": 99,
            "above": 100,
            "below": 90,
            "last_price": 100,
            "change_pct": 0.05,
        },
    )

    assert result["symbol"] == "EEE"
    assert result["price"] == pytest.approx(99)
    assert result["triggered"] is False
    assert result["alerts"] == []


def test_stress_test_uses_market_value_positions(tmp_path: Path) -> None:
    result = stress_test(
        tmp_path,
        {
            "positions": [
                {"symbol": "AAA", "market_value": 1000},
                {"symbol": "BBB", "market_value": 500},
            ],
            "shock_pct": -0.20,
            "cash": 200,
        },
    )

    assert result["before_value"] == pytest.approx(1700)
    assert result["after_value"] == pytest.approx(1400)
    assert result["loss_amount"] == pytest.approx(300)
    assert result["loss_pct"] == pytest.approx(300 / 1700)
    assert result["positions"] == [
        {
            "symbol": "AAA",
            "before_value": pytest.approx(1000),
            "after_value": pytest.approx(800),
            "loss_amount": pytest.approx(200),
        },
        {
            "symbol": "BBB",
            "before_value": pytest.approx(500),
            "after_value": pytest.approx(400),
            "loss_amount": pytest.approx(100),
        },
    ]


def test_stress_test_uses_quantity_and_price_positions_json(tmp_path: Path) -> None:
    result = stress_test(
        tmp_path,
        {
            "positions_json": (
                '[{"symbol": "CCC", "quantity": 10, "price": 20}, '
                '{"symbol": "DDD", "quantity": 5, "price": 40}]'
            ),
            "shock_pct": 0.10,
        },
    )

    assert result["before_value"] == pytest.approx(400)
    assert result["after_value"] == pytest.approx(440)
    assert result["loss_amount"] == pytest.approx(-40)
    assert result["loss_pct"] == pytest.approx(-0.10)
    assert result["positions"] == [
        {
            "symbol": "CCC",
            "before_value": pytest.approx(200),
            "after_value": pytest.approx(220),
            "loss_amount": pytest.approx(-20),
        },
        {
            "symbol": "DDD",
            "before_value": pytest.approx(200),
            "after_value": pytest.approx(220),
            "loss_amount": pytest.approx(-20),
        },
    ]
