"""持仓状态门（RFC 017 §2.2 · 卡 `position-state-branch`）—— **tick 层规则级门**。

## 本文件钉住的口径（与交卷判据逐条对应）

| 判据 | 用例 |
|------|------|
| 0 四族 intent × 两状态 | `TestBranchTable`：entry / add_position / exit 族 / 观察类 × none·holding |
| 0 None = 不可知（≠ 'none'） | `TestUnknownState`：NULL / 缺列 / 非法值 / 读口径不可用 一律照常求值 |
| 0 不一致 fail-open + warn + `state_mismatch` 事件 | `TestMismatchObservation`：事件与 warn 同源，且只在真的记录触发时落 |
| 0 与到期门先后 | `TestGateOrdering`：被状态门跳过的规则**不取价、不推进到期时钟**；状态翻转后下一拍立即求值 |
| 1 不改既有语义 | 本文件只走 `WatchEngine.tick()`；场景矩阵与 15 阶段注册表测试另行全绿 |
| 2 fail-open：状态滞后/缺列绝不静默跳过止损 | `TestFailOpen`：exit_stop 对上 'none'（滞后）、读口径异常、缺列 均照常通知 |

## 为什么这样测

状态门回答的是「这条规则这一拍要不要判」，客观证据只能是**外部副作用**：
取价次数（有没有进评估）、`state.schedule.last_eval_at`（有没有消耗一拍）、
通知次数（止损有没有真的被喊出来）。不 mock 门本身、不 import 私有实现里的
中间变量——门实现改了，这里仍按行为判对错。

`tests/services/test_watch_engine.py` 的 `make_rule` 故意不带 `position_state`
（= 旧库缺列），所以场景矩阵那批用例天然走「状态不可知 → 全部求值」的旧行为；
本文件显式补 `position_state`，才是在测分支。
"""
from datetime import datetime, timedelta

import pytest

from qs_watch.application.services.watch_engine import engine as engine_mod
from qs_watch.application.services.watch_engine.engine import (
    MISMATCH_STOP_WITHOUT_HOLDING, MISMATCH_UNREADABLE,
    POSITION_FAMILY_ENTRY, POSITION_FAMILY_EXIT, POSITION_FAMILY_OBSERVE,
    POSITION_STATE_NONE, POSITION_STATE_SKIP_ENTRY_HELD,
    POSITION_STATE_SKIP_EXIT_FLAT, STATE_MISMATCH_EVENT, WatchEngine,
    position_state_family, position_state_verdict, read_rule_position_state,
)
from tests.services.test_watch_engine import FakeNotifier, FakeQuoteService, make_rule

NOW = datetime(2026, 7, 21, 10, 30)      # 周二，交易时段内（与场景矩阵同一基准）
SYMBOL = '600519.SH'
HIT = 101.0                              # 上破 100 → 条件成立
MISS = 99.0                              # 未上破 → 不触发

#: 四族 intent（与 disposition 的意图枚举同源，不新造值）。
ENTRY_INTENTS = ('entry', 'add_position')
EXIT_INTENTS = ('t_trade', 'exit_stop', 'exit_take_profit', 'exit_reduce')
OBSERVE_INTENTS = ('trend_observe',)

#: 旧库缺列（属性不存在）的哨兵：与显式 NULL 是两种事实，都要测。
_UNSET = object()


class _Clock:
    """可控引擎时钟（now_fn 无参可调用）。"""

    def __init__(self, at: datetime = NOW):
        self.at = at

    def __call__(self) -> datetime:
        return self.at

    def advance(self, seconds: float) -> datetime:
        self.at = self.at + timedelta(seconds=seconds)
        return self.at


class _Repo:
    def __init__(self, rules):
        self.rules = rules

    def list_enabled(self):
        return list(self.rules)


def _rule(intent, position_state='none', *, id=1, interval_sec=None,
          conditions=None, **attrs):
    """带持仓态的规则（make_rule 的裸对象 + RFC 017 新列）。

    `position_state=_UNSET` = 旧库缺列（属性不存在），用于缺列 fail-open 用例。
    """
    rule = make_rule(id=id, conditions=conditions)
    rule.intent = intent
    rule.interval_sec = interval_sec
    if position_state is not _UNSET:
        rule.position_state = position_state
    for key, value in attrs.items():
        setattr(rule, key, value)
    return rule


def _engine(rules, prices=None, clock=None):
    prices = {SYMBOL: MISS} if prices is None else prices
    notifier = FakeNotifier()
    engine = WatchEngine(
        rule_repo=_Repo(rules),
        quote_service=FakeQuoteService(prices),
        notifier=notifier,
        now_fn=clock or (lambda: NOW),
    )
    return engine, notifier


def _evaluated(engine, rule) -> bool:
    """这条规则本拍有没有真的进评估（取价 + 消耗一拍到期时钟）。"""
    return (engine.quote_service.calls == [SYMBOL]
            and engine.state.schedule.last_eval_at.get(rule.id) is not None)


def _mismatches(events):
    return [e for e in events if isinstance(e, dict)
            and e.get('kind') == STATE_MISMATCH_EVENT]


# ── 判据 0：四族 intent × 两状态 ─────────────────────────────────
class TestBranchTable:
    """分支表：entry 族仅 none、exit 族仅 holding（t_trade 归 holding）。

    `exit_stop` 是**唯一的例外**：它是宪法级止损，对上 'none' 也照常求值
    （状态滞后不静默跳过），单独在 `TestFailOpen` 里钉。
    """

    def test_intent_family_classification(self):
        for intent in ENTRY_INTENTS:
            assert position_state_family(intent) == POSITION_FAMILY_ENTRY
        for intent in EXIT_INTENTS:
            assert position_state_family(intent) == POSITION_FAMILY_EXIT
        for intent in OBSERVE_INTENTS:
            assert position_state_family(intent) == POSITION_FAMILY_OBSERVE
        # 未知意图 = observe（照常求值；宁可多判，不可漏判）
        assert position_state_family('') == POSITION_FAMILY_OBSERVE
        assert position_state_family(None) == POSITION_FAMILY_OBSERVE

    @pytest.mark.parametrize('state,evaluated', [('none', True), ('holding', False)])
    @pytest.mark.parametrize('intent', ENTRY_INTENTS)
    def test_entry_family_only_evaluates_when_flat(self, intent, state, evaluated):
        rule = _rule(intent, state)
        engine, _ = _engine([rule], {SYMBOL: HIT})
        engine.tick()
        assert _evaluated(engine, rule) is evaluated

    @pytest.mark.parametrize('state,evaluated', [('none', False), ('holding', True)])
    @pytest.mark.parametrize('intent', ('t_trade', 'exit_take_profit', 'exit_reduce'))
    def test_exit_family_only_evaluates_when_holding(self, intent, state, evaluated):
        rule = _rule(intent, state)
        engine, _ = _engine([rule], {SYMBOL: HIT})
        engine.tick()
        assert _evaluated(engine, rule) is evaluated

    @pytest.mark.parametrize('state', ['none', 'holding'])
    def test_observe_intents_always_evaluate(self, state):
        rule = _rule('trend_observe', state)
        engine, _ = _engine([rule], {SYMBOL: HIT})
        engine.tick()
        assert _evaluated(engine, rule) is True

    def test_skip_reasons_are_observable_in_metrics(self):
        entry = _rule('entry', 'holding', id=1)
        exit_ = _rule('exit_take_profit', 'none', id=2)
        engine, _ = _engine([entry, exit_])
        engine.tick()
        skipped = engine.get_metrics()['position_state_skipped']
        assert skipped[POSITION_STATE_SKIP_ENTRY_HELD] == 1
        assert skipped[POSITION_STATE_SKIP_EXIT_FLAT] == 1
        assert engine.quote_service.calls == [], '两条规则都被状态门挡下 → 本拍不取价'

    def test_market_scope_rules_bypass_the_gate(self):
        """市场级规则没有个股持仓语义（标的=指数/板块/情绪快照）。"""
        rule = _rule('entry', 'holding', scope='market')
        assert position_state_verdict(rule) == (None, None)


# ── 判据 0：None = 状态不可知（不得当 'none'）─────────────────────
class TestUnknownState:

    @pytest.mark.parametrize('intent', ENTRY_INTENTS + EXIT_INTENTS + OBSERVE_INTENTS)
    def test_null_state_means_unknown_and_always_evaluates(self, intent):
        """显式 NULL（旧库/被回滚）→ 不可知：entry 不因"可能持仓"跳过，
        exit 也不因"可能空仓"跳过——与改造前行为完全等价。"""
        rule = _rule(intent, position_state=None)
        engine, _ = _engine([rule], {SYMBOL: HIT})
        events = engine.tick()
        assert _evaluated(engine, rule) is True
        assert _mismatches(events) == [], '读不出的 NULL 不是不一致（旧库常态）'

    @pytest.mark.parametrize('intent', ['entry', 'exit_stop', 'trend_observe'])
    def test_missing_column_keeps_legacy_behaviour(self, intent):
        """缺列（未迁移/已回滚）：属性不存在 → 不可知 → 全部照常求值。"""
        rule = _rule(intent, position_state=_UNSET)
        assert not hasattr(rule, 'position_state')
        engine, _ = _engine([rule], {SYMBOL: HIT})
        events = engine.tick()
        assert _evaluated(engine, rule) is True
        assert _mismatches(events) == []

    def test_none_is_not_the_string_none(self):
        """'none'（确认空仓）与 None（不可知）在门上是两条路，不能混。"""
        flat_entry = _rule('entry', 'none')
        unknown_entry = _rule('entry', position_state=None, id=2)
        engine, _ = _engine([flat_entry, unknown_entry], {SYMBOL: HIT})
        engine.tick()
        assert _evaluated(engine, flat_entry) is True
        assert _evaluated(engine, unknown_entry) is True
        # 而 holding 才让 entry 跳过：证明不是把 None 当成了 'none'
        held_entry = _rule('entry', 'holding', id=3)
        engine2, _ = _engine([held_entry], {SYMBOL: HIT})
        engine2.tick()
        assert _evaluated(engine2, held_entry) is False

    def test_read_delegates_to_repository_reader(self, monkeypatch):
        """读口径必须走仓储 `rule_position_state()`（单一实现，不写第二套归一）。"""
        calls = []

        def _reader(rule):
            calls.append(rule)
            return 'holding'

        monkeypatch.setattr(engine_mod, '_POSITION_STATE_READER', _reader)
        rule = _rule('entry', 'none')
        assert read_rule_position_state(rule) == 'holding'
        assert calls == [rule]

    def test_reader_is_the_repository_function(self, monkeypatch):
        from adapters.outbound.repositories.watch_rule_repository import (
            rule_position_state,
        )

        monkeypatch.setattr(engine_mod, '_POSITION_STATE_READER',
                            engine_mod._READER_UNSET)
        assert engine_mod._load_position_state_reader() is rule_position_state


# ── 判据 0：不一致 fail-open + warn + state_mismatch 事件 ─────────
class TestMismatchObservation:

    def test_constitutional_stop_on_flat_records_mismatch_but_still_fires(self):
        """exit_stop 对上 'none'（状态滞后）：不跳过、照常喊，并落一次不一致事件。"""
        rule = _rule('exit_stop', 'none')
        engine, notifier = _engine([rule], {SYMBOL: HIT})
        events = engine.tick()
        assert len(notifier.notifications) == 1, '止损不得因状态滞后被静默跳过'
        [mismatch] = _mismatches(events)
        assert mismatch['reason'] == MISMATCH_STOP_WITHOUT_HOLDING
        assert mismatch['position_state'] == 'none'
        assert mismatch['fail_open'] is True
        assert mismatch['rule_id'] == rule.id
        assert engine.get_metrics()['position_state_mismatch'] == 1

    def test_no_mismatch_event_when_no_trigger_is_recorded(self):
        """不触发就不刷事件：否则一条空仓止损规则每拍刷一条，真实异常被淹掉。"""
        rule = _rule('exit_stop', 'none')
        engine, notifier = _engine([rule], {SYMBOL: MISS})
        events = engine.tick()
        assert events == []
        assert notifier.notifications == []
        assert engine.get_metrics()['position_state_mismatch'] == 0

    def test_unreadable_declared_state_records_mismatch_and_evaluates(self):
        """声明了非法值（读不懂）→ 不一致留痕，但照常求值（fail-open）。"""
        rule = _rule('entry', 'halfway')
        engine, _ = _engine([rule], {SYMBOL: HIT})
        events = engine.tick()
        assert _evaluated(engine, rule) is True
        [mismatch] = _mismatches(events)
        assert mismatch['reason'] == MISMATCH_UNREADABLE
        assert mismatch['position_state'] is None
        assert "'halfway'" in mismatch['declared_position_state']

    def test_mismatch_event_is_not_a_trigger_event(self):
        """事件 kind 与触发事件区分：不能伪装成一次触发（去重/计数口径会坏）。"""
        rule = _rule('exit_stop', 'none')
        engine, _ = _engine([rule], {SYMBOL: HIT})
        events = engine.tick()
        kinds = [e.get('kind') for e in events]
        assert STATE_MISMATCH_EVENT in kinds
        trigger_events = [e for e in events if e.get('kind') != STATE_MISMATCH_EVENT]
        assert trigger_events and all(e.get('trigger_id') for e in trigger_events)


# ── 判据 0：与到期门/活性过滤的先后 ─────────────────────────────
class TestGateOrdering:

    def test_state_gate_runs_before_due_gate(self):
        """被状态门跳过的规则**不消耗**到期时钟：状态翻转后下一拍照常求值。

        如果门在到期门之后（或被跳过的规则仍 mark_evaluated），翻转后的首拍
        会被 interval_sec 挡在门外——止损会因此晚一个 interval 才被喊。
        """
        clock = _Clock()
        rule = _rule('entry', 'holding', interval_sec=60)
        engine, _ = _engine([rule], {SYMBOL: HIT}, clock=clock)
        assert engine.tick() == []
        assert engine.quote_service.calls == []
        assert engine.state.schedule.last_eval_at == {}, '跳过 ≠ 求值，不记到期时钟'
        assert engine.get_metrics()['position_state_skipped'][
            POSITION_STATE_SKIP_ENTRY_HELD] == 1
        # 状态门在到期门之前：被门挡下的规则不进 deferred 统计
        assert engine.get_metrics()['rule_deferred'] == 0

        rule.position_state = 'none'       # 状态翻转（fill/对账写入）
        clock.advance(5)
        engine.tick()
        assert engine.quote_service.calls == [SYMBOL], '翻转后下一拍立即求值，不等 60s'

    def test_state_gate_runs_after_active_window_filter(self):
        """活性过滤（活跃窗口）先挡下：状态门不该替它计数/留痕。"""
        rule = _rule('entry', 'holding', active_window=['14:30-15:00'])
        engine, _ = _engine([rule], {SYMBOL: HIT})
        engine.tick()
        assert engine.quote_service.calls == []
        assert engine.get_metrics()['position_state_skipped'][
            POSITION_STATE_SKIP_ENTRY_HELD] == 0

    def test_skip_stops_before_quotes_but_other_rules_still_evaluate(self):
        """跳过发生在取价之前：同 symbol 的另一条规则仍照常取价（合并取价不被破坏）。"""
        skipped = _rule('entry', 'holding', id=1)
        evaluated = _rule('trend_observe', 'none', id=2)
        engine, _ = _engine([skipped, evaluated], {SYMBOL: HIT})
        engine.tick()
        assert engine.quote_service.calls == [SYMBOL], '只取一次价（观察类那条仍在）'
        assert not _evaluated(engine, skipped)
        assert _evaluated(engine, evaluated)


# ── 判据 2：fail-open —— 状态滞后/缺列绝不静默跳过止损 ────────────
class TestFailOpen:

    def test_lagging_state_never_silences_stop(self):
        """状态滞后（已买入但规则仍是 'none'）：止损照常判定并通知。"""
        rule = _rule('exit_stop', 'none')
        engine, notifier = _engine([rule], {SYMBOL: HIT})
        events = engine.tick()
        assert len(notifier.notifications) == 1
        assert _mismatches(events), '不一致必须有留痕（warn + 事件）'

    def test_reader_unavailable_fails_open_for_entry(self, monkeypatch):
        """读口径不可用（import 失败缓存 None）→ 不可知 → 不做任何跳过。"""
        rule = _rule('entry', 'holding')      # 若能读到 holding 会被跳过
        engine, _ = _engine([rule], {SYMBOL: HIT})
        monkeypatch.setattr(engine_mod, '_POSITION_STATE_READER', None)
        engine.tick()
        assert _evaluated(engine, rule) is True

    def test_reader_exception_fails_open_for_stop(self, monkeypatch):
        """读库抛异常 = 不可知（不是"确认空仓"）：止损照常喊，并留不一致事件。"""
        rule = _rule('exit_stop', 'none')
        engine, notifier = _engine([rule], {SYMBOL: HIT})

        class _Boom:
            def __call__(self, rule):  # noqa: ARG002 - 口径只关心调用
                raise RuntimeError('db down')

        monkeypatch.setattr(engine_mod, '_POSITION_STATE_READER', _Boom())
        events = engine.tick()
        assert len(notifier.notifications) == 1, '读状态失败不得让止损变哑'
        assert _mismatches(events), '读取异常须留痕（声明了 none 却读不出）'

    def test_missing_column_never_skips_constitutional_stop(self):
        """缺列（未迁移）→ 不可知 → 宪法级止损照常求值并通知。"""
        rule = _rule('exit_stop', position_state=_UNSET)
        engine, notifier = _engine([rule], {SYMBOL: HIT})
        engine.tick()
        assert len(notifier.notifications) == 1

    def test_unknown_state_constant_is_not_flat(self):
        """口径自证：'none' 是确认空仓，不能被当成不可知（反之亦然）。"""
        assert POSITION_STATE_NONE == 'none'
