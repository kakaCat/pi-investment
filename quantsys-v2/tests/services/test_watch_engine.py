"""WatchEngine 核心单测（fake 仓储 + fake 行情源）"""
from datetime import datetime, time, timedelta
from types import SimpleNamespace

import pytest

from application.services.watch_engine.engine import WatchEngine, elapsed_trading_fraction


def make_rule(id=1, symbol='600519.SH', conditions=None, cost_price=None,
              active_window=None):
    return SimpleNamespace(
        id=id, symbol=symbol,
        conditions=conditions or [{'type': 'price_break',
                                   'params': {'direction': 'above', 'price': 100.0}}],
        cost_price=cost_price, active_window=active_window,
    )


class FakeRepo:
    def __init__(self, rules):
        self._rules = rules

    def list_enabled(self):
        return list(self._rules)


class FakeQuoteService:
    def __init__(self, prices: dict):
        self.prices = prices
        self.calls = []

    def get_realtime_quote(self, symbol):
        self.calls.append(symbol)
        price = self.prices.get(symbol)
        if price is None:
            return None
        return SimpleNamespace(symbol=symbol, price=price, prev_close=98.0,
                               volume=1_000_000, change_pct=None)


class FakeNotifier:
    def __init__(self):
        self.notifications = []

    def notify(self, rule, condition, quote, result):
        self.notifications.append((rule.id, condition['type'], quote.price))
        return True


NOW = datetime(2026, 7, 21, 10, 30)  # 周二，交易时段内


def make_engine(rules, prices, notifier=None, **kw):
    return WatchEngine(
        rule_repo=FakeRepo(rules),
        quote_service=FakeQuoteService(prices),
        notifier=notifier or FakeNotifier(),
        now_fn=lambda: NOW,
        **kw,
    )


class TestTick:
    def test_trigger_fires_notification(self):
        notifier = FakeNotifier()
        engine = make_engine([make_rule()], {'600519.SH': 101.0}, notifier)
        events = engine.tick()
        assert len(events) == 1
        assert notifier.notifications == [(1, 'price_break', 101.0)]

    def test_no_trigger_below_threshold(self):
        notifier = FakeNotifier()
        engine = make_engine([make_rule()], {'600519.SH': 99.0}, notifier)
        events = engine.tick()
        assert events == []
        assert notifier.notifications == []

    def test_cooldown_suppresses_repeat(self):
        notifier = FakeNotifier()
        engine = make_engine([make_rule()], {'600519.SH': 101.0}, notifier)
        engine.tick()
        events2 = engine.tick()  # 立即再次 tick，同一条件冷却中
        assert events2 == []
        assert len(notifier.notifications) == 1

    def test_cooldown_expires(self):
        notifier = FakeNotifier()
        clock = {'now': NOW}
        engine = WatchEngine(
            rule_repo=FakeRepo([make_rule()]),
            quote_service=FakeQuoteService({'600519.SH': 101.0}),
            notifier=notifier,
            now_fn=lambda: clock['now'],
        )
        engine.tick()
        clock['now'] = NOW + timedelta(seconds=301)  # 默认冷却 300s 已过
        events = engine.tick()
        assert len(events) == 1

    def test_custom_cooldown(self):
        rule = make_rule(conditions=[{'type': 'price_break',
                                      'params': {'direction': 'above', 'price': 100.0},
                                      'cooldown_sec': 3600}])
        clock = {'now': NOW}
        notifier = FakeNotifier()
        engine = WatchEngine(FakeRepo([rule]), FakeQuoteService({'600519.SH': 101.0}),
                             notifier, now_fn=lambda: clock['now'])
        engine.tick()
        clock['now'] = NOW + timedelta(seconds=301)
        assert engine.tick() == []  # 自定义冷却 3600s 未过

    def test_quote_failure_skips_silently(self):
        notifier = FakeNotifier()
        engine = make_engine([make_rule()], {}, notifier)  # 无价格 → 五源全挂
        assert engine.tick() == []
        assert notifier.notifications == []

    def test_active_window_excludes(self):
        rule = make_rule(active_window=['14:30-15:00'])  # 当前 10:30 不在窗口
        engine = make_engine([rule], {'600519.SH': 101.0})
        assert engine.tick() == []

    def test_active_window_includes(self):
        rule = make_rule(active_window=['09:30-10:30', '14:30-15:00'])
        engine = make_engine([rule], {'600519.SH': 101.0})
        assert len(engine.tick()) == 1

    def test_active_window_malformed_fails_open(self):
        # 畸形格式（无分隔符）不应毒化 tick，fail-open 继续监控
        rule = make_rule(active_window=['14301500'])
        engine = make_engine([rule], {'600519.SH': 101.0})
        assert len(engine.tick()) == 1

    def test_day_rollover_resets_avg_volume_cache(self):
        calls = []
        def provider(symbol):
            calls.append(symbol)
            return 10_000_000.0
        clock = {'now': NOW}
        engine = WatchEngine(FakeRepo([make_rule()]), FakeQuoteService({'600519.SH': 99.0}),
                             FakeNotifier(), avg_volume_provider=provider,
                             now_fn=lambda: clock['now'])
        engine.tick()
        engine.tick()  # 同一天，用缓存
        assert len(calls) == 1
        clock['now'] = NOW + timedelta(days=1)  # 跨天 → 缓存失效重新取
        engine.tick()
        assert len(calls) == 2

    def test_notify_failure_retries_next_tick(self):
        class FlakyNotifier:
            def __init__(self):
                self.calls = 0
            def notify(self, rule, condition, quote, result):
                self.calls += 1
                if self.calls == 1:
                    raise RuntimeError('feishu down')
                return True
        notifier = FlakyNotifier()
        engine = make_engine([make_rule()], {'600519.SH': 101.0}, notifier)
        assert engine.tick() == []  # 第一次抛异常，无事件
        assert len(engine.tick()) == 1  # 未记 _last_triggered，下个 tick 重试成功
        assert notifier.calls == 2


class TestAdaptiveFrequency:
    def test_fast_mode_when_near_threshold(self):
        # 阈值 100，现价 99.5 → distance_ratio = 0.005 <= 0.2 → 高频档
        engine = make_engine([make_rule()], {'600519.SH': 99.5})
        engine.tick()
        assert engine.fast_mode is True

    def test_normal_mode_when_far(self):
        engine = make_engine([make_rule()], {'600519.SH': 50.0})
        engine.tick()
        assert engine.fast_mode is False

    def test_fast_mode_on_trigger(self):
        engine = make_engine([make_rule()], {'600519.SH': 101.0})
        engine.tick()
        assert engine.fast_mode is True  # distance_ratio 0 → 保持高频


class TestPriceHistory:
    def test_velocity_uses_ring_buffer(self):
        rule = make_rule(conditions=[{'type': 'velocity',
                                      'params': {'pct': 2.0, 'window_min': 5}}])
        clock = {'now': NOW}
        notifier = FakeNotifier()
        quotes = FakeQuoteService({'600519.SH': 100.0})
        engine = WatchEngine(FakeRepo([rule]), quotes, notifier, now_fn=lambda: clock['now'])
        engine.tick()  # 积累第一点 100.0
        clock['now'] = NOW + timedelta(minutes=3)
        quotes.prices['600519.SH'] = 103.0  # 3分钟涨3%
        events = engine.tick()
        assert len(events) == 1
        assert notifier.notifications[0][1] == 'velocity'


class TestTradingTime:
    @pytest.mark.parametrize('t,expected', [
        (time(9, 29), False), (time(9, 30), True), (time(11, 30), True),
        (time(12, 0), False), (time(13, 0), True), (time(15, 0), True),
        (time(15, 1), False),
    ])
    def test_is_trading_time(self, t, expected):
        assert WatchEngine.is_trading_time(t) is expected


class TestElapsedFraction:
    def test_open(self):
        assert elapsed_trading_fraction(datetime(2026, 7, 21, 9, 30)) == pytest.approx(0.0)

    def test_lunch_boundary(self):
        # 11:30 已交易 120/240 分钟
        assert elapsed_trading_fraction(datetime(2026, 7, 21, 11, 30)) == pytest.approx(0.5)

    def test_afternoon(self):
        # 14:00 = 上午120 + 下午60 = 180/240
        assert elapsed_trading_fraction(datetime(2026, 7, 21, 14, 0)) == pytest.approx(0.75)

    def test_close(self):
        assert elapsed_trading_fraction(datetime(2026, 7, 21, 15, 0)) == pytest.approx(1.0)
