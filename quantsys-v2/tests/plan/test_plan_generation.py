"""账户级每日计划生成与事务边界（REQ-261026140857-c192，quant_test）"""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest
from sqlalchemy import text

from adapters.outbound.repositories.account_plan_repository import AccountPlanRepository
from adapters.outbound.repositories.trading_plan_unit_of_work import TradingPlanUnitOfWork
from infrastructure.persistence.orm.models.trading_plan import TradingPlanItemVersion
from qs_kernel.infrastructure.persistence.database.engine import get_engine
from qs_plan.application.plan_generation_service import (
    AccountPlanError,
    PlanGenerationService,
)
from qs_plan.application.ports import (
    PortfolioDecision,
    PositionView,
    TargetAllocation,
)

ACCOUNT = "test-account-plan-gen"
TRADE_DATE = date(2026, 10, 26)
DATA_AS_OF = datetime(2026, 10, 26, 8, 30, tzinfo=timezone.utc)


class FakeDecisionProvider:
    def __init__(self, decision):
        self.decision = decision
        self.calls = 0

    def build(self, *, account: str, trade_date: date):
        self.calls += 1
        return self.decision


class FakePositionProvider:
    def __init__(self, positions):
        self.positions = tuple(positions)

    def list_positions(self, *, account: str):
        return self.positions


def _decision(targets=(), account=ACCOUNT, trade_date=TRADE_DATE, data_as_of=DATA_AS_OF):
    return PortfolioDecision(
        account=account,
        trade_date=trade_date,
        data_as_of=data_as_of,
        targets=tuple(targets),
        market_gate={"allowed": True},
        risk_budget={"max_total_exposure": 0.7},
        evidence={"source": "test"},
    )


def _target(symbol, **overrides):
    base = {
        "symbol": symbol,
        "target_weight": 0.1,
        "horizon": "swing",
        "thesis": "测试假设",
        "invalidation": "假设失效",
    }
    base.update(overrides)
    return TargetAllocation(**base)


@pytest.fixture(autouse=True)
def cleanup_account_plan_data():
    yield
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(
            text(
                "DELETE FROM quant.trading_plan_conditions WHERE item_version_id IN "
                "(SELECT iv.id FROM quant.trading_plan_item_versions iv "
                "JOIN quant.trading_plan_items i ON i.id = iv.item_id "
                "JOIN quant.trading_plans p ON p.id = i.plan_id WHERE p.account = :account)"
            ),
            {"account": ACCOUNT},
        )
        conn.execute(
            text(
                "DELETE FROM quant.trading_plan_item_states WHERE item_id IN "
                "(SELECT i.id FROM quant.trading_plan_items i "
                "JOIN quant.trading_plans p ON p.id = i.plan_id WHERE p.account = :account)"
            ),
            {"account": ACCOUNT},
        )
        conn.execute(
            text(
                "DELETE FROM quant.trading_plan_item_versions WHERE item_id IN "
                "(SELECT i.id FROM quant.trading_plan_items i "
                "JOIN quant.trading_plans p ON p.id = i.plan_id WHERE p.account = :account)"
            ),
            {"account": ACCOUNT},
        )
        for table in (
            "trading_plan_fill_receipts",
            "trading_plan_items",
            "trading_plan_events",
            "plan_reflections",
            "trading_plan_runs",
            "trading_plan_versions",
        ):
            column = "item_id" if table == "trading_plan_fill_receipts" else "plan_id"
            if table == "trading_plan_runs":
                conn.execute(
                    text("DELETE FROM quant.trading_plan_runs WHERE account = :account"),
                    {"account": ACCOUNT},
                )
            else:
                conn.execute(
                    text(
                        "DELETE FROM quant.%s WHERE %s IN "
                        "(SELECT id FROM quant.trading_plans WHERE account = :account)"
                        % (table, column)
                    ),
                    {"account": ACCOUNT},
                )
        conn.execute(
            text("DELETE FROM quant.trading_plans WHERE account = :account"), {"account": ACCOUNT}
        )


def _service(decision, positions=()):
    return PlanGenerationService(
        decision_provider=FakeDecisionProvider(decision),
        position_provider=FakePositionProvider(positions),
        unit_of_work_factory=TradingPlanUnitOfWork,
    )


def test_generate_creates_account_plan_items_conditions_state_event_and_run():
    decision = _decision(
        targets=[
            _target(
                "600519.SH",
                entry_conditions=(
                    {"type": "price_break", "params": {"price": 1500, "direction": "above"}},
                ),
            ),
            _target("000001.SZ", target_weight=0.2, stop_loss={"type": "pct", "value": 8}),
        ]
    )
    service = _service(
        decision, positions=[PositionView("600519.SH", 0), PositionView("999999.SZ", 100)]
    )

    result = service.generate(
        account=ACCOUNT,
        trade_date=TRADE_DATE,
        actor="agent",
        idempotency_key="%s:%s:generate" % (ACCOUNT, TRADE_DATE),
    )

    assert result["existing"] is False
    assert result["version"] == 1
    assert result["items"] == 3

    engine = get_engine()
    with engine.connect() as conn:
        plan = (
            conn.execute(
                text("SELECT * FROM quant.trading_plans WHERE account=:account"),
                {"account": ACCOUNT},
            )
            .mappings()
            .one()
        )
        assert plan["plan_kind"] == "account"
        assert plan["spec"] is None
        assert plan["horizon"] is None
        assert plan["draft_revision_id"] == result["revision_id"]

        revision = (
            conn.execute(
                text("SELECT * FROM quant.trading_plan_versions WHERE id=:id"),
                {"id": result["revision_id"]},
            )
            .mappings()
            .one()
        )
        assert revision["status"] == "draft"
        assert revision["generation_key"] == "%s:%s:generate" % (ACCOUNT, TRADE_DATE)
        assert revision["risk_budget"]["max_total_exposure"] == 0.7

        rows = (
            conn.execute(
                text(
                    "SELECT i.symbol, iv.action, s.state, iv.target_weight "
                    "FROM quant.trading_plan_items i "
                    "JOIN quant.trading_plan_item_versions iv ON iv.item_id = i.id "
                    "JOIN quant.trading_plan_item_states s ON s.item_id = i.id "
                    "WHERE i.plan_id=:plan ORDER BY i.symbol"
                ),
                {"plan": plan["id"]},
            )
            .mappings()
            .all()
        )
        assert [(row["symbol"], row["action"], row["state"]) for row in rows] == [
            ("000001.SZ", "buy", "planned"),
            ("600519.SH", "buy", "ready"),
            ("999999.SZ", "hold", "holding"),
        ]

        condition_count = conn.execute(
            text(
                "SELECT count(*) FROM quant.trading_plan_conditions c "
                "JOIN quant.trading_plan_item_versions iv ON iv.id = c.item_version_id "
                "JOIN quant.trading_plan_items i ON i.id = iv.item_id WHERE i.plan_id=:plan"
            ),
            {"plan": plan["id"]},
        ).scalar()
        assert condition_count == 2

        run = (
            conn.execute(
                text("SELECT * FROM quant.trading_plan_runs WHERE id=:id"), {"id": result["run_id"]}
            )
            .mappings()
            .one()
        )
        assert run["status"] == "succeeded"

        event = (
            conn.execute(
                text(
                    "SELECT * FROM quant.trading_plan_events WHERE plan_id=:plan AND kind='generation'"
                ),
                {"plan": plan["id"]},
            )
            .mappings()
            .one()
        )
        assert event["plan_version"] == 1


def test_generate_is_idempotent_for_same_account_and_trade_date():
    service = _service(
        _decision(targets=[_target("600519.SH")]),
        positions=[PositionView("600519.SH", 0)],
    )
    key = "%s:%s:generate" % (ACCOUNT, TRADE_DATE)
    first = service.generate(
        account=ACCOUNT, trade_date=TRADE_DATE, actor="agent", idempotency_key=key
    )
    second = service.generate(
        account=ACCOUNT, trade_date=TRADE_DATE, actor="agent", idempotency_key=key
    )

    assert second["existing"] is True
    assert second["revision_id"] == first["revision_id"]
    with get_engine().connect() as conn:
        plan_id = conn.execute(
            text("SELECT id FROM quant.trading_plans WHERE account=:account"), {"account": ACCOUNT}
        ).scalar()
        assert (
            conn.execute(
                text("SELECT count(*) FROM quant.trading_plan_versions WHERE plan_id=:plan"),
                {"plan": plan_id},
            ).scalar()
            == 1
        )
        assert (
            conn.execute(
                text("SELECT count(*) FROM quant.trading_plan_items WHERE plan_id=:plan"),
                {"plan": plan_id},
            ).scalar()
            == 1
        )


def test_stale_decision_is_rejected_and_run_is_failed():
    service = _service(
        _decision(
            targets=[_target("600519.SH")],
            data_as_of=datetime(2026, 10, 25, 8, tzinfo=timezone.utc),
        )
    )

    with pytest.raises(AccountPlanError) as excinfo:
        service.generate(
            account=ACCOUNT,
            trade_date=TRADE_DATE,
            actor="agent",
            idempotency_key="%s:%s:generate" % (ACCOUNT, TRADE_DATE),
        )
    assert excinfo.value.code == "PLAN_DATA_STALE"

    with get_engine().connect() as conn:
        assert (
            conn.execute(
                text("SELECT count(*) FROM quant.trading_plans WHERE account=:account"),
                {"account": ACCOUNT},
            ).scalar()
            == 0
        )
        run = (
            conn.execute(
                text("SELECT * FROM quant.trading_plan_runs WHERE account=:account"),
                {"account": ACCOUNT},
            )
            .mappings()
            .one()
        )
        assert run["status"] == "failed"
        assert "PLAN_DATA_STALE" in run["error"]


def test_partial_write_failure_rolls_back_all_plan_rows(monkeypatch):
    service = _service(
        _decision(targets=[_target("600519.SH"), _target("000001.SZ")]), positions=[]
    )

    def fail_second_item_version(self, **kwargs):
        count = self.session.query(TradingPlanItemVersion).count()
        if count >= 1:
            raise RuntimeError("injected item_version failure")
        return original_add_item_version(self, **kwargs)

    original_add_item_version = AccountPlanRepository.add_item_version
    monkeypatch.setattr(AccountPlanRepository, "add_item_version", fail_second_item_version)

    with pytest.raises(RuntimeError, match="injected"):
        service.generate(
            account=ACCOUNT,
            trade_date=TRADE_DATE,
            actor="agent",
            idempotency_key="%s:%s:generate" % (ACCOUNT, TRADE_DATE),
        )

    with get_engine().connect() as conn:
        assert (
            conn.execute(
                text("SELECT count(*) FROM quant.trading_plans WHERE account=:account"),
                {"account": ACCOUNT},
            ).scalar()
            == 0
        )
        assert (
            conn.execute(
                text(
                    "SELECT count(*) FROM quant.trading_plan_versions v "
                    "JOIN quant.trading_plans p ON p.id=v.plan_id WHERE p.account=:account"
                ),
                {"account": ACCOUNT},
            ).scalar()
            == 0
        )
        run = (
            conn.execute(
                text("SELECT * FROM quant.trading_plan_runs WHERE account=:account"),
                {"account": ACCOUNT},
            )
            .mappings()
            .one()
        )
        assert run["status"] == "failed"
        assert "injected item_version failure" in run["error"]


def test_rollover_reuses_item_and_clones_previous_conditions():
    first_date = date(2026, 10, 23)
    first_service = _service(
        _decision(
            targets=[
                _target(
                    "600519.SH",
                    entry_conditions=(
                        {
                            "type": "price_break",
                            "params": {"price": 1500, "direction": "above"},
                        },
                    ),
                    stop_loss={"type": "pct", "value": 8},
                    reduce_plan=({"at_pct": 10, "sell_ratio": 0.5},),
                )
            ],
            trade_date=first_date,
            data_as_of=datetime(2026, 10, 23, 15, tzinfo=timezone.utc),
        ),
        positions=[PositionView("600519.SH", 0)],
    )
    first = first_service.generate(
        account=ACCOUNT,
        trade_date=first_date,
        actor="agent",
        idempotency_key="%s:%s:generate" % (ACCOUNT, first_date),
    )

    second_date = TRADE_DATE
    second_service = _service(
        _decision(
            targets=[_target("600519.SH")],
            trade_date=second_date,
            data_as_of=datetime(2026, 10, 26, 8, 30, tzinfo=timezone.utc),
        ),
        positions=[PositionView("600519.SH", 100)],
    )
    second = second_service.generate(
        account=ACCOUNT,
        trade_date=second_date,
        actor="agent",
        idempotency_key="%s:%s:generate" % (ACCOUNT, second_date),
    )

    assert second["existing"] is False
    assert second["version"] == 2
    assert second["plan_id"] == first["plan_id"]

    with get_engine().connect() as conn:
        item_ids = (
            conn.execute(
                text("SELECT id FROM quant.trading_plan_items WHERE plan_id=:plan"),
                {"plan": first["plan_id"]},
            )
            .scalars()
            .all()
        )
        assert len(item_ids) == 1

        copied = (
            conn.execute(
                text(
                    "SELECT c.role, c.condition_type, c.params, c.batch, c.sequence "
                    "FROM quant.trading_plan_conditions c "
                    "JOIN quant.trading_plan_item_versions iv ON iv.id=c.item_version_id "
                    "WHERE iv.revision_id=:revision ORDER BY c.role, c.batch, c.sequence"
                ),
                {"revision": second["revision_id"]},
            )
            .mappings()
            .all()
        )
        assert len(copied) == 3
        assert copied[0]["role"] == "entry"
        assert copied[0]["condition_type"] == "price_break"
        assert copied[1]["role"] == "reduce"
        assert copied[2]["role"] == "stop_loss"
        assert all(row["params"] for row in copied)


def test_generate_defaults_entry_valid_until_for_buy_and_add():
    """provider 未提供 entry_valid_until 时按 horizon 给默认值（回归：曾全表 NULL 致 422）。"""
    decision = _decision(
        targets=[
            _target("600519.SH", action="buy", horizon="day"),
            _target("000001.SZ", action="buy", horizon="swing"),
            _target("000002.SZ", action="observe", horizon="swing"),
        ]
    )
    service = _service(decision, positions=[])

    service.generate(
        account=ACCOUNT,
        trade_date=TRADE_DATE,
        actor="agent",
        idempotency_key="%s:%s:default-valid-until" % (ACCOUNT, TRADE_DATE),
    )

    engine = get_engine()
    with engine.connect() as conn:
        rows = (
            conn.execute(
                text(
                    "SELECT iv.action, iv.horizon, iv.entry_valid_until FROM "
                    "quant.trading_plan_item_versions iv "
                    "JOIN quant.trading_plan_items i ON i.id = iv.item_id "
                    "JOIN quant.trading_plans p ON p.id = i.plan_id "
                    "WHERE p.account=:account ORDER BY iv.id"
                ),
                {"account": ACCOUNT},
            )
            .mappings()
            .all()
        )
    by_symbol_action = {(r["action"], r["horizon"]): r["entry_valid_until"] for r in rows}
    day_until = by_symbol_action[("buy", "day")]
    swing_until = by_symbol_action[("buy", "swing")]
    assert day_until is not None
    assert swing_until is not None
    assert day_until.hour == 15 and day_until.utcoffset().total_seconds() == 8 * 3600
    # day=T+0、swing=T+3；实现以 max(trade_date, today) 为基准（允许补跑历史日期）
    base = max(TRADE_DATE, date.today())
    assert (day_until.date() - base).days == 0
    assert (swing_until.date() - base).days == 3
