"""TradingDayGuard 单测（步2 交易日判断收口，2026-09-11，w-f4aa1f6a）

覆盖：
1. judge_trading_day 纯函数语义（周末/未来/有K线/当日启发式/过去无K线）
2. TradingDayGuard 的判定来源与降级标记（monkeypatch 数据源，不依赖真实 DB）
3. 写入型守卫 should_write_daily 的语义
4. 兼容层：live_trading.simulation_trader.judge_trading_day 仍可用（同名委托）
"""
from datetime import date

import pytest

from application.services.trading_day_guard import (
    SOURCE_COMPUTE_ERROR,
    SOURCE_INTRADAY,
    SOURCE_KLINE,
    SOURCE_NO_DATA,
    SOURCE_UNAVAILABLE,
    SOURCE_WEEKEND,
    TradingDayGuard,
    judge_trading_day,
    reset_degraded_loud_log,
)


# ── 1. 纯函数 ────────────────────────────────────────────────
def test_weekend_is_never_trading_day():
    # 2026-08-08 是周六——正是历史上被写入 5 条合成快照的那天
    assert judge_trading_day(
        date(2026, 8, 8), kline_exists_on_date=True,
        latest_kline_date=date(2026, 8, 7), today=date(2026, 8, 8),
    ) is False


def test_future_date_is_not_trading_day():
    assert judge_trading_day(
        date(2026, 9, 30), kline_exists_on_date=False,
        latest_kline_date=date(2026, 9, 11), today=date(2026, 9, 11),
    ) is False


def test_kline_present_means_trading_day():
    assert judge_trading_day(
        date(2026, 9, 10), kline_exists_on_date=True,
        latest_kline_date=date(2026, 9, 10), today=date(2026, 9, 11),
    ) is True


def test_today_without_kline_uses_recent_activity_heuristic():
    """盘中场景：日K 17:40 才落库，不能因"今天还没K线"判非交易日
    （2026-08-12 事故：v13/v14 调仓因此从未执行却记 success）。"""
    assert judge_trading_day(
        date(2026, 9, 11), kline_exists_on_date=False,
        latest_kline_date=date(2026, 9, 10), today=date(2026, 9, 11),
    ) is True


def test_today_with_stale_market_is_not_trading_day():
    assert judge_trading_day(
        date(2026, 9, 11), kline_exists_on_date=False,
        latest_kline_date=date(2026, 8, 1), today=date(2026, 9, 11),
    ) is False


def test_past_weekday_without_kline_is_holiday():
    assert judge_trading_day(
        date(2026, 10, 1), kline_exists_on_date=False,
        latest_kline_date=date(2026, 9, 30), today=date(2026, 10, 8),
    ) is False


# ── 2. 护栏判定来源与降级 ─────────────────────────────────────
@pytest.fixture(autouse=True)
def _clear_guard_cache():
    from application.services import trading_day_guard as m

    m._verdict_cache.clear()
    yield
    m._verdict_cache.clear()


def test_check_source_weekend(monkeypatch):
    called = {'n': 0}

    def _boom(day):
        called['n'] += 1
        raise AssertionError('周末不应查数据源')

    monkeypatch.setattr(TradingDayGuard, '_kline_stats', staticmethod(_boom))
    v = TradingDayGuard.check('2026-08-08')
    assert v.is_trading_day is False
    assert v.source == SOURCE_WEEKEND and v.degraded is False
    assert called['n'] == 0


def test_check_source_kline(monkeypatch):
    monkeypatch.setattr(
        TradingDayGuard, '_kline_stats',
        staticmethod(lambda day: (True, date(2026, 9, 10))),
    )
    v = TradingDayGuard.check('2026-09-10')
    assert v.is_trading_day is True
    assert v.source == SOURCE_KLINE and v.degraded is False


def test_check_marks_intraday_heuristic_degraded(monkeypatch):
    monkeypatch.setattr(
        TradingDayGuard, '_kline_stats',
        staticmethod(lambda day: (False, date.today())),
    )
    v = TradingDayGuard.check(date.today())
    assert v.is_trading_day is True
    assert v.source == SOURCE_INTRADAY and v.degraded is True


def test_check_no_data_source(monkeypatch):
    monkeypatch.setattr(
        TradingDayGuard, '_kline_stats',
        staticmethod(lambda day: (False, date(2026, 9, 10))),
    )
    v = TradingDayGuard.check('2026-09-09')
    assert v.is_trading_day is False
    assert v.source == SOURCE_NO_DATA


def test_check_datasource_failure_is_conservative_and_visible(monkeypatch):
    def _boom(day):
        raise RuntimeError('db down')

    monkeypatch.setattr(TradingDayGuard, '_kline_stats', staticmethod(_boom))
    v = TradingDayGuard.check('2026-09-10')
    assert v.is_trading_day is False          # 保守：宁可少写，不写合成数据
    assert v.source == SOURCE_UNAVAILABLE and v.degraded is True


# ── 2.1 取数层类型契约（2026-09-14 w-2129d492 回归锚点）────────
# 事故：B3 重构把裸 SQL（psycopg2 直回 date 对象）换成仓储后，
# get_latest_trade_date() 回 'YYYY-MM-DD' 字符串，而 judge_trading_day 要拿它做
# (today - latest_kline_date).days → TypeError。异常沿 resume_from_breakpoint →
# start_orchestrator 上抛，把 orchestrator 的 tick 线程打死一整天（255 次 tick error，
# 盘前撮合与 T1 结算全天未执行）。
# 既有用例都直接喂 date 对象，所以一个都没红——这两条专测"取数层回字符串"。


class _FakeKlineRepo:
    """替身仓储：模拟 get_latest_trade_date 回 ISO 字符串（真实行为）。"""

    latest = '2026-09-10'
    has_bar = False

    def __init__(self, *args, **kwargs):
        pass

    def has_bar_on_date(self, day):
        return type(self).has_bar

    def get_latest_trade_date(self):
        return type(self).latest


@pytest.fixture
def _fake_kline_repo(monkeypatch):
    import adapters.outbound.repositories.kline_repository as repo_mod

    monkeypatch.setattr(repo_mod, 'KlineORMRepository', _FakeKlineRepo)

    def _set(has_bar: bool, latest):
        _FakeKlineRepo.has_bar = has_bar
        _FakeKlineRepo.latest = latest

    return _set


def test_kline_stats_coerces_string_latest_date_to_date(_fake_kline_repo):
    """取数层回字符串时，_kline_stats 必须把它归一成 date（否则下游相减就炸）。"""
    from application.services.trading_day_guard import TradingDayGuard

    _fake_kline_repo(has_bar=False, latest='2026-09-11')
    exists, latest = TradingDayGuard._kline_stats(date(2026, 9, 14))
    assert exists is False
    assert isinstance(latest, date), '取数层的字符串日期必须在此归一为 date'
    assert latest == date(2026, 9, 11)


def test_today_intraday_heuristic_works_with_string_repo_date(_fake_kline_repo):
    """端到端复现：今天无K线 + 取数层回字符串 → 必须给出判定而不是抛 TypeError。"""
    from application.services.trading_day_guard import TradingDayGuard

    _fake_kline_repo(has_bar=False, latest=date.today().isoformat())
    v = TradingDayGuard.check(date.today(), use_cache=False)   # 不得抛异常
    assert v.is_trading_day is True
    assert v.source == SOURCE_INTRADAY and v.degraded is True


def test_check_tolerates_string_from_stats_even_if_coercion_is_lost(monkeypatch):
    """契约级兜底：即使将来 _kline_stats 又回字符串，check() 也不得抛异常。

    与上两条的分工：上面测"归一化在不在"，这条测"就算归一化被后人删掉，
    击穿调用方的路径也不存在"——09-14 的事故形态就是异常直接上抛踢死 orchestrator。
    """
    from application.services.trading_day_guard import TradingDayGuard

    monkeypatch.setattr(
        TradingDayGuard, '_kline_stats',
        staticmethod(lambda day: (False, date.today().isoformat())),   # 故意回字符串
    )
    v = TradingDayGuard.check(date.today(), use_cache=False)   # 不得抛
    assert v.is_trading_day is False
    assert v.source == SOURCE_COMPUTE_ERROR and v.degraded is True


def test_compute_failure_degrades_instead_of_raising(monkeypatch):
    """判定阶段任何异常都不许击穿调用方：必须降级为"不可用"并留痕。"""
    from application.services.trading_day_guard import TradingDayGuard

    def _boom(day):
        raise TypeError("unsupported operand type(s) for -: 'datetime.date' and 'str'")

    monkeypatch.setattr(TradingDayGuard, '_compute', classmethod(lambda cls, d: _boom(d)))
    v = TradingDayGuard.check('2026-09-10', use_cache=False)   # orchestrator 场景：不许抛
    assert v.is_trading_day is False
    # 与"数据源不可用"区分：这是判定器自身的 bug，不是行情问题（复查 M4）
    assert v.source == SOURCE_COMPUTE_ERROR and v.degraded is True


# ── 2.2 降级必须吵（复查 M4）：布尔入口不许把"判不了"静默成"今天不是交易日" ──
class _FakeLogger:
    """捕获 structlog 调用的假 logger。

    为什么不caplog：本模块用 structlog（console renderer 直写 stdout），
    pytest 的 caplog 抓不到 —— 用 caplog 写的断言会"恒空 = 恒真/恒假"，
    正是本仓反复踩的假验证。这里直接盯住 logger 的调用。
    """

    def __init__(self):
        self.calls = []

    def _record(self, level):
        def _fn(event, **kw):
            self.calls.append({'level': level, 'event': event, **kw})
        return _fn

    def __getattr__(self, name):
        return self._record(name)


@pytest.fixture
def _fake_guard_logger(monkeypatch):
    from application.services import trading_day_guard as mod

    fake = _FakeLogger()
    monkeypatch.setattr(mod, 'logger', fake)
    reset_degraded_loud_log()
    yield fake
    reset_degraded_loud_log()


def test_is_trading_day_logs_loud_when_degraded(monkeypatch, _fake_guard_logger):
    """orchestrator 等调用方拿的是布尔值 → 降级必须自己发出声音。"""
    monkeypatch.setattr(
        TradingDayGuard, '_kline_stats',
        staticmethod(lambda day: (_ for _ in ()).throw(RuntimeError('db down'))),
    )
    assert TradingDayGuard.is_trading_day('2026-09-10') is False
    loud = [c for c in _fake_guard_logger.calls
            if c['event'] == 'trading_day_guard_degraded_verdict_consumed_as_bool']
    assert loud, '降级经布尔入口消费时必须留痕'
    assert loud[0]['level'] == 'warning'      # 数据源问题 → warning
    assert loud[0]['source'] == SOURCE_UNAVAILABLE


def test_compute_error_degradation_is_error_level(monkeypatch, _fake_guard_logger):
    """判定器自身 bug 要比数据源问题更响（error）。"""
    monkeypatch.setattr(
        TradingDayGuard, '_compute',
        classmethod(lambda cls, d: (_ for _ in ()).throw(TypeError('boom'))),
    )
    TradingDayGuard.is_trading_day('2026-09-11')   # 必须是过去/当天：未来日期会提前 return
    loud = [c for c in _fake_guard_logger.calls
            if c['event'] == 'trading_day_guard_degraded_verdict_consumed_as_bool']
    assert loud and loud[0]['level'] == 'error'
    assert loud[0]['source'] == SOURCE_COMPUTE_ERROR


def test_is_trading_day_degraded_log_is_deduped_per_day(monkeypatch, _fake_guard_logger):
    """tick 每分钟一次：同一天同一来源只吵一次，不能刷屏。"""
    monkeypatch.setattr(
        TradingDayGuard, '_kline_stats',
        staticmethod(lambda day: (_ for _ in ()).throw(RuntimeError('db down'))),
    )
    for _ in range(3):
        # 必须选"过去的工作日"：周末/未来日期会在判定前提前 return，根本到不了降级分支
        # （我第一版就写成了 09-12 周六，测试因此假失败——日期选择本身就是个坑）
        TradingDayGuard.is_trading_day('2026-09-11')   # 上周五
    hits = [c for c in _fake_guard_logger.calls
            if c['event'] == 'trading_day_guard_degraded_verdict_consumed_as_bool']
    assert len(hits) == 1, '同一天同一来源应只留痕一次，实际 %d' % len(hits)


def test_is_trading_day_does_not_log_for_normal_verdicts(monkeypatch, _fake_guard_logger):
    """正常判定（交易日/周末）不许产生降级留痕噪声。"""
    monkeypatch.setattr(
        TradingDayGuard, '_kline_stats',
        staticmethod(lambda day: (True, date(2026, 9, 10))),
    )
    assert TradingDayGuard.is_trading_day('2026-09-10') is True
    assert TradingDayGuard.is_trading_day('2026-08-08') is False   # 周末：非降级
    assert not [c for c in _fake_guard_logger.calls
                if c['event'] == 'trading_day_guard_degraded_verdict_consumed_as_bool']


def test_compute_error_is_distinguishable_from_datasource_unavailable(monkeypatch):
    """两种降级必须可区分：数据源不可用 vs 判定器异常（前者是行情，后者是 bug）。"""
    from application.services.trading_day_guard import TradingDayGuard

    monkeypatch.setattr(
        TradingDayGuard, '_kline_stats',
        staticmethod(lambda day: (_ for _ in ()).throw(RuntimeError('db down'))),
    )
    v_src = TradingDayGuard.check('2026-09-10', use_cache=False)
    assert v_src.source == SOURCE_UNAVAILABLE

    monkeypatch.setattr(
        TradingDayGuard, '_compute',
        classmethod(lambda cls, d: (_ for _ in ()).throw(TypeError('boom'))),
    )
    v_bug = TradingDayGuard.check('2026-09-10', use_cache=False)
    assert v_bug.source == SOURCE_COMPUTE_ERROR
    assert v_bug.source != v_src.source


# ── 3. 写入型守卫 ────────────────────────────────────────────
def test_should_write_daily_blocks_weekend():
    v = TradingDayGuard.should_write_daily('2026-08-08')
    assert v.is_trading_day is False and v.source == SOURCE_WEEKEND


def test_should_write_daily_allows_trading_day(monkeypatch):
    monkeypatch.setattr(
        TradingDayGuard, '_kline_stats',
        staticmethod(lambda day: (True, date(2026, 9, 10))),
    )
    assert TradingDayGuard.should_write_daily('2026-09-10').is_trading_day is True


# ── 4. 兼容层 ────────────────────────────────────────────────
def test_simulation_trader_reexport_still_works():
    from live_trading.simulation_trader import judge_trading_day as legacy

    assert legacy(
        date(2026, 8, 8), kline_exists_on_date=True,
        latest_kline_date=date(2026, 8, 7), today=date(2026, 8, 8),
    ) is False
    assert legacy(
        date(2026, 9, 10), kline_exists_on_date=True,
        latest_kline_date=date(2026, 9, 10), today=date(2026, 9, 11),
    ) is True

# ── 2.3 降级主动外发告警（飞书）────────────────────────────────
# 守卫热路径不 import 通知栈：通道由应用启动注入（install_degraded_alert_notifier）。
# 这里用替身通道验证"发不发/发几条/什么紧急度/失败是否影响判定"。
@pytest.fixture
def _fake_alert_sink(monkeypatch):
    from application.services import trading_day_guard as mod

    sent = []

    def sink(title, content, urgency):
        sent.append({'title': title, 'content': content, 'urgency': urgency})
        return True

    mod.install_degraded_alert_notifier(sink)
    reset_degraded_loud_log()
    yield sent
    mod.install_degraded_alert_notifier(None)
    reset_degraded_loud_log()


def test_degraded_compute_error_alerts_high_immediately(monkeypatch, _fake_alert_sink):
    """判定器自身异常 = 代码 bug → 首次就 high，不能等 30 分钟。"""
    monkeypatch.setattr(
        TradingDayGuard, '_compute',
        classmethod(lambda cls, d: (_ for _ in ()).throw(TypeError('boom'))),
    )
    assert TradingDayGuard.is_trading_day('2026-09-11') is False
    assert len(_fake_alert_sink) == 1
    assert _fake_alert_sink[0]['urgency'] == 'high'
    assert SOURCE_COMPUTE_ERROR in _fake_alert_sink[0]['content']


def test_degraded_datasource_alerts_normal_then_escalates(monkeypatch, _fake_alert_sink):
    """数据源不可用：首发 normal；持续超过冷却期仍未恢复 → 升 high 再报一次。"""
    from application.services import trading_day_guard as mod

    monkeypatch.setattr(
        TradingDayGuard, '_kline_stats',
        staticmethod(lambda day: (_ for _ in ()).throw(RuntimeError('db down'))),
    )
    clock = {'t': 1_000_000.0}
    monkeypatch.setattr(mod, '_now_seconds', lambda: clock['t'])

    assert TradingDayGuard.is_trading_day('2026-09-11') is False
    assert len(_fake_alert_sink) == 1 and _fake_alert_sink[0]['urgency'] == 'normal'

    clock['t'] += 60          # 只过了一分钟：不重复打扰
    TradingDayGuard.is_trading_day('2026-09-11')
    assert len(_fake_alert_sink) == 1

    clock['t'] += 31 * 60     # 持续未恢复：升级一次
    TradingDayGuard.is_trading_day('2026-09-11')
    assert len(_fake_alert_sink) == 2 and _fake_alert_sink[1]['urgency'] == 'high'

    clock['t'] += 61 * 60     # 已达上限：不再刷屏
    TradingDayGuard.is_trading_day('2026-09-11')
    assert len(_fake_alert_sink) == 2


def test_alert_sink_failure_does_not_break_verdict(monkeypatch):
    """告警通道炸了也不能影响判定结果（告警是旁路，不是依赖）。"""
    from application.services import trading_day_guard as mod

    def boom(title, content, urgency):
        raise RuntimeError('feishu down')

    mod.install_degraded_alert_notifier(boom)
    reset_degraded_loud_log()
    monkeypatch.setattr(
        TradingDayGuard, '_kline_stats',
        staticmethod(lambda day: (_ for _ in ()).throw(RuntimeError('db down'))),
    )
    try:
        assert TradingDayGuard.is_trading_day('2026-09-11') is False
    finally:
        mod.install_degraded_alert_notifier(None)
        reset_degraded_loud_log()


def test_no_alert_when_sink_not_installed(monkeypatch, _fake_guard_logger):
    """未注入通道（离线/测试环境）时只留痕不外发——不得因缺通道而报错。"""
    from application.services import trading_day_guard as mod

    assert mod._degraded_alert_sink is None
    monkeypatch.setattr(
        TradingDayGuard, '_kline_stats',
        staticmethod(lambda day: (_ for _ in ()).throw(RuntimeError('db down'))),
    )
    assert TradingDayGuard.is_trading_day('2026-09-11') is False


def test_no_alert_for_normal_verdicts(monkeypatch, _fake_alert_sink):
    """正常交易日/周末都不许外发告警。"""
    monkeypatch.setattr(
        TradingDayGuard, '_kline_stats',
        staticmethod(lambda day: (True, date(2026, 9, 10))),
    )
    assert TradingDayGuard.is_trading_day('2026-09-10') is True
    assert TradingDayGuard.is_trading_day('2026-08-08') is False
    assert _fake_alert_sink == []
