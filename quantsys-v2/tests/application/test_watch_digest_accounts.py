"""盯盘摘要账户分段与按账户投送单测（2026-09-11，w-aebfddcd）

用户定调：盯盘信息归属 agent_virtual / agent_brain / v13_simulation / user_main_simulation；
账户为空的**交易类**事件不唤醒 agent（没有账户不能交易）→ 只发飞书；
账户为空的**非交易类**（观察/跟踪/治理）仍唤醒 agent 处理。
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

DEFAULT_RULES = [
    _Rule(1, "600519", account="agent_virtual"),
    _Rule(2, "600519", account="agent_brain"),        # 同标的、不同账户
    _Rule(3, "000001", account=None, intent="entry"),  # 未归属 + 交易类
]
DEFAULT_TRIGS = [_Trig(11, 1, "600519"), _Trig(12, 2, "600519"), _Trig(13, 3, "000001")]


def _svc(agent=None, cap=8, rules=None, trigs=None):
    return WatchDigestService(
        trigger_repo=_TriggerRepo(trigs if trigs is not None else DEFAULT_TRIGS),
        rule_repo=_RuleRepo(rules if rules is not None else DEFAULT_RULES),
        agent_service=agent or _Agent(), state_repo=_StateRepo(), daily_cap=cap)


# ── 聚合与分段 ───────────────────────────────────────────────
def test_same_symbol_two_accounts_never_merge():
    """同标的被两个账户盯盘 → 两条独立摘要（合并会把 A 的预案投给 B 的 agent）"""
    d = _svc().build_digest()
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


# ── 投送：账户有归属 ─────────────────────────────────────────
def test_wake_fans_out_per_account_with_scope_instruction():
    agent = _Agent()
    res = _svc(agent=agent).maybe_wake(now=TRADING_NOW)
    assert res["woke"] is True and res["wakes"] == 2
    assert sorted(res["accounts"]) == ["agent_brain", "agent_virtual"]
    by_acct = {c["data"]["account_name"]: c for c in agent.calls}
    assert sorted(by_acct) == ["agent_brain", "agent_virtual"]
    assert 'account_name=\"agent_virtual\"' in by_acct["agent_virtual"]["data"]["instruction"]
    # 每份摘要只含本账户内容
    assert "agent_brain" not in by_acct["agent_virtual"]["data"]["digest"]


# ── 投送：账户为空（关键口径）──────────────────────────────
def test_unassigned_trade_does_not_wake_agent():
    """账户空 + 交易类：没有账户不能交易 → 只发飞书，不唤醒 agent"""
    agent = _Agent()
    rules = [_Rule(3, "000001", account=None, intent="entry")]
    trigs = [_Trig(13, 3, "000001")]
    res = _svc(agent=agent, rules=rules, trigs=trigs).maybe_wake(now=TRADING_NOW)
    assert agent.calls == []
    assert res["woke"] is False
    assert "只发飞书" in res["reason"]
    assert res["feishu_only"][0]["count"] == 1


def test_unassigned_observe_still_wakes_agent():
    """账户空 + 非交易类（观察/跟踪）：照常唤醒 agent，但禁止下单"""
    agent = _Agent()
    rules = [_Rule(4, "600150", account=None, intent="trend_observe")]
    trigs = [_Trig(14, 4, "600150")]
    res = _svc(agent=agent, rules=rules, trigs=trigs).maybe_wake(now=TRADING_NOW)
    assert res["woke"] is True and len(agent.calls) == 1
    data = agent.calls[0]["data"]
    assert data["unassigned"] is True and data["account_name"] is None
    assert "不得下单" in data["instruction"]


def test_mixed_unassigned_bucket_splits_trade_from_observe():
    """同一未归属桶里混着交易类与观察类 → 观察类唤醒，交易类只飞书"""
    agent = _Agent()
    rules = [_Rule(5, "601138", account=None, intent="entry"),
             _Rule(6, "600011", account=None, intent="trend_observe")]
    trigs = [_Trig(15, 5, "601138"), _Trig(16, 6, "600011")]
    res = _svc(agent=agent, rules=rules, trigs=trigs).maybe_wake(now=TRADING_NOW)
    assert res["wakes"] == 1 and len(agent.calls) == 1
    assert "600011" in agent.calls[0]["data"]["digest"]
    assert "601138" not in agent.calls[0]["data"]["digest"]
    assert res["feishu_only"][0]["count"] == 1


def test_wake_respects_daily_cap():
    agent = _Agent()
    res = _svc(agent=agent, cap=1).maybe_wake(now=TRADING_NOW)
    assert res["wakes"] == 1 and len(agent.calls) == 1


def test_wake_skipped_off_hours():
    assert _svc().maybe_wake(now=datetime(2026, 9, 11, 8, 0))["woke"] is False


def test_segment_text_labels_account():
    svc = _svc()
    segs = svc._segments(svc.build_digest())
    assert "[agent_virtual]" in segs["agent_virtual"]["text"]
    assert "agent_brain" not in segs["agent_virtual"]["text"]
