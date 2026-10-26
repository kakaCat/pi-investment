"""计划路由契约测试（t6 验收：IF-1~IF-9、IF-11，quant_test 真库）

每个用例走路由 → 服务 → 仓储/端口全链；cleanup 删除本用例建的计划与托管规则。
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text

from adapters.inbound.fastapi_app.routes.plan_async import router

ACC = "test-plan-t6"
SYM = "999999.SZ"


def _spec(stop=8.0):
    return {
        "targets": [{"symbol": SYM, "budget_pct": 5, "role": "core"}],
        "entry": {
            "conditions": [
                {"type": "price_break", "params": {"price": 9999, "direction": "above"}}
            ],
            "combinator": "all_of",
        },
        "exit": {"stop_loss": {"type": "pct", "value": stop}},
        "monitoring": {"news": True},
        "schedule": {"interval_sec": 30},
    }


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


class TestPlanRoutes:
    def setup_method(self):
        self._ids = []

    def teardown_method(self):
        from qs_kernel.infrastructure.persistence.database.engine import get_engine

        eng = get_engine()
        with eng.begin() as conn:
            if self._ids:
                ids = self._ids
                conn.execute(
                    text(
                        "DELETE FROM quant.watch_rule_changes WHERE rule_id IN "
                        "(SELECT id FROM quant.watch_rules WHERE plan_id = ANY(:ids))"
                    ),
                    {"ids": ids},
                )
                conn.execute(
                    text("DELETE FROM quant.watch_rules WHERE plan_id = ANY(:ids)"), {"ids": ids}
                )
                conn.execute(
                    text("DELETE FROM quant.trading_plans WHERE id = ANY(:ids)"), {"ids": ids}
                )

    def _create(self, client, stop=8.0):
        r = client.post(
            "/api/plans",
            json={
                "account": ACC,
                "name": "契约测试计划",
                "horizon": "day",
                "spec": _spec(stop),
                "created_by": "test",
            },
        )
        assert r.status_code == 201, r.text
        pid = r.json()["data"]["plan"]["id"]
        self._ids.append(pid)
        return pid

    def test_create_get_list(self, client):
        pid = self._create(client)
        r = client.get(f"/api/plans/{pid}")
        assert r.status_code == 200
        body = r.json()["data"]
        assert body["plan"]["status"] == "draft" and body["plan"]["version"] == 1
        assert len(body["versions"]) == 1 and body["events"]
        r = client.get(f"/api/plans?account={ACC}")
        assert r.status_code == 200 and any(p["id"] == pid for p in r.json()["data"]["plans"])
        assert client.get("/api/plans").status_code == 400

    def test_create_invalid_spec_400(self, client):
        r = client.post(
            "/api/plans", json={"account": ACC, "name": "x", "horizon": "day", "spec": {}}
        )
        assert r.status_code == 400
        assert r.json()["code"] == "PLAN_SPEC_INVALID"

    def test_patch_agent_without_audit_400(self, client):
        pid = self._create(client)
        r = client.patch(
            f"/api/plans/{pid}",
            json={
                "expected_version": 1,
                "spec_patch": {"exit": {"stop_loss": {"type": "pct", "value": 10}}},
                "reason": "x",
                "actor": "agent",
            },
        )
        assert r.status_code == 400 and r.json()["code"] == "DECISION_AUDIT_REQUIRED"

    def test_patch_preview_and_apply(self, client):
        pid = self._create(client)
        r = client.patch(
            f"/api/plans/{pid}",
            json={
                "expected_version": 1,
                "spec_patch": {"exit": {"stop_loss": {"type": "pct", "value": 10}}},
                "reason": "止损太紧",
                "actor": "agent",
                "decision_audit_id": "d-1",
            },
        )
        assert r.status_code == 200
        assert any(d["path"] == "exit.stop_loss.value" for d in r.json()["data"]["diff"])
        # 旧版本 apply → 409 之前先成功一次
        r = client.post(
            f"/api/plans/{pid}/apply",
            json={
                "expected_version": 1,
                "reason": "放宽止损",
                "actor": "agent",
                "decision_audit_id": "d-2",
            },
        )
        assert r.status_code == 200, r.text
        assert r.json()["data"]["version"] == 2
        # 草稿 apply 不产生盯盘规则（编译只在激活/运行时）
        assert r.json()["data"]["compiled"] is None
        # 重放同版本 → 409（无待生效修改也是 400；这里先 patch 再 stale apply）
        r = client.post(f"/api/plans/{pid}/apply", json={"expected_version": 1, "actor": "user"})
        assert r.status_code in (400, 409)
        # 草稿阶段不产生规则；激活后才编译，且规则读数为新值
        from qs_kernel.infrastructure.persistence.database.engine import get_engine

        with get_engine().connect() as conn:
            n = conn.execute(
                text("SELECT count(*) FROM quant.watch_rules WHERE plan_id=:p"), {"p": pid}
            ).scalar()
        assert n == 0
        r = client.post(f"/api/plans/{pid}/activate", json={"expected_version": 2})
        assert r.status_code == 200, r.text
        assert r.json()["data"]["compiled"]["created"] == 2
        with get_engine().connect() as conn:
            pct = conn.execute(
                text(
                    "SELECT conditions->0->'params'->>'pct' FROM quant.watch_rules "
                    "WHERE plan_id=:p AND intent='exit_stop' LIMIT 1"
                ),
                {"p": pid},
            ).scalar()
        assert float(pct) == 10.0

    def test_running_plan_reduce_ratio_update_syncs_rule(self, client):
        spec = _spec()
        spec["exit"]["reduce_plan"] = [{"at_pct": 10, "sell_ratio": 0.3}]
        r = client.post(
            "/api/plans",
            json={
                "account": ACC,
                "name": "比例更新",
                "horizon": "day",
                "spec": spec,
                "created_by": "test",
            },
        )
        assert r.status_code == 201, r.text
        pid = r.json()["data"]["plan"]["id"]
        self._ids.append(pid)
        assert (
            client.post(f"/api/plans/{pid}/activate", json={"expected_version": 1}).status_code
            == 200
        )
        new_exit = {
            "stop_loss": {"type": "pct", "value": 8.0},
            "reduce_plan": [{"at_pct": 10, "sell_ratio": 0.5}],
        }
        r = client.patch(
            f"/api/plans/{pid}",
            json={
                "expected_version": 1,
                "spec_patch": {"exit": new_exit},
                "reason": "上调减仓比例",
                "actor": "user",
            },
        )
        assert r.status_code == 200, r.text
        r = client.post(f"/api/plans/{pid}/apply", json={"expected_version": 1, "actor": "user"})
        assert r.status_code == 200, r.text
        assert r.json()["data"]["compiled"]["updated"] == 1
        from qs_kernel.infrastructure.persistence.database.engine import get_engine

        with get_engine().connect() as conn:
            pct = conn.execute(
                text(
                    "SELECT action_params->>'position_pct' FROM quant.watch_rules "
                    "WHERE plan_id=:p AND intent='exit_take_profit'"
                ),
                {"p": pid},
            ).scalar()
        assert float(pct) == 50.0

    def test_archive_requires_closed(self, client):
        pid = self._create(client)
        r = client.post(f"/api/plans/{pid}/archive", json={})
        assert r.status_code == 422 and r.json()["code"] == "PLAN_STATE_ILLEGAL"
        assert (
            client.post(f"/api/plans/{pid}/activate", json={"expected_version": 1}).status_code
            == 200
        )
        assert client.post(f"/api/plans/{pid}/close", json={"reason": "x"}).status_code == 200
        assert client.post(f"/api/plans/{pid}/archive", json={}).status_code == 200

    def test_archive_requires_overdue_cleared(self, client):
        pid = self._create(client)
        assert (
            client.post(f"/api/plans/{pid}/activate", json={"expected_version": 1}).status_code
            == 200
        )
        assert client.post(f"/api/plans/{pid}/close", json={"reason": "x"}).status_code == 200
        from adapters.outbound.repositories.trading_plan_repository import TradingPlanRepository
        from datetime import datetime, timezone

        repo = TradingPlanRepository()
        repo.bump_overdue(pid)
        r = client.post(f"/api/plans/{pid}/archive", json={})
        assert r.status_code == 422 and "反思" in r.json()["error"]
        repo.mark_reflected(pid, datetime.now(timezone.utc))
        assert client.post(f"/api/plans/{pid}/archive", json={}).status_code == 200

    def test_activate_pause_resume_close(self, client):
        pid = self._create(client)
        r = client.post(f"/api/plans/{pid}/activate", json={"expected_version": 1})
        assert r.status_code == 200, r.text
        assert r.json()["data"]["status"] == "active"
        # 托管规则带 plan_id
        from qs_kernel.infrastructure.persistence.database.engine import get_engine

        with get_engine().connect() as conn:
            n = conn.execute(
                text("SELECT count(*) FROM quant.watch_rules WHERE plan_id=:p"), {"p": pid}
            ).scalar()
        assert n == 2
        assert (
            client.post(f"/api/plans/{pid}/pause", json={"reason": "临时"}).json()["data"]["status"]
            == "paused"
        )
        assert (
            client.post(f"/api/plans/{pid}/resume", json={"expected_version": 1}).json()["data"][
                "status"
            ]
            == "active"
        )
        r = client.post(f"/api/plans/{pid}/close", json={"reason": "收工"})
        assert r.status_code == 200 and r.json()["data"]["status"] == "closed"
        with get_engine().connect() as conn:
            alive = conn.execute(
                text("SELECT count(*) FROM quant.watch_rules WHERE plan_id=:p AND enabled"),
                {"p": pid},
            ).scalar()
        assert alive == 0

    def test_draft_close_422(self, client):
        pid = self._create(client)
        r = client.post(f"/api/plans/{pid}/close", json={"reason": "x"})
        assert r.status_code == 422 and r.json()["code"] == "PLAN_STATE_ILLEGAL"

    def test_compile_preview(self, client):
        pid = self._create(client)
        r = client.get(f"/api/plans/{pid}/compile-preview")
        assert r.status_code == 200
        assert r.json()["data"]["counts"] == {"create": 2, "update": 0, "retire": 0}

    def test_list_includes_company_name(self, client):
        from qs_kernel.infrastructure.persistence.database.engine import get_engine

        with get_engine().begin() as conn:
            conn.execute(text("DELETE FROM quant.stocks WHERE symbol='999999'"))
            conn.execute(
                text(
                    "INSERT INTO quant.stocks (symbol, name, market) "
                    "VALUES ('999999', '测试公司', 'A')"
                )
            )
        try:
            self._create(client)
            plans = client.get(f"/api/plans?account={ACC}").json()["data"]["plans"]
            target = plans[0]["spec"]["targets"][0]
            assert target["name"] == "测试公司", target
            detail = client.get(f'/api/plans/{plans[0]["id"]}').json()["data"]["plan"]
            assert detail["spec"]["targets"][0]["name"] == "测试公司"
        finally:
            with get_engine().begin() as conn:
                conn.execute(text("DELETE FROM quant.stocks WHERE symbol='999999'"))

    def test_get_missing_404(self, client):
        assert client.get("/api/plans/99999999").status_code == 404

    def test_today_route_wires_env_and_todo_sources(self, client, monkeypatch):
        pid = self._create(client)
        assert (
            client.post(f"/api/plans/{pid}/activate", json={"expected_version": 1}).status_code
            == 200
        )
        monkeypatch.setattr(
            "adapters.inbound.fastapi_app.routes.plan_async._env_gate_provider",
            lambda: {"status": "blocked", "reason": "指数 -2% 本轮只记录不动作"},
        )
        monkeypatch.setattr(
            "adapters.inbound.fastapi_app.routes.plan_async._pending_todo_count", lambda account: 3
        )
        r = client.get(f"/api/plans/today?account={ACC}")
        assert r.status_code == 200
        item = r.json()["data"]["plans"][0]
        assert item["env_gate"]["status"] == "blocked"
        assert item["pending_todos"] == 3

    def test_today_route_empty_and_fast(self, client):
        import time

        t0 = time.perf_counter()
        r = client.get("/api/plans/today?account=test-plan-t6-empty")
        elapsed = time.perf_counter() - t0
        assert r.status_code == 200
        assert r.json()["data"]["empty"] is True
        assert elapsed < 0.5, "today 空账户响应耗时 %.3fs 超 500ms" % elapsed
        assert client.get("/api/plans/today").status_code == 400
