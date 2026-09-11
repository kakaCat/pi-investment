"""盯盘摘要账户分段与按账户投送单测（2026-09-11，w-aebfddcd）

用户定调：盯盘信息归属 agent_virtual / agent_brain / v13_simulation / user_main_simulation，
即**账户是投送维度**——一个账户一份摘要、投给该账户的处置 agent，账户之间不得串味。
"""
from datetime import datetime

from application.services.watch_engine.digest_service import UNASSIGNED, WatchDigestService


class _Rule:
    def __init__(self, rid, symbol, account=None, intent="entry", scope="symbol"):
        self.id = rid
        self.symbol = symbol
        self.linked_account = account
        self.intent = intent
        self.scope = scope
        self.lifecycle_stage = "watching"
        self.action_hint = {"trigger_level": "L1", "action_on_trigger": "评估建仓"}
        self.context = "预案文本"
        self.next_action_hint = "确认后改规则"


class _Trig:
    def __init__(self, tid, rid, symbol, disposition="pending"):
        self.id = tid
        self.rule_id = rid
        self.symbol = symbol
        self.disposition = disposition
        self.disposition_reason = ""
        self.trigger_price = 10.0
        self.triggered_at = datetime(2026, 9, 11, 10, 0)
        self.condition = {"type": "price_break", "params": {"direction": "below", "price": 10.0}}


class _TriggerRepo:
    def __init__(self, rows):
        self.rows = rows

    def list_triggers(self, dispositions=None, limit=200):
        return list(self.rows)


class _RuleRepo:
    def __init__(self, rules):
        self.rules = rules

    def list_rules(self):
        return list(self.rules)


class _StateRepo:
    def __init__(self):
        self.saves = 0

    def load_state(self):
        return {"last_wake_at": None, "wake_date": None, "wake_count": 0}

    def save_wake(self, now):
        self.saves += 1


class _Agent:
    def __init__(self):
        self.calls = []

    def notify_agent(self, event, data, target=None):
        self.calls.append({"event": event, "data": data, "target": target})
        return True


TRADING_NOW = datetime(2026, 9, 11, 10, 0)


def _svc(agent=None, cap=8):
    rules = [
        _Rule(1, "600519", account="agent_virtual"),
        _Rule(2, "600519", account="agent_brain"),          # 同标的、不同账户
        _Rule(3, "000001", account=None),                    # 未归属
    ]
    trigs = [_Trig(11, 1, "600519"), _Trig(12, 2, "600519"), _Trig(13, 3, "000001")]
    return WatchDigestService(trigger_repo=_TriggerRepo(trigs), rule_repo=_RuleRepo(rules),
                              agent_service=agent or _Agent(), state_repo=_StateRepo(),
                              daily_cap=cap)


def test_same_symbol_two_accounts_never_merge():
    """同标的被两个账户盯盘 → 两条独立摘要（合并会把 A 的预案投给 B 的 agent）"""
    d = _svc().build_digest()
    # 3 组：600519(agent_virtual) / 600519(agent_brain) 不合并 + 000001(未归属)
    assert d["group_count"] == 3
    same_symbol = [g for g in d["groups"] if g["symbol"] == "600519"]
    assert len(same_symbol) == 2
    assert sorted(g["account"] for g in same_symbol) == ["agent_brain", "agent_virtual"]


def test_by_account_and_unassigned_reported():
    d = _svc().build_digest()
    assert d["by_account"]["agent_virtual"] == 1
    assert d["by_account"]["agent_brain"] == 1
    assert d["by_account"]["未归属"] == 1
    assert d["unassigned"] == 1


def test_account_filter():
    d = _svc().build_digest(account="agent_brain")
    assert d["count"] == 1
    assert d["groups"][0]["account"] == "agent_brain"


def test_segments_one_per_account_plus_unassigned():
    svc = _svc()
    segs = svc._segments(svc.build_digest())
    assert set(segs) == {"agent_virtual", "agent_brain", UNASSIGNED}
    assert segs["agent_virtual"]["count"] == 1


def test_wake_fans_out_per_account_with_scope_instruction():
    """一个账户一份唤醒；payload 带 account_name；指令含账户作用域纪律"""
    agent = _Agent()
    svc = _svc(agent=agent)
    res = svc.maybe_wake(now=TRADING_NOW)
    assert res["woke"] is True and res["wakes"] == 3
    assert sorted(res["accounts"]) == sorted(["agent_virtual", "agent_brain", UNASSIGNED])
    by_acct = {c["data"]["account_name"]: c for c in agent.calls}
    assert by_acct["agent_virtual"]["data"]["account_name"] == "agent_virtual"
    assert 'account_name=\"agent_virtual\"' in by_acct["agent_virtual"]["data"]["instruction"]
    # 未归属桶：account_name=None 且显式标注
    assert by_acct[None]["data"]["unassigned"] is True
    assert "未归属账户" in by_acct[None]["data"]["instruction"]
    # 每份摘要只含本账户内容
    assert "agent_brain" not in by_acct["agent_virtual"]["data"]["digest"]


def test_wake_respects_daily_cap():
    agent = _Agent()
    svc = _svc(agent=agent, cap=2)
    res = svc.maybe_wake(now=TRADING_NOW)
    assert res["wakes"] == 2 and len(agent.calls) == 2
    assert svc.state_repo.saves == 2


def test_wake_skipped_off_hours():
    svc = _svc()
    assert svc.maybe_wake(now=datetime(2026, 9, 11, 8, 0))["woke"] is False


def test_segment_text_labels_account():
    svc = _svc()
    segs = svc._segments(svc.build_digest())
    assert "[agent_virtual]" in segs["agent_virtual"]["text"]
    assert "agent_brain" not in segs["agent_virtual"]["text"]
