"""账户级计划原子激活与成交推进（REQ-261026140857-c192，quant_test）"""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest
from sqlalchemy import text

from adapters.outbound.repositories.account_plan_rule_repository import (
    AccountPlanRuleRepository,
)
from adapters.outbound.repositories.trading_plan_unit_of_work import TradingPlanUnitOfWork
from qs_kernel.infrastructure.persistence.database.engine import get_engine
from qs_plan.application.plan_activation_service import PlanActivationService
from qs_plan.application.plan_generation_service import (
    AccountPlanError,
    PlanGenerationService,
)
from qs_plan.application.plan_progress_service import PlanProgressService
from qs_plan.application.ports import (
    PortfolioDecision,
    PositionView,
    TargetAllocation,
)

ACCOUNT = "test-account-plan-activate"
TRADE_DATE = date(2026, 10, 26)
DATA_AS_OF = datetime(2026, 10, 26, 8, 30, tzinfo=timezone.utc)
SYMBOL_A = "600519.SH"
SYMBOL_B = "000001.SZ"
BASE_TRADE_ID = 88000000


class FakeDecisionProvider:
    def __init__(self, decision):
        self.decision = decision

    def build(self, *, account: str, trade_date: date):
        return self.decision


class FakePositionProvider:
    def __init__(self, positions=()):
        self.positions = tuple(positions)

    def list_positions(self, *, account: str):
        return self.positions


def _target(symbol, **overrides):
    base = {
        "symbol": symbol,
        "target_weight": 0.1,
        "horizon": "swing",
        "thesis": "测试假设",
        "invalidation": "假设失效",
        "entry_conditions": (
            {"type": "price_break", "params": {"price": 10, "direction": "above"}},
        ),
        "stop_loss": {"type": "pct", "value": 8},
    }
    base.update(overrides)
    return TargetAllocation(**base)


def _decision(targets):
    return PortfolioDecision(
        account=ACCOUNT,
        trade_date=TRADE_DATE,
        data_as_of=DATA_AS_OF,
        targets=tuple(targets),
        market_gate={"allowed": True},
        risk_budget={},
        evidence={},
    )


def _generate(targets, positions=()):
    service = PlanGenerationService(
        decision_provider=FakeDecisionProvider(_decision(targets)),
        position_provider=FakePositionProvider(positions),
        unit_of_work_factory=TradingPlanUnitOfWork,
    )
    return service.generate(
        account=ACCOUNT,
        trade_date=TRADE_DATE,
        actor="agent",
        idempotency_key="%s:%s:generate" % (ACCOUNT, TRADE_DATE),
    )


def _approve_revision(revision_id: int):
    with get_engine().begin() as conn:
        conn.execute(
            text(
                "UPDATE quant.trading_plan_versions SET status='approved', "
                "reviewed_by='agent', reviewed_at=now() WHERE id=:id"
            ),
            {"id": revision_id},
        )


def _activation_service(holding_symbols=()):
    holding = set(holding_symbols)

    def position_state(symbol: str) -> str:
        return "holding" if symbol in holding else "none"

    return PlanActivationService(
        unit_of_work_factory=TradingPlanUnitOfWork,
        position_state_provider=position_state,
        interval_sec=30,
    )


@pytest.fixture(autouse=True)
def cleanup_account_plan_and_rules():
    yield
    engine = get_engine()
    with engine.begin() as conn:
        plan_ids = [
            row[0]
            for row in conn.execute(
                text("SELECT id FROM quant.trading_plans WHERE account=:account"),
                {"account": ACCOUNT},
            )
        ]
        if plan_ids:
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
            conn.execute(
                text("DELETE FROM quant.trading_plan_fill_receipts WHERE plan_id = ANY(:ids)"),
                {"ids": plan_ids},
            )
            conn.execute(
                text("DELETE FROM quant.trading_plan_item_states WHERE item_id = ANY(:ids)"),
                {"ids": item_ids or [0]},
            )
            conn.execute(
                text("DELETE FROM quant.trading_plan_item_versions WHERE item_id = ANY(:ids)"),
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
            text("DELETE FROM quant.trading_plans WHERE account=:account"), {"account": ACCOUNT}
        )
        conn.execute(
            text("DELETE FROM quant.simulation_trades WHERE account_name=:account"),
            {"account": ACCOUNT},
        )


def _item_ids(plan_id: int):
    with get_engine().connect() as conn:
        return {
            row["symbol"]: row["id"]
            for row in conn.execute(
                text("SELECT id, symbol FROM quant.trading_plan_items WHERE plan_id=:plan"),
                {"plan": plan_id},
            ).mappings()
        }


def test_activation_creates_item_rules_mappings_and_audits_in_one_transaction():
    generated = _generate(
        [
            _target(SYMBOL_A),
            _target(
                SYMBOL_B,
                reduce_plan=({"at_pct": 10, "sell_ratio": 0.5}, {"at_pct": 20, "sell_ratio": 1}),
            ),
        ]
    )
    _approve_revision(generated["revision_id"])

    result = _activation_service(holding_symbols={SYMBOL_B}).activate(
        plan_id=generated["plan_id"], expected_version=generated["version"], actor="agent"
    )

    assert result["status"] == "active"
    assert result["compiled"] == {"create": 6, "update": 0, "retire": 0}

    with get_engine().connect() as conn:
        plan = (
            conn.execute(
                text("SELECT * FROM quant.trading_plans WHERE id=:id"),
                {"id": generated["plan_id"]},
            )
            .mappings()
            .one()
        )
        assert plan["current_revision_id"] == generated["revision_id"]
        assert plan["draft_revision_id"] is None
        assert plan["status"] == "active"

        revision = (
            conn.execute(
                text("SELECT * FROM quant.trading_plan_versions WHERE id=:id"),
                {"id": generated["revision_id"]},
            )
            .mappings()
            .one()
        )
        assert revision["status"] == "active"
        assert revision["activated_at"] is not None

        rules = (
            conn.execute(
                text(
                    "SELECT r.symbol, r.item_id, r.plan_id, m.plan_version, r.enabled, m.role, "
                    "m.batch, r.conditions, r.action_params, r.position_state "
                    "FROM quant.watch_rules r "
                    "JOIN quant.trading_plan_rules m ON m.rule_id=r.id "
                    "WHERE r.plan_id=:plan ORDER BY r.item_id, m.role, m.batch"
                ),
                {"plan": generated["plan_id"]},
            )
            .mappings()
            .all()
        )
        assert len(rules) == 6
        assert {(row["role"], row["batch"]) for row in rules} == {
            ("entry", 0),
            ("stop_loss", 0),
            ("reduce", 0),
            ("reduce", 1),
        }
        assert all(row["item_id"] is not None for row in rules)
        assert all(row["plan_version"] == generated["version"] for row in rules)
        assert all(row["enabled"] is True for row in rules)
        assert {
            row["position_state"]
            for row in rules
            if row["symbol"] == SYMBOL_B and row["role"] != "entry"
        } == {"holding"}

        audits = conn.execute(
            text(
                "SELECT count(*) FROM quant.watch_rule_changes c "
                "JOIN quant.watch_rules r ON r.id=c.rule_id WHERE r.plan_id=:plan "
                "AND c.change_kind='plan_compile'"
            ),
            {"plan": generated["plan_id"]},
        ).scalar()
        assert audits == 6

        event = (
            conn.execute(
                text(
                    "SELECT * FROM quant.trading_plan_events WHERE plan_id=:plan AND kind='compile'"
                ),
                {"plan": generated["plan_id"]},
            )
            .mappings()
            .one()
        )
        assert event["plan_version"] == generated["version"]


def test_activation_audit_failure_rolls_back_rules_and_revision():
    generated = _generate([_target(SYMBOL_A)])
    _approve_revision(generated["revision_id"])

    original = AccountPlanRuleRepository.record_audit

    def fail_audit(self, **kwargs):
        raise RuntimeError("injected audit failure")

    AccountPlanRuleRepository.record_audit = fail_audit
    try:
        with pytest.raises(RuntimeError, match="injected audit failure"):
            _activation_service().activate(
                plan_id=generated["plan_id"],
                expected_version=generated["version"],
                actor="agent",
            )
    finally:
        AccountPlanRuleRepository.record_audit = original

    with get_engine().connect() as conn:
        assert (
            conn.execute(
                text("SELECT count(*) FROM quant.watch_rules WHERE plan_id=:plan"),
                {"plan": generated["plan_id"]},
            ).scalar()
            == 0
        )
        assert (
            conn.execute(
                text("SELECT count(*) FROM quant.trading_plan_rules WHERE plan_id=:plan"),
                {"plan": generated["plan_id"]},
            ).scalar()
            == 0
        )
        revision = conn.execute(
            text("SELECT status FROM quant.trading_plan_versions WHERE id=:id"),
            {"id": generated["revision_id"]},
        ).scalar()
        assert revision == "approved"


def _insert_trade(trade_id: int, symbol: str, action: str, shares: int):
    with get_engine().begin() as conn:
        conn.execute(
            text(
                "INSERT INTO quant.simulation_trades "
                "(id, account_name, symbol, action, shares, price, filled_price, amount, "
                "trade_date, trade_time) VALUES "
                "(:id, :account, :symbol, :action, :shares, 10, 10, :amount, :trade_date, now())"
            ),
            {
                "id": trade_id,
                "account": ACCOUNT,
                "symbol": symbol,
                "action": action,
                "shares": shares,
                "amount": shares * 10,
                "trade_date": TRADE_DATE,
            },
        )


def test_progress_updates_item_and_retires_batches_by_cumulative_sold_ratio():
    generated = _generate(
        [
            _target(
                SYMBOL_A,
                reduce_plan=({"at_pct": 50, "sell_ratio": 0.6}, {"at_pct": 100, "sell_ratio": 1}),
            )
        ]
    )
    _approve_revision(generated["revision_id"])
    _activation_service(holding_symbols={SYMBOL_A}).activate(
        plan_id=generated["plan_id"], expected_version=generated["version"], actor="agent"
    )
    item_id = _item_ids(generated["plan_id"])[SYMBOL_A]
    service = PlanProgressService(
        unit_of_work_factory=TradingPlanUnitOfWork,
        remaining_qty_provider=lambda account, symbol: None,
    )

    buy_trade = BASE_TRADE_ID + 1
    _insert_trade(buy_trade, SYMBOL_A, "BUY", 100)
    buy = service.on_fill(
        account=ACCOUNT,
        symbol=SYMBOL_A,
        side="buy",
        qty=100,
        remaining_qty=100,
        trade_id=buy_trade,
        plan_id=generated["plan_id"],
        item_id=item_id,
        plan_version=generated["version"],
    )
    assert buy["status"] == "ok"
    assert buy["item_state"] == "holding"

    sell_one = BASE_TRADE_ID + 2
    _insert_trade(sell_one, SYMBOL_A, "SELL", 60)
    sell = service.on_fill(
        account=ACCOUNT,
        symbol=SYMBOL_A,
        side="sell",
        qty=60,
        remaining_qty=40,
        trade_id=sell_one,
        plan_id=generated["plan_id"],
        item_id=item_id,
        plan_version=generated["version"],
    )
    assert sell["status"] == "ok"
    assert sell["item_state"] == "reducing"
    assert sell["sold_qty"] == 60
    assert sell["sold_ratio"] == 0.6
    assert sell["retired_batches"] == [0]

    duplicate = service.on_fill(
        account=ACCOUNT,
        symbol=SYMBOL_A,
        side="sell",
        qty=60,
        remaining_qty=40,
        trade_id=sell_one,
        plan_id=generated["plan_id"],
        item_id=item_id,
        plan_version=generated["version"],
    )
    assert duplicate["status"] == "duplicate"
    assert duplicate["item_state"] == "reducing"

    sell_two = BASE_TRADE_ID + 3
    _insert_trade(sell_two, SYMBOL_A, "SELL", 40)
    final = service.on_fill(
        account=ACCOUNT,
        symbol=SYMBOL_A,
        side="sell",
        qty=40,
        remaining_qty=0,
        trade_id=sell_two,
        plan_id=generated["plan_id"],
        item_id=item_id,
        plan_version=generated["version"],
    )
    assert final["status"] == "ok"
    assert final["item_state"] == "exited"
    assert final["sold_qty"] == 100
    assert final["sold_ratio"] == 1.0
    assert final["retired_batches"] == [1]

    with get_engine().connect() as conn:
        state = (
            conn.execute(
                text("SELECT * FROM quant.trading_plan_item_states WHERE item_id=:item"),
                {"item": item_id},
            )
            .mappings()
            .one()
        )
        assert state["state"] == "exited"
        assert state["filled_qty"] == 200
        assert state["remaining_qty"] == 0

        assert (
            conn.execute(
                text("SELECT count(*) FROM quant.trading_plan_fill_receipts WHERE item_id=:item"),
                {"item": item_id},
            ).scalar()
            == 3
        )

        trades = (
            conn.execute(
                text(
                    "SELECT item_id, plan_id, plan_version FROM quant.simulation_trades "
                    "WHERE account_name=:account ORDER BY id"
                ),
                {"account": ACCOUNT},
            )
            .mappings()
            .all()
        )
        assert all(
            row["item_id"] == item_id
            and row["plan_id"] == generated["plan_id"]
            and row["plan_version"] == generated["version"]
            for row in trades
        )

        reduce_rules = (
            conn.execute(
                text(
                    "SELECT m.batch, r.enabled, r.rule_state FROM quant.watch_rules r "
                    "JOIN quant.trading_plan_rules m ON m.rule_id=r.id "
                    "WHERE r.item_id=:item AND m.role='reduce' ORDER BY m.batch"
                ),
                {"item": item_id},
            )
            .mappings()
            .all()
        )
        assert [(row["batch"], row["enabled"], row["rule_state"]) for row in reduce_rules] == [
            (0, False, "archived"),
            (1, False, "archived"),
        ]

        fill_events = conn.execute(
            text(
                "SELECT count(*) FROM quant.trading_plan_events WHERE item_id=:item AND kind='fill'"
            ),
            {"item": item_id},
        ).scalar()
        assert fill_events == 3


def test_progress_rejects_missing_item_attribution_without_receipt():
    generated = _generate([_target(SYMBOL_A)])
    _approve_revision(generated["revision_id"])
    service = PlanProgressService(unit_of_work_factory=TradingPlanUnitOfWork)

    with pytest.raises(AccountPlanError) as excinfo:
        service.on_fill(
            account=ACCOUNT,
            symbol=SYMBOL_A,
            side="buy",
            qty=100,
            remaining_qty=100,
            trade_id=BASE_TRADE_ID + 9,
            plan_id=generated["plan_id"],
            item_id=None,
            plan_version=generated["version"],
        )
    assert excinfo.value.code == "PLAN_ITEM_ATTRIBUTION_REQUIRED"
    with get_engine().connect() as conn:
        assert (
            conn.execute(
                text("SELECT count(*) FROM quant.trading_plan_fill_receipts WHERE trade_id=:id"),
                {"id": str(BASE_TRADE_ID + 9)},
            ).scalar()
            == 0
        )


def test_new_signal_actions_compile_to_v2_intents_and_invalidation_thresholds():
    generated = _generate(
        [
            _target(
                SYMBOL_A,
                action="add",
                entry_conditions=(
                    {
                        "type": "price_break",
                        "params": {"price": 9, "direction": "below"},
                        "invalidation_threshold_pct": 6,
                    },
                ),
            ),
            _target(
                SYMBOL_B,
                action="observe",
                entry_conditions=(
                    {
                        "type": "price_break",
                        "params": {"price": 12, "direction": "above"},
                        "invalidation_threshold_pct": 8,
                    },
                ),
            ),
            _target(
                "000002.SZ",
                action="reduce_risk",
                reduce_plan=({"at_pct": 5, "sell_ratio": 0.2},),
            ),
        ],
        positions=[
            PositionView(SYMBOL_A, 100),
            PositionView("000002.SZ", 200),
        ],
    )
    _approve_revision(generated["revision_id"])
    _activation_service(holding_symbols={SYMBOL_A, "000002.SZ"}).activate(
        plan_id=generated["plan_id"], expected_version=generated["version"], actor="agent"
    )

    with get_engine().connect() as conn:
        rules = (
            conn.execute(
                text(
                    "SELECT r.symbol, r.intent, r.invalidation_threshold_pct, r.engine "
                    "FROM quant.watch_rules r WHERE r.plan_id=:plan "
                    "ORDER BY r.symbol, r.intent"
                ),
                {"plan": generated["plan_id"]},
            )
            .mappings()
            .all()
        )
        by_symbol_intent = {(row["symbol"], row["intent"]): row for row in rules}
        assert by_symbol_intent[(SYMBOL_A, "add_position")]["invalidation_threshold_pct"] == 6
        assert by_symbol_intent[(SYMBOL_B, "trend_observe")]["invalidation_threshold_pct"] == 8
        assert by_symbol_intent[("000002.SZ", "exit_reduce")]
        assert all(row["engine"] == "v2" for row in rules)


def test_add_and_reduce_risk_require_real_positions():
    with pytest.raises(AccountPlanError, match="add 计划项必须有真实持仓"):
        _generate([_target(SYMBOL_A, action="add")], positions=[])

    with pytest.raises(AccountPlanError, match="reduce_risk 计划项必须有真实持仓"):
        _generate(
            [
                _target(
                    SYMBOL_A, action="reduce_risk", reduce_plan=({"at_pct": 5, "sell_ratio": 0.2},)
                )
            ],
            positions=[],
        )
