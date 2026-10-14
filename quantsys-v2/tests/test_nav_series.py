"""净值序列交易日口径测试 — REQ-261006190953-fc43 卡 A

背景（实测取证 2026-10-06）：`quant.simulation_equity_snapshot` 里有 35 行落在非交易日
（5 账户 × 7 天：08-08/08-15/08-29/09-05/09-06/09-12/10-02），而读取端按「行相邻」配对成
日收益——这些行被当成交易日参与波动率/IR/回撤/归因窗口；缺口判断又用「工作日」近似，
把国庆 10-01~10-07 整段算成缺口、逼出无意义的补跑。

本测试锁住 `application/services/nav_series.py` 的口径，八条断言对应任务卡验收 ①~⑧：
① 日历不可得 → None（不是空集）；② 未校验不过滤；③ 收益条数 = 交易日数 - 1；
④ 跨节假日的涨跌归到复市首日一段；⑤ 国庆整段不算缺口；⑥ 缺真交易日要报缺口（活性）；
⑦ trading_days=None → verified False 且 missing_count 0；⑧ 兼容转发 import 仍可用且一致。
"""
from datetime import date
from types import SimpleNamespace

import pytest

from application.services import nav_series
from application.services.nav_series import (
    filter_trading_days,
    nav_coverage,
    nav_returns_from_snapshots,
)
# 交易日集合的读取住在 adapters 层（纯口径模块不做 IO，见模块 docstring）
from adapters.outbound.repositories.trading_calendar_repository import (
    reset_trading_day_cache,
    trading_day_set,
)

# 受控交易日集合（只含需要的交易日，周末与 10-01~10-07 国庆休市不在内）
SEP04 = date(2026, 9, 4)
SEP05 = date(2026, 9, 5)   # 周六
SEP06 = date(2026, 9, 6)   # 周日
SEP09 = date(2026, 9, 9)
SEP24 = date(2026, 9, 24)
SEP25 = date(2026, 9, 25)
SEP28 = date(2026, 9, 28)
SEP30 = date(2026, 9, 30)
OCT08 = date(2026, 10, 8)


def _snap(day, total, cash=0.0):
    """净值快照替身：只带口径判定用到的字段。"""
    return SimpleNamespace(snapshot_date=day, total_value=total, cash=cash)


@pytest.fixture(autouse=True)
def _clear_cache():
    reset_trading_day_cache()
    yield
    reset_trading_day_cache()


# ---------------------------------------------------------------- ① 不可得 ≠ 空集

def test_trading_day_set_returns_none_when_calendar_empty(monkeypatch):
    """日历表为空 → None（**不是** set()）：空集会把净值序列清空、指标静默退化。"""
    class _Repo:
        def list_trading_days(self, exchange):
            return set()

    monkeypatch.setattr(
        'adapters.outbound.repositories.trading_calendar_repository.TradingCalendarORMRepository',
        _Repo,
    )
    assert trading_day_set() is None


def test_trading_day_set_returns_none_on_error(monkeypatch):
    """日历查询抛错 → None + 不向外抛（净值读取不该被日历故障打挂）。"""
    class _Repo:
        def list_trading_days(self, exchange):
            raise RuntimeError('calendar down')

    monkeypatch.setattr(
        'adapters.outbound.repositories.trading_calendar_repository.TradingCalendarORMRepository',
        _Repo,
    )
    assert trading_day_set() is None


def test_trading_day_set_returns_days_when_available(monkeypatch):
    class _Repo:
        def list_trading_days(self, exchange):
            return {SEP30, OCT08}

    monkeypatch.setattr(
        'adapters.outbound.repositories.trading_calendar_repository.TradingCalendarORMRepository',
        _Repo,
    )
    assert trading_day_set() == {SEP30, OCT08}


# ---------------------------------------------------------------- ② 未校验不过滤

def test_filter_passes_through_when_unverified():
    rows = [_snap(SEP05, 1.0), _snap(SEP30, 2.0)]
    assert filter_trading_days(rows, None) == rows


def test_filter_drops_non_trading_rows_and_keeps_undated():
    rows = [_snap(SEP05, 1.0), _snap(SEP30, 2.0), SimpleNamespace(snapshot_date=None, total_value=3.0)]
    kept = filter_trading_days(rows, {SEP30})
    assert len(kept) == 2                     # 周末行被丢、日期不可判定的行保留
    assert kept[0] is rows[1] and kept[1] is rows[2]


# ---------------------------------------------------------------- ③ 收益条数 = 交易日数 - 1

def test_returns_count_equals_trading_days_minus_one():
    """实测样本：09-04(五) 102710.39 → 09-05(六) → 09-06(日) → 09-09(三) 103445.39。

    过滤后只剩 09-04 与 09-09 两个交易日 → 收益条数 == 2 - 1 == 1。
    """
    rows = [
        _snap(SEP04, 102710.39),
        _snap(SEP05, 102908.39),
        _snap(SEP06, 102908.39),
        _snap(SEP09, 103445.39),
    ]
    returns, points = nav_returns_from_snapshots(rows, {SEP04, SEP09})
    assert points == 2
    assert len(returns) == points - 1 == 1
    assert returns[0] == pytest.approx(103445.39 / 102710.39 - 1)


def test_returns_unchanged_when_unverified():
    """未校验 → 退回改造前行为（逐行配对），保证兼容。"""
    rows = [_snap(SEP04, 100.0), _snap(SEP05, 110.0), _snap(SEP09, 121.0)]
    returns, points = nav_returns_from_snapshots(rows)
    assert points == 3 and len(returns) == 2


# ---------------------------------------------------------------- ④ 跨节假日归段

def test_holiday_span_collapses_into_single_return():
    """09-30 → 10-08（跨整段国庆）只产出一条收益，而不是 7 个假日"日收益"。"""
    rows = [_snap(SEP30, 100000.0), _snap(OCT08, 101000.0)]
    returns, points = nav_returns_from_snapshots(rows, {SEP30, OCT08})
    assert points == 2
    assert len(returns) == 1
    assert returns[0] == pytest.approx(0.01)


# ---------------------------------------------------------------- ⑤⑥ 缺口口径

def test_coverage_national_day_span_has_no_gap():
    """⑤ 覆盖 09-30→10-08 且两端齐全 → 缺口 0（10-01~10-07 是法定节假日，不算缺口）。"""
    rows = [_snap(SEP30, 100000.0), _snap(OCT08, 101000.0)]
    cov = nav_coverage(rows, {SEP30, OCT08})
    assert cov['verified'] is True
    assert cov['missing_count'] == 0
    assert cov['missing_trading_days'] == []
    assert cov['points'] == 2
    assert cov['from'] == '2026-09-30' and cov['to'] == '2026-10-08'
    assert '节假日' in cov['basis'] and cov['trading_day_source'] == 'trading-calendar'


def test_coverage_missing_real_trading_day_is_reported():
    """⑥ 缺 2026-09-25（真交易日）→ 缺口 1（证明判据是活的，不是常驻 0 噪声）。"""
    rows = [_snap(SEP24, 100000.0), _snap(SEP28, 101000.0)]
    cov = nav_coverage(rows, {SEP24, SEP25, SEP28})
    assert cov['missing_count'] == 1
    assert cov['missing_trading_days'] == ['2026-09-25']


def test_coverage_ignores_weekend_rows_and_reports_to_as_last_row():
    """序列尾部是周六行时，to 仍取该行日期（缺口只在交易日上算）。"""
    rows = [_snap(SEP24, 100000.0), _snap(SEP25, 100500.0), _snap(SEP28, 101000.0)]
    cov = nav_coverage(rows, {SEP24, SEP25, SEP28})
    assert cov['missing_count'] == 0 and cov['points'] == 3
    assert cov['to'] == '2026-09-28'


# ---------------------------------------------------------------- ⑦ None 的语义

def test_coverage_unverified_is_not_all_missing():
    """⑦ trading_days=None → verified False、missing_count 0、basis 明写未校验。"""
    rows = [_snap(SEP30, 100000.0), _snap(OCT08, 101000.0)]
    cov = nav_coverage(rows, None)
    assert cov['verified'] is False
    assert cov['missing_count'] == 0
    assert cov['missing_trading_days'] == []
    assert '未做交易日校验' in cov['basis']
    assert cov['trading_day_source'] == 'unavailable'


def test_coverage_marks_zero_points_when_no_row_on_calendar():
    """有日历但序列一天都不落在交易日上 → points 0 且 basis 提示查数据（不是静默 0 缺口）。"""
    rows = [_snap(SEP05, 100000.0), _snap(SEP06, 100000.0)]
    cov = nav_coverage(rows, {SEP30, OCT08})
    assert cov['verified'] is True and cov['points'] == 0
    assert cov['from'] is None and cov['to'] is None
    assert '点数为 0' in cov['basis']


# ---------------------------------------------------------------- ⑧ 兼容转发

def test_risk_metrics_service_reexport_is_same_function():
    """⑧ 既有导入路径仍可用，且与 nav_series 是同一实现（不是第二份拷贝）。"""
    pytest.importorskip('empyrical', reason='empyrical 未安装')
    from application.services.risk_metrics_service import (
        nav_returns_from_snapshots as legacy,
    )

    assert legacy is nav_series.nav_returns_from_snapshots
    rows = [_snap(SEP04, 100.0), _snap(SEP05, 110.0), _snap(SEP09, 121.0)]
    assert legacy(rows, {SEP04, SEP09}) == nav_returns_from_snapshots(rows, {SEP04, SEP09})
