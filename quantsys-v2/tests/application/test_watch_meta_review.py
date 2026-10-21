"""元触发复核单测（REQ-f08def P7，RFC 014 v3 §13，w-c8cae280）

守住用户明确要求的那条：「盯盘总触发或者超时也需要 agent 介入处理，不能一直一个规则盯盘」。
"""
from datetime import datetime, timedelta
from types import SimpleNamespace

from qs_watch.domain.watch.services.disposition import (
    DISPOSITION_META_REVIEW, InterventionConfig,
)
from qs_watch.application.services.watch_engine.meta_review_service import WatchMetaReviewService

NOW = datetime(2026, 9, 11, 16, 0, 0)


class FakeRuleRepo:
    def __init__(self, rules):
        self._rules = rules

    def list_enabled(self):
        return self._rules


class FakeTriggerRepo:
    def __init__(self):
        self.records = []

    def record(self, **kw):
        self.records.append(kw)
        return SimpleNamespace(id=len(self.records))


def _rule(rid=1, symbol="600150", intent="entry", created_days_ago=2,
          expires_in_days=None, last_reviewed=None, created_by=None, created_from=None):
    return SimpleNamespace(
        id=rid, symbol=symbol, intent=intent,
        created_at=NOW - timedelta(days=created_days_ago),
        expires_at=(NOW + timedelta(days=expires_in_days)) if expires_in_days is not None else None,
        last_reviewed_at=last_reviewed,
        created_by=created_by, created_from=created_from,
    )


def _svc(rules, stats):
    tr = FakeTriggerRepo()
    svc = WatchMetaReviewService(FakeRuleRepo(rules), tr, InterventionConfig())
    svc._trigger_stats = lambda: stats
    return svc, tr


def test_burst_no_longer_raises_meta_review():
    """REQ-261016155500-4f2a wt:engine:3：burst 复核下线（与自愈双头治理）——
    单日高频不再产生 meta_review 项（归 noise_self_heal：抑噪 + 修规则待办）。"""
    svc, tr = _svc([_rule()], {1: {"today": 9, "last_at": NOW}})
    out = svc.scan(now=NOW)
    assert out["raised"] == 0
    assert tr.records == []


def test_idle_triggers_review_when_rule_never_fires():
    """一直不响：距上次触发 ≥14 天 → 复核（价值还在吗）"""
    svc, tr = _svc([_rule()], {1: {"today": 0, "last_at": NOW - timedelta(days=20)}})
    out = svc.scan(now=NOW)
    assert out["raised"] == 1
    assert "静默超时" in tr.records[0]["disposition_reason"]


def test_expiry_near_triggers_review():
    """快到期 → 续期还是收摊"""
    svc, tr = _svc([_rule(expires_in_days=1)], {1: {"today": 0, "last_at": NOW}})
    out = svc.scan(now=NOW)
    assert out["raised"] == 1
    assert "规则到期" in tr.records[0]["disposition_reason"]


def test_healthy_rule_not_reviewed():
    """健康规则（今天刚复核过）不产生复核项——不能把元触发变成新噪声"""
    svc, tr = _svc([_rule(last_reviewed=NOW)], {1: {"today": 9, "last_at": NOW}})
    out = svc.scan(now=NOW)
    assert out["raised"] == 0
    assert out["skipped_already_reviewed"] == 1
    assert tr.records == []


def test_force_bypasses_daily_guard():
    # burst 下线后用 expiry 类验证 force 绕过「当日已复核」守卫
    svc, tr = _svc([_rule(last_reviewed=NOW, expires_in_days=1)],
                   {1: {"today": 9, "last_at": NOW}})
    out = svc.scan(now=NOW, force=True)
    assert out["raised"] == 1


def test_meta_trigger_param_shape():
    svc, tr = _svc([_rule(expires_in_days=1)], {1: {"today": 6, "last_at": NOW}})
    svc.scan(now=NOW)
    rec = tr.records[0]
    assert rec["condition"]["type"] == "meta_review"
    # burst 下线后 kinds 为 idle/stage/expiry（REQ-261016155500-4f2a wt:engine:3）
    # + unactivated（2026-10-19「规则激活」环节）
    assert rec["condition"]["params"]["kinds"] == ["idle", "stage", "expiry", "unactivated"]
    assert rec["trigger_price"] is None
    assert rec["notified"] is False
    assert rec["disposition_by"] == "system"


# ── unactivated：opportunity_scan 自动建规则的「激活」环节（2026-10-19）────────

def test_unactivated_opportunity_rule_triggers_review():
    """created_by='opportunity_scan' + 无 intent + 创建超 1 天 → 复核「补 intent+account 激活，或退役」"""
    svc, tr = _svc([_rule(intent=None, created_days_ago=3, created_by="opportunity_scan")],
                   {1: {"today": 0, "last_at": NOW}})
    out = svc.scan(now=NOW)
    assert out["raised"] == 1
    reason = tr.records[0]["disposition_reason"]
    assert "规则未激活" in reason
    assert "补 intent+account 激活，或退役" in reason


def test_unactivated_via_created_from_marker():
    """created_from='opportunity_scan' 同样命中（两个标记字段任一即可）"""
    svc, tr = _svc([_rule(intent="", created_days_ago=5, created_from="opportunity_scan")],
                   {1: {"today": 0, "last_at": NOW}})
    out = svc.scan(now=NOW)
    assert out["raised"] == 1
    assert "规则未激活" in tr.records[0]["disposition_reason"]


def test_activated_opportunity_rule_not_reviewed_for_unactivated():
    """已补 intent 的 opportunity_scan 规则 → 不因 unactivated 复核（激活环节已走完）"""
    svc, tr = _svc([_rule(intent="entry", created_days_ago=3,
                          created_by="opportunity_scan")],
                   {1: {"today": 0, "last_at": NOW}})
    out = svc.scan(now=NOW)
    assert out["raised"] == 0
    assert tr.records == []


def test_fresh_opportunity_rule_within_grace_not_reviewed():
    """创建未满 N 天（默认 1 天）→ 给激活留出宽限，不复核"""
    svc, tr = _svc([_rule(intent=None, created_days_ago=0, created_by="opportunity_scan")],
                   {1: {"today": 0, "last_at": NOW}})
    out = svc.scan(now=NOW)
    assert out["raised"] == 0
    assert tr.records == []


def test_unactivated_grace_days_configurable():
    """N 进 InterventionConfig（meta_unactivated_days）：放宽到 7 天后 3 天龄不再命中"""
    tr = FakeTriggerRepo()
    cfg = InterventionConfig(meta_unactivated_days=7)
    svc = WatchMetaReviewService(FakeRuleRepo(
        [_rule(intent=None, created_days_ago=3, created_by="opportunity_scan")]), tr, cfg)
    svc._trigger_stats = lambda: {1: {"today": 0, "last_at": NOW}}
    out = svc.scan(now=NOW)
    assert out["raised"] == 0
    assert tr.records == []


def test_manually_created_rule_without_intent_not_reviewed_for_unactivated():
    """手工建的规则（created_by 非 opportunity_scan）即使无 intent 也不走激活复核"""
    svc, tr = _svc([_rule(intent=None, created_days_ago=30, created_by="user")],
                   {1: {"today": 0, "last_at": NOW}})
    out = svc.scan(now=NOW)
    assert tr.records == [] or all(
        "规则未激活" not in r["disposition_reason"] for r in tr.records)
