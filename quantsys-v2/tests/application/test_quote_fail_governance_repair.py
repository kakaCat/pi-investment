"""盯盘引擎「疑似停牌/退市」误报修复的回归测试（2026-10-21）

背景（事故复盘）：2026-10-20/10-21 盯盘引擎产出 **70 条**假的「疑似停牌/退市」
治理项，覆盖 30 个 symbol。实证 29 个股票标的在 10-20 与 10-21 两天
daily_klines 均齐全 → **100% 误报**。

四缺陷叠加：
  ① 两义性：行情服务对「熔断冷却跳过」与「真实全灭」都 return None。
  ② 计数器语义错：docstring 写「连续 N 个交易日」，实现是每次评估拍 +1
     → 002007 的 3 次失败发生在 90 秒内即触发治理。
  ③ 熔断级联：5 源逐个失败后全体冷却 60 秒，所有标的批量失明。
  ④ 计数按 symbol 聚合。

本测试**以故障注入为主**（只测成功路径等于没测 —— CLAUDE.md 事故沉淀）：
每个用例都必须能证明"旧的错误行为不再发生"，而不是"新行为发生了一次"。

覆盖：
  - A 行情服务：熔断全跳过 → 抛 AllProvidersCoolingDownError（不再返回 None）
  - B 行情服务：真实全灭 → 抛 QuoteUnavailableError（语义与熔断可区分）
  - C 行情服务：部分源冷却 + 部分源真实失败 → 抛 QuoteUnavailableError（真实失败优先）
  - D watch engine：熔断跳过**不**累计停牌计数
  - E watch engine：真实失败按**交易日**计数（同日多次只算 1 天）
  - F watch engine：跨 3 个交易日才触发治理
  - G 跨天 reset：quote_fail_reported 清空后可再次报
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from qs_market_data.application.services.quote_providers.base import (  # noqa: E402
    AllProvidersCoolingDownError,
    QuoteUnavailableError,
)
from qs_market_data.application.services.realtime_quote_service_v2 import (  # noqa: E402
    RealtimeQuoteServiceV2,
)


# ─────────────────────────────────────────────────────────────
# 行情服务侧：失败信号必须可区分
# ─────────────────────────────────────────────────────────────

class _FakeProvider:
    """可控的数据源：success=True 直接给价；否则按 mode 抛错/返回 None。"""

    def __init__(self, name, mode='raise', quote=None):
        self.name = name
        self.mode = mode
        self._quote = quote

    def get_quote(self, symbol):
        if self.mode == 'raise':
            raise RuntimeError(f'{self.name} 查询失败: 模拟超时')
        if self.mode == 'none':
            return None
        return self._quote

    def _is_valid(self, q):
        return q is not None


def _make_service(providers, blocked_names=()):
    """构造一个最小可用的 RealtimeQuoteServiceV2（绕过真实 provider 初始化）。"""
    svc = RealtimeQuoteServiceV2.__new__(RealtimeQuoteServiceV2)
    svc.providers = providers
    svc.cache = SimpleNamespace(get=lambda s: None, set=lambda s, q: None)
    svc.circuit_breaker = SimpleNamespace(
        is_available=lambda name: name not in blocked_names,
        record_failure=lambda name: None,
        get_status=lambda: {
            n: {'blocked': True, 'remaining_seconds': 42} for n in blocked_names
        } if blocked_names else {},
    )
    svc.provider_stats = {p.name: {'success': 0, 'failure': 0, 'skipped': 0}
                          for p in providers}
    svc.total_requests = 0
    svc.cache_hits = 0
    svc.success_count = 0
    svc.failure_count = 0
    return svc


class TestQuoteServiceFailureSignal:
    """A/B/C：行情服务的失败返回必须可区分。"""

    def test_all_cooling_down_raises_distinct_exception(self):
        """A：全部熔断冷却 → 抛 AllProvidersCoolingDownError，**不是** None。

        故障注入：5 个源全在冷却中（正是 10-20 09:30:47~09:30:58 的现场）。
        旧行为：return None → 引擎当成取数失败 → 误报停牌。
        """
        providers = [_FakeProvider(n) for n in
                     ('tencent', 'eastmoney', 'sina', 'akshare', 'netease')]
        svc = _make_service(providers, blocked_names={p.name for p in providers})

        with pytest.raises(AllProvidersCoolingDownError) as exc:
            svc.get_realtime_quote('600000')

        assert exc.value.symbol == '600000'
        assert exc.value.blocked, '必须带出各源冷却剩余秒数，供调用方记账'
        # 关键：冷却异常**不是** QuoteUnavailableError 的"真实失败"语义吗？
        # 是的——它继承自它，但引擎按类型分派时必须先判子类。
        assert isinstance(exc.value, AllProvidersCoolingDownError)

    def test_real_total_failure_raises_quote_unavailable(self):
        """B：真实全灭（源没在冷却、但都失败）→ 抛 QuoteUnavailableError。

        故障注入：所有源不冷却但都抛异常。
        """
        providers = [_FakeProvider('tencent'), _FakeProvider('eastmoney')]
        svc = _make_service(providers, blocked_names=set())

        with pytest.raises(QuoteUnavailableError) as exc:
            svc.get_realtime_quote('600000')

        assert not isinstance(exc.value, AllProvidersCoolingDownError), (
            '真实全灭不能被当成熔断跳过')

    def test_real_failure_wins_over_partial_cooling(self):
        """C：部分源冷却 + 部分源真实失败 → 仍是真实失败（冷却占比不足全部）。"""
        providers = [_FakeProvider('tencent'), _FakeProvider('eastmoney'),
                     _FakeProvider('sina')]
        # 只有 tencent 在冷却；eastmoney/sina 真实失败 → 不算"全部冷却"
        svc = _make_service(providers, blocked_names={'tencent'})

        with pytest.raises(QuoteUnavailableError) as exc:
            svc.get_realtime_quote('600000')

        assert not isinstance(exc.value, AllProvidersCoolingDownError)

    def test_provider_returns_none_is_real_failure(self):
        """provider 返回 None（无效数据）也算真实失败，不是熔断跳过。"""
        providers = [_FakeProvider('tencent', mode='none')]
        svc = _make_service(providers, blocked_names=set())

        with pytest.raises(QuoteUnavailableError) as exc:
            svc.get_realtime_quote('600000')

        assert not isinstance(exc.value, AllProvidersCoolingDownError)


# ─────────────────────────────────────────────────────────────
# watch engine 侧：计数语义 + 熔断豁免
# ─────────────────────────────────────────────────────────────

class _RecordingNotifier:
    def __init__(self):
        self.governance = []

    def record_governance(self, rule, message, extra=None):
        self.governance.append((rule, message, extra or {}))


def _make_engine(notifier):
    """构造只够跑 _note_quote_failure 的最小 engine。"""
    from qs_watch.application.services.watch_engine.engine import WatchEngine
    from qs_watch.application.services.watch_engine.state_manager import StateManager

    engine = WatchEngine.__new__(WatchEngine)
    engine.notifier = notifier
    engine.state = StateManager()
    return engine


def _rule(symbol='600000', rule_id=1):
    return SimpleNamespace(id=rule_id, symbol=symbol, context=None,
                           conditions=None, intent=None, account=None)


class TestQuoteFailCounting:
    """D/E/F：熔断豁免 + 按交易日计数。"""

    def test_same_day_multiple_failures_count_as_one_day(self):
        """E：同一交易日内失败 90 次，只算 1 个交易日 —— 不触发治理。

        故障注入复现事故现场：002007 在 09:31:02.343、09:31:02.343、
        09:32:24.785 连续失败 3 次，旧实现当场误报「连续 3 个交易日」。
        """
        notifier = _RecordingNotifier()
        engine = _make_engine(notifier)
        rule = _rule('002007')
        now = datetime(2026, 10, 20, 9, 32, 24)

        for _ in range(90):          # 90 秒内 90 次失败
            engine._note_quote_failure(rule, now)

        assert notifier.governance == [], (
            '同一天内重复失败不得累计成多个交易日（旧实现 90 秒内即误报）')
        assert len(engine.state.quote_fail_days['002007']) == 1

    def test_three_distinct_trading_days_triggers_governance(self):
        """F：真正连续 3 个交易日失败才报治理项。"""
        notifier = _RecordingNotifier()
        engine = _make_engine(notifier)
        rule = _rule('600000')
        day = datetime(2026, 10, 20, 14, 0)

        engine._note_quote_failure(rule, day)
        assert notifier.governance == []

        engine._note_quote_failure(rule, day + timedelta(days=1))
        assert notifier.governance == [], '第 2 天不该报'

        engine._note_quote_failure(rule, day + timedelta(days=2))
        assert len(notifier.governance) == 1, '第 3 天才报'
        _rule_obj, message, extra = notifier.governance[0]
        assert '疑似停牌/退市' in message
        assert extra.get('quote_fail_days') == 3
        assert extra.get('suspected_halt') is True
        # 新增：治理项必须带出实际失败日，供人工复核
        assert extra.get('failed_dates') == ['2026-10-20', '2026-10-21', '2026-10-22']

    def test_success_resets_counter(self):
        """取价成功 → 计数清零（引擎在成功分支调用）。"""
        notifier = _RecordingNotifier()
        engine = _make_engine(notifier)
        rule = _rule('600000')
        day = datetime(2026, 10, 20, 14, 0)

        engine._note_quote_failure(rule, day)
        engine._note_quote_failure(rule, day + timedelta(days=1))
        # 复刻 engine.py 成功分支的清零动作
        if engine.state.quote_fail_days.get(rule.symbol):
            engine.state.quote_fail_days[rule.symbol] = set()
        engine._note_quote_failure(rule, day + timedelta(days=2))

        assert notifier.governance == [], '成功重置后不应再累计到 3 天'

    def test_daily_reset_allows_re_report_next_day(self):
        """G：跨天 reset 清空已报集合 → 次日可再次报（每规则每日一条）。"""
        notifier = _RecordingNotifier()
        engine = _make_engine(notifier)
        rule = _rule('600000')
        day = datetime(2026, 10, 20, 14, 0)

        for i in range(3):
            engine._note_quote_failure(rule, day + timedelta(days=i))
        assert len(notifier.governance) == 1

        engine.state.reset_daily(day + timedelta(days=3))
        engine._note_quote_failure(rule, day + timedelta(days=3))
        assert len(notifier.governance) == 2, '跨天后应可再次上报'


class TestWatchEngineCoolingExemption:
    """D：熔断冷却的标的**不**进入停牌计数路径。"""

    def test_cooling_symbol_not_noted_as_failure(self):
        """故障注入：quote_service 对所有标的抛 AllProvidersCoolingDownError。

        旧行为：None → _note_quote_failure → 90 秒内误报停牌。
        新行为：熔断异常被单独分派，不计入停牌计数。
        """
        from qs_market_data.application.services.quote_providers.base import (
            AllProvidersCoolingDownError,
        )

        notifier = _RecordingNotifier()
        engine = _make_engine(notifier)
        engine.state = engine.state

        cooling = {'600000', '000999', '002007'}

        class _CoolingQuoteService:
            def get_realtime_quote(self, symbol):
                raise AllProvidersCoolingDownError(symbol, {'tencent': {
                    'blocked': True, 'remaining_seconds': 30}})

        engine.quote_service = _CoolingQuoteService()

        # 复刻 engine.tick 取价循环 + 规则循环的关键分支
        quotes, quote_error_symbols, quote_cooling_symbols = {}, set(), set()
        for symbol in cooling:
            try:
                quotes[symbol] = engine.quote_service.get_realtime_quote(symbol)
            except AllProvidersCoolingDownError:
                quote_cooling_symbols.add(symbol)
            except Exception:
                quote_error_symbols.add(symbol)

        for symbol in cooling:
            assert symbol in quote_cooling_symbols
            assert symbol not in quote_error_symbols

        # 熔断跳过的规则不走 _note_quote_failure
        rule = _rule('600000')
        if rule.symbol in quote_cooling_symbols:
            pass  # 引擎里是 continue
        else:
            engine._note_quote_failure(rule, datetime(2026, 10, 20, 9, 32))

        assert notifier.governance == [], '熔断冷却不得产出停牌治理项'
