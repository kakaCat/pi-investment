"""PlanCompiler 幂等编译单元测试（t5 验收：假件端口，不连库）"""

import copy
from types import SimpleNamespace

import pytest

from qs_plan.application.plan_compiler import PlanCompiler


def _spec(stop=8.0, batches=None):
    batches = (
        batches
        if batches is not None
        else [
            {"at_pct": 8, "sell_ratio": 0.33},
            {"at_pct": 15, "sell_ratio": 1.0},
        ]
    )
    return {
        "targets": [{"symbol": "600519.SH", "budget_pct": 5, "role": "core"}],
        "entry": {
            "conditions": [{"type": "price_break", "params": {"price": 1800}}],
            "combinator": "all_of",
        },
        "exit": {"stop_loss": {"type": "pct", "value": stop}},
        "monitoring": {"news": True},
        "schedule": {"interval_sec": 30},
    } | (
        {"exit": {"stop_loss": {"type": "pct", "value": stop}, "reduce_plan": batches}}
        if batches is not None
        else {}
    )


def _plan(spec=None):
    return SimpleNamespace(id=42, account="agent_brain", status="draft", spec=spec or _spec())


class FakePort:
    def __init__(self):
        self.rules = {}
        self.mappings = []
        self.audits = []
        self._next = 1000
        self.fail_on_create = None
        self.fail_on_update = None
        self.fail_on_retire = None
        self.update_calls = 0
        self.retire_calls = 0

    def list_managed(self, plan_id):
        return [dict(r, rule_id=rid) for rid, r in self.rules.items()]

    def create_rule(self, payload):
        self._next += 1
        if self.fail_on_create is not None and len(self.rules) + 1 == self.fail_on_create:
            raise RuntimeError("db down")
        self.rules[self._next] = dict(payload, enabled=True)
        return self._next

    def update_rule(self, rule_id, payload):
        self.update_calls += 1
        if self.fail_on_update is not None and self.update_calls == self.fail_on_update:
            raise RuntimeError("update down")
        self.rules[rule_id].update(payload)

    def retire_rule(self, rule_id, reason):
        self.retire_calls += 1
        if self.fail_on_retire is not None and self.retire_calls == self.fail_on_retire:
            raise RuntimeError("retire down")
        if rule_id in self.rules:
            self.rules[rule_id]["enabled"] = False

    def record_audit(self, plan_id, rule_id, change_kind, before, after, reason):
        self.audits.append((rule_id, change_kind, before, after, reason))

    def link_rule(self, plan_id, rule_id, role, symbol, batch=0):
        self.mappings.append((plan_id, rule_id, role, symbol, batch))


def _compiler(port):
    return PlanCompiler(port)


class TestCompile:
    def test_first_compile_creates_entry_stop_and_batches(self):
        port = FakePort()
        out = _compiler(port).apply(_plan())
        assert out == {"created": 4, "updated": 0, "retired": 0}
        roles = sorted(r["role"] for r in port.rules.values())
        assert roles == ["entry", "reduce", "reduce", "stop_loss"]
        assert all(p == 42 for p, *_ in port.mappings)
        assert len(port.audits) == 4

    def test_recompile_same_spec_is_noop(self):
        port = FakePort()
        c = _compiler(port)
        c.apply(_plan())
        out = c.apply(_plan())
        assert out == {"created": 0, "updated": 0, "retired": 0}

    def test_stop_change_updates_single_rule(self):
        port = FakePort()
        c = _compiler(port)
        c.apply(_plan())
        out = c.apply(_plan(_spec(stop=10.0)))
        assert out["updated"] == 1 and out["created"] == 0
        stop = [r for r in port.rules.values() if r["role"] == "stop_loss"][0]
        assert stop["conditions"][0]["params"]["pct"] == 10.0
        assert any(
            a[2] and a[2]["conditions"][0]["params"]["pct"] == 8.0 for a in port.audits if a[2]
        )

    def test_removed_batch_retires_rule(self):
        port = FakePort()
        c = _compiler(port)
        c.apply(_plan())
        out = c.apply(_plan(_spec(batches=[{"at_pct": 8, "sell_ratio": 0.5}])))
        assert out["retired"] == 1
        enabled = [r for r in port.rules.values() if r.get("enabled")]
        assert len(enabled) == 3

    def test_position_state_from_holdings_truth(self):
        port = FakePort()
        _compiler(port).apply(_plan(), position_state_for=lambda s: "holding")
        stop = [r for r in port.rules.values() if r["role"] == "stop_loss"][0]
        entry = [r for r in port.rules.values() if r["role"] == "entry"][0]
        assert stop["position_state"] == "holding"
        assert entry["position_state"] == "none"

    def test_pending_entry_compiles_stop_loss_only(self):
        port = FakePort()
        spec = _spec()
        spec["entry"] = {"conditions": [], "combinator": "all_of", "pending": True}
        out = _compiler(port).apply(_plan(spec))
        assert out["created"] == 3  # 止损 + 两批减仓，无入场规则
        roles = sorted(r["role"] for r in port.rules.values())
        assert "entry" not in roles
        assert roles.count("reduce") == 2 and roles.count("stop_loss") == 1

    def test_failure_compensates_created_rules(self):
        port = FakePort()
        port.fail_on_create = 3  # 第 3 条创建时炸
        with pytest.raises(RuntimeError):
            _compiler(port).apply(_plan())
        # 已创建的两条被补偿退役 → 无「半编译存活」规则
        assert [r for r in port.rules.values() if r.get("enabled")] == []

    def test_budget_and_reduce_ratio_changes_update_action_params(self):
        port = FakePort()
        c = _compiler(port)
        c.apply(_plan())
        changed = copy.deepcopy(_spec())
        changed["targets"][0]["budget_pct"] = 8
        changed["exit"]["reduce_plan"][0]["sell_ratio"] = 0.5
        out = c.apply(_plan(changed))
        assert out == {"created": 0, "updated": 2, "retired": 0}
        entry = [r for r in port.rules.values() if r["role"] == "entry"][0]
        first_reduce = [
            r for r in port.rules.values() if r["role"] == "reduce" and r.get("batch") == 0
        ][0]
        assert entry["action_params"]["position_pct"] == 8
        assert first_reduce["action_params"]["position_pct"] == 50
        assert c.apply(_plan(changed)) == {"created": 0, "updated": 0, "retired": 0}

    def test_failure_compensates_updated_rule(self):
        port = FakePort()
        c = _compiler(port)
        c.apply(_plan())
        port.fail_on_update = 1
        with pytest.raises(RuntimeError):
            c.apply(_plan(_spec(stop=10.0)))
        stop = [r for r in port.rules.values() if r["role"] == "stop_loss"][0]
        assert stop["conditions"][0]["params"]["pct"] == 8.0
        assert stop["enabled"] is True

    def test_failure_compensates_retired_rule(self):
        batches = [
            {"at_pct": 8, "sell_ratio": 0.33},
            {"at_pct": 15, "sell_ratio": 0.34},
            {"at_pct": 20, "sell_ratio": 0.33},
        ]
        port = FakePort()
        c = _compiler(port)
        c.apply(_plan(_spec(batches=batches)))
        port.fail_on_retire = 2  # 第一个退役成功、第二个失败 → 第一个要恢复
        with pytest.raises(RuntimeError):
            c.apply(_plan(_spec(batches=batches[:1])))
        assert all(r["enabled"] for r in port.rules.values())
