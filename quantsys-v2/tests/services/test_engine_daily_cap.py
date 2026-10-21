"""引擎级：迟滞带不复读 + 日上限第 3 次只归档（REQ-261016155500-4f2a wt:engine:1）

2026-10-19 裁定变更：日上限对**宪法级意图（exit_stop）豁免**（止损被吞 = 资损风险，
与 dedup 守卫同源）。原用例的夹具恰好是 exit_stop 规则——本文件现拆两条：
  · 非宪法规则（trend_observe）：第 3 次穿越仍只归档不通知（原断言不变）；
  · 宪法级规则（exit_stop）：第 3 次穿越照常通知（上限不适用）。
"""
from datetime import datetime
from types import SimpleNamespace

from qs_watch.application.services.watch_engine.engine import DAILY_CAP_REASON, WatchEngine

NOW = datetime(2026, 7, 21, 10, 30)  # 周二交易时段


def _rule(intent='trend_observe', action_hint=None):
    if action_hint is None:
        action_hint = {'trigger_level': 'L1', 'action_on_trigger': 'observe'}
    return SimpleNamespace(
        id=1, symbol='002007',
        conditions=[{'type': 'price_break',
                     'params': {'direction': 'below', 'price': 12.85},
                     'cooldown_sec': 60}],
        cost_price=13.27, active_window=None,
        intent=intent, action_hint=action_hint,
        escalation_policy=None, scope='symbol', linked_account=None,
        lifecycle_stage='watching', created_from=None, next_action_hint=None,
        target=None, review_interval_days=None, review_due_at=None, enabled=True,
        action_params=None, ops_notes=None,
    )


class _Repo:
    def __init__(self, rule=None):
        self._rule = rule or _rule()

    def list_enabled(self):
        return [self._rule]


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


def _engine(clock, quotes, notifier, rule=None):
    return WatchEngine(rule_repo=_Repo(rule), quote_service=quotes, notifier=notifier,
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


def test_constitutional_intent_bypasses_daily_cap():
    """宪法级意图（exit_stop）不受日上限约束：第 3 次真实穿越照常通知。

    裁定（2026-10-19）：止损被吞 = 资损风险——dedup 已有宪法守卫，日上限同口径豁免。
    """
    clock = {'now': NOW}
    quotes = _Quotes()
    notifier = _Notifier()
    rule = _rule(intent='exit_stop',
                 action_hint={'trigger_level': 'L2', 'action_on_trigger': 'sell'})
    engine = _engine(clock, quotes, notifier, rule=rule)

    # 三次真实穿越（每次都先越过迟滞带重新武装）：全部通知，上限不生效
    for i, minute in enumerate((30, 35, 40)):
        clock['now'] = NOW.replace(minute=minute)
        quotes.price = 12.80          # 跌穿阈值
        engine.tick()
        clock['now'] = NOW.replace(minute=minute + 2)
        quotes.price = 12.95          # 越过迟滞带 → 重新武装
        engine.tick()
    assert len(notifier.notifications) == 3   # 没有任何一次被日上限归档吞掉
