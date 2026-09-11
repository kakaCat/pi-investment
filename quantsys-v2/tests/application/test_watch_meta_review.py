"""元触发复核单测（REQ-f08def P7，RFC 014 v3 §13，w-c8cae280）

守住用户明确要求的那条：「盯盘总触发或者超时也需要 agent 介入处理，不能一直一个规则盯盘」。
"""
from datetime import datetime, timedelta
from types import SimpleNamespace

from application.services.watch_engine.disposition import (
    DISPOSITION_META_REVIEW, InterventionConfig,
)
from application.services.watch_engine.meta_review_service import WatchMetaReviewService

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
          expires_in_days=None, last_reviewed=None):
    return SimpleNamespace(
        id=rid, symbol=symbol, intent=intent,
        created_at=NOW - timedelta(days=created_days_ago),
        expires_at=(NOW + timedelta(days=expires_in_days)) if expires_in_days is not None else None,
        last_reviewed_at=last_reviewed,
    )


def _svc(rules, stats):
    tr = FakeTriggerRepo()
    svc = WatchMetaReviewService(FakeRuleRepo(rules), tr, InterventionConfig())
    svc._trigger_stats = lambda: stats
    return svc, tr


def test_burst_triggers_review_when_rule_keeps_firing():
    """一直响：单日触发 ≥ 5 次 → 必须回到 agent 复核（阈值失真/该转阶段/该取消）"""
    svc, tr = _svc([_rule()], {1: {"today": 5, "last_at": NOW}})
    out = svc.scan(now=NOW)
    assert out["raised"] == 1
    assert tr.records[0]["disposition"] == DISPOSITION_META_REVIEW
    assert "频次超限" in tr.records[0]["disposition_reason"]


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
    svc, tr = _svc([_rule(last_reviewed=NOW)], {1: {"today": 9, "last_at": NOW}})
    out = svc.scan(now=NOW, force=True)
    assert out["raised"] == 1


def test_meta_trigger_param_shape():
    svc, tr = _svc([_rule()], {1: {"today": 6, "last_at": NOW}})
    svc.scan(now=NOW)
    rec = tr.records[0]
    assert rec["condition"]["type"] == "meta_review"
    assert rec["trigger_price"] is None
    assert rec["notified"] is False
    assert rec["disposition_by"] == "system"
