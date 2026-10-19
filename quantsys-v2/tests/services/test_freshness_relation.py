"""穿越 vs 驻留 + 「与我何干」段（2026-10-19 用户裁定）

验收锚点：
  · freshness_of：昨收在触发侧 → 陈旧驻留（False）；昨收未触发 → 新穿越（True）；
  · 引擎驻留分支：不发消息不进缓冲，闩锁置上，每日一条阈值失真治理项；
  · relation_of：持仓/账户观察/扫描线索三级降级；
  · 渲染器与聚合卡带「与我何干」行。
"""
from datetime import datetime, timedelta
from types import SimpleNamespace

from qs_watch.application.services.watch_engine.conditions import freshness_of
from qs_watch.application.services.watch_engine.engine import WatchEngine
from qs_watch.application.services.watch_engine.observe_aggregator import ObserveAggregator
from qs_watch.domain.watch.services.watch_message import relation_of

NOW = datetime(2026, 10, 19, 9, 31)
BELOW = {'type': 'price_break', 'params': {'price': 44.56, 'direction': 'below'},
         'cooldown_sec': 1800}


# ── freshness_of 纯函数 ─────────────────────────────────────────

def test_freshness_classification():
    # 下破阈值 44.56：昨收 45（未触发）→ 新穿越；昨收 38（已触发）→ 陈旧驻留
    assert freshness_of(BELOW, 45.0) is True
    assert freshness_of(BELOW, 38.0) is False
    assert freshness_of(BELOW, 44.56) is False          # 恰在阈值 = 昨收已触发
    above = {'type': 'price_break', 'params': {'price': 45.4, 'direction': 'above'}}
    assert freshness_of(above, 44.0) is True
    assert freshness_of(above, 46.0) is False
    # 无法判定
    assert freshness_of(BELOW, None) is None
    assert freshness_of({'type': 'pnl_pct', 'params': {'pct': -8}}, 38.0) is None


def _rule(rid=239):
    return SimpleNamespace(
        id=rid, symbol='002460', conditions=[BELOW],
        cost_price=None, active_window=None, intent='trend_observe',
        action_hint={'trigger_level': 'L1', 'action_on_trigger': 'observe'},
        escalation_policy=None, scope='symbol', linked_account=None,
        lifecycle_stage=None, created_from=None, next_action_hint=None,
        target=None, review_interval_days=None, review_due_at=None, enabled=True,
        action_params=None, ops_notes=None)


class _Repo:
    def list_enabled(self):
        return [_rule()]


class _Quotes:
    def __init__(self, price, prev_close):
        self.price, self.prev_close = price, prev_close

    def get_realtime_quote(self, symbol):
        return SimpleNamespace(symbol=symbol, price=self.price,
                               prev_close=self.prev_close,
                               volume=1e6, change_pct=None)


class _Notifier:
    def __init__(self):
        self.governance = []
        self.sent = []

    def record_governance(self, rule, reason, detail=None):
        self.governance.append({'rule_id': rule.id, 'reason': reason, 'detail': detail})
        return SimpleNamespace(id=len(self.governance))

    def record_only(self, rule, condition, quote, result, **kw):
        raise AssertionError('陈旧驻留不应进聚合缓冲')

    def notify(self, rule, condition, quote, result, **kw):
        raise AssertionError('陈旧驻留不应发消息')


# ── 引擎驻留分支 ────────────────────────────────────────────────

def test_stale_residency_no_card_and_governance_once():
    clock = {'now': NOW}
    notifier = _Notifier()
    agg = ObserveAggregator(sender=lambda t, c: True)
    # 昨收 38（已在阈值下方）→ 陈旧驻留
    engine = WatchEngine(rule_repo=_Repo(), quote_service=_Quotes(38.08, 38.0),
                         notifier=notifier, observe_agg=agg,
                         now_fn=lambda: clock['now'])
    events = engine.tick()
    assert events == []                          # 无事件（不打扰）
    assert agg.pending_count() == 0              # 不进缓冲
    assert (239, 0) in engine.state.latched      # 闩锁置上
    assert len(notifier.governance) == 1         # 每日一条治理项
    g = notifier.governance[0]
    assert '阈值失真' in g['reason'] and '44.56' in g['reason']
    assert g['detail']['stale_residency'] is True
    assert round(g['detail']['deviation_pct'], 1) == round((38.08-44.56)/44.56*100, 1)

    # 下一 tick（闩锁挡住）→ 不再报
    clock['now'] = NOW + timedelta(minutes=5)
    assert engine.tick() == []
    assert len(notifier.governance) == 1


def test_fresh_cross_still_notifies():
    clock = {'now': NOW}
    sent = []
    agg = ObserveAggregator(sender=lambda t, c: sent.append((t, c)) or True,
                            window_sec=60)
    notifier = _Notifier()

    class _N(_Notifier):
        def record_only(self, rule, condition, quote, result, **kw):
            return SimpleNamespace(id=1, notified=False)

    # 昨收 44.60（> 阈值 44.56，未触发）→ 新穿越：照走缓冲路径（驻留分支不拦）。
    # 现价 44.50 贴近阈值（-0.2%），避免 |涨跌|≥5% 触发升级走即时通道。
    engine = WatchEngine(rule_repo=_Repo(), quote_service=_Quotes(44.50, 44.60),
                         notifier=_N(), observe_agg=agg,
                         now_fn=lambda: clock['now'])
    events = engine.tick()
    assert len(events) == 1
    assert events[0]['disposition'] == 'auto_observed'
    assert agg.pending_count() == 1              # 新穿越照常进缓冲


# ── relation_of 三级降级 ────────────────────────────────────────

def test_relation_of_levels():
    holding = SimpleNamespace(cost_price=13.27)
    assert '持仓视角' in relation_of(holding, -8.0) and '浮-8.00%' in relation_of(holding, -8.0)
    mine = SimpleNamespace(cost_price=None, linked_account='user_main_simulation')
    assert '你账户' in relation_of(mine)
    agents = SimpleNamespace(cost_price=None, linked_account='agent_brain')
    assert 'agent_brain' in relation_of(agents) and '非你的持仓' in relation_of(agents)
    scan = SimpleNamespace(cost_price=None, linked_account=None, account=None)
    assert '扫描线索' in relation_of(scan)


def test_renderer_has_relation_line():
    from qs_watch.domain.watch.services.watch_message import (
        ActionSection, FactSection, WatchMessage)
    from qs_notification.infrastructure.formatters.watch_message_renderer import (
        render_watch_message)
    msg = WatchMessage(level='P2', symbol='002007', name='华兰生物',
                       intent='exit_stop',
                       fact=FactSection(condition_text='现价 12.21 ≤ 阈值 12.85（下破）',
                                        price=12.21),
                       action=ActionSection('sell', '卖出', 'action_params'),
                       relation='持仓视角：成本 ¥13.27（浮-8.00%）')
    text = render_watch_message(msg).text
    assert '**与我何干**：持仓视角：成本 ¥13.27（浮-8.00%）' in text


def test_aggregate_card_has_relation_line():
    sent = []
    agg = ObserveAggregator(sender=lambda t, c: sent.append((t, c)) or True,
                            window_sec=60)
    item = {'rule_id': 239, 'trigger_id': 1, 'message': '下破', 'price': 38.0,
            'at': '2026-10-19T09:30:46.1'}
    agg.add('agent_brain', '002460', item, NOW, 38.0,
            action_text='观察', relation_text='扫描线索（与你持仓无直接关系）')
    agg.maybe_flush(NOW + timedelta(minutes=2), market_open=True)
    assert '**与我何干**：扫描线索' in sent[0][1]
