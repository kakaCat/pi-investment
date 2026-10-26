"""反思写回与统计路由测试（t10/t9 · IF-12/13/14/16）"""

from datetime import date, datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text

from adapters.inbound.fastapi_app.routes.plan_async import router

ACC = "test-plan-t10"
SYM = "999997.SZ"


def _spec():
    return {
        "targets": [{"symbol": SYM, "budget_pct": 5, "role": "core"}],
        "entry": {
            "conditions": [{"type": "price_break", "params": {"price": 9999}}],
            "combinator": "all_of",
        },
        "exit": {"stop_loss": {"type": "pct", "value": 8}},
        "monitoring": {},
        "schedule": {},
    }


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


class TestReflections:
    def setup_method(self):
        self._ids = []

    def teardown_method(self):
        from qs_kernel.infrastructure.persistence.database.engine import get_engine

        with get_engine().begin() as conn:
            if self._ids:
                conn.execute(
                    text("DELETE FROM quant.simulation_trades WHERE plan_id = ANY(:ids)"),
                    {"ids": self._ids},
                )
                conn.execute(
                    text("DELETE FROM quant.trading_plans WHERE id = ANY(:ids)"), {"ids": self._ids}
                )

    def _create(self, client):
        r = client.post(
            "/api/plans",
            json={"account": ACC, "name": "反思测试", "horizon": "day", "spec": _spec()},
        )
        pid = r.json()["data"]["plan"]["id"]
        self._ids.append(pid)
        return pid

    def _answers(self):
        return {f"q{i}": f"第{i}问作答" for i in range(1, 6)}

    def test_missing_question_400(self, client):
        pid = self._create(client)
        a = self._answers()
        a.pop("q3")
        r = client.post(
            f"/api/plans/{pid}/reflections",
            json={"answers": a, "verdict": "keep", "reasoning": "x"},
        )
        assert r.status_code == 400 and r.json()["code"] == "REFLECTION_INCOMPLETE"
        assert "q3" in r.json()["error"]

    def test_keep_requires_reasoning(self, client):
        pid = self._create(client)
        r = client.post(
            f"/api/plans/{pid}/reflections", json={"answers": self._answers(), "verdict": "keep"}
        )
        assert r.status_code == 400

    def test_adjust_requires_actions(self, client):
        pid = self._create(client)
        r = client.post(
            f"/api/plans/{pid}/reflections",
            json={"answers": self._answers(), "verdict": "adjust", "reasoning": "x"},
        )
        assert r.status_code == 400

    def test_valid_report_and_same_period_version(self, client):
        pid = self._create(client)
        body = {
            "answers": self._answers(),
            "verdict": "keep",
            "reasoning": "维持不动",
            "period": "2026-10-21",
            "evidence_pack": {
                "modifications": {"status": "ok"},
                "missed": {"status": "missing"},
                "wins": {"status": "ok"},
                "losses": {"status": "missing"},
            },
        }
        r1 = client.post(f"/api/plans/{pid}/reflections", json=body)
        assert r1.status_code == 201, r1.text
        r2 = client.post(f"/api/plans/{pid}/reflections", json=body)
        assert r2.status_code == 201
        rows = client.get(f"/api/plans/{pid}/reflections").json()["data"]["reflections"]
        assert [x["version"] for x in rows] == [2, 1]
        assert rows[0]["verdict"] == "keep"
        # 报告落库后 overdue 归零
        plan = client.get(f"/api/plans/{pid}").json()["data"]["plan"]
        assert plan["reflection_overdue_count"] == 0
        assert plan["last_reflected_at"] is not None

    def test_reflection_pack_route_returns_four_inputs(self, client):
        pid = self._create(client)
        r = client.get(f"/api/plans/{pid}/reflection-pack")
        assert r.status_code == 200, r.text
        pack = r.json()["data"]
        for key in ("modifications", "missed", "wins", "losses", "inputs_ready"):
            assert key in pack

    def test_empty_evidence_pack_is_built_server_side(self, client):
        pid = self._create(client)
        body = {
            "answers": self._answers(),
            "verdict": "keep",
            "reasoning": "维持不动",
            "period": "2026-10-21",
        }
        r = client.post(f"/api/plans/{pid}/reflections", json=body)
        assert r.status_code == 201, r.text
        row = client.get(f"/api/plans/{pid}/reflections").json()["data"]["reflections"][0]
        pack = row["evidence_pack"]
        for key in ("modifications", "missed", "wins", "losses", "inputs_ready"):
            assert key in pack
        assert pack["modifications"]["status"] == "ok"

    def test_knowledge_updates_are_synced(self, client, monkeypatch):
        from qs_agenthub.application.services.evolution.plan_reflection_consumer import (
            PlanReflectionConsumer,
        )

        consumed = []

        def fake_consume(self, rows):
            consumed.extend(rows)
            return {"upserted": 1, "skipped": 0, "failed": 0}

        monkeypatch.setattr(PlanReflectionConsumer, "consume", fake_consume)
        pid = self._create(client)
        body = {
            "answers": self._answers(),
            "verdict": "keep",
            "reasoning": "维持",
            "period": "2026-10-21",
            "evidence_pack": {"modifications": {"status": "ok"}},
            "knowledge_updates": [{"lesson": "有证据的教训", "evidence": ["e1"]}],
        }
        r = client.post(f"/api/plans/{pid}/reflections", json=body)
        assert r.status_code == 201, r.text
        assert r.json()["data"]["knowledge_sync"] == {"upserted": 1, "skipped": 0, "failed": 0}
        assert len(consumed) == 1 and consumed[0].knowledge_updates == body["knowledge_updates"]

    def test_knowledge_sync_failure_does_not_rollback_reflection(self, client, monkeypatch):
        from qs_agenthub.application.services.evolution.plan_reflection_consumer import (
            PlanReflectionConsumer,
        )

        def boom(self, rows):
            raise RuntimeError("knowledge db down")

        monkeypatch.setattr(PlanReflectionConsumer, "consume", boom)
        pid = self._create(client)
        body = {
            "answers": self._answers(),
            "verdict": "keep",
            "reasoning": "维持",
            "period": "2026-10-21",
            "evidence_pack": {"modifications": {"status": "ok"}},
            "knowledge_updates": [{"lesson": "x", "evidence": ["e1"]}],
        }
        r = client.post(f"/api/plans/{pid}/reflections", json=body)
        assert r.status_code == 201, r.text
        sync = r.json()["data"]["knowledge_sync"]
        assert sync["failed"] == 1 and "knowledge db down" in sync["error"]
        assert client.get(f"/api/plans/{pid}/reflections").json()["data"]["count"] == 1

    def test_stats_counts_plan_trades_and_outside(self, client):
        pid = self._create(client)
        from qs_kernel.infrastructure.persistence.database.engine import get_engine

        with get_engine().begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO quant.simulation_trades (account_name, symbol, action, shares, "
                    "price, filled_price, amount, trade_date, plan_id, realized_pnl) VALUES "
                    "(:a, :s, 'SELL', 100, 10.0, 10.0, 1000, :d, :p, 120.0)"
                ),
                {"a": ACC, "s": SYM, "d": date(2026, 10, 21), "p": pid},
            )
            conn.execute(
                text(
                    "INSERT INTO quant.simulation_trades (account_name, symbol, action, shares, "
                    "price, filled_price, amount, trade_date, plan_id) VALUES "
                    "(:a, :s, 'BUY', 100, 10.0, 10.0, 1000, :d, NULL)"
                ),
                {"a": ACC, "s": SYM, "d": date(2026, 10, 21)},
            )
        data = client.get(f"/api/plans/{pid}/stats").json()["data"]
        assert data["trades"]["sells"] == 1 and data["wins"] == 1
        assert data["pnl"] == 120.0 and data["win_rate"] == 1.0
        assert data["outside_trades"] >= 1

    def test_blocked_stats_shape(self, client):
        r = client.get("/api/watch/outcomes/blocked-stats?since_days=30&horizon=5")
        assert r.status_code == 200
        data = r.json()["data"]
        for key in (
            "samples",
            "decided",
            "blocked_right",
            "blocked_wrong",
            "undecidable",
            "wrong_rate",
        ):
            assert key in data
