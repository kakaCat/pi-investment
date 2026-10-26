"""成交回执闭环测试（t8）：FillEvent 归因 + 计划推进端口 + FillSync 钩子"""

from datetime import datetime
from types import SimpleNamespace

from qs_trading.application.ports.fill_listener import FillEvent
from qs_watch.application.services.watch_engine.fill_sync_service import FillSyncService

from adapters.outbound.repositories.plan_progress_port import PlanProgressPort


def _plan(status="active"):
    return SimpleNamespace(
        id=7,
        account="agent_brain",
        status=status,
        spec={},
        version=1,
        stats={},
        draft_spec=None,
        activated_at=None,
    )


class FakeRepo:
    def __init__(self, plan):
        self.plan = plan
        self.transitions = []

    def get_plan(self, pid):
        return self.plan if pid == self.plan.id else None

    def transition_status(
        self,
        plan_id,
        to_status,
        actor,
        reason=None,
        decision_audit_id=None,
        expected_version=None,
        extra_fields=None,
    ):
        self.transitions.append(to_status)
        self.plan.status = to_status
        return True

    def list_versions(self, plan_id, limit=50):
        return []


class FakeRuleRepo:
    def list_rules(self, **kw):
        return []

    def set_position_state(self, *a, **kw):
        return True


class FakePositionRepo:
    def get_position(self, account, symbol):
        return None


class TestFillEventAttribution:
    def test_plan_fields_roundtrip(self):
        ev = FillEvent(
            account_name="a",
            symbol="600519.SH",
            action="sell",
            shares=100,
            price=10.0,
            trade_id=1,
            plan_id=7,
            plan_version=2,
        )
        d = ev.to_dict()
        assert d["plan_id"] == 7 and d["plan_version"] == 2

    def test_plan_fields_default_none(self):
        ev = FillEvent(account_name="a", symbol="600519.SH", action="buy", shares=100, price=10.0)
        assert ev.to_dict()["plan_id"] is None


class TestPlanProgressPort:
    def test_buy_advances_to_holding(self):
        repo = FakeRepo(_plan("active"))
        port = PlanProgressPort(repo=repo, remaining_provider=lambda a, s: 100)
        out = port(
            {
                "plan_id": 7,
                "account": "agent_brain",
                "symbol": "600519.SH",
                "action": "buy",
                "shares": 100,
                "trade_id": 11,
            }
        )
        assert out["status"] == "ok" and out["plan_status"] == "holding"
        assert repo.plan.status == "holding"

    def test_sell_full_closes(self):
        repo = FakeRepo(_plan("holding"))
        port = PlanProgressPort(repo=repo, remaining_provider=lambda a, s: 0)
        out = port(
            {
                "plan_id": 7,
                "account": "agent_brain",
                "symbol": "600519.SH",
                "action": "sell",
                "shares": 100,
                "trade_id": 12,
            }
        )
        assert out["plan_status"] == "closed"
        assert repo.plan.status == "closed"

    def test_without_plan_id_skips(self):
        port = PlanProgressPort(repo=FakeRepo(_plan()), remaining_provider=lambda a, s: 0)
        assert port({"action": "sell"}) == {"status": "skipped", "reason": "no_plan_id"}

    def test_position_read_failure_degrades(self):
        port = PlanProgressPort(repo=FakeRepo(_plan()), remaining_provider=lambda a, s: None)
        out = port({"plan_id": 7, "action": "sell"})
        assert out["status"] == "degraded"

    def test_cumulative_sold_ratio_uses_plan_trade_total(self):
        port = PlanProgressPort(
            repo=FakeRepo(_plan("holding")),
            remaining_provider=lambda a, s: 40,
            sold_qty_provider=lambda pid, a, s: 60,
        )
        out = port(
            {
                "plan_id": 7,
                "account": "agent_brain",
                "symbol": "600519.SH",
                "action": "sell",
                "shares": 30,
                "trade_id": 13,
            }
        )
        assert out["status"] == "ok"
        assert out["sold_qty"] == 60
        assert out["sold_ratio"] == 0.6

    def test_full_close_with_cumulative_sold_qty(self):
        port = PlanProgressPort(
            repo=FakeRepo(_plan("holding")),
            remaining_provider=lambda a, s: 0,
            sold_qty_provider=lambda pid, a, s: 100,
        )
        out = port(
            {
                "plan_id": 7,
                "account": "agent_brain",
                "symbol": "600519.SH",
                "action": "sell",
                "shares": 100,
                "trade_id": 14,
            }
        )
        assert out["plan_status"] == "closed"
        assert out["sold_ratio"] == 1.0

    def test_sold_qty_read_failure_degrades(self):
        port = PlanProgressPort(
            repo=FakeRepo(_plan("holding")),
            remaining_provider=lambda a, s: 40,
            sold_qty_provider=lambda pid, a, s: None,
        )
        out = port(
            {
                "plan_id": 7,
                "account": "agent_brain",
                "symbol": "600519.SH",
                "action": "sell",
                "shares": 30,
                "trade_id": 15,
            }
        )
        assert out == {"status": "degraded", "reason": "sold_qty_read_failed"}


class TestFillSyncHook:
    def _service(self, plan_progress):
        return FillSyncService(
            rule_repo=FakeRuleRepo(),
            position_repo=FakePositionRepo(),
            plan_progress=plan_progress,
            now_fn=lambda: datetime(2026, 10, 22),
        )

    def test_with_plan_id_calls_progress(self):
        calls = []
        svc = self._service(lambda fill: calls.append(fill) or {"status": "ok"})
        out = svc.on_fill(
            {
                "account_name": "agent_brain",
                "symbol": "600519.SH",
                "action": "sell",
                "shares": 100,
                "price": 10.0,
                "trade_id": 1,
                "plan_id": 7,
            }
        )
        assert calls and calls[0]["plan_id"] == 7
        assert out.get("plan_progress", {}).get("status") == "ok"

    def test_without_plan_id_does_not_call(self):
        calls = []
        svc = self._service(lambda fill: calls.append(fill))
        svc.on_fill(
            {
                "account_name": "agent_brain",
                "symbol": "600519.SH",
                "action": "buy",
                "shares": 100,
                "price": 10.0,
                "trade_id": 2,
            }
        )
        assert calls == []

    def test_progress_exception_does_not_break_convergence(self):
        def boom(fill):
            raise RuntimeError("plan layer down")

        svc = self._service(boom)
        out = svc.on_fill(
            {
                "account_name": "agent_brain",
                "symbol": "600519.SH",
                "action": "sell",
                "shares": 100,
                "price": 10.0,
                "trade_id": 3,
                "plan_id": 7,
            }
        )
        # 主链收敛状态可以是 converged_no_todo 等，关键是错误被记录且未上抛
        assert any("plan_progress" in e for e in out["errors"])
