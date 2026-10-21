"""三态执行闭环 e2e（exec-loop-e2e，2026-10-21）

承接 `fill-event-sync` 与 `rule-change-linkage` 两张卡，把「P0 触发之后的三条
出路」端到端钉进场景矩阵——每条路都走到**外部可见的留痕**为止：

  F1 执行   → 成交回执（FillSync 收敛）：引擎触发 → P0/L3 待办 → 卖出成交 →
              待办 handled(trade) + 触发 disposition=handled + 执行时延落
              `detail.exec` + 持仓态翻转 none + exit 族收摊（幂等：二次成交
              事件不重复收敛、时延只写一次）；
  F2 不执行 → 改规则（rule-change 留痕）：同一触发血缘 → 待办 ignored(rule_change)
              → RuleChangeLinkage 把处置卡动作项落地为规则真更新 +
              一条 watch_rule_changes 审计（trigger_id / todo_id /
              decision_audit_id 三链齐全，缺审计号的 L3 关闭被领域守卫拒）；
  F3 超时   → SLA 升级：L1→L2→L3 机械晋升链 → L3 timeout 回执（P0 → risk_stop
              频道送达本人）→ 同一 due 周期幂等不重发 → 到点再催（R1 轮）；
              P2 超时只落台账不打扰（log_only）。

叠加两门（与闭环正交、但决定闭环会不会被误触发/漏触发）：
  G1 频率调度：interval_sec 未到期的规则本拍不取价、不评估、不消耗一拍；
  G2 持仓状态门：holding 时 entry 规则在取价之前被跳过（已有仓位不再喊建仓）；
     exit_stop 对滞后的 'none' 状态 fail-open 照常触发并落 state_mismatch 事件
     （状态滞后不静默跳过止损 = 资损防线）。

风格与 `test_watch_scenario_matrix.py` / `test_watch_opp_loop_e2e.py` 一致：
假件只替换出口与取数（notifier / 仓储 / 持仓 / 时钟），判定与编排全部走生产代码；
每个用例写明证伪点（哪条断言失败 = 哪条闭环语义破了）。复用既有单测同款假件
（tests.application.test_sla_job 的 FakeTodo/FakeTodoRepo/FakeReceiptRepo、
tests.services.test_watch_engine 的 make_rule/FakeQuoteService/FakeNotifier）。
"""
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from adapters.inbound.fastapi_app.watch_sla_job import WatchSlaJob
from qs_watch.application.services.watch_engine import exec_directive as exec_directive_mod
from qs_watch.application.services.watch_engine.disposition_engine import (
    LINKAGE_NOTE_SOURCE,
    RuleChangeAction,
    RuleChangeLinkage,
)
from qs_watch.application.services.watch_engine.engine import (
    STATE_MISMATCH_EVENT,
    MISMATCH_STOP_WITHOUT_HOLDING,
    WatchEngine,
)
from qs_watch.application.services.watch_engine.fill_sync_service import FillSyncService
from qs_watch.application.services.watch_engine.position_lifecycle_service import (
    PositionLifecycleService,
)
from qs_watch.application.services.watch_engine.receipt_service import (
    ReceiptService,
)
from qs_watch.application.services.watch_engine.todo_service import TodoService
from qs_watch.domain.watch.ports import WatchTodoMissingAudit
from qs_watch.domain.watch.services.disposition import normalize_symbol
from tests.application.test_sla_job import (
    FakeReceiptRepo,
    FakeTodo,
    FakeTodoRepo as _SlaTodoRepo,
)
from tests.services.test_watch_engine import FakeNotifier, FakeQuoteService, make_rule

NOW = datetime(2026, 7, 21, 10, 30)      # 周二，交易时段内（与场景矩阵同一基准）
ACCOUNT = 'agent_virtual'
SYMBOL = '600519.SH'
SYMBOL_KEY = '600519'                    # normalize_symbol 口径（去交易所后缀）

BELOW_STOP = [{'type': 'price_break', 'params': {'direction': 'below', 'price': 100.0}}]


# ── 假件：出口（通知 / 触发回填 / 待办 / 触发 / 审计）────────────
class _TriggerBackfillRepo:
    """引擎建完待办后回填 watch_triggers.todo_id 的口。"""

    def __init__(self):
        self.backfilled = []

    def set_todo_id(self, trigger_id, todo_id):
        self.backfilled.append((trigger_id, todo_id))


class _Notifier:
    """notify 返回带 id 的触发对象（模拟 notifier._record 落库后的投影）。"""

    def __init__(self, first_trigger_id=7):
        self.notifications = []
        self.trigger_repo = _TriggerBackfillRepo()
        self.governance = []
        self._next = first_trigger_id
        self.last_trigger = None

    def notify(self, rule, condition, quote, result, **kwargs):
        self.notifications.append({'rule_id': rule.id,
                                   'level': kwargs.get('level'),
                                   'disposition': kwargs.get('disposition')})
        trigger = SimpleNamespace(id=self._next, todo_id=None, notified=True)
        self._next += 1
        self.last_trigger = trigger
        return trigger

    def record_only(self, rule, condition, quote, result,
                    disposition=None, disposition_reason=None):
        return SimpleNamespace(id=self._next, notified=False)

    def record_governance(self, rule, reason, detail=None):
        self.governance.append({'rule_id': rule.id, 'reason': reason})


class _TodoRepo:
    """TodoService 的内存仓储：create/list_pending/get/close（终态校验由领域服务做）。"""

    def __init__(self):
        self.rows = []
        self.created = []
        self._seq = 0
        self.close_calls = []

    def create(self, symbol, **kwargs):
        self._seq += 1
        row = SimpleNamespace(id=self._seq, symbol=symbol, terminal=None,
                              close_reason=None, next_condition=None,
                              decision_audit_id=None, closed_by=None,
                              closed_at=None, created_at=NOW, **kwargs)
        self.rows.append(row)
        self.created.append(row)
        return row

    def list_pending(self, level=None, account=None, limit=100,
                     flow_state=None, terminal=None):
        rows = [t for t in self.rows if not t.terminal]
        if level is not None:
            rows = [t for t in rows if str(t.level).upper() == str(level).upper()]
        if account is not None:
            rows = [t for t in rows if t.account == account]
        if flow_state is not None:
            rows = [t for t in rows if str(t.flow_state).upper() == str(flow_state).upper()]
        return rows[:limit]

    def get(self, todo_id):
        for todo in self.rows:
            if todo.id == todo_id:
                return todo
        return None

    def close(self, todo_id, terminal, *, close_reason=None, next_condition=None,
              action_kind=None, decision_audit_id=None, closed_by=None, now=None):
        self.close_calls.append(todo_id)
        todo = self.get(todo_id)
        if todo is None or todo.terminal:
            return None
        todo.terminal = terminal
        todo.close_reason = close_reason
        todo.next_condition = next_condition
        todo.action_kind = action_kind
        todo.decision_audit_id = decision_audit_id
        todo.closed_by = closed_by
        todo.closed_at = now or NOW
        return todo


class _Trigger:
    def __init__(self, trigger_id, triggered_at):
        self.id = trigger_id
        self.triggered_at = triggered_at
        self.detail = {}
        self.disposition = 'pending'
        self.disposition_reason = None
        self.disposition_by = None


class _TriggerRepo:
    """FillSync 侧的触发仓储：处置回写 + detail 合并留痕。"""

    def __init__(self, triggers=()):
        self.triggers = {t.id: t for t in triggers}
        self.dispositions = []
        self.updates = []

    def get_by_id(self, trigger_id):
        return self.triggers.get(trigger_id)

    def update(self, trigger):
        self.updates.append(trigger.id)
        return trigger

    def update_disposition(self, trigger_id, disposition, reason=None, by='agent'):
        trigger = self.triggers.get(trigger_id)
        if trigger is None:
            return None
        trigger.disposition = disposition
        trigger.disposition_reason = reason
        trigger.disposition_by = by
        self.dispositions.append((trigger_id, disposition, reason, by))
        return trigger


class _ChangeRepo:
    """watch_rule_changes 写侧：记录每一次 record 的完整参数。"""

    def __init__(self):
        self.rows = []

    def record(self, rule_id, changed_by, change_kind, before=None, after=None,
               reason='', trigger_id=None, todo_id=None, decision_audit_id=None):
        row = SimpleNamespace(id=len(self.rows) + 1, rule_id=rule_id,
                              changed_by=changed_by, change_kind=change_kind,
                              before=before, after=after, reason=reason,
                              trigger_id=trigger_id, todo_id=todo_id,
                              decision_audit_id=decision_audit_id)
        self.rows.append(row)
        return row


# ── 假件：取数（规则 / 持仓）─────────────────────────────────
class _RuleRepo:
    """组合口：引擎 list_enabled + FillSync/Linkage 的 list_rules /
    set_position_state / update_fields / get_by_id。"""

    def __init__(self, rules):
        self.rules = list(rules)
        self.state_writes = []
        self.field_writes = []

    def list_enabled(self):
        return list(self.rules)

    def list_rules(self, **kwargs):
        return list(self.rules)

    def _get(self, rule_id):
        for rule in self.rules:
            if rule.id == rule_id:
                return rule
        return None

    def get_by_id(self, rule_id):
        return self._get(rule_id)

    def set_position_state(self, rule_id, state):
        rule = self._get(rule_id)
        if rule is None:
            return None
        rule.position_state = state
        self.state_writes.append((rule_id, state))
        return rule

    def update_fields(self, rule_id, **fields):
        rule = self._get(rule_id)
        self.field_writes.append((rule_id, dict(fields)))
        if rule is None:
            return None
        for key, value in fields.items():
            setattr(rule, key, value)
        return rule


class _Quotes:
    """逐标的报价；prev_close 默认在触发线之上（下破 = 新穿越，不触发陈旧驻留治理）。"""

    def __init__(self, prices, prev_close=102.0):
        self.prices = dict(prices)
        self.prev_close = prev_close
        self.calls = []

    def get_realtime_quote(self, symbol):
        self.calls.append(symbol)
        price = self.prices.get(symbol)
        if price is None:
            return None
        return SimpleNamespace(symbol=symbol, price=price,
                               prev_close=self.prev_close, volume=1_000_000,
                               change_pct=None)


class _PositionRepo:
    """持仓真值（键 = 归一化标的口径）；同时喂引擎指令卡与 FillSync。"""

    def __init__(self):
        self.positions = {}
        self.calls = []

    def get_position(self, account, symbol):
        self.calls.append((account, normalize_symbol(symbol)))
        return self.positions.get((account, normalize_symbol(symbol)))

    def put(self, account, symbol, shares_total, avg_cost=100.0):
        self.positions[(account, normalize_symbol(symbol))] = SimpleNamespace(
            account_name=account, symbol=symbol, shares_total=shares_total,
            shares_available=shares_total, avg_cost=avg_cost)

    def clear(self, account, symbol):
        self.positions[(account, normalize_symbol(symbol))] = SimpleNamespace(
            account_name=account, symbol=symbol, shares_total=0,
            shares_available=0, avg_cost=0.0)


# ── 闭环前置：引擎触发 → P0 指令卡 → L3 执行待办 ──────────────
def _exec_rule(id=1, symbol=SYMBOL, account=ACCOUNT, conditions=None):
    """P0 止损规则（默认 below 100），归属账户、有成本价 → 触发即 P0/L3 执行待办。"""
    rule = make_rule(id=id, symbol=symbol, cost_price=100.0,
                     conditions=conditions or BELOW_STOP)
    rule.linked_account = account
    return rule


def _trigger_loop(monkeypatch, rules, prices, account=ACCOUNT, shares=1000):
    """走完整生产链路：引擎 tick → P0 通知 + trigger + L3 待办（指令卡同源挂载）。

    持仓真值显式注入（引擎指令卡与 FillSync 读同一个 fake，不经默认 DB 仓储）。
    """
    rule_repo = _RuleRepo(rules)
    todo_repo = _TodoRepo()
    todo_service = TodoService(todo_repo)
    notifier = _Notifier()
    position_repo = _PositionRepo()
    position_repo.put(account, SYMBOL, shares)
    monkeypatch.setattr(exec_directive_mod, '_POSITION_REPO', position_repo)
    engine = WatchEngine(rule_repo=rule_repo, quote_service=_Quotes(prices),
                         notifier=notifier, now_fn=lambda: NOW,
                         todo_service=todo_service)
    events = engine.tick()
    assert len(todo_repo.created) == 1, '前置：P0 触发应建恰好一条待办'
    todo = todo_repo.created[0]
    assert todo.level == 'P0' and todo.flow_state == 'L3'
    assert todo.action_kind == 'trade'
    assert todo.due_at == NOW + timedelta(seconds=300)
    assert todo.exec_directive is not None, '前置：指令卡应挂载到待办（通知/待办同源）'
    assert notifier.trigger_repo.backfilled == [(todo.trigger_id, todo.id)]
    return SimpleNamespace(engine=engine, rule_repo=rule_repo, todo_repo=todo_repo,
                           todo_service=todo_service, notifier=notifier, events=events,
                           todo=todo, position_repo=position_repo)


def _fill_sync(ctx, trigger_id, **over):
    trigger_repo = _TriggerRepo([_Trigger(trigger_id, triggered_at=NOW)])
    lifecycle = PositionLifecycleService(ctx.rule_repo, ctx.position_repo,
                                         accounts=(ACCOUNT,))
    service = FillSyncService(rule_repo=ctx.rule_repo,
                              todo_service=ctx.todo_service,
                              trigger_repo=trigger_repo, position_repo=ctx.position_repo,
                              lifecycle=lifecycle)
    event = dict(account_name=ACCOUNT, symbol=SYMBOL, action='sell', shares=1000,
                 price=98.5, trade_id=9001, decision_audit_id='audit-9001',
                 filled_at=NOW + timedelta(seconds=120), source='watch_directive')
    event.update(over)
    return service, trigger_repo, event


# ══════════════════════════════════════════════════════════════
# F1. 执行 → 成交回执（FillSync 收敛）
# ══════════════════════════════════════════════════════════════

def test_F1_fill_converges_exec_loop_end_to_end(monkeypatch):
    """P0 止损触发 → agent 卖出 → 成交回执把整条闭环收敛掉。

    证伪点：
      · 待办没收敛成 handled(trade) / 审计号丢失 → 执行闭环断了，L3 只能干等超时；
      · 触发未回写 disposition=handled → 触发侧永远 pending，复盘对不上账；
      · detail.exec 缺时延/成交号 → 执行时延这条观测没了；
      · 持仓态没翻 none / exit 族没收摊 → 已清仓的标的还挂着卖出规则族；
      · 重复成交事件二次收敛/二次写时延 → 幂等破了。
    """
    stop = _exec_rule(id=1)
    take_profit = _exec_rule(id=2)
    take_profit.intent = 'exit_take_profit'          # 不随触发自动退役（收摊留给回执）
    take_profit.conditions = [{'type': 'price_break',
                               'params': {'direction': 'above', 'price': 200.0}}]
    ctx = _trigger_loop(monkeypatch, [stop, take_profit], {SYMBOL: 99.0})
    trigger_id = ctx.todo.trigger_id
    # 止损规则触发即被引擎自动退役（使命完成）；止盈规则仍在役、待回执收摊。
    assert stop.enabled is False and stop.lifecycle_stage == 'closed'
    assert take_profit.enabled is True

    ctx.position_repo.clear(ACCOUNT, SYMBOL)         # 卖出后持仓清零
    service, trigger_repo, event = _fill_sync(ctx, trigger_id)
    out = service.on_fill(event)

    # ① 收敛面：待办终态 handled + trade 动作 + 可核验审计号 + 来源留痕
    assert out['status'] == 'executed'
    assert out['converged_todos'] == [ctx.todo.id]
    todo = ctx.todo
    assert todo.terminal == 'handled'
    assert todo.action_kind == 'trade'
    assert todo.decision_audit_id == 'audit-9001'
    assert todo.closed_by == 'fill_sync'
    assert 'watch_directive' in todo.close_reason and '9001' in todo.close_reason

    # ② 触发面：disposition=handled（by=fill_sync）+ 时延/成交号落 detail.exec
    trigger = trigger_repo.triggers[trigger_id]
    assert trigger.disposition == 'handled'
    assert trigger.disposition_by == 'fill_sync'
    exec_detail = trigger.detail['exec']
    assert exec_detail['trade_id'] == 9001
    assert exec_detail['price'] == 98.5
    assert exec_detail['source'] == 'watch_directive'
    assert exec_detail['latency_sec'] == 120.0       # filled_at - triggered_at

    # ③ 持仓面：该 (账户, 标的) 全部规则状态翻转 none；清仓后 exit 族收摊
    assert out['position_state'] == 'none'
    assert (1, 'none') in ctx.rule_repo.state_writes
    assert (2, 'none') in ctx.rule_repo.state_writes
    assert {row['rule_id'] for row in out['retired_rules']} == {2}
    assert take_profit.enabled is False and take_profit.lifecycle_stage == 'closed'

    # ④ 幂等：同一成交事件再来一次 → 不重复收敛、时延只写一次
    again = service.on_fill(event)
    assert again['converged_todos'] == []
    assert ctx.todo_repo.close_calls == [ctx.todo.id]
    handled_marks = [d for d in trigger_repo.dispositions if d[1] == 'handled']
    assert len(handled_marks) == 1
    assert trigger.detail['exec']['latency_sec'] == 120.0
    assert again['errors'] == []


def test_F1_partial_fill_does_not_converge(monkeypatch):
    """部分成交不算执行：卖出后仍有持仓 → 待办保持未收敛，只回 partial。

    证伪点：部分成交把待办收敛掉 → 剩余仓位敞着却被记「已执行」，止损闭环造假。
    """
    ctx = _trigger_loop(monkeypatch, [_exec_rule(id=1)], {SYMBOL: 99.0})
    ctx.position_repo.put(ACCOUNT, SYMBOL, 400)      # 卖后仍剩 400 股
    service, trigger_repo, event = _fill_sync(
        ctx, ctx.todo.trigger_id, shares=600)
    out = service.on_fill(event)

    assert out['status'] == 'partial'
    assert out['converged_todos'] == []
    assert ctx.todo.terminal is None
    trigger = trigger_repo.triggers[ctx.todo.trigger_id]
    assert trigger.disposition == 'pending'
    assert 'exec' not in trigger.detail


# ══════════════════════════════════════════════════════════════
# F2. 不执行 → 改规则（rule-change 留痕）
# ══════════════════════════════════════════════════════════════

def test_F2_decline_closes_ignored_and_linkage_leaves_audit_trail(monkeypatch):
    """P0 触发后 agent 判「不执行」：待办 ignored(rule_change) + 处置卡动作项
    落地为规则真更新 + 一条带三链溯源的 watch_rule_changes。

    证伪点：
      · 待办终态不是 ignored/rule_change → 与 F1 的执行收敛混成一种结局；
      · 审计行缺 trigger_id/todo_id/审计号 → 「卡上说的处置」与「库里的变更」对不上账；
      · 规则阈值没真改 → 只写审计不改规则 = 假动作；
      · 规则本体 ops_notes 没有注记 → 复盘要反查审计表才能看见规则被动过。
    """
    rule = _exec_rule(id=1, account='user_main_simulation')
    ctx = _trigger_loop(monkeypatch, [rule], {SYMBOL: 99.0},
                        account='user_main_simulation')
    todo, directive = ctx.todo, ctx.todo.exec_directive
    # 用户账户：引擎不代改规则，转治理注记（规则保持原样等 agent 来确认）
    assert ctx.notifier.governance, '用户账户止损触发应留治理注记'
    assert rule.enabled is True

    # ① 不执行：待办收敛为 ignored + rule_change 动作（L3 动作必须带审计号）
    closed = ctx.todo_service.close(
        todo.id, 'ignored', close_reason='阈值太紧，盘中噪音反复触发',
        next_condition='价格有效跌破 95 元再重新评估止损',
        action_kind='rule_change', decision_audit_id='audit-42', closed_by='agent')
    assert closed.terminal == 'ignored' and closed.action_kind == 'rule_change'

    # ② 改规则：处置卡动作项落地（同源指令卡直接喂 linkage，调用方不拼装溯源 id）
    change_repo = _ChangeRepo()
    linkage = RuleChangeLinkage(ctx.rule_repo, change_repo, now_fn=lambda: NOW)
    outcome = linkage.apply_for_decline(
        directive, RuleChangeAction.ADJUST_THRESHOLD,
        reason='处置卡：不执行止损，阈值调出噪音带',
        params={'price': 95.0, 'direction': 'below'}, decision_audit_id='audit-42')
    assert outcome.change_kind == 'threshold'

    # ③ 真更新：价格线 100 → 95（审计 before/after 各留一份快照）
    assert rule.conditions[0]['params']['price'] == 95.0
    change = change_repo.rows[0]
    assert change.before['conditions'][0]['params']['price'] == 100.0
    assert change.after['conditions'][0]['params']['price'] == 95.0

    # ④ 三链溯源：trigger_id / todo_id / decision_audit_id 与触发血缘逐一相等
    assert change.trigger_id == directive.trigger_id == todo.trigger_id
    assert change.todo_id == directive.todo_id == todo.id
    assert change.decision_audit_id == 'audit-42'
    assert change.reason and change.changed_by == 'agent'

    # ⑤ 规则本体注记（详情页直接可见，不必先反查审计表）
    note = rule.ops_notes[-1]
    assert note['by'] == LINKAGE_NOTE_SOURCE
    assert note['trigger_id'] == todo.trigger_id
    assert '调阈值' in note['text']

    # 与 F1 的留痕差异：无成交回执（触发无 exec detail）、无 handled 处置
    assert todo.terminal == 'ignored'
    assert todo.decision_audit_id == 'audit-42'


def test_F2_l3_rule_change_without_audit_is_rejected(monkeypatch):
    """L3 待办以 rule_change 关闭必须带 decision_audit_id（I4：动作必须可核验）。

    证伪点：能裸关 → 「改规则」这条处置动作没有审计凭据，留痕链断裂。
    """
    ctx = _trigger_loop(monkeypatch, [_exec_rule(id=1)], {SYMBOL: 99.0})
    with pytest.raises(WatchTodoMissingAudit):
        ctx.todo_service.close(
            ctx.todo.id, 'ignored', close_reason='不想动',
            next_condition='回到 100 元上方再看',
            action_kind='rule_change', closed_by='agent')
    assert ctx.todo.terminal is None, '被拒后待办不得处于终态'


# ══════════════════════════════════════════════════════════════
# F3. 超时 → SLA 升级（L1→L2→L3 晋升链 + timeout 回执 + 幂等 + 再催）
# ══════════════════════════════════════════════════════════════

def _sla_job(todos, monkeypatch=None):
    todo_repo = _SlaTodoRepo(todos)
    receipt_repo = FakeReceiptRepo()
    sent = []
    receipts = ReceiptService(receipt_repo, sender=lambda payload: sent.append(payload))
    job = WatchSlaJob(todo_repo, receipts)
    return job, todo_repo, receipt_repo, sent


def test_F3_promote_chain_l1_to_l3_sends_nothing():
    """低级别待办走完整机械晋升链 L1→L2→L3：全程不发卡（晋升是状态机迁移，
    不是市场事实），due 每级顺延 30min 防收盘三连升。

    证伪点：晋升发了卡 → 回执收敛口径（一待办生命周期卡片 ≤2）破了；
    due 不顺延 → 同一分钟三连升，一分钟刷三张卡。
    """
    job, todo_repo, receipt_repo, sent = _sla_job([])
    todo = FakeTodo(id=1, level='P2', flow_state='L1',
                    due_at=NOW - timedelta(minutes=1), escalate_count=0,
                    owner_kind='user', owner_ref='user')
    todo_repo.rows[1] = todo

    stats = job.run_once(NOW)
    assert stats['promoted'] == 1 and stats['timeout'] == 0 and stats['alerts'] == 0
    assert todo.flow_state == 'L2'
    assert todo.due_at == NOW - timedelta(minutes=1) + timedelta(minutes=30)

    stats = job.run_once(NOW + timedelta(minutes=31))
    assert stats['promoted'] == 1 and stats['timeout'] == 0
    assert todo.flow_state == 'L3'
    assert todo.due_at == NOW + timedelta(minutes=59)   # 10:59 + 30min 顺延
    assert todo.escalate_count == 2              # 两次晋升各计一次（仓储口径）
    assert sent == [] and receipt_repo.rows == [], '晋升链不得发任何卡'


def test_F3_timeout_escalates_l3_with_receipt_idempotent_then_reminds(monkeypatch):
    """P0 待办在 L3 超时无人处置：timeout 回执升级给本人 → 同 due 周期幂等 →
    到点再催（R1/R2 轮，digest 带轮次标签 ≠ 复读）。

    证伪点：
      · timeout 回执没落 risk_stop 频道/没送达 → 超时升级链断在最后一环；
      · 同 due 周期重复巡检重发 → 超时卡复读（2026-10-16 生产事故回潮）；
      · 首催后再到点不重催 → 「L3 一生只催一次」的僵尸待办回潮；
      · 升级改了待办终态 → 把敞着钱的止损记成「已处理」（RFC §2.1.3 明令禁止）。
    """
    monkeypatch.setenv('WATCH_L3_REMIND_INTERVAL_SEC', '600')   # 10min/轮，便于回放
    job, todo_repo, receipt_repo, sent = _sla_job([], monkeypatch)
    # P0 由引擎直达 L3（F1 前置的同一形态）：escalate_count 从 0 起算，轮次即计数
    todo = FakeTodo(id=1, level='P0', flow_state='L3',
                    due_at=NOW - timedelta(minutes=5), escalate_count=0,
                    owner_kind='user', owner_ref='user')
    todo_repo.rows[1] = todo

    # ① L3 超时：timeout 回执送达本人（P0 → risk_stop 频道），escalate_count 0→1，
    #    due 不得顺延（顺延会轮换幂等键 → 复读）
    stats = job.run_once(NOW)
    assert stats['timeout'] == 1 and stats['alerts'] == 1 and stats['promoted'] == 0
    assert todo.escalate_count == 1 and todo.due_at == NOW - timedelta(minutes=5)
    assert todo.terminal is None, '超时是状态不是终态'
    payload = sent[-1]
    assert payload['kind'] == 'timeout' and payload['os_channel'] == 'risk_stop'
    assert '已超时' in payload['message']
    rows = [r for r in receipt_repo.rows if r['kind'] == 'timeout']
    assert len(rows) == 1 and rows[0]['channel'] == 'risk_stop'
    assert rows[0]['delivery_status'] == 'sent'

    # ② 幂等：同一 due 周期再巡检 → 整段跳过（不重发、不计数、不重复催）
    stats = job.run_once(NOW)
    assert stats['duplicates'] == 1 and stats['timeout'] == 0 and stats['reminds'] == 0
    assert len(sent) == 1 and len(receipt_repo.rows) == 1
    assert todo.escalate_count == 1

    # ③ 再催 R1：超 remind_interval（10min）且未达上限 → 第 1 轮催办
    stats = job.run_once(NOW + timedelta(minutes=11))      # 超时 16min ≥ 600s×1
    assert stats['reminds'] == 1 and stats['timeout'] == 1
    assert todo.escalate_count == 2
    assert len(sent) == 2 and len(receipt_repo.rows) == 2
    assert sent[-1]['kind'] == 'timeout' and sent[-1]['os_channel'] == 'risk_stop'

    # ④ 再催 R2：超时 26min ≥ 600s×2 → 第 2 轮；此后达上限（默认 3 轮）停催
    stats = job.run_once(NOW + timedelta(minutes=21))
    assert stats['reminds'] == 1 and todo.escalate_count == 3
    assert len(sent) == 3 and len(receipt_repo.rows) == 3
    stats = job.run_once(NOW + timedelta(minutes=31))
    assert stats['reminds'] == 0 and stats['timeout'] == 0
    assert len(sent) == 3 and todo.escalate_count == 3
    assert todo.terminal is None


def test_F3_p2_timeout_only_ledgered_without_disturbing():
    """P2 超时只落台账不发送（deliver=False，日终汇总点名）。

    证伪点：P2 也推卡 → 低级别噪音照样打扰用户，超时升级的差异分级没了；
    未发送却记 sent → 假成功，日终汇总会漏掉这条滞留。
    """
    job, todo_repo, receipt_repo, sent = _sla_job([])
    todo = FakeTodo(id=2, level='P2', flow_state='L3',
                    due_at=NOW - timedelta(minutes=5), escalate_count=0,
                    owner_kind='user', owner_ref='user')
    todo_repo.rows[2] = todo

    stats = job.run_once(NOW)

    assert stats['timeout'] == 1 and stats['timeout_suppressed'] == 1
    assert stats['alerts'] == 0 and sent == []
    rows = [r for r in receipt_repo.rows if r['kind'] == 'timeout']
    assert len(rows) == 1
    assert rows[0]['delivery_status'] == 'log_only', '未发送必须如实记 log_only，不假装已发'
    assert rows[0]['channel'] == 'risk_stop'   # timeout=升级给本人，频道随回执类型走
    assert todo.terminal is None


# ══════════════════════════════════════════════════════════════
# G1. 频率调度 × G2. 持仓状态门（闭环的两道前置门）
# ══════════════════════════════════════════════════════════════

class _Clock:
    """可控引擎时钟（now_fn 无参可调用）。"""

    def __init__(self, at=NOW):
        self.at = at

    def __call__(self):
        return self.at

    def advance(self, seconds):
        self.at = self.at + timedelta(seconds=seconds)
        return self.at


def test_G1_rule_interval_defers_evaluation_until_due():
    """interval_sec 未到期的规则：本拍不取价、不评估（跟随全局档的规则不受影响的
    可证伪对照）。

    证伪点：
      · 未到期也取价 → 频率调度没接进到期门，interval_sec 形同虚设；
      · 到期后仍不评估 → 调度门变成永久跳过，规则静默失联。
    """
    interval_rule = make_rule(id=1, symbol='600519.SH')
    interval_rule.interval_sec = 600
    follow_rule = make_rule(id=2, symbol='600036.SH')   # 未设 interval → 跟随全局档
    quotes = _Quotes({'600519.SH': 101.0, '600036.SH': 101.0}, prev_close=99.0)
    # prev_close 在触发线之下：上破 100 = 新穿越（不触发陈旧驻留治理）
    clock = _Clock()
    engine = WatchEngine(rule_repo=_RuleRepo([interval_rule, follow_rule]),
                         quote_service=quotes, notifier=FakeNotifier(),
                         now_fn=clock)
    # 稳态前置：interval 规则上一拍刚判过（调度缓存非空 = 不是「首拍全部到期」）
    engine.state.schedule.mark_evaluated(1, NOW)
    engine.state.schedule.set_next_due(1, NOW + timedelta(seconds=600), 600)

    engine.tick()
    assert 1 not in engine.state.schedule.last_eval_at or \
        engine.state.schedule.last_eval_at[1] == NOW, '未到期不应消耗一拍'
    assert quotes.calls == ['600036.SH'], '未到期规则不应取价：%s' % quotes.calls
    assert [n[0] for n in engine.notifier.notifications] == [2], \
        '跟随档规则应照常评估并通知'

    clock.advance(590)
    engine.tick()
    assert '600519.SH' not in quotes.calls[1:], '590s < 600s 仍未到期：%s' % quotes.calls

    clock.advance(20)                                  # 累计 610s > 600s → 到期
    events = engine.tick()
    assert '600519.SH' in quotes.calls[2:]
    assert engine.state.schedule.last_eval_at[1] is not None
    assert any(isinstance(e, dict) and e.get('rule_id') == 1 for e in events), \
        '到期后 interval 规则应恢复评估'


def test_G2_position_state_gate_blocks_entry_but_never_blocks_stop():
    """持仓状态门叠加闭环：holding 时 entry 规则取价之前被跳过（已有仓位不再喊
    建仓、不会再派建仓待办）；exit_stop 对滞后的 'none' 状态 fail-open 照常触发，
    并落 state_mismatch 事件留痕。

    证伪点：
      · entry 规则被取价/触发 → 状态门没拦在取价之前，holding 又喊一遍建仓；
      · 止损被 'none' 状态吞掉 → 状态滞后静默跳过止损 = 资损风险；
      · 触发了却无 state_mismatch 事件 → 滞后状态无留痕，复盘看不出状态口径异常。
    """
    entry = make_rule(id=1, symbol='600519.SH')
    entry.intent = 'entry'
    entry.action_hint = {'trigger_level': 'L1', 'action_on_trigger': 'buy'}
    entry.linked_account = ACCOUNT
    entry.position_state = 'holding'                   # 已持仓：entry 族应被跳过
    stop = _exec_rule(id=2, symbol='600036.SH',
                      conditions=[{'type': 'price_break',
                                   'params': {'direction': 'below', 'price': 40.0}}])
    stop.position_state = 'none'                       # 滞后：其实已持仓（尚未翻转）
    notifier = FakeNotifier()
    quotes = _Quotes({'600519.SH': 101.0, '600036.SH': 39.0})
    engine = WatchEngine(rule_repo=_RuleRepo([entry, stop]), quote_service=quotes,
                         notifier=notifier, now_fn=lambda: NOW)

    events = engine.tick()

    # ① entry 规则被状态门拦在取价之前：无报价、无事件、无通知
    assert '600519.SH' not in quotes.calls, 'holding 的 entry 规则不应取价：%s' % quotes.calls
    assert all(getattr(e, 'rule_id', None) != 1 for e in events
               if not isinstance(e, dict))
    # ② 宪法级止损 fail-open：照常取价、照常通知
    assert '600036.SH' in quotes.calls
    assert [n[0] for n in notifier.notifications] == [2]
    # ③ 滞后状态落 state_mismatch 事件（只在真的触发时留痕，fail_open 语义可见）
    mismatches = [e for e in events if isinstance(e, dict)
                  and e.get('kind') == STATE_MISMATCH_EVENT]
    assert len(mismatches) == 1
    assert mismatches[0]['rule_id'] == 2
    assert mismatches[0]['reason'] == MISMATCH_STOP_WITHOUT_HOLDING
    assert mismatches[0]['fail_open'] is True
    assert mismatches[0]['position_state'] == 'none'
