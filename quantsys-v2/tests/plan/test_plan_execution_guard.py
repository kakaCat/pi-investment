"""计划归因买入的执行前硬校验（quant_test）。"""

from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy import text

from adapters.outbound.repositories.trading_plan_unit_of_work import TradingPlanUnitOfWork
from qs_kernel.infrastructure.persistence.database.engine import get_engine
from qs_plan.application.plan_activation_service import PlanActivationService
from qs_plan.application.plan_execution_guard import PlanExecutionGuard
from qs_plan.application.plan_generation_service import AccountPlanError
from tests.plan import test_plan_readiness as data


@pytest.fixture(autouse=True)
def cleanup_account_data():
    data.POSITIONS.clear()
    data._cleanup_account_data()
    with get_engine().begin() as conn:
        conn.execute(text("DELETE FROM quant.simulation_trades WHERE account_name=:account"), {"account": data.ACCOUNT})
    yield
    data.POSITIONS.clear()
    data._cleanup_account_data()
    with get_engine().begin() as conn:
        conn.execute(text("DELETE FROM quant.simulation_trades WHERE account_name=:account"), {"account": data.ACCOUNT})


def _guard():
    return PlanExecutionGuard(
        unit_of_work_factory=TradingPlanUnitOfWork,
        readiness_service_factory=lambda account: data._readiness(),
        now_date=lambda: data.TRADE_DATE,
        now_fn=lambda: data.DATA_AS_OF,
    )


def _activate():
    generated = data._generate()
    with get_engine().begin() as conn:
        conn.execute(
            text(
                "UPDATE quant.trading_plan_versions SET status='approved', "
                "reviewed_by='agent', reviewed_at=now() WHERE id=:id"
            ),
            {"id": generated["revision_id"]},
        )
        conn.execute(
            text(
                "UPDATE quant.trading_plan_item_versions SET execution_batch=1, "
                "max_chase_pct=5, entry_valid_until=:valid_until WHERE revision_id=:revision"
            ),
            {"revision": generated["revision_id"], "valid_until": data.DATA_AS_OF + timedelta(days=3650)},
        )
    PlanActivationService(
        unit_of_work_factory=TradingPlanUnitOfWork,
        position_state_provider=lambda symbol: "none",
    ).activate(plan_id=generated["plan_id"], expected_version=generated["version"], actor="agent")
    return generated


def _valid_args(generated):
    with get_engine().connect() as conn:
        item_id = conn.execute(
            text("SELECT id FROM quant.trading_plan_items WHERE plan_id=:plan"),
            {"plan": generated["plan_id"]},
        ).scalar()
    return {
        "account": data.ACCOUNT,
        "action": "BUY",
        "symbol": data.SYMBOL,
        "reason": "计划#7 测试买入",
        "plan_id": generated["plan_id"],
        "item_id": item_id,
        "plan_version": generated["version"],
        "signal_grade": "A",
        "decision_audit_id": "audit-plan-execution",
        "price": 10.0,
    }


def _set_item_fields(generated, **values):
    assignments = ", ".join("%s=:%s" % (key, key) for key in values)
    with get_engine().begin() as conn:
        conn.execute(
            text(
                "UPDATE quant.trading_plan_item_versions SET %s WHERE revision_id=:revision" % assignments
            ),
            {**values, "revision": generated["revision_id"]},
        )


def _insert_batch_trade(generated, batch: int, trade_date):
    with TradingPlanUnitOfWork() as uow:
        item = uow.plans.create_item(plan_id=generated["plan_id"], symbol="999999")
        uow.plans.add_item_version(
            revision_id=generated["revision_id"],
            item_id=item.id,
            action="buy",
            horizon="swing",
            target_weight=0.1,
            target_qty=100,
            execution_batch=batch,
            max_chase_pct=5,
            entry_combinator="all_of",
            thesis="历史批次",
            invalidation="测试失效",
            entry_valid_until=data.DATA_AS_OF + timedelta(days=3650),
            evidence={},
            setup_type="breakout",
        )
        uow.commit()
        item_id = item.id
    with get_engine().begin() as conn:
        conn.execute(
            text(
                "INSERT INTO quant.simulation_trades "
                "(account_name,symbol,action,shares,price,filled_price,amount,trade_date,trade_time,"
                "plan_id,item_id,plan_version) VALUES "
                "(:account,'999999','BUY',100,10,10,1000,:trade_date,now(),:plan,:item,:version)"
            ),
            {
                "account": data.ACCOUNT,
                "trade_date": trade_date,
                "plan": generated["plan_id"],
                "item": item_id,
                "version": generated["version"],
            },
        )


def test_valid_plan_buy_passes_and_activation_marks_item_ready():
    generated = _activate()

    result = _guard().validate(**_valid_args(generated))

    assert result["required"] is True
    with get_engine().connect() as conn:
        state = conn.execute(
            text(
                "SELECT s.state FROM quant.trading_plan_item_states s "
                "JOIN quant.trading_plan_items i ON i.id=s.item_id WHERE i.plan_id=:plan"
            ),
            {"plan": generated["plan_id"]},
        ).scalar()
        assert state == "ready"


def test_plan_reference_without_attribution_is_rejected():
    with pytest.raises(AccountPlanError) as error:
        _guard().validate(
            account=data.ACCOUNT,
            action="BUY",
            symbol=data.SYMBOL,
            reason="计划#7 突破买入",
            plan_id=None,
            item_id=None,
            plan_version=None,
            signal_grade="A",
            decision_audit_id="audit",
        )
    assert error.value.code == "PLAN_ATTRIBUTION_REQUIRED"


def test_c_grade_plan_buy_is_rejected_before_trade():
    generated = _activate()
    args = {**_valid_args(generated), "signal_grade": "C"}

    with pytest.raises(AccountPlanError) as error:
        _guard().validate(**args)
    assert error.value.code == "SIGNAL_GRADE_NOT_ALLOWED"


def test_stale_plan_version_is_rejected():
    generated = _activate()
    args = {**_valid_args(generated), "plan_version": generated["version"] + 1}

    with pytest.raises(AccountPlanError) as error:
        _guard().validate(**args)
    assert error.value.code == "PLAN_VERSION_STALE"


def test_actual_position_without_fill_receipt_blocks_plan_buy():
    generated = _activate()
    data.POSITIONS.append(data.PositionView(data.SYMBOL, 100))

    with pytest.raises(AccountPlanError) as error:
        _guard().validate(**_valid_args(generated))
    assert error.value.code == "PLAN_NOT_READY"
    assert any(reason["code"] == "POSITION_MISMATCH" for reason in error.value.details["reasons"])


def test_missing_entry_constraints_are_rejected():
    generated = _activate()
    _set_item_fields(generated, execution_batch=None, entry_valid_until=None, max_chase_pct=None)

    with pytest.raises(AccountPlanError) as error:
        _guard().validate(**_valid_args(generated))
    assert error.value.code == "PLAN_BATCH_REQUIRED"


def test_expired_entry_is_rejected():
    generated = _activate()
    _set_item_fields(generated, entry_valid_until=data.DATA_AS_OF - timedelta(seconds=1))

    with pytest.raises(AccountPlanError) as error:
        _guard().validate(**_valid_args(generated))
    assert error.value.code == "ENTRY_EXPIRED"


def test_chase_above_reviewed_limit_is_rejected():
    generated = _activate()

    with pytest.raises(AccountPlanError) as error:
        _guard().validate(**{**_valid_args(generated), "price": 10.51})
    assert error.value.code == "ENTRY_CHASE_EXCEEDED"


def test_same_day_cross_batch_is_rejected():
    generated = _activate()
    _insert_batch_trade(generated, 2, data.TRADE_DATE)

    with pytest.raises(AccountPlanError) as error:
        _guard().validate(**_valid_args(generated))
    assert error.value.code == "PLAN_BATCH_CONFLICT"


def test_different_batch_requires_seven_day_interval():
    generated = _activate()
    _insert_batch_trade(generated, 2, data.TRADE_DATE - timedelta(days=6))

    with pytest.raises(AccountPlanError) as error:
        _guard().validate(**_valid_args(generated))
    assert error.value.code == "PLAN_BATCH_INTERVAL"
