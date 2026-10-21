"""阶段流水线注册表（Pipeline/Chain）契约测试 —— pipeline-refactor 卡。

验收口径（与本卡逐条对应）：
  · 阶段注册表测试：15 个阶段、顺序固定、名字唯一、trace 三态（done/stop/error）；
  · 每条路径 trace 断言：闩锁 / 陈旧驻留 / 环境闸 / 确认核验 / 日上限 / 抑噪 /
    per-rule 市场门 / 通知失败 / 成功 —— 各自停在预期阶段，后续阶段未执行；
  · 15 步与阶段一一对应、无遗漏：`DEFAULT_STAGES` 就是这 15 个；
  · 新增/删除阶段只改注册表：把 engine 模块的 PIPELINE 换成另一条链，引擎入口
    照跑（证明 `_process_condition` 不认识任何具体阶段，tick 骨架无需改）。
  · 阶段指南存在，且逐条说明「加 / 删 / 调」流程。

测试用假件只替换**出口**（notifier / rule_repo / market 快照）；判定与流水线
全部走生产代码。
"""
import importlib
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from qs_watch.application.services.watch_engine.conditions import (
    DEFAULT_DAILY_EMIT_CAP, EvalResult,
)
from qs_watch.application.services.watch_engine.engine import WatchEngine
from qs_watch.application.services.watch_engine.pipeline import (
    DEFAULT_STAGES, PIPELINE, STAGE_REGISTRY, Pipeline, StageRegistry,
    StageResult, TriggerContext,
)
from qs_watch.domain.watch.models import MarketState

NOW = datetime(2026, 7, 21, 10, 30)  # 周二，交易时段内（与场景矩阵同一基准）

#: 15 步的权威顺序（与 `_process_condition` 改造前逐句对应；改表必须同步这里+指南）
EXPECTED_STAGES = (
    'latch',
    'stale_residency',
    'env_gate',
    'confirm_verify',
    'daily_cap',
    'noise_suppress',
    'escalation',
    'disposition',
    'market_gate',
    'dedup',
    'deliver',
    'daily_emit',
    'todo',
    'settle',
    'finalize',
)

GUIDE_PATH = (Path(__file__).resolve().parents[2]
              / 'docs' / 'guides' / 'watch-pipeline-stages.md')


# ── 注册表 / Pipeline 机制（不依赖引擎）──────────────────────
class _StubStage:
    def __init__(self, name, calls, outcome=None, boom=None):
        self.name = name
        self.calls = calls
        self.outcome = outcome
        self.boom = boom

    def run(self, ctx):
        self.calls.append(self.name)
        if self.boom is not None:
            raise self.boom
        return self.outcome


def _bare_ctx():
    return TriggerContext(
        engine=SimpleNamespace(), rule=SimpleNamespace(id=1, symbol='600519.SH'),
        idx=0, cond={'type': 'price_break'}, quote=SimpleNamespace(price=100.0),
        result=SimpleNamespace(triggered=True, value=100.0), now=NOW, events=[])


# ── 引擎路径假件 ─────────────────────────────────────────────
class _RuleRepo:
    def __init__(self, rule):
        self._rule = rule
        self.updates = []

    def list_enabled(self):
        return [self._rule]

    def update_fields(self, rule_id, **fields):
        self.updates.append((rule_id, fields))


class _TriggerRepo:
    def __init__(self):
        self.rows = []

    def record(self, **kwargs):
        row = SimpleNamespace(id=len(self.rows) + 1, **kwargs)
        self.rows.append(row)
        return row


class _Notifier:
    """三条出口分开计数：notify=真通知，record_only=市场门归档，record=suppressed 归档。"""

    def __init__(self, notify_boom=False):
        self.trigger_repo = _TriggerRepo()
        self.notifications = []
        self.record_only_calls = []
        self.governance_calls = []
        self.notify_boom = notify_boom

    def notify(self, rule, condition, quote, result, **kwargs):
        if self.notify_boom:
            raise RuntimeError('push channel down')
        self.notifications.append({'rule_id': rule.id, 'kwargs': kwargs})
        return SimpleNamespace(id=100 + len(self.notifications), notified=True,
                               todo_id=None)

    def record_only(self, rule, condition, quote, result,
                    disposition=None, disposition_reason=None):
        self.record_only_calls.append({'rule_id': rule.id,
                                       'reason': disposition_reason})
        return SimpleNamespace(id=200 + len(self.record_only_calls), notified=False)

    def record_governance(self, rule, reason, detail=None):
        self.governance_calls.append({'rule_id': rule.id, 'reason': reason})


class _StateProvider:
    def __init__(self, state):
        self.state = state

    def get_state(self):
        return self.state


class _MarketWatchSvc:
    def __init__(self, state):
        self.state_provider = _StateProvider(state)

    def scan_market_rules(self, now):
        return {'scanned': 0, 'triggered': 0, 'skipped_no_data': 0, 'evaluated': []}


def _blocked_state():
    return MarketState(
        indices={'000300.SH': {'change_pct': -1.80}},
        sectors={'银行': 0.30, '农林牧渔': -1.20},
        sentiment_score=18.0, advance_decline_ratio=0.30, degraded=[])


def _down_break_cond(price=100.0):
    return {'type': 'price_break',
            'params': {'direction': 'below', 'price': price}}


def _up_break_cond(price=100.0):
    return {'type': 'price_break',
            'params': {'direction': 'above', 'price': price}}


def _rule(**over):
    """默认是「上行突破 + 观察意图」（环境闸不豁免），可按路径覆盖字段。"""
    defaults = dict(
        id=1, symbol='600519.SH', scope='symbol',
        conditions=[_up_break_cond()], cost_price=None, active_window=None,
        intent='trend_observe',
        action_hint={'trigger_level': 'L1', 'action_on_trigger': 'observe'},
        escalation_policy=None, linked_account=None, account='agent_brain',
        lifecycle_stage='watching', created_from=None, next_action_hint=None,
        target=None, review_interval_days=None, review_due_at=None, enabled=True,
        action_params=None, ops_notes=None, noise_state=None, suppress_until=None,
    )
    defaults.update(over)
    return SimpleNamespace(**defaults)


def _stop_rule(**over):
    """持仓保护线（宪法级 + 结构锚点）——用于成功路径 / 市场门 / 通知失败。"""
    defaults = dict(
        scope='position', lifecycle_stage='holding', cost_price=95.0,
        conditions=[_down_break_cond()], intent='exit_stop',
        action_hint={'trigger_level': 'L2', 'action_on_trigger': 'sell'},
        linked_account='agent_virtual',
    )
    defaults.update(over)
    return _rule(**defaults)


def _engine(rule, notifier, state=None, **kw):
    return WatchEngine(
        rule_repo=_RuleRepo(rule), quote_service=SimpleNamespace(
            get_realtime_quote=lambda symbol: None),
        notifier=notifier, now_fn=lambda: NOW,
        market_watch_service=_MarketWatchSvc(state or _blocked_state()),
        **kw)


def _result(triggered=True, value=None, message='条件命中'):
    return EvalResult(triggered=triggered, value=value, distance_ratio=None,
                      message=message)


def _run(rule, *, quote, result, env_gate=None, verify_confirm=False,
         prepare=None, notifier=None, state=None, engine=None):
    notifier = notifier or _Notifier()
    engine = engine or _engine(rule, notifier, state=state)
    if prepare is not None:
        prepare(engine)
    events = []
    res = engine._process_condition(
        rule, 0, rule.conditions[0], quote, result, NOW, events,
        env_gate=env_gate, verify_confirm=verify_confirm)
    return res, events, notifier, engine


def _assert_stopped_at(res, stage):
    assert res.stopped is True, '该路径应终止，实际跑完了整条流水线'
    assert res.stopped_at == stage
    assert res.executed[-1] == stage
    assert res.trace[-1].status == 'stop'
    later = EXPECTED_STAGES[EXPECTED_STAGES.index(stage) + 1:]
    assert not (set(later) & set(res.executed)), '终止后仍有后续阶段被执行'


# ── 0. 注册表：15 步、顺序、唯一 ────────────────────────────
def test_registry_has_exactly_fifteen_stages_in_documented_order():
    assert len(DEFAULT_STAGES) == 15
    assert STAGE_REGISTRY.names == EXPECTED_STAGES
    assert PIPELINE.stage_names == EXPECTED_STAGES
    assert len(set(EXPECTED_STAGES)) == 15, '阶段名必须唯一（trace 靠它定位路径）'


def test_registry_rejects_duplicate_stage_names():
    registry = StageRegistry([_StubStage('a', [])])
    with pytest.raises(ValueError, match='重复'):
        registry.register(_StubStage('a', []))


def test_pipeline_runs_stages_in_registration_order():
    calls = []
    pipe = Pipeline([_StubStage(name, calls) for name in ('one', 'two', 'three')])
    ctx = _bare_ctx()
    res = pipe.run(ctx)
    assert calls == ['one', 'two', 'three']
    assert res.executed == ('one', 'two', 'three')
    assert res.statuses() == ('done', 'done', 'done')
    assert res.stopped is False
    assert [e.stage for e in ctx.trace] == ['one', 'two', 'three']


def test_pipeline_stop_is_terminal_and_trace_records_only_executed_stages():
    calls = []
    pipe = Pipeline([
        _StubStage('one', calls),
        _StubStage('guard', calls, StageResult.stop('blocked')),
        _StubStage('never', calls),
    ])
    res = pipe.run(_bare_ctx())
    assert calls == ['one', 'guard']
    assert res.stopped_at == 'guard'
    assert res.stop_reason == 'blocked'
    assert res.executed == ('one', 'guard')
    assert [e.status for e in res.trace] == ['done', 'stop']
    assert res.trace[-1].reason == 'blocked'


def test_stage_exception_is_traced_then_reraised():
    calls = []
    pipe = Pipeline([
        _StubStage('boom', calls, boom=RuntimeError('kaboom')),
        _StubStage('never', calls),
    ])
    ctx = _bare_ctx()
    with pytest.raises(RuntimeError, match='kaboom'):
        pipe.run(ctx)
    assert calls == ['boom']
    assert ctx.trace[-1].stage == 'boom'
    assert ctx.trace[-1].status == 'error'
    assert 'RuntimeError' in ctx.trace[-1].reason


# ── 1. 每条终止路径的 trace 断言 ─────────────────────────────
def test_path_latch_stops_at_first_stage():
    rule = _rule()
    res, events, notifier, _ = _run(
        rule, quote=SimpleNamespace(price=101.0, prev_close=98.0),
        result=_result(triggered=False, value=101.0))
    _assert_stopped_at(res, 'latch')
    assert events == []
    assert notifier.notifications == []


def test_path_stale_residency_stops_before_env_gate():
    rule = _rule()
    # 下行破位 100，昨收 99 已在触发侧 → 非今日新穿越（陈旧驻留）
    rule.conditions = [_down_break_cond()]
    res, events, notifier, _ = _run(
        rule, quote=SimpleNamespace(price=99.0, prev_close=99.0),
        result=_result(value=99.0), env_gate=(True, '环境闸拦截：指数暴跌'))
    _assert_stopped_at(res, 'stale_residency')
    assert events == [], '陈旧驻留不进事件流（它不是市场事件）'
    assert notifier.notifications == []


def test_path_env_gate_archives_and_stops():
    rule = _rule()   # 观察意图，不满足止损/保护线豁免
    res, events, notifier, engine = _run(
        rule, quote=SimpleNamespace(price=101.0, prev_close=98.0),
        result=_result(value=101.0), env_gate=(True, '环境闸拦截：指数暴跌'))
    _assert_stopped_at(res, 'env_gate')
    assert len(events) == 1 and events[0]['suppressed'] is True
    assert events[0]['notified'] is False
    assert engine.state.daily_emit_counts == {}, '环境闸拦截不占日配额'


def test_path_confirm_verify_failure_stops():
    rule = _rule()
    verified = SimpleNamespace(passed=False, reason='流动性枯竭',
                               failed_stages=('liquidity',))
    engine = _engine(rule, _Notifier())
    engine.confirm_verify_pipeline = SimpleNamespace(
        verify=lambda symbol, quote=None, now=None: verified)
    res, events, notifier, _ = _run(
        rule, quote=SimpleNamespace(price=101.0, prev_close=98.0),
        result=_result(value=101.0), verify_confirm=True, engine=engine)
    _assert_stopped_at(res, 'confirm_verify')
    assert events and events[0]['false_signal'] is True
    assert notifier.notifications == []


def test_path_daily_cap_stops_after_escalation_is_skipped():
    rule = _rule()

    def _exhaust(engine):
        engine.state.daily_emit_counts[(rule.id, 0)] = (
            NOW.date(), DEFAULT_DAILY_EMIT_CAP)

    res, events, notifier, _ = _run(
        rule, quote=SimpleNamespace(price=101.0, prev_close=98.0),
        result=_result(value=101.0), prepare=_exhaust)
    _assert_stopped_at(res, 'daily_cap')
    assert len(events) == 1 and events[0]['suppressed'] is True
    assert notifier.notifications == []
    assert 'escalation' not in res.executed, '日上限在升级检查之前（原顺序）'


def test_path_noise_suppress_stops():
    rule = _rule(noise_state='suppressed', suppress_until=None)
    res, events, notifier, _ = _run(
        rule, quote=SimpleNamespace(price=101.0, prev_close=98.0),
        result=_result(value=101.0))
    _assert_stopped_at(res, 'noise_suppress')
    assert len(events) == 1 and events[0]['suppressed'] is True
    assert notifier.notifications == []


def test_path_market_gate_archives_and_stops():
    rule = _stop_rule(action_params={'market_gate': {
        'index': '000300.SH', 'max_down_pct': -1.5}})
    res, events, notifier, engine = _run(
        rule, quote=SimpleNamespace(price=99.0, prev_close=102.0),
        result=_result(value=99.0))
    _assert_stopped_at(res, 'market_gate')
    assert notifier.notifications == []
    assert len(notifier.record_only_calls) == 1
    assert notifier.trigger_repo.rows == []      # 市场门走 record_only，不走 suppressed 口
    assert engine.state.daily_emit_counts == {(rule.id, 0): (NOW.date(), 1)}


def test_path_notify_failure_stops_at_deliver_without_latching():
    rule = _stop_rule()
    notifier = _Notifier(notify_boom=True)
    res, events, _, engine = _run(
        rule, quote=SimpleNamespace(price=99.0, prev_close=102.0),
        result=_result(value=99.0), notifier=notifier)
    _assert_stopped_at(res, 'deliver')
    assert events == []
    assert (rule.id, 0) not in engine.state.latched, '未送达不闩锁（下 tick 重试）'
    assert engine.state.daily_emit_counts == {}, '未送达不计数'


def test_path_success_runs_all_fifteen_stages():
    rule = _stop_rule()
    res, events, notifier, engine = _run(
        rule, quote=SimpleNamespace(price=99.0, prev_close=102.0),
        result=_result(value=99.0))
    assert res.stopped is False
    assert res.executed == EXPECTED_STAGES
    assert set(res.statuses()) == {'done'}
    assert res.trace[-1].reason == '', 'finalize 是普通完成，不是终止'
    assert len(notifier.notifications) == 1
    assert len(events) == 1 and events[0]['notified'] is True
    assert engine.state.daily_emit_counts == {(rule.id, 0): (NOW.date(), 1)}
    assert (rule.id, 0) in engine.state.latched


def test_path_env_gate_exempt_continues_to_finalize():
    rule = _stop_rule()
    res, events, notifier, _ = _run(
        rule, quote=SimpleNamespace(price=99.0, prev_close=102.0),
        result=_result(value=99.0),
        env_gate=(True, '环境闸拦截：指数暴跌'))
    assert res.stopped is False
    assert res.executed == EXPECTED_STAGES
    env_entry = res.trace[2]
    assert env_entry.stage == 'env_gate'
    assert env_entry.status == 'done'
    assert env_entry.reason == 'env_gate_exempt'
    assert len(notifier.notifications) == 1
    assert events[0]['env_gate_exempt'] is True
    assert events[0]['env_gate_exempt_reason']


# ── 2. 注册表是唯一装配点：换链不动 engine ──────────────────
def test_engine_entry_is_registry_driven_swap_pipeline_without_touching_engine():
    """把 engine 模块的 PIPELINE 换成任意阶段链，`_process_condition` 照跑。

    证明加/删阶段只需改注册表：engine 入口不认识任何具体阶段，tick 骨架不动。
    """
    engine_module = importlib.import_module(
        'qs_watch.application.services.watch_engine.engine')
    calls = []
    swapped = Pipeline([_StubStage('probe_a', calls),
                        _StubStage('probe_b', calls)])
    original = engine_module.PIPELINE
    engine_module.PIPELINE = swapped
    try:
        rule = _rule()
        engine = _engine(rule, _Notifier())
        res = engine._process_condition(
            rule, 0, rule.conditions[0],
            SimpleNamespace(price=101.0, prev_close=98.0),
            _result(value=101.0), NOW, [])
    finally:
        engine_module.PIPELINE = original
    assert calls == ['probe_a', 'probe_b']
    assert res.executed == ('probe_a', 'probe_b')


# ── 3. 阶段指南：存在且说明加/删/调 ─────────────────────────
def test_stage_guide_exists_and_documents_every_stage_and_maintenance_flow():
    assert GUIDE_PATH.is_file(), '缺阶段维护指南：%s' % GUIDE_PATH
    text = GUIDE_PATH.read_text(encoding='utf-8')
    for name in EXPECTED_STAGES:
        assert name in text, '指南未覆盖阶段 %r（15 步一一对应会漂移）' % name
    for action in ('加阶段', '删阶段', '调流程'):
        assert action in text, '指南缺少「%s」的维护步骤' % action
    assert 'DEFAULT_STAGES' in text, '指南必须指明唯一装配点是 DEFAULT_STAGES'
