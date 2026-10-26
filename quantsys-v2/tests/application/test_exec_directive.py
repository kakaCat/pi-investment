"""P0 执行指令卡（卡 `exec-directive-card`，RFC 017 §2.1.2）验收测试。

三条判据逐条对应本文件的测试分组：

  0. **指令构造器单测**（`TestBuildDirective`）：P0 止损 / 止盈 / 非止损 / 缺账户 /
     缺持仓，外加 T+1 锁仓、持仓读失败（fail-open）、期限口径、id 回填。
     构造器是纯函数，这一组**不碰 DB、不碰引擎**（持仓真值当参数传入），
     所以它能在任何环境跑红/跑绿。
  1. **流水线注入**（`TestPipelineInjection`）：15 阶段注册表不变（不新增阶段）、
     DeliverStage 是唯一构造点（构造 1 次）、通知与待办读**同一个对象**、
     事件带 structured payload。
  2. **动作项是结构化枚举**（`TestActionItemsAreEnums`）：三态处置动作项的字段
     全是枚举/布尔，payload 里没有自由文本文案；文案只在渲染时由枚举派生。

可失败性（每条都能被改坏证伪）：
  · 把 qty 改成 shares_total → T+1 用例红；
  · 把「读失败」当成「没持仓」→ degraded 用例红（executable 必须为 True）；
  · 把超时写成 terminal='expired' → 三态枚举用例红；
  · 在 TodoStage 里二次构造指令 → 构造计数用例红；
  · 新增一个阶段 → 15 阶段注册表用例红。
"""
import json
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from qs_watch.application.services.watch_engine.engine import WatchEngine
from qs_watch.application.services.watch_engine.exec_directive import (
    DEFAULT_EXEC_SLA_MIN, EXEC_SLA_ENV, ExecAction, ExecSide, ExecState,
    NotExecutableReason, PositionFacts, TodoActionKind, TodoTerminal,
    build_exec_directive, exec_sla_minutes, is_exec_directive_intent,
    read_position_facts, render_action_item,
)
from qs_watch.application.services.watch_engine.notifier import WatchNotifier
from qs_watch.application.services.watch_engine.pipeline import (
    DEFAULT_STAGES, PIPELINE, STAGE_REGISTRY,
)
from qs_watch.application.services.watch_engine.pipeline import stages as stages_mod
from qs_watch.application.services.watch_engine.todo_service import TodoService
from tests.services.test_watch_engine import FakeQuoteService, FakeRepo, make_rule

NOW = datetime(2026, 7, 21, 10, 30)      # 周二，交易时段内（与场景矩阵同一基准）
PRICE_UP = {'600519.SH': 101.0}

#: 15 阶段权威顺序（与 `pipeline.DEFAULT_STAGES`/维护指南一致；本卡不得改动）
EXPECTED_STAGES = (
    'latch', 'stale_residency', 'env_gate', 'confirm_verify', 'daily_cap',
    'noise_suppress', 'escalation', 'disposition', 'market_gate', 'dedup',
    'deliver', 'daily_emit', 'todo', 'settle', 'finalize',
)


# ── 假件（只替换出口/仓储，判定与流水线走生产代码）──────────────────────────
def _rule(**over):
    """完整规则对象（字段与真实 ORM 同构；默认 P0 止损 + 有归属账户）。"""
    base = make_rule(id=119, symbol='600519.SH', cost_price=28.0)
    base = SimpleNamespace(**{**vars(base), **dict(
        intent='exit_stop', linked_account='agent_brain', account='agent_brain',
        scope='position', lifecycle_stage='holding',
        action_params=None, noise_state=None, suppress_until=None, ops_notes=None,
        next_action_hint='旧指引',
    )})
    for key, value in over.items():
        setattr(base, key, value)
    return base


def _quote(price=26.57, name='中铝国际'):
    return SimpleNamespace(symbol='600519.SH', price=price, prev_close=28.0,
                           change_pct=None, name=name)


def _result(message='现价 26.57 下破止损线 26.88', value=26.57, triggered=True):
    return SimpleNamespace(message=message, value=value, metric=None,
                           triggered=triggered, distance_ratio=None)


def _directive(**over):
    params = dict(rule=_rule(), level='P0', now=NOW, trigger_price=26.57,
                  position=PositionFacts(shares_total=1000, shares_available=1000,
                                         avg_cost=28.0),
                  position_read='ok')
    params.update(over)
    return build_exec_directive(**params)


class _Facade:
    """记录型通知门面（不触网，暴露传给 facade 的真实 kwargs）。"""

    def __init__(self):
        self.calls = []

    def send_watch_triggered(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(success=True)


class _TriggerRepo:
    def __init__(self):
        self.rows = []

    def record(self, **kwargs):
        row = SimpleNamespace(id=len(self.rows) + 1, **kwargs)
        self.rows.append(row)
        return row


class _Notifier:
    """引擎出口假件：记录 notify 的 kwargs（含 exec_directive），返回落库后的触发。"""

    def __init__(self):
        self.notifications = []
        self.trigger_repo = _TriggerRepo()

    def notify(self, rule, condition, quote, result, **kwargs):
        self.notifications.append({'rule_id': rule.id, 'kwargs': kwargs})
        return SimpleNamespace(id=100 + len(self.notifications), notified=True,
                               todo_id=None)

    def record_only(self, rule, condition, quote, result,
                    disposition=None, disposition_reason=None):
        return SimpleNamespace(id=900, notified=False)

    def record_governance(self, rule, reason, detail=None):
        return None


class _TodoRepo:
    """IWatchTodoRepository 的 create 侧；保留返回对象以便断言指令被挂上。"""

    def __init__(self):
        self.created = []
        self.objects = []

    def create(self, symbol, **kwargs):
        self.created.append(dict(symbol=symbol, **kwargs))
        todo = SimpleNamespace(id=len(self.created), **kwargs)
        self.objects.append(todo)
        return todo


def _engine(rule, notifier, todo_service=None):
    return WatchEngine(
        rule_repo=FakeRepo([rule]), quote_service=FakeQuoteService(PRICE_UP),
        notifier=notifier, now_fn=lambda: NOW, todo_service=todo_service)


# ═══════════════════════════════════════════════════════════════════════════
# 0. 指令构造器单测（纯函数；不碰 DB / 引擎）
# ═══════════════════════════════════════════════════════════════════════════
class TestBuildDirective:
    def test_p0_stop_loss_is_executable_and_uses_available_shares(self):
        """① P0 止损：可执行 + qty = **可卖量**（不是总持仓）+ 期限 = now + SLA。"""
        d = _directive()
        assert d.action is ExecAction.EXECUTE_STOP_LOSS
        assert d.side is ExecSide.SELL
        assert d.executable is True
        assert d.not_executable_reason is None
        assert d.qty == 1000                      # shares_available
        assert d.deadline_at == NOW + timedelta(minutes=DEFAULT_EXEC_SLA_MIN)
        assert d.sla_minutes == DEFAULT_EXEC_SLA_MIN
        assert d.ref_price == 28.0                # 规则成本价优先
        assert d.pnl_pct == -5.11                 # (26.57-28)/28
        assert d.evidence['position_read'] == 'ok'
        assert d.evidence['shares_total'] == 1000
        assert d.rule_id == 119
        assert '止损' in d.card_action_text()
        assert '1000 股' in d.card_action_text()

    def test_p0_take_profit_uses_take_profit_action_not_stop_loss(self):
        """② P0 止盈：动作是止盈，绝不冒充止损。"""
        d = _directive(rule=_rule(intent='exit_take_profit', cost_price=10.0),
                       trigger_price=12.0,
                       position=PositionFacts(500, 500, 10.0))
        assert d.action is ExecAction.EXECUTE_TAKE_PROFIT
        assert d.action is not ExecAction.EXECUTE_STOP_LOSS
        assert d.executable is True
        assert d.qty == 500
        assert d.pnl_pct == 20.0
        assert '止盈' in d.card_action_text()

    def test_p0_reduce_uses_reduce_action(self):
        d = _directive(rule=_rule(intent='exit_reduce'),
                       position=PositionFacts(2000, 1200, 28.0))
        assert d.action is ExecAction.EXECUTE_REDUCE
        assert d.qty == 1200

    @pytest.mark.parametrize('intent', ['entry', 'add_position', 't_trade', 'trend_observe'])
    def test_non_exit_intent_yields_no_execution(self, intent):
        """③ 非止损/非退出类：没有执行动作，也没有执行期限（不是执行卡）。"""
        d = _directive(rule=_rule(intent=intent), position=PositionFacts(1000, 1000, 28.0))
        assert d.action is ExecAction.NONE
        assert d.side is ExecSide.NONE
        assert d.executable is False
        assert d.not_executable_reason is NotExecutableReason.NOT_EXIT_INTENT
        assert d.qty is None
        assert d.deadline_at is None        # 执行期限只适用于可执行指令
        assert d.action_params() is None
        assert is_exec_directive_intent(intent) is False

    @pytest.mark.parametrize('intent', ['exit_stop', 'exit_take_profit', 'exit_reduce'])
    def test_exit_intents_are_exec_directive_intents(self, intent):
        assert is_exec_directive_intent(intent) is True

    def test_missing_account_blocks_execution_but_names_the_defect(self):
        """④ 缺账户：不可执行（数据缺陷），但仍如实产出指令供唤醒去补归属。"""
        d = _directive(rule=_rule(linked_account=None, account=None),
                       account=None, position=None, position_read='degraded')
        assert d.account is None
        assert d.executable is False
        assert d.not_executable_reason is NotExecutableReason.ACCOUNT_UNKNOWN
        assert d.qty is None
        assert d.deadline_at is None
        text = d.card_action_text()
        assert 'linked_account' in text and '勿重试下单' in text

    def test_missing_position_blocks_execution(self):
        """⑤ 缺持仓：确认没持仓 → 不可执行，且明确「无需执行」。"""
        d = _directive(position=None, position_read='missing')
        assert d.executable is False
        assert d.not_executable_reason is NotExecutableReason.NO_POSITION
        assert d.qty is None
        assert '无需执行' in d.card_action_text()

    def test_zero_total_shares_is_no_position(self):
        d = _directive(position=PositionFacts(0, 0, 28.0), position_read='missing')
        assert d.not_executable_reason is NotExecutableReason.NO_POSITION

    def test_t1_locked_when_available_is_zero(self):
        """有总量但可卖 0：不可执行，原因必须是 t1_locked（不能报 no_position）。"""
        d = _directive(position=PositionFacts(1000, 0, 28.0))
        assert d.executable is False
        assert d.not_executable_reason is NotExecutableReason.T1_LOCKED
        assert d.qty is None
        assert d.evidence['shares_total'] == 1000
        assert 'T+1' in d.card_action_text()

    def test_position_read_degraded_stays_executable_and_is_marked(self):
        """读失败 ≠ 没持仓：executable 保持 True（交 agent 核实），evidence 标 degraded。"""
        d = _directive(position=None, position_read='degraded')
        assert d.executable is True
        assert d.not_executable_reason is None
        assert d.qty is None                     # 不臆造数量
        assert d.deadline_at is not None
        assert d.evidence['position_read'] == 'degraded'
        assert '持仓读失败' in d.card_action_text()

    def test_unknown_position_read_state_is_rejected_loudly(self):
        with pytest.raises(ValueError, match='持仓读取状态'):
            _directive(position_read='wat')

    def test_ref_price_falls_back_to_avg_cost_and_never_fabricates(self):
        d = _directive(rule=_rule(cost_price=None),
                       position=PositionFacts(1000, 1000, avg_cost=30.0),
                       trigger_price=33.0)
        assert d.ref_price == 30.0
        assert d.pnl_pct == 10.0
        d2 = _directive(rule=_rule(cost_price=None), position=PositionFacts(1000, 1000, None))
        assert d2.ref_price is None
        assert d2.pnl_pct is None                # 不臆造参考价/盈亏

    def test_sla_env_override_and_invalid_fallback(self):
        assert exec_sla_minutes({}) == DEFAULT_EXEC_SLA_MIN
        assert exec_sla_minutes({EXEC_SLA_ENV: '15'}) == 15
        assert exec_sla_minutes({EXEC_SLA_ENV: '0'}) == DEFAULT_EXEC_SLA_MIN
        assert exec_sla_minutes({EXEC_SLA_ENV: 'abc'}) == DEFAULT_EXEC_SLA_MIN
        d = _directive(sla_minutes=15)
        assert d.deadline_at == NOW + timedelta(minutes=15)
        assert d.sla_minutes == 15
        assert '期限 15 分钟' in d.card_action_text()

    def test_partial_available_says_remaining_shares_not_fully_cleared(self):
        """部分可卖：明说「余 N 股待 T+1 解锁」，不许把「今天能卖」说成「已清仓」。"""
        d = _directive(position=PositionFacts(1000, 300, 28.0))
        assert d.qty == 300
        text = d.card_action_text()
        assert '可卖 300 股' in text
        assert '持仓 1000 股' in text and '余 700 股' in text

    def test_with_ids_fills_trigger_and_todo_without_mutating_source(self):
        d = _directive()
        assert d.trigger_id is None and d.todo_id is None
        d2 = d.with_ids(trigger_id=7)
        assert (d2.trigger_id, d2.todo_id) == (7, None)
        d3 = d2.with_ids(todo_id=42)
        assert (d3.trigger_id, d3.todo_id) == (7, 42)
        assert d.trigger_id is None, '原对象不得被就地修改（frozen 契约）'

    def test_to_dict_is_json_safe_and_complete(self):
        d = _directive().with_ids(trigger_id=7, todo_id=42)
        payload = d.to_dict()
        json.dumps(payload, ensure_ascii=False)          # 必须可 JSON 序列化
        assert set(payload) == {
            'action', 'symbol', 'intent', 'level', 'account', 'side', 'qty',
            'ref_price', 'trigger_price', 'pnl_pct', 'executable',
            'not_executable_reason', 'deadline_at', 'sla_minutes', 'evidence',
            'action_items', 'rule_id', 'trigger_id', 'todo_id'}
        assert payload['action'] == 'execute_stop_loss'
        assert payload['side'] == 'sell'
        assert (payload['trigger_id'], payload['todo_id']) == (7, 42)
        assert payload['deadline_at'] == (NOW + timedelta(minutes=30)).isoformat()

    # ── 唯一的 I/O 包装：三种读结果（用假 repo，不碰 DB）────────────────
    def test_read_position_facts_ok(self):
        repo = SimpleNamespace(get_position=lambda a, s: SimpleNamespace(
            shares_total=1000, shares_available=300, avg_cost=12.5))
        facts, state = read_position_facts('agent_brain', '600519.SH', repo=repo)
        assert state == 'ok'
        assert (facts.shares_total, facts.shares_available, facts.avg_cost) == (1000, 300, 12.5)

    def test_read_position_facts_missing_and_degraded(self):
        repo = SimpleNamespace(get_position=lambda a, s: None)
        assert read_position_facts('agent_brain', '600519.SH', repo=repo) == (None, 'missing')

        def boom(a, s):
            raise RuntimeError('db down')
        assert read_position_facts('agent_brain', '600519.SH',
                                   repo=SimpleNamespace(get_position=boom)) == (None, 'degraded')

    def test_read_position_facts_without_account_never_claims_flat(self):
        """无账户 → degraded（不可知），绝不能返回 missing（= 确认没持仓）。"""
        assert read_position_facts(None, '600519.SH') == (None, 'degraded')
        assert read_position_facts('', '600519.SH') == (None, 'degraded')


# ═══════════════════════════════════════════════════════════════════════════
# 2. 动作项是结构化枚举（不是自由文本）
# ═══════════════════════════════════════════════════════════════════════════
class TestActionItemsAreEnums:
    def test_payload_action_items_are_enums_not_free_text(self):
        payload = _directive().to_dict()
        items = payload['action_items']
        assert len(items) == 4  # 执行/不执行/持有/超时（HOLD 2026-10-22 新增）
        for item in items:
            assert set(item) == {'state', 'terminal', 'action_kind',
                                 'requires_decision_audit', 'requires_next_condition',
                                 'escalate'}
            assert item['state'] in {s.value for s in ExecState}
            assert item['terminal'] in ({t.value for t in TodoTerminal} | {None})
            assert item['action_kind'] in ({k.value for k in TodoActionKind} | {None})
            # 动作项里**没有**任何自由文本字段（文案只在渲染层）
            assert not ({'text', 'label', 'message', 'instruction'} & set(item))
            assert isinstance(item['requires_decision_audit'], bool)
            assert isinstance(item['requires_next_condition'], bool)
            assert isinstance(item['escalate'], bool)

    def test_four_state_mapping_matches_rfc(self):
        """执行→handled/trade；不执行→ignored/rule_change+下次条件；持有→handled/不催办；超时→无终态。

        第四态 HOLD（2026-10-22 用户裁定）：继续持有——关待办、规则有效、
        不催办、不要求下次条件（与 declined 的关键区别）。
        """
        executed, declined, hold, timeout = _directive().action_items
        assert (executed.state, executed.terminal, executed.action_kind) == (
            ExecState.EXECUTED, TodoTerminal.HANDLED, TodoActionKind.TRADE)
        assert executed.requires_decision_audit is True
        assert (declined.state, declined.terminal, declined.action_kind) == (
            ExecState.DECLINED, TodoTerminal.IGNORED, TodoActionKind.RULE_CHANGE)
        assert declined.requires_next_condition is True
        # 持有：terminal=handled 关待办；无动作；要决策审计；不要求下次条件；不催办
        assert (hold.state, hold.terminal, hold.action_kind) == (
            ExecState.HOLD, TodoTerminal.HANDLED, None)
        assert hold.requires_decision_audit is True
        assert hold.requires_next_condition is False
        assert hold.escalate is False
        assert (timeout.state, timeout.terminal, timeout.action_kind) == (
            ExecState.TIMEOUT, None, None)
        assert timeout.escalate is True

    def test_timeout_is_a_state_not_a_terminal_and_never_expired(self):
        """RFC §2.1.3 硬约定：超时不写 expired（把敞着钱的止损记成已处理）。"""
        assert 'expired' not in {t.value for t in TodoTerminal}
        timeout = _directive().action_items[3]
        assert timeout.terminal is None
        assert '不落终态' in render_action_item(timeout)

    def test_guide_text_is_derived_from_enums(self):
        d = _directive()
        guide = d.card_guide_text()
        assert guide.startswith('四态处置：')
        for item in d.action_items:
            assert render_action_item(item) in guide
        assert 'handled' in guide and 'ignored' in guide and '不写 expired' in guide

    def test_card_context_keeps_plan_and_appends_guide(self):
        d = _directive()
        ctx = d.card_context('按宪法第 4 条清仓')
        assert ctx.splitlines()[0] == '按宪法第 4 条清仓'
        assert '四态处置：' in ctx
        assert d.card_context(None).startswith('四态处置：')


# ═══════════════════════════════════════════════════════════════════════════
# 1. 流水线注入（15 阶段不变 / 唯一构造点 / 通知与待办同源）
# ═══════════════════════════════════════════════════════════════════════════
class TestPipelineInjection:
    def test_registry_still_has_fifteen_stages_and_no_exec_stage(self):
        """本卡不新增流水线阶段：注册表逐字不变。"""
        assert len(DEFAULT_STAGES) == 15
        assert STAGE_REGISTRY.names == EXPECTED_STAGES
        assert PIPELINE.stage_names == EXPECTED_STAGES
        assert 'exec_directive' not in STAGE_REGISTRY.names
        assert 'exec' not in STAGE_REGISTRY.names

    def test_deliver_stage_builds_once_and_todo_reads_same_object(
            self, monkeypatch):
        """DeliverStage 构造 1 次；通知与待办拿到同一份 payload（含 id 回填）。"""
        calls = []
        real_build = stages_mod.build_exec_directive

        def spy(**kwargs):
            calls.append(kwargs)
            return real_build(**kwargs)

        monkeypatch.setattr(stages_mod, 'build_exec_directive', spy)
        monkeypatch.setattr(stages_mod, 'read_position_facts',
                            lambda acct, sym: (PositionFacts(1000, 1000, 28.0), 'ok'))
        rule = _rule()
        notifier = _Notifier()
        todo_repo = _TodoRepo()
        engine = _engine(rule, notifier, TodoService(todo_repo))

        events = []
        res = engine._process_condition(
            rule, 0, rule.conditions[0], _quote(), _result(), NOW, events)

        assert res.stopped is False
        assert len(calls) == 1, '指令只能构造一次（通知与待办同源，禁止二次构造）'

        # ① 通知拿到指令
        sent = notifier.notifications[0]['kwargs']
        assert 'exec_directive' in sent
        delivered = sent['exec_directive']
        assert delivered.action is ExecAction.EXECUTE_STOP_LOSS
        assert delivered.qty == 1000

        # ② 待办挂的是同一份 payload（同一 action/qty，trigger_id/todo_id 已回填）
        assert len(todo_repo.objects) == 1
        todo = todo_repo.objects[0]
        attached = todo.exec_directive
        assert attached.action is delivered.action
        assert attached.qty == delivered.qty
        assert attached.trigger_id == 101          # _Notifier 的触发 id
        assert attached.todo_id == todo.id
        assert engine.state is not None

        # ③ 事件里带 structured payload（复盘直接消费，不从文案反解）
        event = events[-1]
        assert event['exec_directive']['action'] == 'execute_stop_loss'
        assert event['exec_directive']['trigger_id'] == 101
        assert event['exec_directive']['todo_id'] == todo.id
        assert [i['state'] for i in event['exec_directive']['action_items']] == [
            'executed', 'declined', 'hold', 'timeout']

    def test_deliver_stage_skips_directive_for_non_exit_intents(self, monkeypatch):
        """非退出类 P0（如 entry）：不构造指令（不覆盖既有指引），也不建执行卡。"""
        monkeypatch.setattr(stages_mod, 'read_position_facts',
                            lambda acct, sym: (None, 'missing'))
        rule = _rule(intent='entry', scope='symbol',
                     action_hint={'trigger_level': 'L2', 'action_on_trigger': 'buy'})
        notifier = _Notifier()
        engine = _engine(rule, notifier, TodoService(_TodoRepo()))

        engine._process_condition(rule, 0, rule.conditions[0], _quote(), _result(),
                                  NOW, [])
        sent = notifier.notifications[0]['kwargs']
        assert 'exec_directive' not in sent

    def test_directive_absent_when_closure_disabled(self, monkeypatch):
        """闭环关闭（未注入 todo_service → 无级别）时不产指令：旧行为保持不变。"""
        monkeypatch.setattr(stages_mod, 'read_position_facts',
                            lambda acct, sym: (PositionFacts(1000, 1000, 28.0), 'ok'))
        rule = _rule()
        notifier = _Notifier()
        engine = _engine(rule, notifier)            # 无 todo_service
        engine._process_condition(rule, 0, rule.conditions[0], _quote(), _result(),
                                  NOW, [])
        assert 'exec_directive' not in notifier.notifications[0]['kwargs']

    def test_market_scope_never_gets_a_position_execution_card(self, monkeypatch):
        """市场/板块级规则的伪标的没有持仓语义：不产执行指令（不误报「这笔该卖」）。"""
        calls = []
        monkeypatch.setattr(stages_mod, 'read_position_facts',
                            lambda acct, sym: (calls.append(sym) or (None, 'missing')))
        rule = _rule(scope='market')
        notifier = _Notifier()
        engine = _engine(rule, notifier, TodoService(_TodoRepo()))
        engine._process_condition(rule, 0, rule.conditions[0], _quote(), _result(),
                                  NOW, [])
        assert 'exec_directive' not in notifier.notifications[0]['kwargs']
        assert calls == [], '市场级规则不该去读个股持仓'


# ═══════════════════════════════════════════════════════════════════════════
# 通知侧渲染（notifier 把同一份指令喂进既有三个落点）
# ═══════════════════════════════════════════════════════════════════════════
class TestNotifierRendering:
    def _notify(self, directive):
        facade = _Facade()
        notifier = WatchNotifier(trigger_repo=None, ws_url=None,
                                 notification_facade=facade)
        rule = _rule(action_params={'action': 'sell', 'observation_criterion': '旧'})
        notifier.notify(rule, rule.conditions[0], _quote(), _result(),
                        disposition='escalated', level='P0',
                        exec_directive=directive)
        assert len(facade.calls) == 1
        return facade.calls[0]

    def test_directive_overrides_next_step_action_block_and_plan(self):
        d = _directive()
        call = self._notify(d)
        assert call['next_action_hint'] == d.card_action_text()
        assert '止损' in call['next_action_hint']
        assert call['action_params']['action'] == 'sell'
        assert call['action_params']['quantity'] == 1000
        assert call['action_params']['reference_price'] == 28.0
        assert call['action_params']['exec_action'] == 'execute_stop_loss'
        assert '四态处置：' in call['context']

    def test_without_directive_rendering_is_unchanged(self):
        """缺省 exec_directive=None：三个落点与改造前逐字一致（硬约束）。"""
        facade = _Facade()
        notifier = WatchNotifier(trigger_repo=None, ws_url=None,
                                 notification_facade=facade)
        rule = _rule(next_action_hint='旧指引', context='按宪法第 4 条清仓',
                     action_params={'action': 'sell'})
        notifier.notify(rule, rule.conditions[0], _quote(), _result(),
                        disposition='escalated', level='P0')
        call = facade.calls[0]
        assert call['next_action_hint'] == '旧指引'
        assert call['action_params'] == {'action': 'sell'}
        assert call['context'] == '按宪法第 4 条清仓'

    def test_blocked_directive_keeps_rule_action_params(self):
        """不可执行指令不拿残缺指令顶替规则自己的结构化指引。"""
        d = _directive(rule=_rule(linked_account=None, account=None),
                       account=None, position=None, position_read='degraded')
        call = self._notify(d)
        assert call['next_action_hint'] == d.card_action_text()
        assert 'linked_account' in call['next_action_hint']
        assert call['action_params'] == {'action': 'sell', 'observation_criterion': '旧'}

    def test_p0_level_template_renders_directive_next_step(self):
        """真模板消费：「下一步」逐字出现指令（通知卡与待办同一个 action 文本）。"""
        from qs_notification.infrastructure.formatters.watch_level_templates import (
            render_watch_variables,
        )

        d = _directive()
        card = render_watch_variables({
            'watch_level': 'P0', 'symbol': '601600', 'name': '中铝国际',
            'price': 26.57, 'message': '现价 26.57 下破止损线 26.88',
            'next_action_hint': d.card_action_text(), 'account': 'agent_brain',
            'rule_id': 119, 'intent': 'exit_stop', 'todo_id': 42,
        })
        content = card['card']['elements'][0]['text']['content']
        assert '下一步' in content
        assert d.card_action_text() in content
        assert '止损' in content
