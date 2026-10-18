"""观察聚合缓冲（REQ-261016155500-4f2a wt:validate:1，2026-10-16）

验收锚点：无判据 observe 进缓冲、有判据即时发；到期 flush 一屏（含区间/溯源）；
收盘 flush 残余；每标的日上限 8 张（超出压收盘）；投递失败顺延重试不丢。
"""
from datetime import datetime, timedelta
from types import SimpleNamespace

from qs_watch.application.services.watch_engine.observe_aggregator import (
    DAILY_AGG_CAP_PER_SYMBOL, ObserveAggregator, _has_observation_criterion,
)

NOW = datetime(2026, 10, 16, 10, 0, 0)


def _rule(criterion=None):
    return SimpleNamespace(
        action_params={'observation_criterion': criterion} if criterion else None)


def _sender_rec():
    sent = []
    return sent, lambda title, content: (sent.append((title, content)), True)[1]


def _item(tid, price=12.3, msg='下破 12.85'):
    return {'rule_id': 157, 'trigger_id': tid, 'message': msg, 'price': price,
            'name': '华兰生物', 'at': NOW.isoformat()}


# ── 路由判定 ────────────────────────────────────────────────

def test_should_buffer_only_for_uncriterioned_observe():
    agg = ObserveAggregator(sender=lambda t, c: True)
    assert agg.should_buffer(_rule(), 'auto_observed') is True
    assert agg.should_buffer(_rule('放量 1.5x'), 'auto_observed') is False
    assert agg.should_buffer(_rule(), 'escalated') is False
    assert agg.should_buffer(_rule(), 'pending') is False
    assert _has_observation_criterion(_rule('x')) is True
    assert _has_observation_criterion(_rule('  ')) is False


# ── 缓冲与 flush ────────────────────────────────────────────

def test_window_expiry_flushes_one_card_per_symbol():
    sent, sender = _sender_rec()
    agg = ObserveAggregator(sender=sender, window_sec=900)
    agg.add('agent_brain', '002007', _item(1, 12.30), NOW, 12.30)
    agg.add('agent_brain', '002007', _item(2, 12.10), NOW + timedelta(minutes=5), 12.10)
    agg.add('agent_brain', '600036', _item(3, 41.5), NOW, 41.5)

    # 窗口未到：不 flush
    assert agg.maybe_flush(NOW + timedelta(minutes=10), market_open=True) == 0
    # 到期：每标的各一卡
    assert agg.maybe_flush(NOW + timedelta(minutes=16), market_open=True) == 2
    assert agg.pending_count() == 0
    t007 = [c for c in sent if '002007' in c[0]][0]
    assert '第 2 次触发聚合' in t007[1]
    assert '区间 12.10 ~ 12.30' in t007[1]
    assert '#1' in t007[1] and '#2' in t007[1]      # 逐条溯源
    assert '华兰生物' in t007[1]


def test_close_flush_sends_even_before_window_expiry():
    sent, sender = _sender_rec()
    agg = ObserveAggregator(sender=sender, window_sec=900)
    agg.add(None, '002007', _item(1), NOW, 12.3)
    # 收盘（market_open=False）：未到期也强刷
    assert agg.maybe_flush(NOW + timedelta(minutes=3), market_open=False) == 1
    assert len(sent) == 1


def test_daily_cap_defers_to_close():
    sent, sender = _sender_rec()
    agg = ObserveAggregator(sender=sender, window_sec=60,
                            daily_cap=DAILY_AGG_CAP_PER_SYMBOL)
    for i in range(DAILY_AGG_CAP_PER_SYMBOL):
        agg.add('a', '002007', _item(i), NOW + timedelta(minutes=2 * i), 12.0)
        agg.maybe_flush(NOW + timedelta(minutes=2 * i + 2), market_open=True)
    assert len(sent) == DAILY_AGG_CAP_PER_SYMBOL
    # 第 9 屏：盘中被压（不超上限），收盘强刷
    agg.add('a', '002007', _item(99), NOW + timedelta(minutes=30), 12.0)
    assert agg.maybe_flush(NOW + timedelta(minutes=31), market_open=True) == 0
    assert agg.maybe_flush(NOW + timedelta(minutes=32), market_open=False) == 1
    assert len(sent) == DAILY_AGG_CAP_PER_SYMBOL + 1


def test_failed_send_retries_without_loss():
    calls = {'n': 0}
    sent = []

    def flaky(title, content):
        calls['n'] += 1
        if calls['n'] == 1:
            raise RuntimeError('feishu down')
        sent.append((title, content))
        return True

    agg = ObserveAggregator(sender=flaky, window_sec=60)
    agg.add('a', '002007', _item(1), NOW, 12.3)
    assert agg.maybe_flush(NOW + timedelta(minutes=2), market_open=True) == 0
    # 缓冲还在，顺延重试成功
    assert agg.maybe_flush(NOW + timedelta(minutes=4), market_open=True) == 1
    assert len(sent) == 1 and '第 1 次' in sent[0][1]


# ── 引擎集成：无判据 observe 走缓冲，有判据/escalated 即时发 ──────

def test_engine_routes_uncriterioned_observe_to_buffer():
    from tests.services.test_engine_daily_cap import _Notifier  # noqa: F401
    from qs_watch.application.services.watch_engine.engine import WatchEngine

    sent, sender = _sender_rec()
    agg = ObserveAggregator(sender=sender, window_sec=60)

    class _N:     # record_only 走真 notifier？不——引擎调 notifier.record_only，fake 之
        def __init__(self):
            self.records = []

        def record_only(self, rule, condition, quote, result, **kw):
            self.records.append((rule.id, kw.get('disposition')))
            return SimpleNamespace(id=len(self.records), notified=False)

        def notify(self, rule, condition, quote, result, **kw):
            raise AssertionError('无判据 observe 不应走即时 notify')

    class _Repo:
        def list_enabled(self):
            return [SimpleNamespace(
                id=1, symbol='002007',
                conditions=[{'type': 'price_break',
                             'params': {'direction': 'below', 'price': 12.85}}],
                cost_price=None, active_window=None, intent='trend_observe',
                action_hint={'trigger_level': 'L1', 'action_on_trigger': 'observe'},
                escalation_policy=None, scope='symbol', linked_account=None,
                lifecycle_stage=None, created_from=None, next_action_hint=None,
                target=None, review_interval_days=None, review_due_at=None,
                enabled=True, action_params=None, ops_notes=None)]

    class _Q:
        def get_realtime_quote(self, symbol):
            return SimpleNamespace(symbol=symbol, price=12.80, prev_close=13.0,
                                   volume=1e6, change_pct=None)

    clock = {'now': NOW}
    engine = WatchEngine(rule_repo=_Repo(), quote_service=_Q(), notifier=_N(),
                         observe_agg=agg, now_fn=lambda: clock['now'])
    events = engine.tick()
    assert len(events) == 1
    assert events[0]['disposition'] == 'auto_observed'
    assert '聚合缓冲' in (events[0]['disposition_reason'] or '')
    assert agg.pending_count() == 1
    # 窗口到期（60s）：第二 tick flush 出聚合卡（10:02 仍在交易时段）
    clock['now'] = NOW + timedelta(minutes=2)
    engine.tick()
    assert agg.pending_count() == 0
    assert len(sent) == 1
