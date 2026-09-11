"""摘要门影子模式（2026-09-11，w-aebfddcd）

真开之前先跑 24h：照常算"该唤醒谁、带什么授权"，但**不发唤醒、不消耗预算**。
"""
from tests.application.test_watch_digest_accounts import (
    TRADING_NOW, _Agent, _Rule, _RuleRepo, _Trig, _TriggerRepo, _StateRepo,
)
from application.services.watch_engine.digest_service import WatchDigestService


def _svc(agent, state=None, dry_run=True):
    rules = [_Rule(1, "600519", account="agent_virtual"),
             _Rule(9, "300224", account="v13_simulation", intent="trend_observe")]
    trigs = [_Trig(11, 1, "600519"), _Trig(19, 9, "300224")]
    return WatchDigestService(trigger_repo=_TriggerRepo(trigs), rule_repo=_RuleRepo(rules),
                              agent_service=agent, state_repo=state or _StateRepo(),
                              dry_run=dry_run)


def test_shadow_reports_plan_without_waking():
    a = _Agent()
    state = _StateRepo()
    res = _svc(a, state).maybe_wake(now=TRADING_NOW)
    assert res["woke"] is False and res["dry_run"] is True
    assert a.calls == [], "影子模式不得发唤醒"
    assert state.saves == 0, "影子模式不得消耗唤醒预算（不写状态）"
    plan = {p.get("account"): p for p in res["would_wake"]}
    assert plan["agent_virtual"]["action"] == "wake"
    assert plan["agent_virtual"]["autonomy"] == "autonomous"
    assert plan["v13_simulation"]["action"] == "skip"      # 策略账户不介入


def test_shadow_respects_cooldown_to_avoid_log_spam():
    a = _Agent()
    svc = _svc(a)
    svc.maybe_wake(now=TRADING_NOW)
    again = svc.maybe_wake(now=TRADING_NOW)
    assert again["woke"] is False and "冷却" in again["reason"]


def test_live_mode_still_wakes():
    """dry_run=False 时行为不变（真唤醒）"""
    a = _Agent()
    res = _svc(a, dry_run=False).maybe_wake(now=TRADING_NOW)
    assert res["woke"] is True and a.calls
