"""成交回执同步单测（RFC 017 §2.1.4，卡 `fill-event-sync`，2026-10-21）

覆盖本卡四条验收，全部**不连库**（仓储/服务用假件，时钟与持仓真值显式注入）：

  0. 成交同步：买入→holding / 清仓→none / 幂等 / 时延 / **任何来源**的卖出都收敛；
  2. 唤醒载荷 additive `exec_directive`：无则载荷**逐字不变**（回归锚点）；
  3. 回调失败不影响成交落库（trading 侧 `_notify_fill` 双保险）；
  4. 端口 + 组合根注册：`IFillListener` 结构协议、一行注册、注册失败降级不阻断。

分层的三层断言（与 RFC 的「不造假」纪律对应）：
  · 领域层：位置状态翻转 / 待办收敛 / 触发处置 / 时延落 detail 的**事实**；
  · 端口层：`FillEvent` 字段完整、`source` 只进留痕不作收敛判据；
  · 宿主层：注册/未注册/回调抛错三种情况下成交路径都照常落库。
"""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from application.trading.paper_trading_engine import (
    FillEvent,
    IFillListener,
    PaperTradingEngine,
    get_fill_listener,
    register_fill_listener as trading_register,
    unregister_fill_listener,
)
from domain.trading.models.signal import Signal
from qs_watch.application.services.watch_engine import watch_channels
from qs_watch.application.services.watch_engine.exec_directive import (
    PositionFacts,
    build_exec_directive,
)
from qs_watch.application.services.watch_engine.fill_sync_service import (
    FillSyncService,
    get_fill_sync_service,
    latency_seconds,
    register_fill_listener,
)
from qs_watch.application.services.watch_engine.position_lifecycle_service import (
    PositionLifecycleService,
)
from qs_watch.application.services.watch_engine.todo_service import TodoService

NOW = datetime(2026, 10, 21, 10, 0, 0)
ACCOUNT = 'agent_virtual'
SYMBOL = '600000.SH'
SYMBOL_KEY = '600000'          # normalize_symbol 口径（去交易所后缀）


# ═══════════════════════════════════════════════════════════════════════════
# 假件（只实现被调用的端口方法，失败面可显式注入）
# ═══════════════════════════════════════════════════════════════════════════

class FakeRule:
    def __init__(self, rule_id, symbol=SYMBOL, account=ACCOUNT, intent='exit_stop',
                 enabled=True, position_state=None, lifecycle_stage='holding',
                 context='', linked_account=None, action_hint=None):
        self.id = rule_id
        self.symbol = symbol
        self.account = account
        self.linked_account = linked_account
        self.intent = intent
        self.action_hint = action_hint or {}
        self.enabled = enabled
        self.position_state = position_state
        self.lifecycle_stage = lifecycle_stage
        self.context = context


class FakeRuleRepo:
    def __init__(self, rules):
        self.rules = list(rules)
        self.state_writes = []
        self.field_writes = []

    def list_rules(self, symbol=None, enabled=None, account=None):
        return [r for r in self.rules
                if (symbol is None or r.symbol == symbol)
                and (enabled is None or bool(r.enabled) is bool(enabled))
                and (account is None or r.account == account)]

    def _get(self, rule_id):
        for r in self.rules:
            if r.id == rule_id:
                return r
        return None

    def set_position_state(self, rule_id, state):
        rule = self._get(rule_id)
        rule.position_state = state
        self.state_writes.append((rule_id, state))
        return rule

    def update_fields(self, rule_id, **fields):
        rule = self._get(rule_id)
        for key, value in fields.items():
            setattr(rule, key, value)
        self.field_writes.append((rule_id, dict(fields)))
        return rule


class FakePositionRepo:
    """持仓真值（键 = 归一化标的口径）；raises=True 模拟读失败（fail-closed 面）。"""

    def __init__(self, positions=None, raises=False):
        self.positions = dict(positions or {})
        self.raises = raises
        self.calls = []

    def get_position(self, account, symbol):
        self.calls.append((account, symbol))
        if self.raises:
            raise RuntimeError('db down')
        return self.positions.get((account, symbol))

    def put(self, account, symbol, shares_total, shares_available=None, avg_cost=10.0):
        self.positions[(account, symbol)] = SimpleNamespace(
            account_name=account, symbol=symbol,
            shares_total=shares_total,
            shares_available=(shares_total if shares_available is None else shares_available),
            avg_cost=avg_cost)


class FakeTodo:
    def __init__(self, todo_id, symbol=SYMBOL, level='P0', action_kind='trade',
                 account=ACCOUNT, terminal=None, trigger_id=101,
                 created_at=None, flow_state='L3'):
        self.id = todo_id
        self.symbol = symbol
        self.level = level
        self.action_kind = action_kind
        self.account = account
        self.terminal = terminal
        self.trigger_id = trigger_id
        self.created_at = created_at or NOW
        self.flow_state = flow_state
        self.close_reason = None
        self.decision_audit_id = None
        self.closed_at = None


class FakeTodoRepo:
    def __init__(self, todos=()):
        self.todos = list(todos)
        self.closed = []

    def list_pending(self, level=None, account=None, limit=100,
                     flow_state=None, terminal=None):
        rows = [t for t in self.todos if not t.terminal]
        if level is not None:
            rows = [t for t in rows if t.level == level]
        if account is not None:
            rows = [t for t in rows if t.account == account]
        return rows[:limit]

    def get(self, todo_id):
        for t in self.todos:
            if t.id == todo_id:
                return t
        return None

    def close(self, todo_id, terminal, *, close_reason=None, next_condition=None,
              action_kind=None, decision_audit_id=None, closed_by=None, now=None):
        todo = self.get(todo_id)
        if todo is None or todo.terminal:
            return None
        todo.terminal = terminal
        todo.close_reason = close_reason
        todo.action_kind = action_kind
        todo.decision_audit_id = decision_audit_id
        todo.closed_at = now or NOW
        self.closed.append(todo_id)
        return todo


class FakeTrigger:
    def __init__(self, trigger_id=101, triggered_at=None, detail=None):
        self.id = trigger_id
        self.triggered_at = triggered_at
        self.detail = detail
        self.disposition = 'pending'
        self.disposition_reason = None
        self.disposition_by = None


class FakeTriggerRepo:
    def __init__(self, triggers=()):
        self.triggers = {t.id: t for t in triggers}
        self.updates = []
        self.dispositions = []
        self.reads = []
        self.raises = False

    def get_by_id(self, trigger_id):
        self.reads.append(trigger_id)
        if self.raises:
            raise RuntimeError('trigger db down')
        return self.triggers.get(trigger_id)

    def update(self, trigger):
        if self.raises:
            raise RuntimeError('trigger db down')
        self.updates.append(trigger.id)
        return trigger

    def update_disposition(self, trigger_id, disposition, reason=None, by='agent'):
        if self.raises:
            raise RuntimeError('trigger db down')
        trigger = self.triggers.get(trigger_id)
        if trigger is None:
            return None
        trigger.disposition = disposition
        trigger.disposition_reason = reason
        trigger.disposition_by = by
        self.dispositions.append((trigger_id, disposition, reason, by))
        return trigger


def _build(rules=(), positions=None, todos=(), triggers=(), raises_position=False,
           lifecycle=None, todo_scan_limit=200):
    rule_repo = FakeRuleRepo(rules)
    position_repo = FakePositionRepo(positions, raises=raises_position)
    todo_service = TodoService(FakeTodoRepo(todos))
    trigger_repo = FakeTriggerRepo(triggers)
    svc = FillSyncService(
        rule_repo=rule_repo,
        todo_service=todo_service,
        trigger_repo=trigger_repo,
        position_repo=position_repo,
        lifecycle=lifecycle if lifecycle is not None else PositionLifecycleService(
            rule_repo, position_repo, accounts=(ACCOUNT,)),
        todo_scan_limit=todo_scan_limit,
    )
    return svc, SimpleNamespace(rule_repo=rule_repo, position_repo=position_repo,
                                todo_service=todo_service, todo_repo=todo_service._repo,
                                trigger_repo=trigger_repo)


def _sell_fill(**over):
    base = dict(account_name=ACCOUNT, symbol=SYMBOL, action='sell', shares=1000,
                price=9.8, trade_id=9001, filled_at=NOW + timedelta(seconds=42),
                source='watch_directive', decision_audit_id='DEC-20261021-1')
    base.update(over)
    return FillEvent(**base)


# ═══════════════════════════════════════════════════════════════════════════
# 判据 0-a：买入成交 → position_state=holding（只作用于该 (账户, 标的)）
# ═══════════════════════════════════════════════════════════════════════════

class TestBuyFillFlipsHolding:

    def test_buy_fill_flips_holding_for_matching_rules_only(self):
        rules = [
            FakeRule(1, symbol=SYMBOL, account=ACCOUNT, intent='entry', position_state='none'),
            FakeRule(2, symbol=SYMBOL, account='agent_brain', intent='entry', position_state='none'),
            FakeRule(3, symbol='600519.SH', account=ACCOUNT, intent='entry', position_state='none'),
            # 无账户观察规则：成交证明不了它的立场，不在作用域内
            FakeRule(4, symbol=SYMBOL, account=None, intent='trend_observe', position_state=None),
        ]
        svc, fakes = _build(rules=rules, positions={})
        fakes.position_repo.put(ACCOUNT, SYMBOL_KEY, shares_total=1000)

        result = svc.on_fill(FillEvent(account_name=ACCOUNT, symbol=SYMBOL, action='buy',
                                       shares=1000, price=10.0, trade_id=5001,
                                       filled_at=NOW, source='rotation'))

        assert result['status'] == 'ok'
        assert result['position_state'] == 'holding'
        assert result['position_read'] == 'ok'
        assert fakes.rule_repo.state_writes == [(1, 'holding')]
        assert fakes.rule_repo.rules[0].position_state == 'holding'
        # 别的账户 / 别的标的 / 无账户观察规则都不动
        assert fakes.rule_repo.rules[1].position_state == 'none'
        assert fakes.rule_repo.rules[2].position_state == 'none'
        assert fakes.rule_repo.rules[3].position_state is None
        # 买入不做收敛/退役
        assert result['converged_todos'] == []
        assert fakes.todo_repo.closed == []

    def test_buy_fill_already_holding_is_noop(self):
        rules = [FakeRule(1, position_state='holding')]
        svc, fakes = _build(rules=rules, positions={})
        fakes.position_repo.put(ACCOUNT, SYMBOL_KEY, shares_total=1000)
        result = svc.on_fill(FillEvent(account_name=ACCOUNT, symbol=SYMBOL, action='buy',
                                       shares=200, price=10.0, trade_id=5002,
                                       filled_at=NOW, source='rotation'))
        assert result['status'] == 'ok'
        assert fakes.rule_repo.state_writes == []          # 已是 holding → 不写
        assert result['rules_updated'] == []


# ═══════════════════════════════════════════════════════════════════════════
# 判据 0-b：清仓成交 → none + 待办 handled(executed) + exit 族退役 + 时延落 detail
# ═══════════════════════════════════════════════════════════════════════════

class TestClearPositionConvergence:

    def _setup(self, **over):
        rules = [
            FakeRule(11, intent='exit_stop', position_state='holding',
                     context='止损预案：跌破 28 元清仓'),
            FakeRule(12, intent='exit_take_profit', position_state='holding'),
            FakeRule(13, intent='entry', position_state='holding'),
            FakeRule(14, symbol='600519.SH', intent='exit_stop', position_state='holding'),
        ]
        todos = [FakeTodo(201, trigger_id=101, created_at=NOW - timedelta(minutes=5))]
        triggers = [FakeTrigger(101, triggered_at=NOW,
                                detail={'condition': {'type': 'price_break'}})]
        svc, fakes = _build(rules=rules, positions={}, todos=todos, triggers=triggers, **over)
        return svc, fakes

    def test_sell_to_zero_converges_todo_retires_exit_and_records_latency(self):
        svc, fakes = self._setup()
        result = svc.on_fill(_sell_fill())

        # ① 状态翻转：清仓 → none（该账户该标的的全部规则）
        assert result['status'] == 'executed'
        assert result['position_state'] == 'none'
        assert {rid for rid, _ in fakes.rule_repo.state_writes} == {11, 12, 13}

        # ② 执行待办收敛 handled（trade + 可核验审计号）
        todo = fakes.todo_repo.get(201)
        assert result['converged_todos'] == [201]
        assert todo.terminal == 'handled'
        assert todo.action_kind == 'trade'
        assert todo.decision_audit_id == 'DEC-20261021-1'
        assert 'watch_directive' in todo.close_reason      # 来源落留痕
        assert '执行完成' in todo.close_reason

        # ③ 触发处置 handled + 时延落 detail.exec（只写一次）
        trigger = fakes.trigger_repo.get_by_id(101)
        assert trigger.disposition == 'handled'
        assert trigger.disposition_by == 'fill_sync'
        assert result['detail_written'] is True
        assert result['latency_sec'] == 42.0
        assert trigger.detail['exec']['trade_id'] == 9001
        assert trigger.detail['exec']['price'] == 9.8
        assert trigger.detail['exec']['latency_sec'] == 42.0
        assert trigger.detail['exec']['source'] == 'watch_directive'
        assert trigger.detail['exec']['audit_degraded'] is False
        assert trigger.detail['condition'] == {'type': 'price_break'}   # 既有 detail 不丢

        # ④ exit 族即时退役；entry 保留
        assert fakes.rule_repo.rules[0].enabled is False
        assert fakes.rule_repo.rules[0].lifecycle_stage == 'closed'
        assert '已清仓' in fakes.rule_repo.rules[0].context
        assert fakes.rule_repo.rules[1].enabled is False
        assert fakes.rule_repo.rules[2].enabled is True     # entry 不动
        assert fakes.rule_repo.rules[3].enabled is True     # 别的标的不动
        assert [r['rule_id'] for r in result['retired_rules']] == [11, 12]

    def test_partial_sell_does_not_converge(self):
        svc, fakes = self._setup()
        fakes.position_repo.put(ACCOUNT, SYMBOL_KEY, shares_total=400)   # 卖后仍剩 400 股

        result = svc.on_fill(_sell_fill(shares=600))

        assert result['status'] == 'partial'
        assert result['converged_todos'] == []
        assert fakes.todo_repo.get(201).terminal is None          # 待办保持未收敛
        assert fakes.trigger_repo.get_by_id(101).disposition == 'pending'
        assert fakes.rule_repo.rules[0].enabled is True           # 止损仍要盯剩余仓位
        assert result['position_state'] == 'holding'
        assert result['detail_written'] is False

    def test_clear_without_open_todo_still_flips_and_retires(self):
        svc, fakes = self._setup()
        fakes.todo_repo.todos = []                                # 人工/兜底卖出：无 watch 待办

        result = svc.on_fill(_sell_fill())

        assert result['status'] == 'converged_no_todo'
        assert result['converged_todos'] == []
        assert result['position_state'] == 'none'
        assert fakes.rule_repo.rules[0].enabled is False          # 清仓事实仍收摊规则
        assert fakes.trigger_repo.dispositions == []

    def test_only_p0_trade_todos_are_converged(self):
        svc, fakes = self._setup()
        # P1 提醒单 / P0 治理单（rule_change）都不属于「执行闭环」
        fakes.todo_repo.todos.extend([
            FakeTodo(202, level='P1', trigger_id=102),
            FakeTodo(203, level='P0', action_kind='rule_change', trigger_id=103),
        ])
        result = svc.on_fill(_sell_fill())
        assert result['converged_todos'] == [201]
        assert fakes.todo_repo.get(202).terminal is None
        assert fakes.todo_repo.get(203).terminal is None

    def test_close_requires_audit_id_degrades_honestly(self):
        """拿不到决策审计号：退化为 trade:<id> 并标 audit_degraded（不虚报审计）。"""
        svc, fakes = self._setup()
        result = svc.on_fill(_sell_fill(decision_audit_id=None))

        todo = fakes.todo_repo.get(201)
        assert todo.decision_audit_id == 'trade:9001'
        assert result['audit_degraded'] is True
        assert fakes.trigger_repo.get_by_id(101).detail['exec']['audit_degraded'] is True

    def test_preexisting_exec_detail_is_not_overwritten(self):
        """detail.exec 已存在 → 时延只写一次（幂等），既有成交留痕不覆盖。"""
        svc, fakes = self._setup()
        fakes.trigger_repo.get_by_id(101).detail = {
            'exec': {'trade_id': 7001, 'latency_sec': 12.0}}

        result = svc.on_fill(_sell_fill())

        assert result['detail_written'] is False
        exec_detail = fakes.trigger_repo.get_by_id(101).detail['exec']
        assert exec_detail['trade_id'] == 7001
        assert exec_detail['latency_sec'] == 12.0


# ═══════════════════════════════════════════════════════════════════════════
# 判据 0-c：幂等（重复 fill 不二次收敛、不二次写时延）
# ═══════════════════════════════════════════════════════════════════════════

class TestIdempotency:

    def test_duplicate_fill_does_not_reconverge(self):
        rules = [FakeRule(11, intent='exit_stop', position_state='holding')]
        todos = [FakeTodo(201, trigger_id=101)]
        triggers = [FakeTrigger(101, triggered_at=NOW)]
        svc, fakes = _build(rules=rules, positions={}, todos=todos, triggers=triggers)

        first = svc.on_fill(_sell_fill())
        second = svc.on_fill(_sell_fill())        # 同一 trade_id 的重复事件

        assert first['status'] == 'executed'
        assert second['converged_todos'] == []    # 已终态 → 不再收敛
        assert fakes.todo_repo.closed == [201]    # 只 close 一次
        exec_detail = fakes.trigger_repo.get_by_id(101).detail['exec']
        assert exec_detail['trade_id'] == 9001
        assert exec_detail['latency_sec'] == 42.0  # 时延不被第二次事件改写

    def test_already_terminal_todo_is_tolerated_not_raised(self):
        rules = [FakeRule(11, position_state='holding')]
        todos = [FakeTodo(201, terminal='ignored', trigger_id=101)]
        svc, fakes = _build(rules=rules, positions={}, todos=todos,
                            triggers=[FakeTrigger(101, triggered_at=NOW)])

        result = svc.on_fill(_sell_fill())

        assert result['status'] == 'converged_no_todo'
        assert fakes.todo_repo.closed == []          # 已终态的不再动
        assert result['errors'] == []


# ═══════════════════════════════════════════════════════════════════════════
# 判据 0-d：时延（触发时刻 → 成交时刻；缺失退回建单时刻）
# ═══════════════════════════════════════════════════════════════════════════

class TestLatency:

    def test_latency_seconds_pure_function(self):
        assert latency_seconds(NOW + timedelta(seconds=42.25), NOW) == 42.2  # round 1 位
        assert latency_seconds(NOW - timedelta(seconds=5), NOW) == 0.0      # 负值按 0
        assert latency_seconds(None, NOW) is None
        assert latency_seconds('2026-10-21T10:00:42', NOW) == 42.0          # ISO 字符串
        aware = datetime(2026, 10, 21, 10, 0, 42, tzinfo=timezone.utc)
        assert latency_seconds(aware, NOW) == 42.0                          # aware/naive 混用不炸

    def test_latency_falls_back_to_todo_created_at(self):
        rules = [FakeRule(11, position_state='holding')]
        todos = [FakeTodo(201, trigger_id=101, created_at=NOW)]
        triggers = [FakeTrigger(101, triggered_at=None)]   # 触发时刻缺失
        svc, fakes = _build(rules=rules, positions={}, todos=todos, triggers=triggers)

        result = svc.on_fill(_sell_fill(filled_at=NOW + timedelta(seconds=30)))

        assert result['latency_sec'] == 30.0
        assert fakes.trigger_repo.get_by_id(101).detail['exec']['latency_sec'] == 30.0


# ═══════════════════════════════════════════════════════════════════════════
# 判据 0-e：任何来源的卖出成交都收敛（source 只进留痕，不作判据）
# ═══════════════════════════════════════════════════════════════════════════

class TestMultiSourceConvergence:

    @pytest.mark.parametrize('source', [
        'watch_directive',     # watch 指令 → agent 执行
        'intraday_monitor',    # 盘中止损兜底（RFC §4.4）
        'stop_loss',           # 纸面引擎内置止损
        'manual',              # 人工卖出
    ])
    def test_any_source_sell_converges_same_way(self, source):
        rules = [FakeRule(11, intent='exit_stop', position_state='holding')]
        todos = [FakeTodo(201, trigger_id=101)]
        triggers = [FakeTrigger(101, triggered_at=NOW)]
        svc, fakes = _build(rules=rules, positions={}, todos=todos, triggers=triggers)

        result = svc.on_fill(_sell_fill(source=source))

        assert result['status'] == 'executed'
        assert result['converged_todos'] == [201]
        assert source in fakes.todo_repo.get(201).close_reason
        assert fakes.trigger_repo.get_by_id(101).detail['exec']['source'] == source
        assert fakes.rule_repo.rules[0].enabled is False

    def test_unattributed_account_todo_still_converges(self):
        """待办账户为空（数据缺陷）：成交仍收敛，不让缺陷把闭环卡住。"""
        rules = [FakeRule(11, intent='exit_stop', position_state='holding')]
        todos = [FakeTodo(201, trigger_id=101, account=None)]
        svc, fakes = _build(rules=rules, positions={}, todos=todos,
                            triggers=[FakeTrigger(101, triggered_at=NOW)])
        result = svc.on_fill(_sell_fill(source='manual'))
        assert result['converged_todos'] == [201]

    def test_paper_engine_stop_loss_signal_source_reaches_listener(self, monkeypatch):
        """引擎内置止损（strategy_name=stop_loss）→ source 如实上报，不硬编码来源。"""
        seen = []

        class Recording:
            def on_fill(self, event):
                seen.append(event)

        engine, _ = _make_engine(monkeypatch, listener=Recording())
        engine.repo.get_position.return_value = SimpleNamespace(
            symbol='600000', shares_total=100, shares_available=100, avg_cost=10.0)
        engine._execute_sell(Signal(symbol='600000', action='SELL',
                                    strategy_name='stop_loss', price=9.0), 9.0)

        assert len(seen) == 1
        assert seen[0].source == 'stop_loss'
        assert seen[0].action == 'sell'


# ═══════════════════════════════════════════════════════════════════════════
# fail-closed / 降级：读不到持仓、端口缺失、坏事件
# ═══════════════════════════════════════════════════════════════════════════

class TestFailClosed:

    def test_position_read_failure_touches_nothing(self):
        rules = [FakeRule(11, intent='exit_stop', position_state='holding')]
        todos = [FakeTodo(201, trigger_id=101)]
        svc, fakes = _build(rules=rules, positions={}, todos=todos,
                            triggers=[FakeTrigger(101, triggered_at=NOW)],
                            raises_position=True)

        result = svc.on_fill(_sell_fill())

        assert result['status'] == 'degraded'
        assert fakes.rule_repo.state_writes == []       # 绝不把数据故障写成"已清仓"
        assert fakes.todo_repo.closed == []             # 待办保持未收敛（等人核实）
        assert fakes.rule_repo.rules[0].enabled is True  # 止损规则绝不误退役
        assert fakes.trigger_repo.dispositions == []

    def test_invalid_event_is_ignored_without_writes(self):
        svc, fakes = _build(rules=[FakeRule(11)], positions={})
        assert svc.on_fill({})['status'] == 'invalid'
        assert svc.on_fill({'symbol': SYMBOL, 'action': 'sell'})['status'] == 'invalid'
        assert svc.on_fill({'account_name': ACCOUNT, 'symbol': SYMBOL,
                            'action': 'transfer'})['status'] == 'invalid'
        assert fakes.rule_repo.state_writes == []
        assert fakes.todo_repo.closed == []

    def test_trigger_repo_failure_does_not_block_convergence(self):
        rules = [FakeRule(11, intent='exit_stop', position_state='holding')]
        todos = [FakeTodo(201, trigger_id=101)]
        svc, fakes = _build(rules=rules, positions={}, todos=todos,
                            triggers=[FakeTrigger(101, triggered_at=NOW)])
        fakes.trigger_repo.raises = True

        result = svc.on_fill(_sell_fill())

        assert result['status'] == 'executed'           # 待办收敛是主线，触发降级只记 errors
        assert result['converged_todos'] == [201]
        assert result['detail_written'] is False
        assert any('trigger' in e for e in result['errors'])

    def test_rule_repo_failure_does_not_block_convergence(self):
        rules = [FakeRule(11, intent='exit_stop', position_state='holding')]
        todos = [FakeTodo(201, trigger_id=101)]
        svc, fakes = _build(rules=rules, positions={}, todos=todos,
                            triggers=[FakeTrigger(101, triggered_at=NOW)])

        def boom(*a, **k):
            raise RuntimeError('rules db down')

        fakes.rule_repo.list_rules = boom
        result = svc.on_fill(_sell_fill())

        assert result['status'] == 'executed'
        assert result['converged_todos'] == [201]
        assert any('rule' in e for e in result['errors'])


# ═══════════════════════════════════════════════════════════════════════════
# 判据 2：唤醒载荷 additive exec_directive（无则载荷逐字不变）
# ═══════════════════════════════════════════════════════════════════════════

BASELINE_WAKE_KEYS = {
    'event', 'todo_id', 'symbol', 'level', 'flow_state', 'action_kind', 'rule_id',
    'account', 'owner_kind', 'owner_ref', 'autonomy', 'escalate_count', 'due_at',
    'created_at', 'message', 'instruction',
}


def _wake_todo(**over):
    base = dict(id=91, symbol=SYMBOL, level='P0', flow_state='L3', action_kind='trade',
                rule_id=255, account=ACCOUNT, owner_kind='agent', owner_ref='agent-dh',
                autonomy='remind_only', escalate_count=1, due_at=NOW, created_at=NOW)
    base.update(over)
    return SimpleNamespace(**base)


class TestWakePayloadAdditive:

    def test_without_directive_payload_is_unchanged(self):
        data = watch_channels._todo_wake_data(_wake_todo(), event='watch_todo_assigned')
        assert set(data) == BASELINE_WAKE_KEYS
        assert 'exec_directive' not in data

    def test_explicit_none_does_not_add_key(self):
        todo = _wake_todo()
        todo.exec_directive = None
        data = watch_channels._todo_wake_data(todo, event='watch_todo_timeout')
        assert 'exec_directive' not in data

    def test_attached_directive_is_projected_additively(self):
        directive = build_exec_directive(
            rule=FakeRule(255, intent='exit_stop', action_hint={'action': 'sell'}),
            level='P0', now=NOW, trigger_price=27.5, intent='exit_stop',
            account=ACCOUNT, position=PositionFacts(1000, 1000, 28.0),
            position_read='ok', trigger_id=101, todo_id=91)
        todo = _wake_todo()
        todo.exec_directive = directive

        data = watch_channels._todo_wake_data(todo, event='watch_todo_assigned')

        # additive：既有键一个不少、值不变；只多 exec_directive
        assert set(data) - {'exec_directive'} == BASELINE_WAKE_KEYS
        assert data['todo_id'] == 91 and data['event'] == 'watch_todo_assigned'
        assert data['exec_directive']['action'] == 'execute_stop_loss'
        assert data['exec_directive']['qty'] == 1000
        assert data['exec_directive']['trigger_id'] == 101
        assert [i['state'] for i in data['exec_directive']['action_items']] == [
            'executed', 'declined', 'timeout']

    def test_dict_directive_passes_through(self):
        todo = _wake_todo()
        todo.exec_directive = {'action': 'execute_stop_loss', 'qty': 100}
        data = watch_channels._todo_wake_data(todo, event='watch_todo_assigned')
        assert data['exec_directive'] == {'action': 'execute_stop_loss', 'qty': 100}

    def test_wake_assignment_carries_directive_through_facade(self, monkeypatch):
        """整链路：wake 送达的 data 里带指令（文档契约：agent-dh 原样交给 agent）。"""
        seen = []

        class Facade:
            def wake_agent(self, event, data, target_agent=None):
                seen.append(data)
                return 'ok'

        import qs_notification.application as notification_pkg
        monkeypatch.setattr(notification_pkg, 'get_notification_facade', lambda: Facade())

        todo = _wake_todo()
        todo.exec_directive = build_exec_directive(
            rule=FakeRule(255, intent='exit_stop'),
            level='P0', now=NOW, trigger_price=27.5, intent='exit_stop',
            account=ACCOUNT, position=PositionFacts(1000, 1000, 28.0),
            position_read='ok')
        assert watch_channels.wake_todo_assignment(todo) is True
        assert seen[0]['exec_directive']['action'] == 'execute_stop_loss'

    def test_wake_assignment_without_directive_keys_unchanged(self, monkeypatch):
        seen = []

        class Facade:
            def wake_agent(self, event, data, target_agent=None):
                seen.append(data)
                return 'ok'

        import qs_notification.application as notification_pkg
        monkeypatch.setattr(notification_pkg, 'get_notification_facade', lambda: Facade())

        assert watch_channels.wake_todo_assignment(_wake_todo()) is True
        assert set(seen[0]) == BASELINE_WAKE_KEYS


# ═══════════════════════════════════════════════════════════════════════════
# 判据 3：回调失败不影响成交落库（trading 侧双保险）
# ═══════════════════════════════════════════════════════════════════════════

def _make_engine(monkeypatch, listener=None):
    """构造不触库的 PaperTradingEngine（broker/repo 全 mock，模拟成交落库）。"""
    import application.trading.paper_trading_engine as pte

    broker = MagicMock()
    broker.buy.return_value = {'filled_price': 10.0, 'commission': 3.0,
                               'total_cost': 10003.0, 'amount': 10000.0}
    broker.sell.return_value = {'filled_price': 9.0, 'commission': 2.7,
                                'stamp_duty': 9.0, 'total_revenue': 8988.3,
                                'amount': 9000.0}
    repo = MagicMock()
    repo.get_account.return_value = SimpleNamespace(
        cash_available=1_000_000, total_value=1_000_000, position_value=0,
        peak_value=1_000_000, cumulative_return=0, max_drawdown=0)
    repo.add_trade.return_value = 1234
    repo.get_position.return_value = None

    monkeypatch.setattr(pte, 'SimulationBroker', lambda *a, **k: broker)
    monkeypatch.setattr(pte, 'SimulationORMRepository', lambda *a, **k: repo)
    engine = pte.PaperTradingEngine(account_name=ACCOUNT, fill_listener=listener)
    engine.repo = repo
    engine.broker = broker
    return engine, SimpleNamespace(broker=broker, repo=repo)


@pytest.fixture(autouse=True)
def _clean_fill_registry():
    """模块级注册位是进程级状态：每条测试前后都清空，避免跨测试串味。"""
    unregister_fill_listener()
    yield
    unregister_fill_listener()


class TestTradingSideCallback:

    def test_buy_callback_receives_fill_event_and_trade_persists(self, monkeypatch):
        seen = []

        class Recording:
            def on_fill(self, event):
                seen.append(event)

        engine, fakes = _make_engine(monkeypatch, listener=Recording())
        result = engine._execute_buy(
            Signal(symbol='600000', action='BUY', strength=1.0, price=10.0,
                   strategy_name='rotation', reason='动量突破'), 10.0)

        assert result.success is True
        fakes.repo.add_trade.assert_called_once()
        assert len(seen) == 1
        event = seen[0]
        assert event.account_name == ACCOUNT
        assert event.symbol == '600000'
        assert event.action == 'buy'
        assert event.shares == 20000
        assert event.price == 10.0
        assert event.trade_id == 1234
        assert event.source == 'rotation'
        assert event.reason == '动量突破'
        assert isinstance(event, FillEvent)

    def test_callback_exception_does_not_break_buy_persistence(self, monkeypatch):
        class Boom:
            def on_fill(self, event):
                raise RuntimeError('watch 侧挂了')

        engine, fakes = _make_engine(monkeypatch, listener=Boom())
        result = engine._execute_buy(
            Signal(symbol='600000', action='BUY', strength=1.0, price=10.0), 10.0)

        assert result.success is True                       # 成交照常成功
        fakes.repo.add_trade.assert_called_once()           # 成交照常落库
        fakes.repo.upsert_position.assert_called_once()     # 持仓照常更新

    def test_callback_exception_does_not_break_sell_persistence(self, monkeypatch):
        class Boom:
            def on_fill(self, event):
                raise RuntimeError('watch 侧挂了')

        engine, fakes = _make_engine(monkeypatch, listener=Boom())
        fakes.repo.get_position.return_value = SimpleNamespace(
            symbol='600000', shares_total=1000, shares_available=1000, avg_cost=10.0)

        result = engine._execute_sell(
            Signal(symbol='600000', action='SELL', strength=1.0, price=9.0), 9.0)

        assert result.success is True
        fakes.repo.add_trade.assert_called_once()
        fakes.repo.upsert_position.assert_called_once()
        assert fakes.repo.upsert_position.call_args.kwargs['shares_total'] == 0

    def test_no_listener_means_no_behaviour_change(self, monkeypatch):
        engine, fakes = _make_engine(monkeypatch, listener=None)
        assert get_fill_listener() is None
        result = engine._execute_buy(
            Signal(symbol='600000', action='BUY', strength=1.0, price=10.0), 10.0)
        assert result.success is True
        fakes.repo.add_trade.assert_called_once()

    def test_unpersisted_trade_is_not_reported_as_fill(self, monkeypatch):
        """add_trade 返回 None（落库失败）→ 绝不回调虚构成交。"""
        seen = []

        class Recording:
            def on_fill(self, event):
                seen.append(event)

        engine, fakes = _make_engine(monkeypatch, listener=Recording())
        fakes.repo.add_trade.return_value = None
        result = engine._execute_buy(
            Signal(symbol='600000', action='BUY', strength=1.0, price=10.0), 10.0)
        assert result.success is True
        assert seen == []


# ═══════════════════════════════════════════════════════════════════════════
# 判据 4：IFillListener 端口 + 组合根注册（幂等 / 失败降级）
# ═══════════════════════════════════════════════════════════════════════════

class TestPortAndRegistration:

    def _service(self):
        return _build(rules=[FakeRule(11, intent='exit_stop', position_state='holding')],
                      positions={},    # 清仓态
                      todos=[FakeTodo(201, trigger_id=101)],
                      triggers=[FakeTrigger(101, triggered_at=NOW)])[0]

    def test_fill_sync_service_structurally_satisfies_ifilllistener(self):
        svc = self._service()
        assert isinstance(svc, IFillListener)           # runtime_checkable 结构协议
        assert trading_register(svc) is None
        assert get_fill_listener() is svc

    def test_one_line_registration_installs_service(self):
        svc = self._service()
        installed = register_fill_listener(svc, registrar=trading_register)
        assert installed is svc
        assert get_fill_listener() is svc
        assert get_fill_sync_service() is svc

    def test_registration_is_idempotent(self):
        first = register_fill_listener(self._service(), registrar=trading_register)
        second = register_fill_listener(registrar=trading_register)
        assert first is second
        assert get_fill_listener() is first

    def test_registration_failure_degrades_without_blocking_host(self):
        def boom(_service):
            raise RuntimeError('端口不可用')

        assert register_fill_listener(self._service(), registrar=boom) is None
        assert get_fill_listener() is None               # 注册失败 = 保持 no-op，宿主照常

    def test_registered_service_receives_real_engine_fill(self, monkeypatch):
        """组合根注册后，引擎成交直接回流到 FillSyncService（端到端接线证明）。"""
        svc, fakes = _build(
            rules=[FakeRule(11, intent='exit_stop', position_state='holding')],
            positions={}, todos=[FakeTodo(201, trigger_id=101)],
            triggers=[FakeTrigger(101, triggered_at=NOW)])
        register_fill_listener(svc, registrar=trading_register)

        engine, engine_fakes = _make_engine(monkeypatch, listener=None)
        engine_fakes.repo.get_position.return_value = SimpleNamespace(
            symbol='600000', shares_total=1000, shares_available=1000, avg_cost=10.0)
        result = engine._execute_sell(
            Signal(symbol='600000', action='SELL', strategy_name='watch_directive',
                   price=9.0), 9.0)

        assert result.success is True
        assert fakes.todo_repo.get(201).terminal == 'handled'
        assert fakes.trigger_repo.get_by_id(101).detail['exec']['trade_id'] == 1234
        assert fakes.rule_repo.rules[0].enabled is False
