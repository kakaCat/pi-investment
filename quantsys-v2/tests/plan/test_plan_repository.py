"""TradingPlanRepository 集成测试（quant_test 库，t2 验收）

覆盖：五表增删查改、版本 CAS、编译映射幂等、反思同周期 version+1、缺表降级。
清理：teardown 按 account 前缀硬删（FK CASCADE 连带版本/事件/映射/反思）。
"""

from datetime import datetime, timezone

import pytest
from sqlalchemy import text

from adapters.outbound.repositories.trading_plan_repository import (
    TradingPlanRepository,
    TradingPlanSchemaMissing,
)
from infrastructure.persistence.orm import close_session

ACC = "test-plan-t2"


def _spec(stop: float = 8.0):
    return {
        "targets": [{"symbol": "600519.SH", "budget_pct": 5, "role": "core"}],
        "entry": {
            "conditions": [{"type": "price_break", "params": {"price": 10}}],
            "combinator": "all_of",
        },
        "exit": {"stop_loss": {"type": "pct", "value": stop}},
        "monitoring": {"news": True},
        "schedule": {"interval_sec": 30},
    }


@pytest.mark.integration
class TestTradingPlanRepository:
    def setup_method(self):
        self.repo = TradingPlanRepository()
        self._ids = []

    def teardown_method(self):
        try:
            for pid in self._ids:
                self.repo.session.execute(
                    text("DELETE FROM quant.trading_plans WHERE id = :id"), {"id": pid}
                )
            self.repo.session.commit()
        finally:
            close_session()

    def _create(self, name="计划", horizon="day"):
        p = self.repo.create_plan(
            account=ACC, name=name, horizon=horizon, spec=_spec(), created_by="test"
        )
        self._ids.append(p.id)
        return p

    def test_create_and_get(self):
        p = self._create()
        assert p.status == "draft" and p.version == 1
        got = self.repo.get_plan(p.id)
        assert got is not None and got.spec["exit"]["stop_loss"]["value"] == 8.0
        versions = self.repo.list_versions(p.id)
        assert len(versions) == 1 and versions[0].version == 1
        events = self.repo.list_events(p.id)
        assert any(e.kind == "status_change" and e.to_status == "draft" for e in events)

    def test_list_plans_filters(self):
        p1 = self._create("a")
        p2 = self._create("b")
        rows = self.repo.list_plans(ACC)
        assert {r.id for r in rows} >= {p1.id, p2.id}
        assert all(r.account == ACC for r in rows)
        assert [r.id for r in self.repo.list_plans(ACC, statuses=["active"])] == []

    def test_draft_spec_cas(self):
        # CAS 口径：暂存本身不 bump version（版本只在 apply 时 +1），
        # 但 apply 之后旧版本的暂存必须被拒（防「基于旧版本改的东西盖到新版本上」）。
        p = self._create()
        assert self.repo.update_draft_spec(p.id, {"x": 1}, expected_version=1) is True
        assert self.repo.apply_version(p.id, expected_version=1, spec=_spec(9.0)) == 2
        assert self.repo.update_draft_spec(p.id, {"x": 2}, expected_version=1) is False
        assert self.repo.update_draft_spec(p.id, {"x": 3}, expected_version=2) is True

    def test_apply_version_cas_and_rows(self):
        p = self._create()
        new_v = self.repo.apply_version(
            p.id,
            expected_version=1,
            spec=_spec(10.0),
            baseline={"stop_false_rate": 0.7},
            change_reason="止损太紧",
            hypothesis={"change": "stop 8→10"},
            created_by="agent",
            decision_audit_id="d-1",
        )
        assert new_v == 2
        got = self.repo.get_plan(p.id)
        assert got.version == 2 and got.spec["exit"]["stop_loss"]["value"] == 10.0
        assert got.draft_spec is None
        versions = self.repo.list_versions(p.id)
        assert [v.version for v in versions] == [2, 1]
        assert versions[0].baseline["stop_false_rate"] == 0.7
        # 旧版本重放 → 冲突，不改任何行
        assert self.repo.apply_version(p.id, expected_version=1, spec=_spec(11.0)) is None
        assert self.repo.get_plan(p.id).version == 2

    def test_transition_status_and_event(self):
        p = self._create()
        assert self.repo.transition_status(p.id, "active", actor="agent", reason="激活") is True
        assert self.repo.get_plan(p.id).status == "active"
        ev = self.repo.list_events(p.id)[0]
        assert ev.kind == "status_change" and ev.from_status == "draft" and ev.to_status == "active"
        # CAS 不匹配 → 拒绝
        assert (
            self.repo.transition_status(p.id, "paused", actor="agent", expected_version=99) is False
        )

    def test_rule_mapping_idempotent(self):
        p = self._create()
        # FK rule_id → watch_rules 且 rule_id 全局唯一：每个映射需要独立规则
        ids = []
        for _ in range(4):
            self.repo.session.execute(
                text(
                    "INSERT INTO quant.watch_rules (symbol, conditions, created_by, enabled) "
                    "VALUES ('600519.SH', CAST('[{\"type\": \"price_break\"}]' AS jsonb), "
                    "'test-plan-t2', true)"
                )
            )
            self.repo.session.commit()
            ids.append(
                self.repo.session.execute(
                    text(
                        "SELECT id FROM quant.watch_rules WHERE created_by='test-plan-t2' "
                        "ORDER BY id DESC LIMIT 1"
                    )
                ).scalar()
            )
        r1, r2, r3 = ids[0], ids[1], ids[2]
        try:
            self.repo.record_rule_mapping(p.id, r1, "entry", "600519.SH")
            self.repo.record_rule_mapping(p.id, r1, "entry", "600519.SH")  # 同键幂等
            self.repo.record_rule_mapping(p.id, 999999, "entry", "600519.SH")  # FK 会拒绝
        except Exception:
            pass
        # 同标的同 role 但不同批次 → 各自一行（PK 含 batch）
        self.repo.record_rule_mapping(p.id, r2, "reduce", "600519.SH", batch=0)
        self.repo.record_rule_mapping(p.id, r3, "reduce", "600519.SH", batch=1)
        rows = self.repo.list_rule_mappings(p.id)
        assert len(rows) == 3
        assert self.repo.delete_rule_mapping(p.id, "reduce", "600519.SH", batch=0) == 1
        assert len(self.repo.list_rule_mappings(p.id)) == 2
        self.repo.session.execute(
            text("DELETE FROM quant.watch_rules WHERE created_by=:c"), {"c": "test-plan-t2"}
        )
        self.repo.session.commit()

    def test_reflection_same_period_bumps_version(self):
        p = self._create()
        base = dict(
            kind="daily",
            period="2026-10-21",
            evidence_pack={"modifications": [], "missed": [], "wins": [], "losses": []},
            answers={"q1": "ok", "q2": "ok", "q3": "ok", "q4": "ok", "q5": "ok"},
            verdict="keep",
            reasoning="维持",
        )
        rid1 = self.repo.record_reflection(p.id, **base)
        rid2 = self.repo.record_reflection(p.id, **base)
        assert rid1 != rid2
        rows = self.repo.list_reflections(p.id)
        assert len(rows) == 2
        assert sorted(r.version for r in rows) == [1, 2]
        latest = self.repo.get_reflection(rid2)
        assert latest is not None and latest.version == 2
        assert self.repo.get_reflection(99999999) is None

    def test_overdue_and_mark_reflected(self):
        p = self._create()
        assert self.repo.bump_overdue(p.id) == 1
        assert self.repo.bump_overdue(p.id) == 2
        self.repo.mark_reflected(p.id, datetime.now(timezone.utc))
        assert self.repo.get_plan(p.id).reflection_overdue_count == 0

    def test_missing_schema_degrades_reads_and_rejects_writes(self, monkeypatch):
        monkeypatch.setattr(self.repo, "_tables_ready", lambda: False)
        assert self.repo.get_plan(1) is None
        assert self.repo.list_plans(ACC) == []
        assert self.repo.list_events(1) == []
        with pytest.raises(TradingPlanSchemaMissing):
            self.repo.create_plan(
                account=ACC, name="x", horizon="day", spec=_spec(), created_by="test"
            )
