"""引擎级：迟滞带不复读 + 日上限第 3 次只归档（REQ-261016155500-4f2a wt:engine:1）"""
from datetime import datetime
from types import SimpleNamespace

from application.services.watch_engine.engine import DAILY_CAP_REASON, WatchEngine

NOW = datetime(2026, 7, 21, 10, 30)  # 周二交易时段


def _rule():
    return SimpleNamespace(
        id=1, symbol='002007',
        conditions=[{'type': 'price_break',
                     'params': {'direction': 'below', 'price': 12.85},
                     'cooldown_sec': 60}],
        cost_price=13.27, active_window=None,
        intent='exit_stop', action_hint={'trigger_level': 'L2', 'action_on_trigger': 'sell'},
        escalation_policy=None, scope='symbol', linked_account=None,
        lifecycle_stage='watching', created_from=None, next_action_hint=None,
        target=None, review_interval_days=None, review_due_at=None, enabled=True,
        action_params=None, ops_notes=None,
    )


class _Repo:
    def list_enabled(self):
        return [_rule()]


class _Quotes:
    def __init__(self):
        self.price = 13.00

    def get_realtime_quote(self, symbol):
        return SimpleNamespace(symbol=symbol, price=self.price, prev_close=13.10,
                               volume=1_000_000, change_pct=None)


class _Notifier:
    def __init__(self):
        self.notifications = []

    def notify(self, rule, condition, quote, result, **kwargs):
        self.notifications.append(quote.price)
        return SimpleNamespace(id=len(self.notifications), notified=True)


def _engine(clock, quotes, notifier):
    return WatchEngine(rule_repo=_Repo(), quote_service=quotes, notifier=notifier,
                       now_fn=lambda: clock['now'])


def test_hysteresis_blocks_jitter_and_daily_cap_archives_third():
    clock = {'now': NOW}
    quotes = _Quotes()
    notifier = _Notifier()
    engine = _engine(clock, quotes, notifier)

    # 第 1 次：跌穿 → 通知
    quotes.price = 12.80
    engine.tick()
    assert len(notifier.notifications) == 1

    # 抖动：回升到阈值上方但在迟滞带内（12.90 ≤ 12.914）→ 闩锁保持
    clock['now'] = NOW.replace(minute=35)
    quotes.price = 12.90
    engine.tick()
    # 再跌穿 → 闩锁挡住（迟滞带生效），不计数
    clock['now'] = NOW.replace(minute=36)
    quotes.price = 12.80
    events = engine.tick()
    assert len(notifier.notifications) == 1
    assert events == []

    # 真正越过迟滞带（12.95）→ 重新武装
    clock['now'] = NOW.replace(minute=37)
    quotes.price = 12.95
    engine.tick()
    # 第 2 次真实再穿越 → 通知（冷却 60s 已过）
    clock['now'] = NOW.replace(minute=38)
    quotes.price = 12.80
    engine.tick()
    assert len(notifier.notifications) == 2

    # 再次越过迟滞带 + 第 3 次穿越 → 日上限（2 次）命中：只归档不通知
    clock['now'] = NOW.replace(minute=39)
    quotes.price = 12.95
    engine.tick()
    clock['now'] = NOW.replace(minute=40)
    quotes.price = 12.80
    events = engine.tick()
    assert len(notifier.notifications) == 2          # 第 3 次没有通知
    assert len(events) == 1                           # 但有一条归档事件
    assert events[0]['suppressed'] is True
    assert events[0]['disposition_reason'] == DAILY_CAP_REASON
    assert events[0]['notified'] is False
