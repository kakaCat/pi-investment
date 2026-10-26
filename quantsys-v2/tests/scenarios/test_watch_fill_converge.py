"""成交收敛端到端场景（REQ-261021194640-69b8 FR-1/FR-2，卡 t-2ff7ca）

用生产 `FillSyncService` + 假件端口，钉住五条闭环语义：
  1. 卖出清仓 → 待办 handled、触发 disposition=handled、规则退役、状态 none、时延落账；
  2. 买入 → 状态 holding，不收敛、不退役；
  3. 部分卖出（仍有持仓）→ 待办保持未收敛；
  4. 重复成交事件 → 只收敛一次、时延只写一次；
  5. 持仓读失败 → fail-closed：不翻状态、不收敛待办。
"""
from datetime import datetime, timedelta
from types import SimpleNamespace

from qs_watch.application.services.watch_engine.fill_sync_service import FillSyncService

NOW = datetime(2026, 10, 21, 10, 30)
ACCOUNT = 'agent_virtual'
SYMBOL = '600519.SH'


class FakeRule:
    def __init__(self, rule_id, intent):
        self.id = rule_id
        self.symbol = SYMBOL
        self.account = ACCOUNT
        self.linked_account = None
        self.intent = intent
        self.enabled = True
        self.position_state = None
        self.lifecycle_stage = 'holding'


class FakeRuleRepo:
    def __init__(self):
        self.rules = [FakeRule(1, 'entry'), FakeRule(2, 'exit_stop')]
        self.state_writes = []
        self.field_writes = []

    def list_rules(self, **kwargs):
        return list(self.rules)

    def set_position_state(self, rule_id, state):
        for r in self.rules:
            if r.id == rule_id:
                r.position_state = state
        self.state_writes.append((rule_id, state))
        return next(r for r in self.rules if r.id == rule_id)

    def update_fields(self, rule_id, **fields):
        self.field_writes.append((rule_id, fields))
        for r in self.rules:
            if r.id == rule_id:
                for k, v in fields.items():
                    setattr(r, k, v)
        return next(r for r in self.rules if r.id == rule_id)


class FakePositionRepo:
    def __init__(self, shares=0, raises=False):
        self.shares = shares
        self.raises = raises

    def get_position(self, account, symbol):
        if self.raises:
            raise RuntimeError('position db down')
        return SimpleNamespace(account_name=account, symbol=symbol,
                               shares_total=self.shares, shares_available=self.shares,
                               avg_cost=10.0)


class FakeTodo:
    def __init__(self, todo_id, terminal=None):
        self.id = todo_id
        self.symbol = SYMBOL
        self.trigger_id = 55
        self.created_at = NOW - timedelta(minutes=5)
        self.terminal = terminal
        self.close_reason = None
        self.decision_audit_id = None


class FakeTodoService:
    def __init__(self, todos):
        self.todos = todos
        self.close_calls = []

    def list(self, **kwargs):
        return [t for t in self.todos if t.terminal is None]

    def close(self, todo_id, terminal, **kwargs):
        self.close_calls.append({'todo_id': todo_id, 'terminal': terminal, **kwargs})
        todo = next(t for t in self.todos if t.id == todo_id)
        todo.terminal = terminal
        return todo


class FakeTrigger:
    def __init__(self, trigger_id):
        self.id = trigger_id
        self.disposition = 'escalated'
        self.detail = {}
        self.detail_updates = 0


class FakeTriggerRepo:
    def __init__(self, trigger):
        self.trigger = trigger
        self.detail_updates = 0
        self.dispositions = []

    def get_by_id(self, trigger_id):
        return self.trigger if trigger_id == self.trigger.id else None

    def update(self, trigger, **fields):
        # 生产收敛器口径：传 ORM 对象（先就地合并 detail 再落库）
        self.trigger = trigger
        if getattr(trigger, 'detail', None):
            trigger.detail_updates += 1
        return trigger

    def update_disposition(self, trigger_id, disposition, **kwargs):
        self.trigger.disposition = disposition
        self.dispositions.append(disposition)
        return self.trigger


class FakeLifecycle:
    def __init__(self):
        self.retired = []

    def retire_exit_rules(self, account, symbol, why):
        self.retired.append((account, symbol))
        return [{'rule_id': 2, 'symbol': symbol, 'reason': why}]


def _event(action='sell', trade_id=99, shares=1000, price=10.5):
    from qs_trading.application.ports.fill_listener import FillEvent
    return FillEvent(account_name=ACCOUNT, symbol=SYMBOL, action=action,
                     shares=shares, price=price, trade_id=trade_id,
                     filled_at=NOW, source='agent_trade')


def _service(position_shares=0, trigger=None, read_raises=False):
    rules = FakeRuleRepo()
    todos = [FakeTodo(7)]
    trigger = trigger or FakeTrigger(55)
    lifecycle = FakeLifecycle()
    svc = FillSyncService(
        rule_repo=rules,
        todo_service=FakeTodoService(todos),
        trigger_repo=FakeTriggerRepo(trigger),
        position_repo=FakePositionRepo(position_shares, raises=read_raises),
        lifecycle=lifecycle,
        now_fn=lambda: NOW,
    )
    return svc, rules, todos, trigger, lifecycle


def test_sell_clears_position_converges_everything():
    svc, rules, todos, trigger, lifecycle = _service(position_shares=0)
    result = svc.on_fill(_event())

    assert result['status'] == 'executed'
    assert todos[0].terminal == 'handled'
    assert trigger.disposition == 'handled'
    assert trigger.detail['exec']['trade_id'] == 99
    assert trigger.detail['exec']['latency_sec'] is not None
    assert lifecycle.retired, '清仓后 exit 族必须退役'
    assert all(r.position_state == 'none' for r in rules.rules)


def test_buy_flips_state_without_converging():
    svc, rules, todos, trigger, lifecycle = _service(position_shares=1000)
    result = svc.on_fill(_event(action='buy', trade_id=1))

    assert result['status'] == 'ok'
    assert result['position_state'] == 'holding'
    assert todos[0].terminal is None
    assert trigger.disposition == 'escalated'
    assert lifecycle.retired == []


def test_partial_sell_keeps_todo_open():
    svc, rules, todos, _trigger, lifecycle = _service(position_shares=400)
    result = svc.on_fill(_event(shares=600))

    assert result['status'] == 'partial'
    assert todos[0].terminal is None
    assert lifecycle.retired == []


def test_duplicate_fill_converges_once():
    svc, _rules, todos, trigger, _lifecycle = _service(position_shares=0)
    first = svc.on_fill(_event())
    second = svc.on_fill(_event())

    assert first['status'] == 'executed'
    assert second['status'] in ('converged_no_todo', 'executed')
    assert trigger.detail_updates == 1, '时延只写一次'
    assert todos[0].terminal == 'handled'


def test_position_read_failure_is_fail_closed():
    svc, rules, todos, trigger, lifecycle = _service(read_raises=True)
    result = svc.on_fill(_event())

    assert result['status'] == 'degraded'
    assert todos[0].terminal is None
    assert trigger.disposition == 'escalated'
    assert lifecycle.retired == []
    assert rules.state_writes == []
