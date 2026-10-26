"""减仓批次收敛测试（REQ-261022022657-857f · t2/t3 · FR-2）

t2：match_reduce_batches 纯函数（累计比例口径）；
t3：PlanService.on_fill(sold_ratio) 退役对应批次 + 事件留痕 + 幂等。
"""

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from qs_plan.application.plan_service import PlanService
from qs_plan.domain.plan.batch_matcher import match_reduce_batches

NOW = datetime(2026, 10, 22, 6, 0, tzinfo=timezone.utc)

BATCHES = [
    {"at_pct": 8, "sell_ratio": 0.33},
    {"at_pct": 15, "sell_ratio": 0.67},
]


def _spec(batches=None):
    return {
        "targets": [{"symbol": "600519.SH", "budget_pct": 5, "role": "core"}],
        "entry": {
            "conditions": [{"type": "price_break", "params": {"price": 10}}],
            "combinator": "all_of",
        },
        "exit": {"reduce_plan": batches if batches is not None else BATCHES},
        "monitoring": {"news": True},
        "schedule": {"interval_sec": 30},
    }


class FakeRepo:
    def __init__(self, plan):
        self.plan = plan
        self.events = []
        self.transitions = []

    def get_plan(self, plan_id):
        return self.plan if plan_id == self.plan.id else None

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
        self.transitions.append((self.plan.status, to_status))
        self.plan.status = to_status
        for k, v in (extra_fields or {}).items():
            setattr(self.plan, k, v)
        return True

    def record_event(
        self,
        plan_id,
        kind,
        actor,
        reason=None,
        detail=None,
        from_status=None,
        to_status=None,
        decision_audit_id=None,
    ):
        self.events.append(
            SimpleNamespace(kind=kind, detail=detail or {}, reason=reason, actor=actor)
        )

    def list_events(self, plan_id, limit=50):
        return list(reversed(self.events))[:limit]


class FakeRulePort:
    def __init__(self, managed):
        self.managed = managed
        self.retired = []

    def list_managed(self, plan_id):
        return list(self.managed)

    def retire_rule(self, rule_id, reason):
        self.retired.append((rule_id, reason))


def _plan(status="holding", spec=None):
    return SimpleNamespace(
        id=1,
        account="agent_brain",
        status=status,
        spec=spec or _spec(),
        draft_spec=None,
        version=1,
        activated_at=NOW,
        closed_at=None,
        reflection_overdue_count=0,
    )


def _service(repo, rule_port=None):
    return PlanService(repo, now_fn=lambda: NOW, rule_port=rule_port)


class TestMatchReduceBatches:
    def test_zero_sold(self):
        assert match_reduce_batches(BATCHES, 0) == []

    def test_first_batch_only(self):
        assert match_reduce_batches(BATCHES, 0.33) == [0]

    def test_partial_second_not_retired(self):
        # 卖出 80%：第一批完成、第二批只完成 47%，不退役（按批比例判定）
        assert match_reduce_batches(BATCHES, 0.8) == [0]

    def test_full(self):
        assert match_reduce_batches(BATCHES, 1.0) == [0, 1]

    def test_out_of_range_raises(self):
        with pytest.raises(ValueError):
            match_reduce_batches(BATCHES, -0.1)
        with pytest.raises(ValueError):
            match_reduce_batches(BATCHES, 1.1)

    def test_empty_batches(self):
        assert match_reduce_batches([], 1.0) == []


class TestOnFillBatchConvergence:
    def test_partial_fill_retires_first_batch(self):
        plan = _plan()
        repo = FakeRepo(plan)
        port = FakeRulePort(
            [
                {"role": "reduce", "batch": 0, "rule_id": 101},
                {"role": "reduce", "batch": 1, "rule_id": 102},
                {"role": "stop_loss", "batch": 0, "rule_id": 103},
            ]
        )
        status = _service(repo, port).on_fill(
            1, side="sell", qty=33, remaining_qty=67, trade_id="t-a", sold_ratio=0.33
        )
        assert status == "holding" and plan.status == "holding"
        assert port.retired and port.retired[0][0] == 101
        fills = [e for e in repo.events if e.kind == "fill"]
        assert len(fills) == 1 and fills[0].detail["batch"] == 0
        assert fills[0].detail["retired"] is True

    def test_full_fill_retires_all_and_closes(self):
        plan = _plan()
        repo = FakeRepo(plan)
        port = FakeRulePort(
            [
                {"role": "reduce", "batch": 0, "rule_id": 101},
                {"role": "reduce", "batch": 1, "rule_id": 102},
            ]
        )
        status = _service(repo, port).on_fill(
            1, side="sell", qty=100, remaining_qty=0, trade_id="t-b", sold_ratio=1.0
        )
        assert status == "closed" and plan.status == "closed"
        assert sorted(r[0] for r in port.retired) == [101, 102]
        assert len([e for e in repo.events if e.kind == "fill"]) == 2

    def test_replay_same_trade_is_idempotent(self):
        plan = _plan()
        repo = FakeRepo(plan)
        port = FakeRulePort([{"role": "reduce", "batch": 0, "rule_id": 101}])
        svc = _service(repo, port)
        svc.on_fill(1, side="sell", qty=33, remaining_qty=67, trade_id="t-a", sold_ratio=0.33)
        svc.on_fill(1, side="sell", qty=33, remaining_qty=67, trade_id="t-a", sold_ratio=0.33)
        fills = [e for e in repo.events if e.kind == "fill"]
        assert len(fills) == 1 and len(port.retired) == 1

    def test_cumulative_ratio_does_not_retire_same_batch_twice(self):
        class StatefulRulePort(FakeRulePort):
            def retire_rule(self, rule_id, reason):
                super().retire_rule(rule_id, reason)
                for row in self.managed:
                    if row.get("rule_id") == rule_id:
                        row["enabled"] = False

        batches = [{"at_pct": 8, "sell_ratio": 0.25}, {"at_pct": 15, "sell_ratio": 0.25}]
        plan = _plan(spec=_spec(batches=batches))
        repo = FakeRepo(plan)
        port = StatefulRulePort(
            [
                {"role": "reduce", "batch": 0, "rule_id": 101, "enabled": True},
                {"role": "reduce", "batch": 1, "rule_id": 102, "enabled": True},
            ]
        )
        svc = _service(repo, port)
        svc.on_fill(1, side="sell", qty=25, remaining_qty=75, trade_id="t-a", sold_ratio=0.25)
        svc.on_fill(1, side="sell", qty=25, remaining_qty=50, trade_id="t-b", sold_ratio=0.5)
        assert sorted(rule_id for rule_id, _ in port.retired) == [101, 102]
        fills = [e for e in repo.events if e.kind == "fill"]
        assert len(fills) == 3  # 第一批一次；第二批累计时第一批只留痕，不重复退役
        assert fills[1].detail["already_retired"] is True
        assert fills[1].detail["retired"] is False
        assert fills[2].detail["already_retired"] is False
        assert fills[2].detail["retired"] is True

    def test_no_matching_rule_writes_degraded_event(self):
        plan = _plan()
        repo = FakeRepo(plan)
        port = FakeRulePort([])  # 规则已不在（例如手工删过）
        _service(repo, port).on_fill(
            1, side="sell", qty=33, remaining_qty=67, trade_id="t-c", sold_ratio=0.33
        )
        fills = [e for e in repo.events if e.kind == "fill"]
        assert fills and fills[0].detail["degraded"] is True

    def test_buy_does_not_touch_batches(self):
        plan = _plan(status="active")
        repo = FakeRepo(plan)
        port = FakeRulePort([{"role": "reduce", "batch": 0, "rule_id": 101}])
        status = _service(repo, port).on_fill(
            1, side="buy", qty=100, remaining_qty=100, trade_id="t-d", sold_ratio=0.0
        )
        assert status == "holding" and not port.retired
