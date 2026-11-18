"""盯盘摘要账户分段与按账户投送单测（2026-09-11，w-aebfddcd）

用户定调：盯盘信息归属 agent_virtual / agent_brain / v13_simulation / user_main_simulation；
账户为空的**交易类**事件不唤醒 agent（没有账户不能交易）→ 只发飞书；
账户为空的**非交易类**（观察/跟踪/治理）仍唤醒 agent 处理。
"""
from datetime import datetime

from qs_watch.application.services.watch_engine.digest_service import (
    GLOBAL_OBSERVATION, UNASSIGNED, WatchDigestService,
)


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
        self.detail = {}


class _TriggerRepo:
    def __init__(self, rows):
        self.rows = rows

    def list_triggers(self, dispositions=None, limit=200, digest_unacked=False,
                      rule_ids=None, exclude_rule_ids=None):
        rows = [row for row in self.rows
                if (not digest_unacked or not (row.detail or {}).get('digest_event_id'))
                and (rule_ids is None or row.rule_id in rule_ids)
                and (not exclude_rule_ids or row.rule_id not in exclude_rule_ids)]
        if digest_unacked:
            rows.sort(key=lambda row: row.triggered_at)
        return rows[:limit]

    def claim_digest_batch(self, trigger_ids, event_id, at):
        selected = [row for row in self.rows if row.id in trigger_ids]
        if len(selected) != len(set(trigger_ids)):
            return False
        for row in selected:
            detail = row.detail or {}
            old = detail.get('digest_event_id') or detail.get('digest_claim_event_id')
            if old and old != event_id:
                return False
        for row in selected:
            row.detail = dict(row.detail or {})
            row.detail.setdefault('digest_claim_event_id', event_id)
            row.detail.setdefault('digest_claimed_at', at.isoformat())
        return True

    def mark_digest_delivered(self, trigger_ids, event_id, at):
        selected = [row for row in self.rows if row.id in trigger_ids]
        if len(selected) != len(set(trigger_ids)):
            return False
        for row in selected:
            old = (row.detail or {}).get('digest_event_id')
            if old and old != event_id:
                return False
        for row in selected:
            row.detail = dict(row.detail or {})
            row.detail.setdefault('digest_event_id', event_id)
            row.detail.setdefault('digest_delivered_at', at.isoformat())
        return True


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
    if trigs is None:
        # 确认标记会写 trigger.detail；默认夹具必须逐测试隔离，不能共享可变对象。
        trigs = [_Trig(row.id, row.rule_id, row.symbol, row.disposition) for row in DEFAULT_TRIGS]
    return WatchDigestService(
        trigger_repo=_TriggerRepo(trigs),
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
    # 2 个账户各一份 + 未归属桶一份（未归属照常唤醒，只是带缺陷标注）
    assert res["woke"] is True and res["wakes"] == 3
    assert sorted(res["accounts"]) == sorted(["agent_brain", "agent_virtual", UNASSIGNED])
    by_acct = {c["data"]["account_name"]: c for c in agent.calls}
    assert sorted(by_acct, key=str) == sorted(["agent_brain", "agent_virtual", None], key=str)
    assert 'account_name=\"agent_virtual\"' in by_acct["agent_virtual"]["data"]["instruction"]
    # 每份摘要只含本账户内容
    assert "agent_brain" not in by_acct["agent_virtual"]["data"]["digest"]


def test_strategy_account_rule_is_not_delivered_to_agent():
    """策略账户持有盯盘规则 = 设计错误：不投递 agent，显式上报 out_of_scope"""
    agent = _Agent()
    rules = [_Rule(9, "300224", account="v13_simulation", intent="trend_observe")]
    trigs = [_Trig(19, 9, "300224")]
    res = _svc(agent=agent, rules=rules, trigs=trigs).maybe_wake(now=TRADING_NOW)
    assert agent.calls == []
    assert res["woke"] is False and "盯盘不介入" in res["reason"]
    assert res["out_of_scope"][0]["account"] == "v13_simulation"


def test_wake_carries_per_account_authority():
    """授权按账户给：agent 自有账户可自主下单；用户账户只提醒（用户 2026-09-11 定调）"""
    agent = _Agent()
    rules = [_Rule(7, "600519", account="agent_virtual"),
             _Rule(8, "600036", account="user_main_simulation")]
    trigs = [_Trig(17, 7, "600519"), _Trig(18, 8, "600036")]
    _svc(agent=agent, rules=rules, trigs=trigs).maybe_wake(now=TRADING_NOW)
    by_acct = {c["data"]["account_name"]: c["data"] for c in agent.calls}
    assert by_acct["agent_virtual"]["autonomy"] == "autonomous"
    assert "你可以自主操作" in by_acct["agent_virtual"]["instruction"]
    assert by_acct["user_main_simulation"]["autonomy"] == "remind_only"
    assert "不得下单" in by_acct["user_main_simulation"]["instruction"]


# ── 投送：账户为空 = 数据缺陷（关键口径）────────────────────
def test_unassigned_still_wakes_agent_and_flags_defect():
    """账户为空是**规则数据缺陷**，不是投送模式：
    照常唤醒 agent，并把'补 linked_account'作为第一优先交给它——绝不'只发飞书'把缺陷藏起来。
    """
    agent = _Agent()
    rules = [_Rule(3, "000001", account=None, intent="entry")]
    trigs = [_Trig(13, 3, "000001")]
    res = _svc(agent=agent, rules=rules, trigs=trigs).maybe_wake(now=TRADING_NOW)
    assert res["woke"] is True and len(agent.calls) == 1
    data = agent.calls[0]["data"]
    assert data["unassigned"] is True and "linked_account" in data["data_defect"]
    assert "数据缺陷" in data["instruction"]
    assert res["data_defects"] == [{"count": 1, "rule_ids": [3]}]


def test_global_observe_wakes_without_fake_account_defect():
    """无账户趋势观察是合法全局事件，不再要求 PATCH linked_account。"""
    agent = _Agent()
    rules = [_Rule(4, "600150", account=None, intent="trend_observe")]
    trigs = [_Trig(14, 4, "600150")]
    res = _svc(agent=agent, rules=rules, trigs=trigs).maybe_wake(now=TRADING_NOW)
    assert res["woke"] is True and len(agent.calls) == 1
    data = agent.calls[0]["data"]
    assert data["global_observation"] is True
    assert data["unassigned"] is False
    assert "data_defect" not in data
    assert "不是缺账户缺陷" in data["instruction"]
    assert res["accounts"] == [GLOBAL_OBSERVATION]


def test_global_observe_and_unassigned_entry_are_separate_buckets():
    """合法全局观察与缺账户入场不得混成同一数据缺陷桶。"""
    agent = _Agent()
    rules = [_Rule(5, "601138", account=None, intent="entry"),
             _Rule(6, "600011", account=None, intent="trend_observe")]
    trigs = [_Trig(15, 5, "601138"), _Trig(16, 6, "600011")]
    res = _svc(agent=agent, rules=rules, trigs=trigs).maybe_wake(now=TRADING_NOW)
    assert res["wakes"] == 2 and len(agent.calls) == 2
    by_kind = {c["data"].get("global_observation", False): c["data"] for c in agent.calls}
    assert "600011" in by_kind[True]["digest"]
    assert "601138" not in by_kind[True]["digest"]
    assert "601138" in by_kind[False]["digest"]
    assert "600011" not in by_kind[False]["digest"]
    assert res["data_defects"] == [{"count": 1, "rule_ids": [5]}]


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


# ── 逐账户水位（2026-10-19，P1-5）──────────────────────────────
class _MarkStateRepo:
    """支持逐账户水位的状态 fake（对齐 WatchDigestStateRepository 新端口）"""

    def __init__(self):
        self.marks = {}
        self.pending = {}
        self.last_wake_at = None
        self.wake_count = 0
        self.fail_wake = False
        self.load_error = None

    def load_state(self):
        if self.load_error:
            return {"last_wake_at": None, "wake_date": None, "wake_count": 0,
                    "wake_marks": {}, "load_error": self.load_error}
        return {"last_wake_at": self.last_wake_at, "wake_date": None,
                "wake_count": self.wake_count,
                "wake_marks": {k: v.isoformat() for k, v in self.marks.items()},
                "pending_batches": dict(self.pending)}

    def save_wake(self, now, account=None):
        if self.fail_wake:
            return False
        self.last_wake_at = now
        self.wake_count += 1
        if account is not None:
            self.marks[str(account)] = now
        return True

    def save_wake_mark(self, account, at):
        self.marks[str(account)] = at

    def save_pending_batch(self, account, batch):
        existing = self.pending.get(str(account))
        old_id = ((existing or {}).get('payload') or {}).get('event_id')
        new_id = (batch.get('payload') or {}).get('event_id')
        if existing is not None and old_id != new_id:
            return False
        self.pending[str(account)] = batch
        return True

    def clear_pending_batch(self, account, expected_event_id):
        current = self.pending.get(str(account))
        current_id = ((current or {}).get('payload') or {}).get('event_id')
        if current is not None and current_id == expected_event_id:
            self.pending.pop(str(account), None)
        return True


class _FlakyAgent:
    """指定账户投递失败、其余成功的 agent fake"""

    def __init__(self, fail_account):
        self.fail_account = fail_account
        self.calls = []

    def notify_agent(self, event, data, target=None):
        self.calls.append({"event": event, "data": data, "target": target})
        return data.get("account_name") != self.fail_account


def test_failed_account_watermark_stays_put_and_content_redelivered():
    """部分账户唤醒失败：失败账户水位不推进，其触发下轮仍在增量段并被补投。

    修复前：全局 last_wake_at 被成功账户推进，失败账户更早的触发被 since 过滤出
    增量段，只剩 backlog 计数、永不进摘要分组。
    """
    early = datetime(2026, 9, 11, 9, 50)   # 失败账户的触发早于首轮唤醒时刻
    rules = [_Rule(1, "600519", account="agent_virtual"),
             _Rule(2, "600036", account="agent_brain")]
    trigs = [_Trig(11, 1, "600519"), _Trig(12, 2, "600036")]
    trigs[1].triggered_at = early
    state = _MarkStateRepo()
    agent = _FlakyAgent(fail_account="agent_brain")
    svc = WatchDigestService(trigger_repo=_TriggerRepo(trigs),
                             rule_repo=_RuleRepo(rules),
                             agent_service=agent, state_repo=state)

    r1 = svc.maybe_wake(now=TRADING_NOW)
    assert r1["woke"] is True and r1["accounts"] == ["agent_virtual"]
    assert r1["failed"] == ["agent_brain"]
    assert "agent_virtual" in state.marks            # 成功账户水位推进
    assert state.marks.get("agent_brain") is not None  # 失败账户水位**钉住**在原窗口
    assert state.marks["agent_brain"] < TRADING_NOW

    # 第二轮（冷却过后；brain 恢复可用）：brain 的早间触发仍在增量段并被补投
    agent2 = _Agent()
    svc2 = WatchDigestService(trigger_repo=_TriggerRepo(trigs),
                              rule_repo=_RuleRepo(rules),
                              agent_service=agent2, state_repo=state)
    r2 = svc2.maybe_wake(now=TRADING_NOW.replace(hour=11))
    brain_calls = [c for c in agent2.calls if c["data"]["account_name"] == "agent_brain"]
    assert brain_calls, "失败账户的触发必须在新一轮摘要中补投"
    assert "600036" in brain_calls[0]["data"]["digest"]


def test_retry_replays_fixed_batch_and_new_trigger_waits_for_next_event():
    """失败重试期间新增 trigger：旧批 event_id/payload 不变，新 trigger 下批必达。"""
    rules = [_Rule(1, '600519', account='agent_brain')]
    first = _Trig(11, 1, '600519')
    first.triggered_at = datetime(2026, 9, 11, 9, 50)
    rows = [first]
    state = _MarkStateRepo()
    failing = _FlakyAgent(fail_account='agent_brain')
    WatchDigestService(trigger_repo=_TriggerRepo(rows), rule_repo=_RuleRepo(rules),
                       agent_service=failing, state_repo=state).maybe_wake(now=TRADING_NOW)
    original = failing.calls[0]['data']
    assert original['trigger_ids'] == [11]
    assert state.pending['agent_brain']['payload']['event_id'] == original['event_id']

    late = _Trig(12, 1, '600519')
    late.triggered_at = datetime(2026, 9, 11, 10, 5)
    rows.append(late)
    retry_agent = _Agent()
    WatchDigestService(trigger_repo=_TriggerRepo(rows), rule_repo=_RuleRepo(rules),
                       agent_service=retry_agent, state_repo=state).maybe_wake(
                           now=datetime(2026, 9, 11, 10, 30))
    replay = retry_agent.calls[0]['data']
    assert replay['event_id'] == original['event_id']
    assert replay['trigger_ids'] == [11]
    assert state.marks['agent_brain'] == TRADING_NOW
    assert state.pending == {}

    next_agent = _Agent()
    WatchDigestService(trigger_repo=_TriggerRepo(rows), rule_repo=_RuleRepo(rules),
                       agent_service=next_agent, state_repo=state).maybe_wake(
                           now=datetime(2026, 9, 11, 11, 0))
    following = next_agent.calls[0]['data']
    assert following['trigger_ids'] == [12]
    assert following['event_id'] != original['event_id']


def test_claim_conflict_blocks_second_worker_before_network():
    class FailingAgent(_Agent):
        def notify_agent(self, event, data, target=None):
            self.calls.append({'event': event, 'data': data, 'target': target})
            return False

    rows = [_Trig(11, 1, '600519')]
    rules = [_Rule(1, '600519', account='agent_brain')]
    repo = _TriggerRepo(rows)
    first_agent = FailingAgent()
    WatchDigestService(trigger_repo=repo, rule_repo=_RuleRepo(rules),
                       agent_service=first_agent, state_repo=_StateRepo()).maybe_wake(now=TRADING_NOW)
    assert len(first_agent.calls) == 1
    claimed_event = rows[0].detail['digest_claim_event_id']

    second_agent = _Agent()
    result = WatchDigestService(
        trigger_repo=repo, rule_repo=_RuleRepo(rules), agent_service=second_agent,
        state_repo=_StateRepo()).maybe_wake(now=datetime(2026, 9, 11, 10, 1))
    assert second_agent.calls == []
    assert result['woke'] is False
    assert rows[0].detail['digest_claim_event_id'] == claimed_event


def test_failed_account_backlog_does_not_starve_healthy_account():
    rules = [_Rule(1, '600519', account='acct_A'), _Rule(2, '000001', account='acct_B')]
    rows = [_Trig(1000 + index, 1, '600519') for index in range(200)]
    healthy = _Trig(2001, 2, '000001')
    healthy.triggered_at = datetime(2026, 9, 11, 10, 1)
    rows.append(healthy)
    agent = _FlakyAgent('acct_A')
    state = _MarkStateRepo()
    service = WatchDigestService(
        trigger_repo=_TriggerRepo(rows), rule_repo=_RuleRepo(rules),
        agent_service=agent, state_repo=state)
    result = service.maybe_wake(now=TRADING_NOW)
    delivered_accounts = [call['data']['account_name'] for call in agent.calls]
    assert 'acct_B' in delivered_accounts
    assert healthy.detail.get('digest_event_id')
    assert result['accounts'] == ['acct_B']
    assert state.pending.get('acct_A')

    agent.calls.clear()
    service.maybe_wake(now=datetime(2026, 9, 11, 11, 0))
    assert [call['data']['account_name'] for call in agent.calls] == ['acct_A']


def test_state_read_failure_is_fail_closed_and_never_creates_new_event():
    state = _MarkStateRepo()
    state.pending['agent_brain'] = {'payload': {'event_id': 'watch_digest:keep'}, 'through': TRADING_NOW.isoformat()}
    state.load_error = 'database unavailable'
    agent = _Agent()
    result = WatchDigestService(
        trigger_repo=_TriggerRepo([_Trig(11, 1, '600519')]),
        rule_repo=_RuleRepo([_Rule(1, '600519', account='agent_brain')]),
        agent_service=agent, state_repo=state).maybe_wake(now=TRADING_NOW)
    assert result['woke'] is False and result['reason'] == 'state_unavailable'
    assert agent.calls == []
    assert state.pending['agent_brain']['payload']['event_id'] == 'watch_digest:keep'


def test_wake_save_failure_keeps_fixed_identity_until_state_finally_commits():
    state = _MarkStateRepo()
    state.fail_wake = True
    rows = [_Trig(11, 1, '600519')]
    rules = [_Rule(1, '600519', account='agent_brain')]
    first_agent = _Agent()
    WatchDigestService(trigger_repo=_TriggerRepo(rows), rule_repo=_RuleRepo(rules),
                       agent_service=first_agent, state_repo=state).maybe_wake(now=TRADING_NOW)
    original = first_agent.calls[0]['data']
    assert state.pending['agent_brain']['payload']['event_id'] == original['event_id']
    assert rows[0].detail['digest_event_id'] == original['event_id']

    state.fail_wake = False
    retry_agent = _Agent()
    WatchDigestService(trigger_repo=_TriggerRepo(rows), rule_repo=_RuleRepo(rules),
                       agent_service=retry_agent, state_repo=state).maybe_wake(
                           now=datetime(2026, 9, 11, 10, 30))
    assert retry_agent.calls[0]['data']['event_id'] == original['event_id']
    assert state.pending == {}

    quiet_agent = _Agent()
    result = WatchDigestService(trigger_repo=_TriggerRepo(rows), rule_repo=_RuleRepo(rules),
                                agent_service=quiet_agent, state_repo=state).maybe_wake(
                                    now=datetime(2026, 9, 11, 11, 0))
    assert result['woke'] is False
    assert quiet_agent.calls == []


def test_trigger_ack_not_timestamp_covers_future_and_delayed_commit_interleavings():
    class DelayedCommitRepo(_TriggerRepo):
        def __init__(self, rows, late):
            super().__init__(rows)
            self.late = late
            self.injected = False

        def list_triggers(self, dispositions=None, limit=200, digest_unacked=False,
                          rule_ids=None, exclude_rule_ids=None):
            snapshot = super().list_triggers(
                dispositions, limit, digest_unacked, rule_ids, exclude_rule_ids)
            if not self.injected and rule_ids == [1]:
                self.rows.append(self.late)  # 该账户查询快照之后才提交，但业务时间早于本轮 now。
                self.injected = True
            return snapshot

    rules = [_Rule(1, '600519', account='agent_brain')]
    future = _Trig(11, 1, '600519')
    future.triggered_at = datetime(2026, 9, 11, 10, 5)  # > now，仍被本批确认，下轮不得重投。
    late = _Trig(12, 1, '600519')
    late.triggered_at = datetime(2026, 9, 11, 9, 55)   # < 首轮水位，下轮仍必须送达。
    repo = DelayedCommitRepo([future], late)
    state = _MarkStateRepo()
    first_agent = _Agent()
    WatchDigestService(trigger_repo=repo, rule_repo=_RuleRepo(rules),
                       agent_service=first_agent, state_repo=state).maybe_wake(now=TRADING_NOW)
    assert first_agent.calls[0]['data']['trigger_ids'] == [11]

    next_agent = _Agent()
    WatchDigestService(trigger_repo=repo, rule_repo=_RuleRepo(rules),
                       agent_service=next_agent, state_repo=state).maybe_wake(
                           now=datetime(2026, 9, 11, 11, 0))
    assert next_agent.calls[0]['data']['trigger_ids'] == [12]
    assert next_agent.calls[0]['data']['event_id'] != first_agent.calls[0]['data']['event_id']

    quiet_agent = _Agent()
    WatchDigestService(trigger_repo=repo, rule_repo=_RuleRepo(rules),
                       agent_service=quiet_agent, state_repo=state).maybe_wake(
                           now=datetime(2026, 9, 11, 11, 30))
    assert quiet_agent.calls == []
