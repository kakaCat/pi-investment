"""完整信号目录：组合、均线、RSI、放量、伏击、资金流、时间退出（quant_test）"""

from datetime import datetime, timezone

import pytest
from sqlalchemy import text

from qs_kernel.infrastructure.persistence.database.engine import get_engine
from tests.plan.test_plan_activation_progress import (
    SYMBOL_A,
    SYMBOL_B,
    _activation_service,
    _approve_revision,
    _generate,
    _target,
    PositionView,
    cleanup_account_plan_and_rules,
)


def _cleanup():
    generator = cleanup_account_plan_and_rules.__wrapped__()
    next(generator)
    try:
        next(generator)
    except StopIteration:
        pass


@pytest.fixture(autouse=True)
def cleanup_signal_catalog_data():
    _cleanup()
    yield
    _cleanup()


def test_full_signal_catalog_is_generated_with_setup_types():
    generated = _generate(
        [
            _target(
                SYMBOL_A,
                setup_type="breakout",
                entry_combinator="any_of",
                entry_conditions=(
                    {"type": "ma_break", "params": {"days": 20, "direction": "above"}},
                    {"type": "volume_surge", "params": {"multiple": 2.0}},
                ),
            ),
            _target(
                SYMBOL_B,
                action="observe",
                setup_type="pullback",
                entry_conditions=(
                    {
                        "type": "staged_break",
                        "params": {
                            "touch": {"price": 8.5, "direction": "below"},
                            "confirm": {"kind": "reclaim"},
                            "window_min": 60,
                        },
                    },
                ),
            ),
            _target(
                "000002.SZ",
                setup_type="mean_reversion",
                entry_conditions=(
                    {
                        "type": "rsi",
                        "params": {"threshold": 30, "direction": "below", "period": 14},
                    },
                ),
            ),
            _target(
                "000003.SZ",
                action="reduce_risk",
                setup_type="risk_off",
                reduce_plan=(
                    {"type": "volume_surge", "params": {"multiple": 2.0}, "sell_ratio": 0.25},
                ),
            ),
            _target(
                "000004.SZ",
                setup_type="event_driven",
                entry_combinator="any_of",
                entry_conditions=(
                    {"type": "pct_change", "params": {"pct": 3, "direction": "above"}},
                    {"type": "velocity", "params": {"pct": 2, "window_min": 5}},
                    {"type": "fund_flow", "params": {"amount_yi": 1.0, "direction": "above"}},
                ),
            ),
            _target(
                "000005.SZ",
                setup_type="custom",
                stop_loss={
                    "type": "time_stop",
                    "params": {"start": "2026-10-20T09:30:00+08:00", "max_days": 5},
                },
            ),
        ],
        positions=[PositionView("000003.SZ", 200)],
    )
    _approve_revision(generated["revision_id"])
    _activation_service(holding_symbols={"000003.SZ"}).activate(
        plan_id=generated["plan_id"], expected_version=generated["version"], actor="agent"
    )

    with get_engine().connect() as conn:
        rules = (
            conn.execute(
                text(
                    "SELECT r.symbol, r.intent, r.conditions, r.action_params, r.engine "
                    "FROM quant.watch_rules r WHERE r.plan_id=:plan "
                    "ORDER BY r.symbol, r.intent"
                ),
                {"plan": generated["plan_id"]},
            )
            .mappings()
            .all()
        )
        assert len(rules) == 12
        condition_types = {condition["type"] for row in rules for condition in row["conditions"]}
        assert {
            "combined",
            "staged_break",
            "rsi",
            "time_stop",
            "volume_surge",
            "pnl_pct",
        } <= condition_types

        combined = next(
            row for row in rules if row["symbol"] == SYMBOL_A and row["intent"] == "entry"
        )
        assert combined["conditions"][0]["type"] == "combined"
        assert combined["conditions"][0]["params"]["operator"] == "OR"
        assert {c["type"] for c in combined["conditions"][0]["params"]["conditions"]} == {
            "ma_break",
            "volume_surge",
        }

        event = next(
            row for row in rules if row["symbol"] == "000004.SZ" and row["intent"] == "entry"
        )
        nested_types = {c["type"] for c in event["conditions"][0]["params"]["conditions"]}
        assert nested_types == {"pct_change", "velocity", "fund_flow"}

        time_exit = next(
            row for row in rules if row["symbol"] == "000005.SZ" and row["intent"] == "exit_stop"
        )
        assert time_exit["conditions"][0]["type"] == "time_stop"
        assert time_exit["conditions"][0]["params"]["max_days"] == 5

        setup_types = {
            row["action_params"].get("setup_type")
            for row in rules
            if row["action_params"] and row["action_params"].get("setup_type")
        }
        assert {
            "breakout",
            "pullback",
            "mean_reversion",
            "risk_off",
            "event_driven",
            "custom",
        } <= setup_types
        assert all(row["engine"] == "v2" for row in rules)
