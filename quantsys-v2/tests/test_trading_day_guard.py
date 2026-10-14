"""TradingDayGuard 单测（步2 交易日判断收口 2026-09-11 w-f4aa1f6a；
交易日判定收敛到日历链 2026-10-04 REQ-261004154902-a7cd · FR-3）

覆盖：
1. `judge_trading_day` 纯函数语义（周末/未来/有K线/当日启发式/过去无K线）+ 新增末位可选参数
   `calendar_has_day`（None → 旧逻辑逐字保留）；
2. **FR-3 证伪点**：Guard 的「今天」分支以交易日历为准——
   2026-10-05 / 10-06 / 10-07 → 非交易日；2026-10-08（复市首日）→ 交易日；
3. 解析链降级（工作日回退）结论照用但 `degraded=True` + 留痕/外发；
   解析链异常 → 保守非交易日 + `degraded=True` + `unavailable`；
   K 线只作事后交叉校验（无K线 → 记降级，判定不变）；
4. 写入型守卫 `should_write_daily` 语义；
5. 兼容层：`live_trading.simulation_trader.judge_trading_day` 同名委托仍可用；
6. `TradingCalendarService` 的「工作日兜底」不再静默（source/degraded 带得出来）。

全部用例**零网络、零 DB、不依赖真实系统日期**：日历链的取数函数（表 / provider）被换成
假日历，"今天"由 `freeze_today` 冻结。假日历按上证公告口径只放真实交易日
（中秋 09-25~09-27 休市、国庆 10-01~10-07 休市、10-08 复市）。
"""
from datetime import date, datetime

import pytest

from application.services.trading_day_guard import (
    SOURCE_CALENDAR,
    SOURCE_CALENDAR_HOLIDAY,
    SOURCE_COMPUTE_ERROR,
    SOURCE_FUTURE,
    SOURCE_UNAVAILABLE,
    SOURCE_WEEKEND,
    TradingDayGuard,
    judge_trading_day,
    reset_degraded_loud_log,
)

# ── 通用夹具 ─────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _isolate_degraded_alert_sink():
    """本文件只测**判定语义**，不该真的把降级告警发出去。

    2026-10-03（REQ-261003150739-b98d 全量清点发现）：`_degraded_alert_sink` 是模块级全局，
    全量跑时别的用例已经把它接上（`install_degraded_alert_notifier`），于是本文件里
    「消费一次降级判定」就会经 NotificationFacade **真实外发**——**单跑复现不出来**（顺序相关），
    实测 3 个用例中招。这里在本文件范围内把 sink 摘掉，跑完还原（不影响文件外行为）。
    """
    from application.services import trading_day_guard as _tdg

    saved = _tdg._degraded_alert_sink
    _tdg.install_degraded_alert_notifier(None)
    try:
        yield
    finally:
        _tdg.install_degraded_alert_notifier(saved)


@pytest.fixture(autouse=True)
def _clear_guard_cache():
    """判定缓存 60 秒 + 两张"留痕去重表"都是模块级全局：逐用例清空，避免顺序相关。"""
    from application.services import trading_day_guard as m

    m._verdict_cache.clear()
    reset_degraded_loud_log()
    yield
    m._verdict_cache.clear()
    reset_degraded_loud_log()


@pytest.fixture
def freeze_today(monkeypatch):
    """把守卫眼里的"现在"冻结成指定日期（消除"今天星期几/真实日期"的时间依赖）。

    2026-10-02（REQ-261001145152-3982 审查）教训：用真实系统日期写守卫用例，
    会变成"只在工作日通过"的时间炸弹。这里显式注入。
    """

    def _freeze(target: date):
        import application.services.trading_day_guard as tdg

        class _FrozenDatetime(datetime):
            @classmethod
            def now(cls, tz=None):
                return cls(target.year, target.month, target.day, 10, 0, 0)

        monkeypatch.setattr(tdg, 'datetime', _FrozenDatetime)
        return target

    return _freeze


class _FakeLogger:
    """捕获 structlog 调用的假 logger。

    为什么不 caplog：本模块用 structlog（console renderer 直写 stdout），
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
    """`calendar_has_day=None`（缺省）时旧逻辑逐字保留：盘中场景日K 17:40 才落库，
    不能因"今天还没K线"判非交易日（2026-08-12 事故的另一面）。"""
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


# ── 1.1 新增 `calendar_has_day`（FR-3）────────────────────────
def test_calendar_says_holiday_beats_kline_activity():
    """反证：日历说休市时，即便"该日有K线 / 近 7 日活跃"也不得判交易日。

    2026-10-05（周一·国庆休市）在旧口径下是 True（会开火）——这是本卡要修的误判。
    """
    assert judge_trading_day(
        date(2026, 10, 5), kline_exists_on_date=True,
        latest_kline_date=date(2026, 10, 5), today=date(2026, 10, 5),
        calendar_has_day=False,
    ) is False


def test_calendar_says_trading_beats_stale_kline():
    """正证：复市首日 2026-10-08，K 线还没落库、且距最近K线 8 天（> 7 天），
    日历说交易日就是交易日（旧口径下这里是 False → 整天被跳过）。"""
    assert judge_trading_day(
        date(2026, 10, 8), kline_exists_on_date=False,
        latest_kline_date=date(2026, 9, 30), today=date(2026, 10, 8),
        calendar_has_day=True,
    ) is True


def test_calendar_none_is_exactly_the_legacy_logic():
    """同一组入参、只差 `calendar_has_day`：None → 旧逻辑；False → 日历口径。"""
    kwargs = dict(
        kline_exists_on_date=False, latest_kline_date=date(2026, 9, 30),
        today=date(2026, 10, 8),
    )
    assert judge_trading_day(date(2026, 10, 8), **kwargs) is False           # 旧：差 8 天 > 7
    assert judge_trading_day(date(2026, 10, 8), **kwargs, calendar_has_day=True) is True


def test_calendar_does_not_override_weekend_or_future():
    """周末 / 未来日期仍是硬否决（日历入参不得把它们翻成交易日）。"""
    # 2026-10-10 是周六
    assert judge_trading_day(
        date(2026, 10, 10), kline_exists_on_date=True,
        latest_kline_date=date(2026, 10, 9), today=date(2026, 10, 10),
        calendar_has_day=True,
    ) is False
    # 2026-10-12（周一）在未来
    assert judge_trading_day(
        date(2026, 10, 12), kline_exists_on_date=True,
        latest_kline_date=date(2026, 10, 9), today=date(2026, 10, 8),
        calendar_has_day=True,
    ) is False


def test_legacy_source_constants_still_importable():
    """旧来源常量保留（K 线不再是判定真源，但既有导入不许断）。"""
    from application.services import trading_day_guard as m

    assert (m.SOURCE_KLINE, m.SOURCE_INTRADAY, m.SOURCE_NO_DATA) == (
        'kline-data', 'intraday-recent-market', 'no-kline-data')


# ── 2. 假日历链（零网络零 DB）────────────────────────────────
# 真实交易日（只放本次用得到的那些）：中秋 09-25~09-27 休市、国庆 10-01~10-07 休市、10-08 复市
CALENDAR = (
    date(2026, 9, 24),
    date(2026, 9, 28),
    date(2026, 9, 29),
    date(2026, 9, 30),
    date(2026, 10, 8),
    date(2026, 10, 9),
)


def _table_reader(days):
    """复刻真 `_read_calendar_table` 的两条语义：① 覆盖校验(max >= anchor) ② 取 <=anchor 的最大交易日。"""
    coverage = max(days)

    def _read(anchor):
        if coverage < anchor:
            return None                      # 表不覆盖该日 → 交给 provider（真实现同样返回 None）
        candidates = [d for d in days if d <= anchor]
        return max(candidates) if candidates else None

    return _read


@pytest.fixture
def fake_calendar(monkeypatch):
    """注入假日历**取数函数**（不是替换 `resolve_trading_day` 本身）→ Guard 走真解析链逻辑。

    打在 resolver 模块自己的全局名上（被调函数所在模块），避免"桩打错地方、静默失效"。
    """
    from application.services import trading_day_resolver as tr

    monkeypatch.setattr(tr, '_read_calendar_table', _table_reader(CALENDAR))
    monkeypatch.setattr(
        tr, '_read_provider', lambda *a, **k: pytest.fail('表已覆盖该日，不应再调 provider')
    )


@pytest.fixture
def chain_unavailable(monkeypatch):
    """解析链全挂：表不可用 + provider 答不出 → 工作日回退（degraded=True）。"""
    from application.services import trading_day_resolver as tr

    monkeypatch.setattr(tr, '_read_calendar_table', lambda anchor: None)
    monkeypatch.setattr(tr, '_read_provider', lambda *a, **k: None)


@pytest.fixture
def chain_raises(monkeypatch):
    """解析链本身抛异常（如 DB 挂了且未就地降级）→ 判定器必须保守 + 可见。"""
    from application.services import trading_day_guard as tdg

    def _boom(day, **_kw):
        raise RuntimeError('calendar chain down')

    monkeypatch.setattr(tdg, 'resolve_trading_day', _boom)


# ── 2.1 `resolve_trading_day`（姊妹函数）判据 ─────────────────
def test_resolve_trading_day_holiday_returns_earlier_trading_day(fake_calendar):
    """判据：`result.date == day` ⟺ 交易日。休市日 → 返回其前一个交易日。"""
    from application.services import trading_day_resolver as tr

    for holiday in (date(2026, 10, 5), date(2026, 10, 6), date(2026, 10, 7)):
        result = tr.resolve_trading_day(holiday)
        assert result.date == date(2026, 9, 30) and result.date != holiday
        assert result.source == tr.SOURCE_CALENDAR_TABLE and result.degraded is False

    resumption = tr.resolve_trading_day(date(2026, 10, 8))
    assert (resumption.date, resumption.source, resumption.degraded) == (
        date(2026, 10, 8), tr.SOURCE_CALENDAR_TABLE, False)


def test_resolve_trading_day_table_not_covering_falls_to_provider(monkeypatch):
    """表不覆盖该日 → 必须继续走链（不许静默用表/用猜），provider 答得出就不算降级。"""
    from application.services import trading_day_resolver as tr

    monkeypatch.setattr(tr, '_read_calendar_table', _table_reader((date(2026, 9, 30),)))  # 覆盖到 09-30
    monkeypatch.setattr(tr, '_read_provider', lambda anchor, lookback: date(2026, 9, 30))

    result = tr.resolve_trading_day(date(2026, 10, 5))
    assert (result.date, result.source, result.degraded) == (
        date(2026, 9, 30), tr.SOURCE_PROVIDER, False)


def test_resolve_trading_day_weekday_fallback_is_degraded(monkeypatch):
    """链全挂 → 周一~周五回退：工作日答"是"、周末答"否"，但**必须** degraded=True。"""
    from application.services import trading_day_resolver as tr

    monkeypatch.setattr(tr, '_read_calendar_table', lambda anchor: None)
    monkeypatch.setattr(tr, '_read_provider', lambda *a, **k: None)

    thursday = tr.resolve_trading_day(date(2026, 10, 8))
    assert (thursday.date, thursday.source, thursday.degraded) == (
        date(2026, 10, 8), tr.SOURCE_WEEKDAY_FALLBACK, True)

    saturday = tr.resolve_trading_day(date(2026, 10, 10))
    assert saturday.date == date(2026, 10, 9) and saturday.date != date(2026, 10, 10)
    assert saturday.degraded is True


def test_resolve_trading_day_rejects_bare_string():
    """入参守卫：只接受 date / datetime（字符串由 Guard 入口归一化）。"""
    from application.services import trading_day_resolver as tr

    with pytest.raises(TypeError):
        tr.resolve_trading_day('2026-10-05')


# ── 3. Guard 判定（FR-3 证伪点）──────────────────────────────
def test_check_national_day_holidays_are_not_trading_days(fake_calendar, freeze_today, monkeypatch):
    """FR-3 证伪点 ①：2026-10-05 / 10-06 / 10-07（国庆休市）→ 非交易日。

    改前实测 True/True/True（会开火）；这三条就是本卡的回归锁。
    """
    freeze_today(date(2026, 10, 8))
    monkeypatch.setattr(
        TradingDayGuard, '_kline_stats',
        staticmethod(lambda day: pytest.fail('休市日的判定不该依赖 K 线')),
    )
    for raw in ('2026-10-05', '2026-10-06', '2026-10-07'):
        v = TradingDayGuard.check(raw, use_cache=False)
        assert v.is_trading_day is False, raw
        assert v.source == SOURCE_CALENDAR_HOLIDAY, raw
        assert v.degraded is False, raw


def test_check_resumption_day_is_trading_day(fake_calendar, freeze_today, monkeypatch):
    """FR-3 证伪点 ②：2026-10-08（复市首日）→ 交易日。改前实测 False（整天被跳过）。"""
    freeze_today(date(2026, 10, 8))
    monkeypatch.setattr(
        TradingDayGuard, '_kline_stats',
        staticmethod(lambda day: pytest.fail('当天日K 17:40 才落库，不应作为判据')),
    )
    v = TradingDayGuard.check('2026-10-08', use_cache=False)
    assert v.is_trading_day is True
    assert v.source == SOURCE_CALENDAR and v.degraded is False


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


def test_check_source_calendar(fake_calendar, freeze_today):
    """判定来源收敛：日历说交易日 → `trading-calendar`（K 线不再是来源）。"""
    freeze_today(date(2026, 9, 30))
    v = TradingDayGuard.check('2026-09-30', use_cache=False)
    assert v.is_trading_day is True
    assert v.source == SOURCE_CALENDAR and v.degraded is False


def test_check_past_trading_day_with_kline_is_not_degraded(fake_calendar, freeze_today, monkeypatch):
    """事后交叉校验通过：日历说交易日 + 该过去日确有日K → 不降级。"""
    freeze_today(date(2026, 10, 9))
    monkeypatch.setattr(
        TradingDayGuard, '_kline_stats', staticmethod(lambda day: (True, date(2026, 10, 8))))
    v = TradingDayGuard.check(date(2026, 10, 8), use_cache=False)
    assert (v.is_trading_day, v.source, v.degraded) == (True, SOURCE_CALENDAR, False)


def test_check_past_trading_day_without_kline_is_degraded_but_still_trading(
        fake_calendar, freeze_today, monkeypatch):
    """K 线只作事后交叉校验：日历说交易日、过去日却无日K → 记 degraded，**判定不变**。"""
    freeze_today(date(2026, 10, 9))
    monkeypatch.setattr(
        TradingDayGuard, '_kline_stats', staticmethod(lambda day: (False, date(2026, 10, 8))))
    v = TradingDayGuard.check(date(2026, 10, 8), use_cache=False)
    assert v.is_trading_day is True and v.source == SOURCE_CALENDAR
    assert v.degraded is True and '冲突' in v.reason


def test_kline_crosscheck_failure_degrades_but_keeps_calendar_verdict(
        fake_calendar, freeze_today, monkeypatch):
    """交叉校验取数炸了也不许击穿判定（K 线已不是真源）：判定照用 + degraded + 留痕。"""
    freeze_today(date(2026, 10, 9))

    def _boom(day):
        raise RuntimeError('db down')

    monkeypatch.setattr(TradingDayGuard, '_kline_stats', staticmethod(_boom))
    v = TradingDayGuard.check(date(2026, 10, 8), use_cache=False)
    assert v.is_trading_day is True and v.source == SOURCE_CALENDAR and v.degraded is True
    assert '交叉校验不可用' in v.reason


def test_check_calendar_chain_degraded_keeps_verdict_and_marks(
        chain_unavailable, freeze_today, _fake_guard_logger):
    """T11：解析链降级（工作日回退）→ 结论照用 + `degraded=True` + 来源下标 + 留痕。

    （本条取代旧的 `test_check_marks_intraday_heuristic_degraded`：旧的「近 7 日有K线」
    启发式已随 FR-3 移除，降级来源改为日历链。）
    """
    freeze_today(date(2026, 10, 8))
    v = TradingDayGuard.check('2026-10-08', use_cache=False)
    assert v.is_trading_day is True                       # 工作日口径：结论照用
    assert v.source == SOURCE_CALENDAR and v.degraded is True
    assert [c for c in _fake_guard_logger.calls
            if c['event'] == 'trading_day_guard_calendar_chain_degraded'], '降级必须留痕'


def test_check_future_date_wins_over_chain(chain_unavailable, freeze_today):
    """未来日期在进链之前就被否决（降级不影响这条硬否决）。"""
    freeze_today(date(2026, 10, 8))
    v = TradingDayGuard.check('2026-10-12', use_cache=False)
    assert v.is_trading_day is False and v.source == SOURCE_FUTURE and v.degraded is False


def test_check_datasource_failure_is_conservative_and_visible(chain_raises, freeze_today):
    """解析链不可用 → 保守判非交易日 + degraded + `unavailable`（既有可见性契约保留）。"""
    freeze_today(date(2026, 10, 8))
    v = TradingDayGuard.check('2026-10-08', use_cache=False)
    assert v.is_trading_day is False          # 保守：宁可少写，不写合成数据
    assert v.source == SOURCE_UNAVAILABLE and v.degraded is True


# ── 3.1 取数层类型契约（2026-09-14 w-2129d492 回归锚点）────────
# 事故：B3 重构把裸 SQL（psycopg2 直回 date 对象）换成仓储后，
# get_latest_trade_date() 回 'YYYY-MM-DD' 字符串，而 judge_trading_day 要拿它做
# (today - latest_kline_date).days → TypeError。异常沿 resume_from_breakpoint →
# start_orchestrator 上抛，把 orchestrator 的 tick 线程打死一整天（255 次 tick error）。
# 现在 `_latest` 不再参与判定（K 线只做交叉校验），但取数层的归一化契约继续锁。


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


def test_past_trading_day_crosscheck_works_with_string_repo_date(
        _fake_kline_repo, fake_calendar, freeze_today):
    """端到端复现：日历说交易日 + 取数层回字符串 → 必须给出判定而不是抛 TypeError。"""
    from application.services.trading_day_guard import TradingDayGuard

    _fake_kline_repo(has_bar=True, latest='2026-09-30')
    freeze_today(date(2026, 10, 8))
    v = TradingDayGuard.check(date(2026, 9, 30), use_cache=False)   # 不得抛异常
    assert (v.is_trading_day, v.source, v.degraded) == (True, SOURCE_CALENDAR, False)


def test_check_tolerates_garbage_latest_even_if_coercion_is_lost(
        monkeypatch, fake_calendar, freeze_today):
    """契约级兜底：即使将来 `_kline_stats` 又回字符串、且归一化被后人删掉，
    击穿调用方的路径也不存在（09-14 的事故形态就是异常直接上抛踢死 orchestrator）。
    现在 `_latest` 不参与判定 → 判定照给，只把"日历说有K线却没有"标成降级。"""
    from application.services.trading_day_guard import TradingDayGuard

    freeze_today(date(2026, 10, 8))
    monkeypatch.setattr(
        TradingDayGuard, '_kline_stats',
        staticmethod(lambda day: (False, '2026-09-30')),   # 故意回字符串
    )
    v = TradingDayGuard.check(date(2026, 9, 30), use_cache=False)   # 不得抛
    assert v.is_trading_day is True and v.source == SOURCE_CALENDAR and v.degraded is True


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


# ── 3.2 降级必须吵（复查 M4）：布尔入口不许把"判不了"静默成"今天不是交易日" ──
def test_is_trading_day_logs_loud_when_degraded(chain_raises, freeze_today, _fake_guard_logger):
    """orchestrator 等调用方拿的是布尔值 → 降级必须自己发出声音。"""
    freeze_today(date(2026, 10, 8))
    assert TradingDayGuard.is_trading_day('2026-10-08') is False
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


def test_is_trading_day_degraded_log_is_deduped_per_day(
        chain_raises, freeze_today, _fake_guard_logger):
    """tick 每分钟一次：同一天同一来源只吵一次，不能刷屏。"""
    freeze_today(date(2026, 10, 8))
    for _ in range(3):
        # 必须选"过去的工作日"：周末/未来日期会在判定前提前 return，根本到不了降级分支
        TradingDayGuard.is_trading_day('2026-10-08')
    hits = [c for c in _fake_guard_logger.calls
            if c['event'] == 'trading_day_guard_degraded_verdict_consumed_as_bool']
    assert len(hits) == 1, '同一天同一来源应只留痕一次，实际 %d' % len(hits)


def test_is_trading_day_does_not_log_for_normal_verdicts(
        monkeypatch, fake_calendar, freeze_today, _fake_guard_logger):
    """正常判定（交易日/周末）不许产生降级留痕噪声。"""
    monkeypatch.setattr(
        TradingDayGuard, '_kline_stats', staticmethod(lambda day: (True, date(2026, 9, 30))))
    freeze_today(date(2026, 9, 30))
    assert TradingDayGuard.is_trading_day('2026-09-30') is True
    assert TradingDayGuard.is_trading_day('2026-08-08') is False   # 周末：非降级
    assert not [c for c in _fake_guard_logger.calls
                if c['event'] == 'trading_day_guard_degraded_verdict_consumed_as_bool']


def test_compute_error_is_distinguishable_from_datasource_unavailable(
        chain_raises, freeze_today, monkeypatch):
    """两种降级必须可区分：数据源不可用 vs 判定器异常（前者是行情，后者是 bug）。"""
    from application.services.trading_day_guard import TradingDayGuard

    freeze_today(date(2026, 10, 8))
    v_src = TradingDayGuard.check('2026-09-30', use_cache=False)
    assert v_src.source == SOURCE_UNAVAILABLE

    monkeypatch.setattr(
        TradingDayGuard, '_compute',
        classmethod(lambda cls, d: (_ for _ in ()).throw(TypeError('boom'))),
    )
    v_bug = TradingDayGuard.check('2026-09-30', use_cache=False)
    assert v_bug.source == SOURCE_COMPUTE_ERROR
    assert v_bug.source != v_src.source


# ── 4. 写入型守卫 ────────────────────────────────────────────
def test_should_write_daily_blocks_weekend():
    v = TradingDayGuard.should_write_daily('2026-08-08')
    assert v.is_trading_day is False and v.source == SOURCE_WEEKEND


def test_should_write_daily_allows_trading_day(monkeypatch, fake_calendar, freeze_today):
    freeze_today(date(2026, 9, 30))
    monkeypatch.setattr(
        TradingDayGuard, '_kline_stats', staticmethod(lambda day: (True, date(2026, 9, 30))))
    assert TradingDayGuard.should_write_daily('2026-09-30').is_trading_day is True


def test_should_write_daily_blocks_national_day_holiday(fake_calendar, freeze_today):
    """2026-10-06（国庆休市·周二）：写入型路径不得落按日数据（08-08 合成快照同类事故）。"""
    freeze_today(date(2026, 10, 8))
    v = TradingDayGuard.should_write_daily('2026-10-06')
    assert v.is_trading_day is False and v.source == SOURCE_CALENDAR_HOLIDAY


# ── 5. 兼容层 ────────────────────────────────────────────────
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


# ── 6. 降级主动外发告警（飞书）────────────────────────────────
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


def test_degraded_calendar_chain_alerts_with_correct_risk_direction(
        chain_unavailable, freeze_today, _fake_alert_sink):
    """日历链降级且结论是"交易日" → 告警文案必须是"可能把休市日当交易日"，
    **不能**照抄"保守视为非交易日、今天会被跳过"（那是反的，会误导处置）。"""
    freeze_today(date(2026, 10, 8))
    assert TradingDayGuard.is_trading_day('2026-10-08') is True
    assert len(_fake_alert_sink) == 1
    assert _fake_alert_sink[0]['urgency'] == 'normal'
    content = _fake_alert_sink[0]['content']
    assert '周一~周五' in content and '保守视为非交易日' not in content


def test_degraded_datasource_alerts_normal_then_escalates(
        chain_raises, freeze_today, monkeypatch, _fake_alert_sink):
    """数据源不可用：首发 normal；持续超过冷却期仍未恢复 → 升 high 再报一次。"""
    from application.services import trading_day_guard as mod

    freeze_today(date(2026, 10, 8))
    clock = {'t': 1_000_000.0}
    monkeypatch.setattr(mod, '_now_seconds', lambda: clock['t'])

    assert TradingDayGuard.is_trading_day('2026-10-08') is False
    assert len(_fake_alert_sink) == 1 and _fake_alert_sink[0]['urgency'] == 'normal'

    clock['t'] += 60          # 只过了一分钟：不重复打扰
    TradingDayGuard.is_trading_day('2026-10-08')
    assert len(_fake_alert_sink) == 1

    clock['t'] += 31 * 60     # 持续未恢复：升级一次
    TradingDayGuard.is_trading_day('2026-10-08')
    assert len(_fake_alert_sink) == 2 and _fake_alert_sink[1]['urgency'] == 'high'

    clock['t'] += 61 * 60     # 已达上限：不再刷屏
    TradingDayGuard.is_trading_day('2026-10-08')
    assert len(_fake_alert_sink) == 2


def test_alert_sink_failure_does_not_break_verdict(chain_raises, freeze_today):
    """告警通道炸了也不能影响判定结果（告警是旁路，不是依赖）。"""
    from application.services import trading_day_guard as mod

    def boom(title, content, urgency):
        raise RuntimeError('feishu down')

    mod.install_degraded_alert_notifier(boom)
    reset_degraded_loud_log()
    freeze_today(date(2026, 10, 8))
    try:
        assert TradingDayGuard.is_trading_day('2026-10-08') is False
    finally:
        mod.install_degraded_alert_notifier(None)
        reset_degraded_loud_log()


def test_no_alert_when_sink_not_installed(chain_raises, freeze_today, _fake_guard_logger):
    """未注入通道（离线/测试环境）时只留痕不外发——不得因缺通道而报错。"""
    from application.services import trading_day_guard as mod

    assert mod._degraded_alert_sink is None
    freeze_today(date(2026, 10, 8))
    assert TradingDayGuard.is_trading_day('2026-10-08') is False


def test_no_alert_for_normal_verdicts(monkeypatch, fake_calendar, freeze_today, _fake_alert_sink):
    """正常交易日/周末都不许外发告警。"""
    freeze_today(date(2026, 9, 30))
    monkeypatch.setattr(
        TradingDayGuard, '_kline_stats', staticmethod(lambda day: (True, date(2026, 9, 30))))
    assert TradingDayGuard.is_trading_day('2026-09-30') is True
    assert TradingDayGuard.is_trading_day('2026-08-08') is False
    assert _fake_alert_sink == []


# ── 7. TradingCalendarService：工作日兜底不再静默（FR-3）──────
class _FakeProviderManager:
    def __init__(self, result):
        self._result = result

    def get_trading_calendar(self, start_date, end_date):
        return self._result


@pytest.fixture
def _provider_unavailable(monkeypatch):
    """上游日历取数失败（返回 success=False）→ 只能走工作日兜底。"""
    from infrastructure.services.service_factory import ServiceFactory

    monkeypatch.setattr(
        ServiceFactory, 'get_data_provider_manager',
        staticmethod(lambda: _FakeProviderManager({'success': False, 'data': None})),
    )


def test_calendar_service_fallback_carries_source_and_degraded(_provider_unavailable):
    """兜底必须能标注：`get_trading_days_with_meta` 带 source/degraded（旧入口签名不变）。"""
    from application.services.trading_calendar_service import (
        SOURCE_WEEKDAY_FALLBACK,
        TradingCalendarService,
    )

    svc = TradingCalendarService()
    result = svc.get_trading_days_with_meta('2026-10-01', '2026-10-07')
    assert result.degraded is True and result.source == SOURCE_WEEKDAY_FALLBACK
    # 国庆 10-01~10-07 全是工作日 → 兜底口径会把它们当交易日（这正是原静默 bug 的形态）
    assert '2026-10-05' in result.days
    # 旧入口签名/返回类型不变（缓存命中，逐字一致）
    assert svc.get_trading_days('2026-10-01', '2026-10-07') == result.days
    assert svc.is_trading_day('2026-10-05') is True


def test_calendar_service_fallback_logs_warning_not_info(_provider_unavailable, monkeypatch):
    """兜底不得只留 info：必须有一条带 degraded/source 的 warning（离线日志也看得见）。"""
    from application.services import trading_calendar_service as mod

    fake = _FakeLogger()
    monkeypatch.setattr(mod, 'logger', fake)

    svc = mod.TradingCalendarService()
    svc.get_trading_days('2026-10-01', '2026-10-07')

    hits = [c for c in fake.calls if c['event'] == 'trading_calendar_weekday_fallback']
    assert hits, '工作日兜底必须留 warning 级事件'
    assert hits[0]['degraded'] is True and hits[0]['source'] == mod.SOURCE_WEEKDAY_FALLBACK


def test_calendar_service_provider_success_is_not_degraded(monkeypatch):
    """上游成功 → source=provider、degraded=False（不得把好日子也标成降级）。"""
    from infrastructure.services.service_factory import ServiceFactory
    from application.services.trading_calendar_service import SOURCE_PROVIDER, TradingCalendarService

    rows = [{'trade_date': '2026-10-08'}, {'trade_date': '2026-10-09'}]
    monkeypatch.setattr(
        ServiceFactory, 'get_data_provider_manager',
        staticmethod(lambda: _FakeProviderManager({'success': True, 'data': rows})),
    )
    result = TradingCalendarService().get_trading_days_with_meta('2026-10-01', '2026-10-09')
    assert result.days == ['2026-10-08', '2026-10-09']
    assert (result.source, result.degraded) == (SOURCE_PROVIDER, False)
