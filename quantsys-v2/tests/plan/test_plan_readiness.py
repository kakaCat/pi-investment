"""账户级 readiness 与运行时对账（REQ-261026140857-c192，quant_test）"""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest
from sqlalchemy import text

from adapters.outbound.repositories.trading_plan_unit_of_work import TradingPlanUnitOfWork
from qs_kernel.infrastructure.persistence.database.engine import get_engine
from qs_plan.application.plan_activation_service import PlanActivationService
from qs_plan.application.plan_generation_service import PlanGenerationService
from qs_plan.application.plan_readiness_service import PlanReadinessService
from qs_plan.application.ports import PortfolioDecision, PositionView, TargetAllocation

ACCOUNT = "test-account-plan-readiness"
SYMBOL = "600519.SH"
TRADE_DATE = date(2026, 10, 26)
DATA_AS_OF = datetime(2026, 10, 26, 8, 30, tzinfo=timezone.utc)
POSITIONS = []


class FakeDecisionProvider:
    def __init__(self, decision):
        self.decision = decision

    def build(self, *, account: str, trade_date: date):
        return self.decision


class FakePositionProvider:
    def list_positions(self, *, account: str):
        return tuple(POSITIONS)


def _target():
    return TargetAllocation(
        symbol=SYMBOL,
        target_weight=0.1,
        horizon="swing",
        thesis="测试假设",
        invalidation="假设失效",
        entry_conditions=({"type": "price_break", "params": {"price": 10, "direction": "above"}},),
        stop_loss={"type": "pct", "value": 8},
    )


def _generate():
    decision = PortfolioDecision(
        account=ACCOUNT,
        trade_date=TRADE_DATE,
        data_as_of=DATA_AS_OF,
        targets=(_target(),),
        market_gate={"allowed": True},
        risk_budget={},
        evidence={},
    )
    service = PlanGenerationService(
        decision_provider=FakeDecisionProvider(decision),
        position_provider=FakePositionProvider(),
        unit_of_work_factory=TradingPlanUnitOfWork,
    )
    return service.generate(
        account=ACCOUNT,
        trade_date=TRADE_DATE,
        actor="agent",
        idempotency_key="%s:%s:generate" % (ACCOUNT, TRADE_DATE),
    )


def _activate(generated, holding=False):
    with get_engine().begin() as conn:
        conn.execute(
            text(
                "UPDATE quant.trading_plan_versions SET status='approved', "
                "reviewed_by='agent', reviewed_at=now() WHERE id=:id"
            ),
            {"id": generated["revision_id"]},
        )
    return PlanActivationService(
        unit_of_work_factory=TradingPlanUnitOfWork,
        position_state_provider=lambda symbol: "holding" if holding else "none",
    ).activate(plan_id=generated["plan_id"], expected_version=generated["version"], actor="agent")


def _cleanup_account_data() -> None:
    engine = get_engine()
    with engine.begin() as conn:
        plan_ids = [
            row[0]
            for row in conn.execute(
                text("SELECT id FROM quant.trading_plans WHERE account=:account"),
                {"account": ACCOUNT},
            )
        ]
        if not plan_ids:
            return
        item_ids = [
            row[0]
            for row in conn.execute(
                text("SELECT id FROM quant.trading_plan_items WHERE plan_id = ANY(:ids)"),
                {"ids": plan_ids},
            )
        ]
        rule_ids = [
            row[0]
            for row in conn.execute(
                text(
                    "SELECT id FROM quant.watch_rules WHERE plan_id = ANY(:ids) "
                    "OR item_id = ANY(:item_ids)"
                ),
                {"ids": plan_ids, "item_ids": item_ids or [0]},
            )
        ]
        if rule_ids:
            conn.execute(
                text("DELETE FROM quant.watch_rule_changes WHERE rule_id = ANY(:ids)"),
                {"ids": rule_ids},
            )
            conn.execute(
                text("DELETE FROM quant.watch_rules WHERE id = ANY(:ids)"), {"ids": rule_ids}
            )
        conn.execute(
            text(
                "DELETE FROM quant.trading_plan_conditions WHERE item_version_id IN "
                "(SELECT id FROM quant.trading_plan_item_versions WHERE item_id = ANY(:ids))"
            ),
            {"ids": item_ids or [0]},
        )
        for table in (
            "trading_plan_fill_receipts",
            "trading_plan_item_states",
            "trading_plan_item_versions",
        ):
            conn.execute(
                text("DELETE FROM quant.%s WHERE item_id = ANY(:ids)" % table),
                {"ids": item_ids or [0]},
            )
        for table in (
            "trading_plan_items",
            "trading_plan_events",
            "plan_reflections",
            "trading_plan_runs",
            "trading_plan_versions",
        ):
            conn.execute(
                text("DELETE FROM quant.%s WHERE plan_id = ANY(:ids)" % table),
                {"ids": plan_ids},
            )
        conn.execute(
            text("DELETE FROM quant.trading_plans WHERE account=:account"),
            {"account": ACCOUNT},
        )


@pytest.fixture(autouse=True)
def cleanup_readiness_account_data():
    POSITIONS.clear()
    _cleanup_account_data()
    yield
    POSITIONS.clear()
    _cleanup_account_data()


def _readiness():
    return PlanReadinessService(
        unit_of_work_factory=TradingPlanUnitOfWork,
        position_provider=FakePositionProvider(),
        position_state_provider=lambda symbol: "holding" if POSITIONS else "none",
    )


def test_missing_account_plan_returns_revision_missing_and_persists_run():
    result = _readiness().evaluate(account=ACCOUNT, trade_date=TRADE_DATE, stage="runtime")

    assert result["ready"] is False
    assert result["status"] == "not_ready"
    assert [(reason["code"], reason["message"]) for reason in result["reasons"]] == [
        ("REVISION_MISSING", "账户主计划不存在")
    ]
    with get_engine().connect() as conn:
        run = (
            conn.execute(
                text("SELECT * FROM quant.trading_plan_runs WHERE id=:id"),
                {"id": result["run_id"]},
            )
            .mappings()
            .one()
        )
        assert run["run_kind"] == "readiness"
        assert run["status"] == "failed"
        assert run["reasons"][0]["code"] == "REVISION_MISSING"


def test_draft_revision_requires_review():
    _generate()
    result = _readiness().evaluate(account=ACCOUNT, trade_date=TRADE_DATE, stage="runtime")

    assert result["ready"] is False
    assert {reason["code"] for reason in result["reasons"]} == {"REVIEW_REQUIRED"}


def test_approved_revision_is_ready_for_activation():
    generated = _generate()
    with get_engine().begin() as conn:
        conn.execute(
            text(
                "UPDATE quant.trading_plan_versions SET status='approved', "
                "reviewed_by='agent', reviewed_at=now() WHERE id=:id"
            ),
            {"id": generated["revision_id"]},
        )

    result = _readiness().evaluate(account=ACCOUNT, trade_date=TRADE_DATE, stage="activation")

    assert result["ready"] is True
    assert result["reasons"] == []


def test_active_revision_is_ready_when_positions_match_rules():
    generated = _generate()
    _activate(generated, holding=True)
    POSITIONS.append(PositionView(SYMBOL, 100))
    with get_engine().begin() as conn:
        conn.execute(
            text(
                "UPDATE quant.trading_plan_item_states SET state='holding', filled_qty=100 "
                "WHERE item_id IN (SELECT id FROM quant.trading_plan_items WHERE plan_id=:plan)"
            ),
            {"plan": generated["plan_id"]},
        )

    result = _readiness().evaluate(account=ACCOUNT, trade_date=TRADE_DATE, stage="runtime")

    assert result["ready"] is True, result["reasons"]
    assert result["status"] == "ready"
    assert result["reasons"] == []
    with get_engine().connect() as conn:
        run = (
            conn.execute(
                text("SELECT * FROM quant.trading_plan_runs WHERE id=:id"),
                {"id": result["run_id"]},
            )
            .mappings()
            .one()
        )
        assert run["status"] == "succeeded"


def test_entry_fill_state_is_not_rule_drift():
    generated = _generate()
    _activate(generated, holding=False)
    with get_engine().begin() as conn:
        conn.execute(
            text("UPDATE quant.watch_rules SET position_state='holding' WHERE plan_id=:plan"),
            {"plan": generated["plan_id"]},
        )
        conn.execute(
            text(
                "UPDATE quant.trading_plan_item_states SET state='holding', filled_qty=100 "
                "WHERE item_id IN (SELECT id FROM quant.trading_plan_items WHERE plan_id=:plan)"
            ),
            {"plan": generated["plan_id"]},
        )
    POSITIONS.append(PositionView(SYMBOL, 100))

    result = _readiness().evaluate(account=ACCOUNT, trade_date=TRADE_DATE, stage="runtime")

    assert result["ready"] is True, result["reasons"]


def test_disabled_exit_rule_without_position_is_not_rule_drift():
    generated = _generate()
    _activate(generated, holding=False)
    with get_engine().begin() as conn:
        conn.execute(
            text(
                "UPDATE quant.watch_rules SET enabled=false, "
                "context='[生命周期联动] 已清仓，卖出规则族收摊' || chr(10) || context "
                "WHERE plan_id=:plan AND intent='exit_stop'"
            ),
            {"plan": generated["plan_id"]},
        )

    result = _readiness().evaluate(account=ACCOUNT, trade_date=TRADE_DATE, stage="runtime")

    assert result["ready"] is True, result["reasons"]


def test_runtime_detects_rule_drift_and_position_mismatch():
    generated = _generate()
    _activate(generated, holding=True)

    with get_engine().begin() as conn:
        conn.execute(
            text(
                "UPDATE quant.trading_plan_item_states s SET state='holding' "
                "FROM quant.trading_plan_items i WHERE s.item_id=i.id "
                "AND i.plan_id=:plan AND i.symbol=:symbol"
            ),
            {"plan": generated["plan_id"], "symbol": SYMBOL},
        )
        conn.execute(
            text(
                "UPDATE quant.watch_rules SET enabled=false WHERE plan_id=:plan "
                "AND item_id IS NOT NULL"
            ),
            {"plan": generated["plan_id"]},
        )

    result = _readiness().evaluate(account=ACCOUNT, trade_date=TRADE_DATE, stage="runtime")
    codes = {reason["code"] for reason in result["reasons"]}
    assert result["ready"] is False
    assert "RULE_DRIFT" in codes
    assert "POSITION_MISMATCH" in codes


def test_previous_trading_day_data_is_allowed_for_next_session():
    generated = _generate()
    _activate(generated, holding=True)
    with get_engine().begin() as conn:
        conn.execute(
            text("UPDATE quant.trading_plan_versions SET data_as_of=:data_as_of WHERE id=:id"),
            {
                "id": generated["revision_id"],
                "data_as_of": datetime(2026, 10, 23, 15, tzinfo=timezone.utc),
            },
        )

    result = _readiness().evaluate(account=ACCOUNT, trade_date=TRADE_DATE, stage="runtime")

    assert "DATA_STALE" not in {reason["code"] for reason in result["reasons"]}


def test_position_read_failure_is_not_ready_not_empty_positions():
    class FailingPositionProvider:
        def list_positions(self, *, account: str):
            raise RuntimeError("positions unavailable")

    generated = _generate()
    _activate(generated, holding=True)
    service = PlanReadinessService(
        unit_of_work_factory=TradingPlanUnitOfWork,
        position_provider=FailingPositionProvider(),
    )

    result = service.evaluate(account=ACCOUNT, trade_date=TRADE_DATE, stage="runtime")

    assert result["ready"] is False
    assert "POSITION_READ_FAILED" in {reason["code"] for reason in result["reasons"]}
