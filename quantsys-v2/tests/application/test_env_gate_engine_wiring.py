"""环境闸 ↔ WatchEngine 接线（2026-10-20，tick 前置全局环境门）

验收口径（与任务卡一致）：
  · tick 前置调用环境门：每 tick 只判一次，复用 60s MarketState 缓存；
  · 环境不达标 → 个股信号**全部只记录不动作**：归档 suppressed 触发 + 日志，
    不发通知、不进摘要队列、不建待办、不升级/记账、**不占日配额**；
  · per-rule market_gate 保留为加严项：环境闸放行（或数据缺失 fail-open）后，
    规则自己的 market_gate 仍可按更严阈值拦截，且保持原有日计数语义；
  · 叠加语义：两者同时命中时以全局环境闸为准（更早、覆盖面更大），
    market_gate 不重复拦截；
  · 数据缺失 fail-open：无快照 / 取数异常 / 三维全 skipped 一律放行，
    绝不用「没数据」当事实拦信号（R-013）。

测试用假件只替换**出口与取数**（notifier / quote / state_provider），
判定与流水线全部走生产代码。
"""
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from qs_watch.application.services.watch_engine.engine import WatchEngine
from qs_watch.application.services.watch_engine.environment_gate_service import (
    EnvironmentGatePolicy,
    EnvironmentGateService,
)
from qs_watch.domain.watch.models import MarketState

NOW = datetime(2026, 7, 21, 10, 30)  # 周二，交易时段内（与场景矩阵同一基准）


# ── 假件 ────────────────────────────────────────────────────
class _RuleRepo:
    def __init__(self, rules):
        self._rules = list(rules)
        self.updates = []

    def list_enabled(self):
        return list(self._rules)

    def update_fields(self, rule_id, **fields):
        self.updates.append((rule_id, fields))


class _QuoteService:
    def __init__(self, prices):
        self.prices = dict(prices)
        self.calls = []

    def get_realtime_quote(self, symbol):
        self.calls.append(symbol)
        price = self.prices.get(symbol)
        if price is None:
            return None
        # prev_close=98：101 上破 100 属「今日新穿越」，不触发陈旧驻留分支
        return SimpleNamespace(symbol=symbol, price=price, prev_close=98.0,
                               volume=1_000_000, change_pct=None)


class _TriggerRepo:
    """只实现 _record_suppressed_trigger 用到的 record(...) 归档口。"""

    def __init__(self):
        self.rows = []

    def record(self, **kwargs):
        row = SimpleNamespace(id=len(self.rows) + 1, **kwargs)
        self.rows.append(row)
        return row


class _Notifier:
    """三条出口分开计数：notify=真通知，record_only=市场门归档，record=suppressed 归档。"""

    def __init__(self):
        self.trigger_repo = _TriggerRepo()
        self.notifications = []
        self.record_only_calls = []
        self.governance_calls = []

    def notify(self, rule, condition, quote, result, **kwargs):
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
    def __init__(self, state=None, boom=False):
        self.state = state
        self.boom = boom
        self.calls = 0

    def get_state(self):
        self.calls += 1
        if self.boom:
            raise RuntimeError('market data source down')
        return self.state


class _MarketWatchSvc:
    """引擎侧只用 state_provider；市场级扫描默认空清单（可被子类覆盖）。"""

    def __init__(self, provider, candidates=None):
        self.state_provider = provider
        self._candidates = list(candidates or [])

    def scan_market_rules(self, now):
        return {'scanned': 1, 'triggered': len(self._candidates),
                'skipped_no_data': 0, 'evaluated': list(self._candidates)}


class _TodoService:
    def __init__(self):
        self.created = []

    def create(self, *args, **kwargs):
        self.created.append((args, kwargs))
        return SimpleNamespace(id=1)


class _Ledger:
    def __init__(self):
        self.records = []

    def count_today(self):
        return 0

    def record(self, **kwargs):
        self.records.append(kwargs)


class _RecordOnlyNotifier:
    """只提供 notifier.record_only、没有 trigger_repo 的装配形态（归档退化口）。"""

    def __init__(self):
        self.notifications = []
        self.record_only_calls = []

    def notify(self, rule, condition, quote, result, **kwargs):
        self.notifications.append(rule.id)
        return SimpleNamespace(id=1, notified=True, todo_id=None)

    def record_only(self, rule, condition, quote, result,
                    disposition=None, disposition_reason=None):
        self.record_only_calls.append({'rule_id': rule.id,
                                       'reason': disposition_reason})
        return SimpleNamespace(id=300 + len(self.record_only_calls), notified=False)


# ── 规则 / 快照工厂 ─────────────────────────────────────────
def _rule(id=1, symbol='600519.SH', scope='symbol', action_params=None):
    return SimpleNamespace(
        id=id, symbol=symbol, scope=scope,
        conditions=[{'type': 'price_break',
                     'params': {'direction': 'above', 'price': 100.0}}],
        cost_price=None, active_window=None,
        # 宪法级意图：证明环境闸对**全部**个股信号生效（不因止损豁免）
        intent='exit_stop',
        action_hint={'trigger_level': 'L2', 'action_on_trigger': 'sell'},
        escalation_policy=None, linked_account=None, account='agent_brain',
        lifecycle_stage='watching', created_from=None, next_action_hint=None,
        target=None, review_interval_days=None, review_due_at=None, enabled=True,
        action_params=action_params, ops_notes=None,
        noise_state=None, suppress_until=None,
    )


def _market_rule(id=7):
    return SimpleNamespace(
        id=id, symbol='000001.SH', scope='market',
        conditions=[{'type': 'index_break',
                     'params': {'direction': 'below', 'price': 3900.0},
                     'cooldown_sec': 60}],
        cost_price=None, active_window=None, intent='trend_observe',
        action_hint={'trigger_level': 'L1', 'action_on_trigger': 'observe'},
        escalation_policy=None, linked_account='agent_brain', account='agent_brain',
        lifecycle_stage='watching', created_from=None, next_action_hint=None,
        target=None, review_interval_days=None, review_due_at=None, enabled=True,
        action_params=None, ops_notes=None, noise_state=None, suppress_until=None,
    )


def _blocked_state():
    """三维同时命中：指数暴跌 + 板块无主线 + 资金偏冷。"""
    return MarketState(
        indices={'000300.SH': {'change_pct': -1.80}},
        sectors={'银行': 0.30, '农林牧渔': -1.20},
        sentiment_score=18.0, advance_decline_ratio=0.30, degraded=[],
    )


def _ok_state():
    return MarketState(
        indices={'000300.SH': {'change_pct': 0.60}},
        sectors={'半导体': 2.40, '银行': 0.30},
        sentiment_score=58.0, advance_decline_ratio=1.30, degraded=[],
    )


def _empty_state():
    """三维全缺失：环境闸必须 fail-open（skipped），不得当「环境异常」拦信号。"""
    return MarketState()


def _engine(rules, prices, notifier, provider, clock=None, market_svc=None, **kw):
    clock = clock or {'now': NOW}
    engine = WatchEngine(
        rule_repo=_RuleRepo(rules),
        quote_service=_QuoteService(prices),
        notifier=notifier,
        now_fn=lambda: clock['now'],
        market_watch_service=market_svc or _MarketWatchSvc(provider),
        **kw,
    )
    return engine, clock


# ── 1. 环境不达标：只归档、不通知、不占配额 ─────────────────
def test_blocked_environment_archives_only_and_never_notifies():
    notifier = _Notifier()
    engine, _ = _engine([_rule()], {'600519.SH': 101.0}, notifier,
                        _StateProvider(_blocked_state()))

    events = engine.tick()

    assert notifier.notifications == []
    assert notifier.record_only_calls == []      # 不走市场门归档双通道
    assert len(notifier.trigger_repo.rows) == 1  # 归档恰好一条

    row = notifier.trigger_repo.rows[0]
    assert row.suppressed is True
    assert row.notified is False
    assert row.disposition == 'auto_observed'
    assert str(row.disposition_reason).startswith('环境闸拦截：')
    assert '只记录不动作' in row.disposition_reason

    assert len(events) == 1
    ev = events[0]
    assert ev['rule_id'] == 1 and ev['notified'] is False
    assert ev['suppressed'] is True
    assert ev['disposition'] == 'auto_observed'
    assert ev['trigger_id'] == 1
    assert '环境闸拦截' in ev['disposition_reason']

    # 不占配额：归档不是一次通知，不得写日通知计数
    assert engine.state.daily_emit_counts == {}
    # 闩锁/冷却照常置上：电平保持不每 tick 复读
    assert (1, 0) in engine.state.latched


def test_blocked_environment_archives_every_individual_signal_once():
    """「全部个股信号」：不同标的多条规则都归档；同一条件持续成立只归档一次。"""
    notifier = _Notifier()
    rules = [_rule(id=1, symbol='600519.SH'), _rule(id=2, symbol='600036.SH')]
    engine, _ = _engine(rules, {'600519.SH': 101.0, '600036.SH': 101.0},
                        notifier, _StateProvider(_blocked_state()))

    engine.tick()
    engine.tick()   # 同一 tick 状态：闩锁挡住复读

    assert notifier.notifications == []
    assert [r.rule_id for r in notifier.trigger_repo.rows] == [1, 2]
    assert engine.state.daily_emit_counts == {}


def test_blocked_environment_does_not_create_todo_or_intervention():
    """「不动作」的可证伪面：不建待办、不记账、不退役止损规则。"""
    notifier = _Notifier()
    todo = _TodoService()
    ledger = _Ledger()
    rule = _rule()
    engine, _ = _engine([rule], {'600519.SH': 101.0}, notifier,
                        _StateProvider(_blocked_state()),
                        todo_service=todo, ledger=ledger)

    engine.tick()

    assert notifier.notifications == []
    assert todo.created == []
    assert ledger.records == []
    assert engine.state.interventions_today == 0
    assert engine.state.last_intervention == {}
    # exit_stop 被拦截 = 本次不消费止损线：规则不得被自动退役
    assert engine.rule_repo.updates == []
    assert rule.enabled is True


def test_policy_override_can_tighten_environment_gate():
    """阈值可配：environment_gate_service 注入即生效（-0.8% 在严格策略下拦截）。"""
    notifier = _Notifier()
    state = MarketState(
        indices={'000300.SH': {'change_pct': -0.80}},
        sectors={'半导体': 2.40}, sentiment_score=58.0,
        advance_decline_ratio=1.30, degraded=[])
    strict = EnvironmentGateService(EnvironmentGatePolicy(index_drop_pct=-0.50))
    engine, _ = _engine([_rule()], {'600519.SH': 101.0}, notifier,
                        _StateProvider(state), environment_gate_service=strict)

    engine.tick()

    assert notifier.notifications == []
    assert len(notifier.trigger_repo.rows) == 1


def test_archive_falls_back_to_record_only_when_no_trigger_repo():
    """端口形态退化：只有 notifier.record_only 时归档照常（不丢「只记录」语义）。"""
    notifier = _RecordOnlyNotifier()
    engine, _ = _engine([_rule()], {'600519.SH': 101.0}, notifier,
                        _StateProvider(_blocked_state()))

    events = engine.tick()

    assert notifier.notifications == []
    assert len(notifier.record_only_calls) == 1
    assert str(notifier.record_only_calls[0]['reason']).startswith('环境闸拦截：')
    assert len(events) == 1 and events[0]['notified'] is False
    assert engine.state.daily_emit_counts == {}


def test_archive_failure_does_not_latch_so_next_tick_retries():
    """归档失败 → 不闩锁：环境日也不能让信号静默消失（下 tick 重试）。"""

    class _BrokenRepo:
        def record(self, **kwargs):
            raise RuntimeError('db down')

    class _BrokenNotifier(_Notifier):
        def __init__(self):
            super().__init__()
            self.trigger_repo = _BrokenRepo()

        def record_only(self, *a, **kw):
            raise RuntimeError('db down')

    notifier = _BrokenNotifier()
    engine, _ = _engine([_rule()], {'600519.SH': 101.0}, notifier,
                        _StateProvider(_blocked_state()))

    assert engine.tick() == []
    assert (1, 0) not in engine.state.latched
    assert engine.state.daily_emit_counts == {}


def test_environment_gate_runs_before_individual_signal_evaluation():
    """「tick 前置」的可证伪面：环境闸取数发生在任何个股取价之前。"""
    trace = []

    class _TracingProvider(_StateProvider):
        def get_state(self):
            trace.append('env_gate')
            return super().get_state()

    class _TracingQuotes(_QuoteService):
        def get_realtime_quote(self, symbol):
            trace.append('quote')
            return super().get_realtime_quote(symbol)

    notifier = _Notifier()
    engine = WatchEngine(
        rule_repo=_RuleRepo([_rule()]),
        quote_service=_TracingQuotes({'600519.SH': 101.0}),
        notifier=notifier,
        now_fn=lambda: NOW,
        market_watch_service=_MarketWatchSvc(_TracingProvider(_ok_state())),
    )

    engine.tick()

    assert trace and trace[0] == 'env_gate'
    assert 'quote' in trace
    assert len(notifier.notifications) == 1


def test_engine_consumes_check_tuple_style_gate():
    """兼容环境闸文档推荐的消费方式：check(state) -> (blocked, reason)。"""

    class _TupleGate:
        def check(self, state):
            return True, '环境闸拦截：stub——本次信号只记录不动作'

    notifier = _Notifier()
    engine, _ = _engine([_rule()], {'600519.SH': 101.0}, notifier,
                        _StateProvider(_ok_state()),
                        environment_gate_service=_TupleGate())

    engine.tick()

    assert notifier.notifications == []
    assert len(notifier.trigger_repo.rows) == 1
    assert 'stub' in notifier.trigger_repo.rows[0].disposition_reason


# ── 2. fail-open：没有数据 ≠ 环境异常 ───────────────────────
def test_missing_environment_data_fails_open_and_notifies():
    notifier = _Notifier()
    engine, _ = _engine([_rule()], {'600519.SH': 101.0}, notifier,
                        _StateProvider(_empty_state()))

    events = engine.tick()

    assert len(notifier.notifications) == 1
    assert notifier.trigger_repo.rows == []
    assert events[0]['notified'] is True


def test_state_provider_failure_fails_open_and_notifies():
    notifier = _Notifier()
    engine, _ = _engine([_rule()], {'600519.SH': 101.0}, notifier,
                        _StateProvider(boom=True))

    engine.tick()

    assert len(notifier.notifications) == 1
    assert notifier.trigger_repo.rows == []


def test_no_market_watch_service_fails_open_and_notifies():
    """未装配市场状态端口（旧装配/单测路径）：环境闸不得凭空拦截。"""
    notifier = _Notifier()
    engine = WatchEngine(
        rule_repo=_RuleRepo([_rule()]),
        quote_service=_QuoteService({'600519.SH': 101.0}),
        notifier=notifier,
        now_fn=lambda: NOW,
    )
    engine.tick()
    assert len(notifier.notifications) == 1


def test_environment_gate_exception_fails_open(monkeypatch):
    """环境闸自身故障不得让盯盘全体失明：判定异常 → 放行。"""

    class _BoomGate:
        def evaluate(self, state):
            raise RuntimeError('gate bug')

    notifier = _Notifier()
    engine, _ = _engine([_rule()], {'600519.SH': 101.0}, notifier,
                        _StateProvider(_ok_state()),
                        environment_gate_service=_BoomGate())

    engine.tick()

    assert len(notifier.notifications) == 1


# ── 3. per-rule market_gate 保留为加严项 ────────────────────
def test_market_gate_still_tightens_when_environment_ok():
    """环境正常（环境闸放行）→ 规则自己的 market_gate 仍按更严阈值拦截。

    存量语义保持不变：只落触发不通知 + 日计数照常（per-rule 加严项）。
    """
    notifier = _Notifier()
    rule = _rule(action_params={'market_gate': {
        'index': '000300.SH', 'max_up_pct': 0.50}})
    engine, _ = _engine([rule], {'600519.SH': 101.0}, notifier,
                        _StateProvider(_ok_state()))

    engine.tick()

    assert notifier.notifications == []
    assert len(notifier.record_only_calls) == 1
    assert str(notifier.record_only_calls[0]['reason']).startswith('市场门拦截：')
    assert notifier.trigger_repo.rows == []       # 不走 suppressed 归档通道
    assert engine.state.daily_emit_counts == {(1, 0): (NOW.date(), 1)}


def test_market_gate_still_fails_open_when_state_missing():
    """环境闸 fail-open 不改变 market_gate 自己的取数口径（同样 fail-open）。"""
    notifier = _Notifier()
    rule = _rule(action_params={'market_gate': {'max_down_pct': -1.5}})
    engine, _ = _engine([rule], {'600519.SH': 101.0}, notifier,
                        _StateProvider(_empty_state()))
    engine.tick()
    assert len(notifier.notifications) == 1


# ── 4. 叠加语义：全局环境闸优先 ─────────────────────────────
def test_environment_gate_wins_over_market_gate_without_double_archive():
    notifier = _Notifier()
    rule = _rule(action_params={'market_gate': {
        'index': '000300.SH', 'max_down_pct': -1.5}})
    engine, _ = _engine([rule], {'600519.SH': 101.0}, notifier,
                        _StateProvider(_blocked_state()))

    engine.tick()

    assert notifier.notifications == []
    # 只走环境闸的 suppressed 归档；market_gate 不重复落一条
    assert len(notifier.trigger_repo.rows) == 1
    assert str(notifier.trigger_repo.rows[0].disposition_reason).startswith(
        '环境闸拦截：')
    assert notifier.record_only_calls == []
    assert engine.state.daily_emit_counts == {}


def test_environment_gate_applies_even_to_constitutional_stop():
    """「全部个股信号」：宪法级止损信号在环境日同样只归档不通知。"""
    notifier = _Notifier()
    rule = _rule()
    assert rule.intent == 'exit_stop'
    engine, _ = _engine([rule], {'600519.SH': 101.0}, notifier,
                        _StateProvider(_blocked_state()))

    events = engine.tick()

    assert notifier.notifications == []
    assert events[0]['notified'] is False
    assert events[0]['suppressed'] is True


# ── 5. 只拦个股：市场级规则本就是环境信号 ──────────────────
def test_environment_gate_does_not_block_market_scope_rules():
    notifier = _Notifier()
    rule = _market_rule()
    cand = {
        'rule': rule, 'idx': 0, 'cond': rule.conditions[0],
        'result': SimpleNamespace(triggered=True, value=3880.0,
                                  distance_ratio=None, degraded=False,
                                  metric=None, unit=None,
                                  message='指数 000001 3880.00 < 3900.00（阈值）'),
        'quote': SimpleNamespace(symbol='000001.SH', price=3880.0, name=None,
                                 prev_close=None, change_pct=None, volume=None),
    }
    provider = _StateProvider(_blocked_state())
    engine, _ = _engine([rule], {}, notifier, provider,
                        market_svc=_MarketWatchSvc(provider, [cand]))

    events = engine.tick()

    assert len(notifier.notifications) == 1
    assert events and events[0]['rule_id'] == 7 and events[0]['notified'] is True
    assert notifier.trigger_repo.rows == []


# ── 6. 60s MarketState 缓存复用 ─────────────────────────────
def test_market_state_cache_is_shared_by_env_gate_and_market_gate():
    """同 tick 内环境闸与 market_gate 共用一份快照；60s 内跨 tick 不重复取数。"""
    notifier = _Notifier()
    rule = _rule(action_params={'market_gate': {
        'index': '000300.SH', 'max_down_pct': -9.0}})   # 不拦截，只为走取数
    provider = _StateProvider(_ok_state())
    engine, clock = _engine([rule], {'600519.SH': 101.0}, notifier, provider)

    engine.tick()                       # 环境闸取一次，market_gate 读缓存
    assert provider.calls == 1

    clock['now'] = NOW + timedelta(seconds=59)
    engine.tick()                       # 仍在 60s 内
    assert provider.calls == 1

    clock['now'] = NOW + timedelta(seconds=61)
    engine.tick()                       # 缓存过期
    assert provider.calls == 2


def test_blocked_then_recovered_notifies_after_rearm():
    """环境恢复 + 条件回落重臂 → 恢复正常通知（拦截不是永久静音）。"""
    notifier = _Notifier()
    provider = _StateProvider(_blocked_state())
    engine, clock = _engine([_rule()], {'600519.SH': 101.0}, notifier, provider)

    engine.tick()                       # 环境拦截：归档
    assert notifier.notifications == []

    engine.quote_service.prices['600519.SH'] = 99.0
    clock['now'] = NOW + timedelta(minutes=1)
    engine.tick()                       # 回落到阈值下 → 解除闩锁

    provider.state = _ok_state()        # 环境恢复
    engine.quote_service.prices['600519.SH'] = 101.0
    clock['now'] = NOW + timedelta(minutes=6)   # 越过 300s 冷却窗
    engine.tick()

    assert len(notifier.notifications) == 1
    assert len(notifier.trigger_repo.rows) == 1  # 环境日的归档仍在（审计不丢）
