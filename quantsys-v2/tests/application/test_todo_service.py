"""TodoService 单测（REQ-c9f899 t5）

覆盖 t5 验收要求的终态校验 + 账户路由边界（service 层，用内存 fake 仓储，不碰 DB）：
  · close：terminal 枚举 / ignored 缺 next_condition / 重复关闭 / L3+trade|rule_change 缺审计；
  · create：策略账户 out_of_scope 拒绝（且不得落库）、空账户数据缺陷照常建、
            autonomy 只允许 autonomous/remind_only（DB CHECK 一致）；
  · claim：不存在 / 已终态 / 正常认领。

为什么用 fake 而不是真库：终态校验是**纯应用层规则**，用 fake 才能精确断言
「拒绝时有没有误写库」（真库测不出"该拒绝却写了一半"）。真库路径由
tests/api/test_watch_todo_routes.py 走真实适配器覆盖。

防漂移：test_port_and_adapter_signatures 用 inspect 比对端口与适配器的参数名——
签名改了（端口加参数忘改适配器）这里必须红。
"""
import inspect
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import pytest

from adapters.outbound.repositories.watch_todo_repository import WatchTodoRepository
from application.services.watch_engine import todo_service as todo_service_module
from application.services.watch_engine.todo_service import TodoService
from domain.watch.ports import (
    IWatchTodoRepository,
    WatchTodoAlreadyClosed,
    WatchTodoInvalidAutonomy,
    WatchTodoInvalidTerminal,
    WatchTodoMissingAudit,
    WatchTodoMissingNextCondition,
    WatchTodoNotFound,
    WatchTodoOutOfScope,
)
from domain.watch.services.owner_router import OwnerRoute

NOW = datetime(2026, 9, 18, 10, 0, tzinfo=timezone.utc)


@dataclass
class FakeTodo:
    """待办记录（属性与 quant.watch_todos 对齐，供 service duck-typed 访问）"""
    id: int
    symbol: str
    rule_id: int = None
    trigger_id: int = None
    account: str = None
    level: str = 'P2'
    flow_state: str = 'L1'
    owner_kind: str = None
    owner_ref: str = None
    autonomy: str = None
    sla_seconds: int = 1800
    due_at: datetime = None
    claimed_at: datetime = None
    closed_at: datetime = None
    terminal: str = None
    close_reason: str = None
    next_condition: str = None
    action_kind: str = None
    decision_audit_id: str = None
    escalate_count: int = 0


class FakeTodoRepo:
    """IWatchTodoRepository 的内存实现（行为对齐适配器契约：失败返回 None / 抛错）"""

    def __init__(self):
        self.rows = {}
        self._seq = 1000
        self.create_calls = []

    def create(self, symbol, *, rule_id=None, trigger_id=None, account=None, level,
               flow_state='L1', owner_kind=None, owner_ref=None, autonomy=None,
               sla_seconds=1800, due_at=None, action_kind=None):
        self._seq += 1
        todo = FakeTodo(id=self._seq, symbol=symbol, rule_id=rule_id,
                        trigger_id=trigger_id, account=account, level=level,
                        flow_state=flow_state, owner_kind=owner_kind, owner_ref=owner_ref,
                        autonomy=autonomy, sla_seconds=sla_seconds, due_at=due_at,
                        action_kind=action_kind)
        self.rows[todo.id] = todo
        self.create_calls.append(todo)
        return todo

    def get(self, todo_id):
        return self.rows.get(todo_id)

    def claim(self, todo_id, owner_ref, *, now=None):
        todo = self.rows.get(todo_id)
        if todo is None or todo.terminal:
            return None
        todo.owner_ref = owner_ref
        todo.claimed_at = now or NOW
        if todo.flow_state == 'L1':
            todo.flow_state = 'L2'
        return todo

    def close(self, todo_id, terminal, *, close_reason=None, next_condition=None,
              action_kind=None, decision_audit_id=None, closed_by=None, now=None):
        todo = self.rows.get(todo_id)
        if todo is None or todo.terminal:
            return None
        todo.terminal = terminal
        todo.closed_at = now or NOW
        todo.close_reason = close_reason
        todo.next_condition = next_condition
        todo.action_kind = action_kind
        todo.decision_audit_id = decision_audit_id
        return todo

    def list_overdue(self, now=None, limit=100):
        cutoff = now or NOW
        rows = [t for t in self.rows.values()
                if t.terminal is None and t.due_at is not None and t.due_at < cutoff]
        return rows[:limit]

    def promote(self, todo_id, to_state, *, escalate_count=None, now=None):
        todo = self.rows.get(todo_id)
        if todo is None or todo.terminal:
            return None
        todo.flow_state = to_state
        todo.escalate_count = (todo.escalate_count + 1 if escalate_count is None
                               else escalate_count)
        return todo

    def list_pending(self, level=None, account=None, limit=100, *, flow_state=None,
                     terminal=None):
        rows = []
        for t in self.rows.values():
            if terminal is None and t.terminal is not None:
                continue
            if terminal not in (None, '*') and t.terminal != terminal:
                continue
            if level and t.level != level:
                continue
            if account and t.account != account:
                continue
            if flow_state and t.flow_state != flow_state:
                continue
            rows.append(t)
        return rows[:limit]


def _seed(repo, **over):
    """造一条未收敛待办（默认 L3/P1，便于测 L3 审计规则）"""
    kwargs = dict(symbol='600150.SH', level='P1', sla_seconds=1800,
                  due_at=NOW + timedelta(minutes=30), account='agent_brain',
                  flow_state='L3')
    kwargs.update(over)
    return repo.create(**kwargs)


@pytest.fixture
def repo():
    return FakeTodoRepo()


@pytest.fixture
def service(repo):
    return TodoService(repo)


# ── 端口 / 装配防漂移 ─────────────────────────────────────────

def test_port_method_set_is_stable():
    """端口方法集固定为 interfaces §2 的 7 个（增删/改名必须显式面对本测试）"""
    assert IWatchTodoRepository.__abstractmethods__ == frozenset(
        {'create', 'get', 'claim', 'close', 'list_overdue', 'promote', 'list_pending'})


def _param_names(func):
    return list(inspect.signature(func).parameters)


def test_implementations_cover_port_and_signatures_match():
    """两个实现都要有端口的每个方法，且**参数名逐一相同**

    注意：本仓适配器是结构化实现（不显式继承端口 ABC，同 watch_runtime_state_repository），
    因此这里用「方法存在 + 签名比对」而不是 isinstance（ABC 不做结构匹配）。
    签名漂移（端口加参数忘改实现）= 静默 TypeError 的温床，必须在这里红。
    """
    for name in IWatchTodoRepository.__abstractmethods__:
        expected = _param_names(getattr(IWatchTodoRepository, name))
        assert callable(getattr(WatchTodoRepository(), name, None)), f'适配器缺 {name}'
        assert callable(getattr(FakeTodoRepo(), name, None)), f'fake 缺 {name}'
        assert _param_names(getattr(WatchTodoRepository, name)) == expected, f'适配器签名 {name}'
        assert _param_names(getattr(FakeTodoRepo, name)) == expected, f'fake 签名 {name}'


# ── create：账户路由 ─────────────────────────────────────────

def test_create_agent_account_autonomous(service, repo):
    todo = service.create('600150.SH', level='P1', sla_seconds=1800,
                          due_at=NOW, account='agent_brain')
    assert todo.owner_kind == 'agent'
    assert todo.owner_ref == 'agent-dh'
    assert todo.autonomy == 'autonomous'


def test_create_user_account_remind_only(service):
    todo = service.create('600150.SH', level='P2', sla_seconds=None, due_at=NOW,
                          account='user_main_simulation')
    assert (todo.owner_kind, todo.owner_ref, todo.autonomy) == ('user', 'user', 'remind_only')


def test_create_strategy_account_rejected_and_not_written(service, repo):
    """策略账户盯盘不介入：拒绝且**不得落库**（其 autonomy=not_applicable 不符 DB CHECK）"""
    with pytest.raises(WatchTodoOutOfScope):
        service.create('600150.SH', level='P1', sla_seconds=1800, due_at=NOW,
                       account='v13_simulation')
    assert repo.create_calls == []
    assert repo.rows == {}


def test_create_empty_account_is_data_defect_but_still_created(service):
    """空账户 = 数据缺陷路径：照常建待办（不阻断闭环），但只提醒、不得下单"""
    todo = service.create('600150.SH', level='P1', sla_seconds=1800, due_at=NOW,
                          account=None)
    assert todo.owner_kind == 'agent'
    assert todo.autonomy == 'remind_only'
    assert todo.account is None
    # 空白字符串与 None 同路（边界）
    todo2 = service.create('600150.SH', level='P1', sla_seconds=1800, due_at=NOW,
                           account='   ')
    assert todo2.autonomy == 'remind_only'


def test_create_default_flow_state_by_level(service):
    """flow_state 缺省派生：P0/P1 → L3（直达 agent）；P2/P3 → L1（先通知）"""
    assert service.create('A', level='P0', sla_seconds=300, due_at=NOW,
                          account='agent_brain').flow_state == 'L3'
    assert service.create('A', level='P1', sla_seconds=1800, due_at=NOW,
                          account='agent_brain').flow_state == 'L3'
    assert service.create('A', level='P2', sla_seconds=None, due_at=NOW,
                          account='agent_brain').flow_state == 'L1'
    assert service.create('A', level='P3', sla_seconds=None, due_at=NOW,
                          account='agent_brain').flow_state == 'L1'


def test_create_explicit_flow_state_wins(service):
    todo = service.create('A', level='P1', sla_seconds=1, due_at=NOW,
                          account='agent_brain', flow_state='l2')
    assert todo.flow_state == 'L2'


def test_create_rejects_non_check_autonomy(service, repo, monkeypatch):
    """防守型兜底：autonomy 不在 DB CHECK 允许集时必须响亮失败，不得改写后落库"""
    monkeypatch.setattr(todo_service_module, 'route_owner',
                        lambda account, policy=None: OwnerRoute(
                            owner_kind='agent', owner_ref='agent-dh',
                            autonomy='not_applicable', is_data_defect=False,
                            out_of_scope=False, reason='构造的非法路由'))
    with pytest.raises(WatchTodoInvalidAutonomy):
        service.create('A', level='P1', sla_seconds=1800, due_at=NOW, account='agent_brain')
    assert repo.create_calls == []


# ── close：四条终态校验 ───────────────────────────────────────

def test_close_invalid_terminal_rejected(service, repo):
    todo = _seed(repo)
    with pytest.raises(WatchTodoInvalidTerminal):
        service.close(todo.id, 'done')
    assert repo.rows[todo.id].terminal is None       # 拒绝即不落终态


def test_close_missing_terminal_rejected(service, repo):
    with pytest.raises(WatchTodoInvalidTerminal):
        service.close(_seed(repo).id, None)


def test_close_ignored_requires_next_condition(service, repo):
    todo = _seed(repo)
    with pytest.raises(WatchTodoMissingNextCondition):
        service.close(todo.id, 'ignored', close_reason='暂不动作')
    assert repo.rows[todo.id].terminal is None
    # 空白 next_condition 等同缺失
    with pytest.raises(WatchTodoMissingNextCondition):
        service.close(todo.id, 'ignored', next_condition='   ')


def test_close_ignored_with_next_condition_ok(service, repo):
    todo = _seed(repo)
    closed = service.close(todo.id, 'ignored', close_reason='幅度不够',
                           next_condition='放量站上 27 再看', action_kind='observe')
    assert closed.terminal == 'ignored'
    assert closed.next_condition == '放量站上 27 再看'
    assert closed.closed_at is not None


def test_close_already_closed_conflicts(service, repo):
    todo = _seed(repo)
    service.close(todo.id, 'handled', action_kind='observe')
    with pytest.raises(WatchTodoAlreadyClosed):
        service.close(todo.id, 'expired')


def test_close_l3_trade_requires_audit(service, repo):
    """I4：L3 用 trade 关闭必须带 decision_audit_id"""
    todo = _seed(repo)
    with pytest.raises(WatchTodoMissingAudit):
        service.close(todo.id, 'handled', close_reason='已减仓', action_kind='trade')
    assert repo.rows[todo.id].terminal is None


def test_close_l3_rule_change_requires_audit(service, repo):
    with pytest.raises(WatchTodoMissingAudit):
        service.close(_seed(repo).id, 'handled', action_kind='rule_change')


def test_close_l3_trade_with_audit_ok(service, repo):
    todo = _seed(repo)
    closed = service.close(todo.id, 'handled', close_reason='已减仓 1/2',
                           action_kind='trade', decision_audit_id='DA-2026-0001')
    assert (closed.terminal, closed.action_kind, closed.decision_audit_id) == (
        'handled', 'trade', 'DA-2026-0001')


def test_close_l3_observe_without_audit_ok(service, repo):
    """只有 trade/rule_change 需要审计；observe 类关单不强制"""
    closed = service.close(_seed(repo).id, 'handled', action_kind='observe')
    assert closed.terminal == 'handled'


def test_close_l2_trade_without_audit_ok(service, repo):
    """审计硬门槛仅对 L3——L2 关单不受 I4 约束"""
    todo = _seed(repo, flow_state='L2')
    closed = service.close(todo.id, 'handled', action_kind='trade')
    assert closed.terminal == 'handled'


def test_close_terminal_is_case_insensitive(service, repo):
    closed = service.close(_seed(repo).id, ' HANDLED ')
    assert closed.terminal == 'handled'


def test_close_not_found(service):
    with pytest.raises(WatchTodoNotFound):
        service.close(999999, 'handled')


def test_close_invalid_terminal_checked_before_lookup(service):
    """先校输入再查库：不存在的 id + 非法 terminal 报 400 语义（invalid terminal）"""
    with pytest.raises(WatchTodoInvalidTerminal):
        service.close(999999, 'nope')


# ── claim ────────────────────────────────────────────────────

def test_claim_not_found(service):
    with pytest.raises(WatchTodoNotFound):
        service.claim(999999, 'agent-dh')


def test_claim_already_closed(service, repo):
    todo = _seed(repo)
    service.close(todo.id, 'handled', action_kind='observe')
    with pytest.raises(WatchTodoAlreadyClosed):
        service.claim(todo.id, 'agent-dh')


def test_claim_moves_l1_to_l2(service, repo):
    todo = _seed(repo, flow_state='L1', level='P2')
    claimed = service.claim(todo.id, 'agent-dh')
    assert claimed.owner_ref == 'agent-dh'
    assert claimed.flow_state == 'L2'
    assert claimed.claimed_at is not None


def test_claim_race_returns_none_becomes_conflict(service, repo):
    """仓储 claim 返回 None（并发抢先收敛）必须映射为冲突，绝不能静默成功"""
    todo = _seed(repo)
    repo.claim = lambda *a, **k: None
    with pytest.raises(WatchTodoAlreadyClosed):
        service.claim(todo.id, 'agent-dh')
