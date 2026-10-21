"""市场级规则并入主流水线 + 聚合缓冲日上限/待办口径（2026-10-19 审查批次二）

守三件事：
1) P0-4：市场级触发走与个股相同的处置链——通知送达、闩锁防复读（重启不丢）、
   占用真实预算（不再有 notified=False 写死的半条流水线）；
2) P0-5a：进聚合缓冲的触发计入每日通知上限（observe 聚合通道不再不受约束）；
3) P0-5b：聚合缓冲的触发不建待办（SLA 时钟不早于用户看到聚合卡）。
"""
from datetime import datetime
from types import SimpleNamespace

from qs_watch.application.services.watch_engine.engine import WatchEngine

NOW = datetime(2026, 7, 21, 10, 30)  # 周二交易时段


def _market_rule():
    return SimpleNamespace(
        id=7, symbol='000001.SH', scope='market',
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


def _eval_result(triggered, value=3880.0):
    return SimpleNamespace(triggered=triggered, value=value,
                           distance_ratio=None, degraded=False, metric=None,
                           unit=None, message='指数 000001 3880.00 < 3900.00（阈值）')


def _quote_like(value=3880.0):
    return SimpleNamespace(symbol='000001.SH', price=value, name=None,
                           prev_close=None, change_pct=None, volume=None)


class _MarketSvc:
    """scan_market_rules 的 fake：直接喂评估候选（真实评估器由领域层单测覆盖）"""

    def __init__(self, candidates):
        self._candidates = candidates

    def scan_market_rules(self, now):
        return {'scanned': 1, 'triggered': 1, 'skipped_no_data': 0,
                'evaluated': self._candidates}


class _EmptyRepo:
    def list_enabled(self):
        return []


class _Notifier:
    def __init__(self):
        self.calls = []
        self._seq = 0

    def notify(self, rule, condition, quote, result, **kwargs):
        self._seq += 1
        self.calls.append({'price': float(quote.price), 'kwargs': kwargs})
        return SimpleNamespace(id=self._seq, notified=True)

    def record_only(self, rule, condition, quote, result, disposition=None,
                    disposition_reason=None):
        self._seq += 1
        self.calls.append({'price': float(quote.price), 'record_only': True})
        return SimpleNamespace(id=self._seq, notified=False)


def _engine(market_svc, notifier, observe_agg=None, todo_service=None, clock=None):
    clock = clock or {'now': NOW}
    return WatchEngine(rule_repo=_EmptyRepo(), quote_service=None, notifier=notifier,
                       now_fn=lambda: clock['now'], market_watch_service=market_svc,
                       observe_agg=observe_agg, todo_service=todo_service)


class TestMarketRulesJoinMainPipeline:
    def test_market_trigger_notifies_and_latches(self):
        """市场级触发：通知送达（不再是 notified=False 归档了事）；同状态再 tick 不复读"""
        rule = _market_rule()
        cand = {'rule': rule, 'idx': 0, 'cond': rule.conditions[0],
                'result': _eval_result(True), 'quote': _quote_like()}
        notifier = _Notifier()
        engine = _engine(_MarketSvc([cand]), notifier)

        events = engine.tick()
        assert len(notifier.calls) == 1            # 真实通知（主流水线）
        assert events and events[0]['rule_id'] == 7
        assert events[0]['notified'] is True

        events2 = engine.tick()                    # 条件持续成立 → 闩锁挡住
        assert events2 == [] and len(notifier.calls) == 1

    def test_market_trigger_rearms_after_falloff(self):
        """条件回落 → 重新武装；再次成立 → 再报一次（与个股闩锁同语义）"""
        rule = _market_rule()
        on = {'rule': rule, 'idx': 0, 'cond': rule.conditions[0],
              'result': _eval_result(True), 'quote': _quote_like()}
        off = {'rule': rule, 'idx': 0, 'cond': rule.conditions[0],
               'result': _eval_result(False, 3905.0), 'quote': _quote_like(3905.0)}
        notifier = _Notifier()
        svc = _MarketSvc([on])
        clock = {'now': NOW}
        engine = _engine(svc, notifier, clock=clock)

        engine.tick()
        svc._candidates = [off]                    # 回落
        clock['now'] = NOW.replace(minute=31)
        engine.tick()
        svc._candidates = [on]                     # 再次成立（冷却 60s 已过）
        clock['now'] = NOW.replace(minute=33)
        engine.tick()
        assert len(notifier.calls) == 2


class _ObserveAgg:
    """无判据 observe 一律进缓冲的 fake"""

    def __init__(self):
        self.items = []

    def should_buffer(self, rule, disposition):
        return True

    def add(self, account, symbol, item, now, price, action_text=None,
            relation_text=None):
        self.items.append(item)

    def maybe_flush(self, now, market_open=True):
        return 0


class _TodoSvc:
    def __init__(self):
        self.created = []

    def create(self, symbol, **kwargs):
        self.created.append(symbol)
        return SimpleNamespace(id=len(self.created), flow_state='L1')


class TestObserveBufferAccounting:
    def test_buffered_trigger_counts_toward_daily_cap(self):
        """P0-5a：入缓冲的触发计入日上限——第 3 次穿越只归档不进缓冲"""
        rule = _market_rule()
        on = {'rule': rule, 'idx': 0, 'cond': rule.conditions[0],
              'result': _eval_result(True), 'quote': _quote_like()}
        off = {'rule': rule, 'idx': 0, 'cond': rule.conditions[0],
               'result': _eval_result(False, 3905.0), 'quote': _quote_like(3905.0)}
        agg = _ObserveAgg()
        notifier = _Notifier()
        svc = _MarketSvc([on])
        clock = {'now': NOW}
        engine = _engine(svc, notifier, observe_agg=agg, clock=clock)

        # 两次真实穿越都进缓冲（日上限 2 次）
        for i, minute in enumerate((30, 34)):
            clock['now'] = NOW.replace(minute=minute)
            engine.tick()
            svc._candidates = [off]
            clock['now'] = NOW.replace(minute=minute + 1)
            engine.tick()
            svc._candidates = [on]
        assert len(agg.items) == 2

        # 第 3 次穿越：日上限命中 → 只归档，不进缓冲
        clock['now'] = NOW.replace(minute=40)
        events = engine.tick()
        assert len(agg.items) == 2                  # 没有第 3 条缓冲项
        assert len(events) == 1 and events[0]['suppressed'] is True

    def test_buffered_trigger_creates_no_todo(self):
        """P0-5b：聚合缓冲的触发不建待办（SLA 时钟不早于用户看到聚合卡）"""
        rule = _market_rule()
        cand = {'rule': rule, 'idx': 0, 'cond': rule.conditions[0],
                'result': _eval_result(True), 'quote': _quote_like()}
        agg = _ObserveAgg()
        todos = _TodoSvc()
        engine = _engine(_MarketSvc([cand]), _Notifier(),
                         observe_agg=agg, todo_service=todos)
        engine.tick()
        assert len(agg.items) == 1
        assert todos.created == []                  # 缓冲路径：零待办
