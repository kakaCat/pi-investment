"""触发 → 待办创建接线（REQ-c9f899 t12 续工）。

补的洞：引擎触发后没有待办载体，L1→L2→L3 晋升 / 到期巡检 / 三段回执全都没有对象。

可失败性（每条都能被 code 侧改坏证伪）：
  · P1 → 建待办，level=P1 / flow_state=L3（TodoService 派生）/ due_at=now+1800 / action_kind=trade；
  · P2 → flow_state=L1 / due_at=当日 15:00（MarketSessionPolicy.CONTINUOUS_END）；
  · P3 → **不建**（R1：纯归档，建待办会灌满表）；
  · deduped → 不建；
  · todo_service 未注入（总闸关）→ 不建，通知不带级别（旧行为）；same trigger_id 已有 todo → 不建；
  · create 抛错 → tick 不崩、通知仍发出、回填/记账不中断。
"""
from datetime import datetime, timedelta
from types import SimpleNamespace

from application.services.watch_engine.engine import WatchEngine
from application.services.watch_engine.todo_service import TodoService
from tests.services.test_watch_engine import FakeQuoteService, FakeRepo, make_rule

NOW = datetime(2026, 7, 21, 10, 30)      # 周二，交易时段内
DAY_CLOSE = datetime(2026, 7, 21, 15, 0)  # 当日收盘（CONTINUOUS_END）


class _TriggerRepo:
    def __init__(self):
        self.backfilled = []

    def set_todo_id(self, trigger_id, todo_id):
        self.backfilled.append((trigger_id, todo_id))


class _Notifier:
    """记录通知调用，返回带 id 的触发（模拟 notifier._record 落库后的触发对象）。"""

    def __init__(self, start_id=7):
        self.notifications = []
        self.trigger_repo = _TriggerRepo()
        self._next = start_id

    def notify(self, rule, condition, quote, result, **kwargs):
        self.notifications.append((rule.id, kwargs.get("level")))
        self._next += 1
        return SimpleNamespace(id=self._next - 1, todo_id=None)


class FakeTodoRepo:
    """IWatchTodoRepository 假的 create 侧；记录 TodoService 实际派生的字段。"""

    def __init__(self):
        self.created = []

    def create(self, symbol, **kwargs):
        self.created.append(dict(symbol=symbol, **kwargs))
        return SimpleNamespace(id=len(self.created), level=kwargs.get("level"),
                               flow_state=kwargs.get("flow_state"),
                               due_at=kwargs.get("due_at"),
                               trigger_id=kwargs.get("trigger_id"))


class BoomTodoRepo:
    def create(self, symbol, **kwargs):
        raise RuntimeError("todo db down")


def _engine(rules, prices, notifier, todo_service):
    return WatchEngine(
        rule_repo=FakeRepo(rules), quote_service=FakeQuoteService(prices),
        notifier=notifier, now_fn=lambda: NOW, todo_service=todo_service)


def _rule(level):
    """按目标级别造规则（走真实 resolve_level 路径）"""
    rule = make_rule()
    rule.linked_account = "agent_brain"
    if level == "P0":
        rule.intent, rule.scope = "exit_stop", "symbol"
    elif level == "P1":
        rule.intent, rule.scope = "entry", "symbol"
        rule.action_hint = {"trigger_level": "L1", "action_on_trigger": "buy"}
    elif level == "P2":
        rule.intent, rule.scope = "trend_observe", "sector"
        rule.action_hint = {"trigger_level": "L1", "action_on_trigger": "observe"}
    else:  # P3：纯观察 + 非 L2 + 非市场级
        rule.intent, rule.scope = "trend_observe", "symbol"
        rule.action_hint = {"trigger_level": "L1", "action_on_trigger": "observe"}
    return rule


PRICE_UP = {"600519.SH": 101.0}


def test_p1_trigger_creates_todo_l3_due_1800_and_backfills():
    rule = _rule("P1")
    repo, notifier = FakeTodoRepo(), _Notifier(start_id=7)
    engine = _engine([rule], PRICE_UP, notifier, TodoService(repo))
    engine.tick()
    assert len(repo.created) == 1
    c = repo.created[0]
    assert c["level"] == "P1"
    assert c["flow_state"] == "L3"            # P0/P1 直达 L3（TodoService 派生）
    assert c["due_at"] == NOW + timedelta(seconds=1800)
    assert c["sla_seconds"] == 1800
    assert c["rule_id"] == rule.id
    assert c["trigger_id"] == 7
    assert c["account"] == "agent_brain"
    assert c["action_kind"] == "trade"        # entry 属交易意图
    assert notifier.trigger_repo.backfilled == [(7, 1)]   # 触发回填 todo_id


def test_p2_trigger_creates_todo_l1_due_day_close():
    rule = _rule("P2")
    repo, notifier = FakeTodoRepo(), _Notifier()
    engine = _engine([rule], PRICE_UP, notifier, TodoService(repo))
    engine.tick()
    assert len(repo.created) == 1
    c = repo.created[0]
    assert c["level"] == "P2"
    assert c["flow_state"] == "L1"            # P2 先通知，靠 SLA/认领推进
    assert c["due_at"] == DAY_CLOSE           # 当日收盘 15:00
    assert c["sla_seconds"] == int((DAY_CLOSE - NOW).total_seconds())


def test_p3_trigger_does_not_create_todo():
    rule = _rule("P3")
    repo, notifier = FakeTodoRepo(), _Notifier()
    engine = _engine([rule], PRICE_UP, notifier, TodoService(repo))
    engine.tick()
    assert repo.created == []                 # R1：P3 纯归档，不建待办
    assert notifier.notifications == [(rule.id, "P3")]   # 但通知仍发出（带级别渲染）


def test_p0_trigger_creates_todo_due_300():
    rule = _rule("P0")
    repo, notifier = FakeTodoRepo(), _Notifier()
    engine = _engine([rule], PRICE_UP, notifier, TodoService(repo))
    engine.tick()
    assert len(repo.created) == 1
    c = repo.created[0]
    assert c["level"] == "P0"
    assert c["flow_state"] == "L3"
    assert c["due_at"] == NOW + timedelta(seconds=300)
    assert c["sla_seconds"] == 300
    assert c["action_kind"] == "trade"        # exit_stop 属交易意图


def test_deduped_trigger_does_not_create_todo():
    rules = [_rule("P1"), _rule("P1")]
    rules[0].id, rules[1].id = 1, 2
    repo, notifier = FakeTodoRepo(), _Notifier()
    engine = _engine(rules, PRICE_UP, notifier, TodoService(repo))
    events = engine.tick()
    assert "deduped" in [e.get("disposition") for e in events]
    assert len(repo.created) == 1             # 被去重的那条不建待办


def test_existing_todo_id_skips_create():
    rule = _rule("P1")
    repo, notifier = FakeTodoRepo(), _Notifier()
    engine = _engine([rule], PRICE_UP, notifier, TodoService(repo))
    trigger = SimpleNamespace(id=9, todo_id=123)
    assert engine._create_watch_todo(rule, NOW, "pending", trigger, "P1") is None
    assert repo.created == []                 # 同一 trigger_id 最多一条待办


def test_no_todo_service_keeps_old_behavior():
    rule = _rule("P1")
    notifier = _Notifier()
    engine = _engine([rule], PRICE_UP, notifier, None)   # 总闸关：未注入
    events = engine.tick()
    assert len(events) == 1
    assert notifier.notifications == [(rule.id, None)]   # 不带级别 → 旧渲染


def test_create_failure_does_not_crash_tick_and_still_notifies():
    rule = _rule("P1")
    notifier = _Notifier()
    engine = _engine([rule], PRICE_UP, notifier, TodoService(BoomTodoRepo()))
    events = engine.tick()
    assert len(events) == 1                   # tick 未被建待办失败打挂
    assert len(notifier.notifications) == 1   # 通知仍发出（未被吞掉）


def test_action_kind_meta_review_is_rule_change():
    engine = _engine([], {}, _Notifier(), None)
    rule = _rule("P1")
    assert engine._todo_action_kind(rule, "meta_review") == "rule_change"
    assert engine._todo_action_kind(rule, "pending") == "trade"
    rule2 = _rule("P3")
    assert engine._todo_action_kind(rule2, "pending") == "observe"


def test_p2_due_falls_back_when_past_close():
    engine = _engine([], {}, _Notifier(), None)
    late = datetime(2026, 7, 21, 15, 30)
    due, sla = WatchEngine._todo_due("P2", late)
    assert due == late + timedelta(minutes=1)   # 已过收盘 → 不把 due 放过去
    assert sla >= 1
