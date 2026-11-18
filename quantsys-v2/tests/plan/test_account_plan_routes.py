"""账户级计划 API 冒烟（REQ-261026140857-c192，quant_test）"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text
import pytest

import adapters.inbound.fastapi_app.routes.plan_async as plan_routes
from qs_kernel.infrastructure.persistence.database.engine import get_engine
from qs_plan.application.ports import PositionView
from tests.plan import test_plan_readiness as readiness_data


@pytest.fixture(autouse=True)
def cleanup_account_data():
    readiness_data._cleanup_account_data()
    readiness_data.POSITIONS.clear()
    yield
    readiness_data.POSITIONS.clear()
    readiness_data._cleanup_account_data()


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(
        plan_routes,
        "_account_decision_provider",
        readiness_data.FakeDecisionProvider(
            readiness_data.PortfolioDecision(
                account=readiness_data.ACCOUNT,
                trade_date=readiness_data.TRADE_DATE,
                data_as_of=readiness_data.DATA_AS_OF,
                targets=(readiness_data._target(),),
                market_gate={"allowed": True},
                risk_budget={},
                evidence={},
            )
        ),
    )
    monkeypatch.setattr(
        plan_routes, "_account_position_provider", readiness_data.FakePositionProvider()
    )
    app = FastAPI()
    app.include_router(plan_routes.router)
    return TestClient(app)


def test_generate_activate_and_readiness_routes(client):
    generate = client.post(
        "/api/plans/generate",
        json={
            "account": readiness_data.ACCOUNT,
            "trade_date": readiness_data.TRADE_DATE.isoformat(),
            "actor": "agent",
        },
    )
    assert generate.status_code == 201, generate.text
    generated = generate.json()["data"]

    readiness_draft = client.post(
        f"/api/plans/{generated['plan_id']}/readiness",
        json={"trade_date": readiness_data.TRADE_DATE.isoformat(), "stage": "runtime"},
    )
    assert readiness_draft.status_code == 200
    assert readiness_draft.json()["data"]["ready"] is False
    assert readiness_draft.json()["data"]["reasons"][0]["code"] == "REVIEW_REQUIRED"

    with get_engine().connect() as conn:
        item_id = conn.execute(
            text("SELECT id FROM quant.trading_plan_items WHERE plan_id=:plan"),
            {"plan": generated["plan_id"]},
        ).scalar()

    patch = client.patch(
        f"/api/plans/{generated['plan_id']}",
        json={
            "expected_version": generated["version"],
            "actor": "agent",
            "decision_audit_id": "audit-account-plan-1",
            "reason": "补充入场条件",
            "item_patches": [
                {
                    "item_id": item_id,
                    "entry": {
                        "combinator": "all_of",
                        "conditions": [
                            {
                                "type": "price_break",
                                "params": {"price": 10, "direction": "above"},
                            }
                        ],
                    },
                }
            ],
        },
    )
    assert patch.status_code == 200, patch.text
    assert patch.json()["data"]["status"] == "reviewing"

    apply = client.post(
        f"/api/plans/{generated['plan_id']}/apply",
        json={
            "expected_version": generated["version"],
            "actor": "agent",
            "decision_audit_id": "audit-account-plan-1",
            "reason": "审核通过",
        },
    )
    assert apply.status_code == 200, apply.text
    assert apply.json()["data"]["status"] == "approved"

    activate = client.post(
        f"/api/plans/{generated['plan_id']}/activate",
        json={"expected_version": generated["version"], "actor": "agent"},
    )
    assert activate.status_code == 200, activate.text
    assert activate.json()["data"]["status"] == "active"
    assert activate.json()["data"]["compiled"]["create"] == 2

    readiness_data.POSITIONS.append(PositionView(readiness_data.SYMBOL, 100))
    with get_engine().begin() as conn:
        conn.execute(
            text(
                "UPDATE quant.trading_plan_item_states SET state='holding', filled_qty=100 "
                "WHERE item_id IN (SELECT id FROM quant.trading_plan_items WHERE plan_id=:plan)"
            ),
            {"plan": generated["plan_id"]},
        )
    readiness_ready = client.post(
        f"/api/plans/{generated['plan_id']}/readiness",
        json={"trade_date": readiness_data.TRADE_DATE.isoformat(), "stage": "runtime"},
    )
    assert readiness_ready.status_code == 200
    assert readiness_ready.json()["data"]["ready"] is True

    today = client.get(
        "/api/plans/today",
        params={
            "account": readiness_data.ACCOUNT,
            "trade_date": readiness_data.TRADE_DATE.isoformat(),
        },
    )
    assert today.status_code == 200, today.text
    today_data = today.json()["data"]
    assert today_data["plan_id"] == generated["plan_id"]
    assert today_data["version"] == generated["version"]
    assert today_data["revision_status"] == "active"
    assert today_data["readiness"]["ready"] is True
    assert len(today_data["items"]) == 1
    item = today_data["items"][0]
    assert item["symbol"] == readiness_data.SYMBOL
    assert item["action"] == "buy"
    assert item["entry"]["conditions"]
    assert item["exit"][0]["role"] == "stop_loss"


def test_patch_requires_audit_and_apply_rejects_incomplete_item(client):
    generated_response = client.post(
        "/api/plans/generate",
        json={
            "account": readiness_data.ACCOUNT,
            "trade_date": readiness_data.TRADE_DATE.isoformat(),
            "actor": "agent",
        },
    )
    assert generated_response.status_code == 201
    generated = generated_response.json()["data"]
    with get_engine().connect() as conn:
        item_id = conn.execute(
            text("SELECT id FROM quant.trading_plan_items WHERE plan_id=:plan"),
            {"plan": generated["plan_id"]},
        ).scalar()

    no_audit = client.patch(
        f"/api/plans/{generated['plan_id']}",
        json={
            "expected_version": generated["version"],
            "actor": "agent",
            "item_patches": [{"item_id": item_id, "entry": {"conditions": []}}],
        },
    )
    assert no_audit.status_code == 400
    assert no_audit.json()["code"] == "DECISION_AUDIT_REQUIRED"

    conflict = client.patch(
        f"/api/plans/{generated['plan_id']}",
        json={
            "expected_version": generated["version"] + 99,
            "actor": "agent",
            "decision_audit_id": "audit-version-conflict",
            "item_patches": [{"item_id": item_id, "entry": {"conditions": []}}],
        },
    )
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "VERSION_CONFLICT"

    clear_entry = client.patch(
        f"/api/plans/{generated['plan_id']}",
        json={
            "expected_version": generated["version"],
            "actor": "agent",
            "decision_audit_id": "audit-clear-entry",
            "item_patches": [{"item_id": item_id, "entry": {"conditions": []}}],
        },
    )
    assert clear_entry.status_code == 200

    apply = client.post(
        f"/api/plans/{generated['plan_id']}/apply",
        json={
            "expected_version": generated["version"],
            "actor": "agent",
            "decision_audit_id": "audit-incomplete",
        },
    )
    assert apply.status_code == 422
    assert apply.json()["code"] == "PLAN_NOT_READY"

    with get_engine().connect() as conn:
        status = conn.execute(
            text("SELECT status FROM quant.trading_plan_versions WHERE id=:id"),
            {"id": generated["revision_id"]},
        ).scalar()
        assert status == "reviewing"
