"""聚合缓冲路径闩锁回归（2026-10-19 生产事故：规则 #239 六分钟触发 25 次）

根因：wt:engine:2 的「未送达不闩锁」逻辑对 buffered 路径也生效——record_only 的
trigger.notified 恒为 False（设计上就不单发），于是闩锁/冷却每次缓冲入库即被销毁，
dedup 窗口（60s）到期就复读一发。本测试钉死：buffered 路径**必须**保持闩锁与冷却。
"""
from datetime import datetime
from types import SimpleNamespace

from qs_watch.application.services.watch_engine.engine import WatchEngine
from qs_watch.application.services.watch_engine.observe_aggregator import ObserveAggregator

NOW = datetime(2026, 10, 19, 9, 30)


def _rule():
    return SimpleNamespace(
        id=239, symbol='002460',
        conditions=[{'type': 'price_break',
                     'params': {'direction': 'below', 'price': 44.56},
                     'cooldown_sec': 1800}],
        cost_price=None, active_window=None, intent='trend_observe',
        action_hint={'trigger_level': 'L1', 'action_on_trigger': 'observe'},
        escalation_policy=None, scope='symbol', linked_account=None,
        lifecycle_stage=None, created_from=None, next_action_hint=None,
        target=None, review_interval_days=None, review_due_at=None, enabled=True,
        action_params=None, ops_notes=None,
    )


class _Repo:
    def list_enabled(self):
        return [_rule()]


class _Quotes:
    def __init__(self, price):
        self.price = price

    def get_realtime_quote(self, symbol):
        # prev_close=45.0 > 阈值 44.56：昨收未在触发侧 → 今日是「新穿越」而非陈旧驻留
        # （2026-10-19 陈旧驻留裁定后，prev_close 已在阈值下方会被转治理而不进缓冲）。
        # change_pct 显式置 0：缺省 None 时升级检查会按 prev_close 自算涨跌幅
        # （38.46 vs 45.0 = -14.5% → 命中异常波动升级，触发就走即时通道而非缓冲）。
        return SimpleNamespace(symbol=symbol, price=self.price, prev_close=45.0,
                               volume=1e6, change_pct=0.0)


class _Notifier:
    def __init__(self):
        self.records = []
        self.sends = 0

    def record_only(self, rule, condition, quote, result, **kw):
        self.records.append(quote.price)
        return SimpleNamespace(id=len(self.records), notified=False)

    def notify(self, rule, condition, quote, result, **kw):
        raise AssertionError('无判据 observe 应走缓冲，不应即时 notify')


def _engine(clock, quotes, notifier, agg):
    return WatchEngine(rule_repo=_Repo(), quote_service=quotes, notifier=notifier,
                       observe_agg=agg, now_fn=lambda: clock['now'])


def test_buffered_path_keeps_latch_no_retrigger():
    sent = []
    agg = ObserveAggregator(sender=lambda t, c: sent.append((t, c)) or True,
                            window_sec=900)
    clock = {'now': NOW}
    notifier = _Notifier()
    engine = _engine(clock, _Quotes(38.46), notifier, agg)

    # 第 1 次：缓冲入库（notified=False 是设计值）
    events1 = engine.tick()
    assert len(events1) == 1 and len(notifier.records) == 1
    # 闩锁与冷却必须保留（事故的反面）
    assert (239, 0) in engine.state.latched
    assert (239, 0) in engine.state.last_triggered

    # 电平保持的后续 tick：价格仍在阈值下方 → 闩锁挡住，零新增记录
    for minute in (1, 2, 3, 5, 10, 20):
        clock['now'] = NOW.replace(minute=30 + minute)
        events = engine.tick()
        assert notifier.records == [38.46], '缓冲路径复读：闩锁被拆（事故根因）'
        assert events == []


def test_aggregate_card_has_action_and_real_timestamps():
    sent = []
    agg = ObserveAggregator(sender=lambda t, c: sent.append((t, c)) or True,
                            window_sec=60)
    item = {'rule_id': 239, 'trigger_id': 2939,
            'message': '现价 38.46 ≤ 阈值 44.56（下破）', 'price': 38.46,
            'name': '赣锋锂业', 'at': '2026-10-19T09:30:46.434938'}
    agg.add('agent_brain', '002460', item, NOW, 38.46,
            action_text='跌破 44.56 进入买入区，评估建仓（评分82）')
    agg.maybe_flush(NOW, market_open=False)
    assert len(sent) == 1
    card = sent[0][1]
    assert '09:30:46' in card and '434938' not in card.split('\n')[0]  # 时间戳可读
    assert '**建议动作**：跌破 44.56 进入买入区' in card                 # 决策要素
