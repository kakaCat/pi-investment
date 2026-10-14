"""FR-1 回归锁（REQ-261007101318-c392）：`tick()` 的**日级**开市闸门。

背景（需求文档取证 E4）：`tick()` 的自检只判「周末 + 交易时段」，**不判法定节假日**——
日级闸门此前只在 `run_forever()` 那一层。于是任何旁路调用（补跑脚本 / 新服务 / 其他窗口）
在国庆这类休市日的盘中时段会**照常判定并推送**。用户 2026-10-07（周三·休市）收到的
「盯盘触发 - 688525 / 现价 192.35 ≤ 阈值 218.24（下破）」正是这一形态。

本文件锁定三条（全部用注入判定 + 冻结时钟，不依赖真实日期）：
  1. 休市日：零事件，且**连规则都不取**（"不判定"而不是"判定后丢弃"）；
  2. 交易日盘中：正常判定并下发级别（FR-4：级别恒有）；
  3. 交易日盘后：仍拦住；
外加一条：默认闸门（未注入时）真的认识法定节假日。
"""
from datetime import date, datetime
from types import SimpleNamespace

from application.services.watch_engine.engine import WatchEngine

HOLIDAY_1000 = datetime(2026, 10, 7, 10, 0, 0)     # 国庆休市 · 周三 · 盘中时段
TRADING_1000 = datetime(2026, 9, 30, 10, 0, 0)     # 节前最后交易日 · 盘中
TRADING_1600 = datetime(2026, 9, 30, 16, 0, 0)     # 同一交易日 · 盘后


class _Repo:
    def __init__(self, rules):
        self.rules = rules
        self.calls = 0

    def list_enabled(self):
        self.calls += 1
        return self.rules


class _Quotes:
    def __init__(self, price):
        self.price = price

    def get_realtime_quote(self, symbol):
        return SimpleNamespace(symbol=symbol, price=self.price, change_pct=-1.0,
                               volume=None, prev_close=self.price * 1.02)


class _Notifier:
    def __init__(self):
        self.calls = []

    def notify(self, rule, condition, quote, result, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(id=1, todo_id=None)

    def record_governance(self, *args, **kwargs):  # pragma: no cover - 本用例不触发
        return None


def _rule():
    """688525 佰维存储 · 下破 218.24（与用户收到的那张卡同参数）。"""
    return SimpleNamespace(
        id=501, symbol='688525.SH', account='agent_brain', intent='exit_stop',
        lifecycle_stage='holding', next_action_hint=None, context=None,
        cost_price=None, action_hint=None, active_window=None, expires_at=None,
        noise_state=None, suppress_until=None, scope='position',
        conditions=[{'type': 'price_break',
                     'params': {'price': 218.24, 'direction': 'below'},
                     'cooldown_sec': 600}],
    )


def _engine(now, is_trading_day):
    repo, notifier = _Repo([_rule()]), _Notifier()
    engine = WatchEngine(repo, _Quotes(192.35), notifier, now_fn=lambda: now,
                         is_trading_day_fn=lambda day: is_trading_day)
    return engine, repo, notifier


def test_holiday_tick_produces_nothing_and_never_reads_rules():
    """休市日（2026-10-07 盘中）：**零事件**，且连规则都不取。"""
    engine, repo, notifier = _engine(HOLIDAY_1000, is_trading_day=False)
    assert engine.tick() == []
    assert repo.calls == 0, '休市日不该进入判定（不是"判定后丢弃"）'
    assert notifier.calls == [], '休市日不得产生任何外发'


def test_trading_day_in_session_still_evaluates_and_carries_level():
    """交易日盘中：照常判定；级别恒下发（FR-4，闭环开关不再吞掉级别）。"""
    engine, repo, notifier = _engine(TRADING_1000, is_trading_day=True)
    events = engine.tick()
    assert len(events) == 1
    assert repo.calls >= 1, '交易日必须真的去取规则（与休市日的 0 次形成对照）'
    assert notifier.calls, '交易日触发必须发通知'
    assert notifier.calls[0].get('level'), '级别必须下发（旧实现闭环关闭时为 None）'
    assert notifier.calls[0].get('closed_loop') is False, '未注入 todo_service → 如实标注闭环未开'


def test_trading_day_off_session_is_still_blocked():
    """交易日盘后：仍拦住（时段闸门不因本次改动而放松）。"""
    engine, repo, _ = _engine(TRADING_1600, is_trading_day=True)
    assert engine.tick() == []
    assert repo.calls == 0


def test_default_gate_knows_calendar_holiday():
    """未注入时默认走 TradingDayGuard：节假日判非交易日，节前最后交易日判交易日。"""
    engine, _, _ = _engine(TRADING_1000, is_trading_day=True)
    engine._is_trading_day_fn = None          # 摘掉注入 → 用真实默认闸门
    engine._trading_day_verdict_fn = None

    holiday, holiday_src = engine._resolve_trading_day(date(2026, 10, 7))
    trading, trading_src = engine._resolve_trading_day(date(2026, 9, 30))

    assert holiday is False, f'2026-10-07 是休市日，默认闸门必须拦住（source={holiday_src}）'
    assert 'holiday' in holiday_src
    assert trading is True, f'2026-09-30 是交易日（source={trading_src}）'


# ── t5 补充：run_forever 整环 + 跳过留痕去重（设计 §6 登记的未覆盖项）─────────────

def _drive_one_loop(monkeypatch, engine):
    """跑 run_forever 的**一轮**就停：把 sleep 换成停机开关，绝不真睡、绝不落库心跳。"""
    import application.services.watch_engine.engine as engine_mod

    monkeypatch.setenv('WATCH_HEARTBEAT_ENABLED', 'false')   # 心跳会写库，链路测试里关掉
    calls = []
    monkeypatch.setattr(engine, 'tick', lambda: calls.append(1) or [])
    monkeypatch.setattr(engine_mod.time_module, 'sleep',
                        lambda seconds: setattr(engine, '_stopped', True))
    engine.run_forever()
    return calls


def test_run_forever_does_not_tick_on_holiday(monkeypatch):
    """整环口径（不只是 tick 自己）：休市日 run_forever 一轮都不进 tick。"""
    engine, repo, _ = _engine(HOLIDAY_1000, is_trading_day=False)
    assert _drive_one_loop(monkeypatch, engine) == []
    assert repo.calls == 0


def test_run_forever_ticks_on_trading_day(monkeypatch):
    """对照：交易日盘中必须真的进 tick（否则"休市日不进"可能是引擎整体不转）。"""
    engine, _, _ = _engine(TRADING_1000, is_trading_day=True)
    assert _drive_one_loop(monkeypatch, engine) == [1]


def test_closed_skip_log_is_deduped_by_day_and_reason():
    """跳过留痕按「日 + 原因」去重：同日同因只留一条，原因不同才是另一条。"""
    engine, _, _ = _engine(HOLIDAY_1000, is_trading_day=False)
    engine._log_market_closed(HOLIDAY_1000, is_trading_day=False, in_session=True,
                              day_source='trading-calendar-holiday')
    engine._log_market_closed(HOLIDAY_1000, is_trading_day=False, in_session=True,
                              day_source='trading-calendar-holiday')
    assert len(engine._closed_skip_logged) == 1, '同日同因不得刷屏'

    engine._log_market_closed(HOLIDAY_1000, is_trading_day=True, in_session=False,
                              day_source='trading-calendar')
    assert len(engine._closed_skip_logged) == 2, '原因不同（非时段）应各自留痕'
