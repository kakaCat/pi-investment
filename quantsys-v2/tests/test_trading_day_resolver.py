"""交易日解析器回归用例（REQ-261004102115-d3de · FR-1 / FR-4）。

全部注入假数据源：**零网络、零数据库**。

日期表按上证公告〔2026〕22 号构造：中秋 09-25~09-27 休市、国庆 10-01~10-07 休市、10-08 复市。
这组用例就是本次告警（把 10-02 当成应有交易日）的回归锁。
"""
from __future__ import annotations

from datetime import date, datetime, time as dtime

import pytest

from application.services import trading_day_resolver as tr

# 真实交易日（含 10-08 复市日；09-25/10-01/10-02 均为休市）
CALENDAR = (
    date(2026, 9, 24),
    date(2026, 9, 28),
    date(2026, 9, 29),
    date(2026, 9, 30),
    date(2026, 10, 8),
    date(2026, 10, 9),
)


def _fake_reader(days):
    """按 anchor 取 <=anchor 的最大交易日（表与 provider 形状一致）。"""

    def _read(*_args, **_kwargs):
        anchor = _args[0]
        candidates = [d for d in days if d <= anchor]
        return max(candidates) if candidates else None

    return _read


@pytest.fixture
def table_only(monkeypatch):
    """表可用：provider 一旦被调用即判失败（证明优先走表）。"""
    monkeypatch.setattr(tr, "_read_calendar_table", _fake_reader(CALENDAR))
    monkeypatch.setattr(
        tr, "_read_provider", lambda *a, **k: pytest.fail("表已覆盖 anchor，不应再调 provider")
    )


# ── 用例 1-7：日期表驱动（FR-4）────────────────────────────────────────


@pytest.mark.parametrize(
    "ref,expected",
    [
        (datetime(2026, 10, 4, 10, 18), date(2026, 9, 30)),   # 1 本次告警正例：周日·国庆中
        (datetime(2026, 10, 2, 16, 0), date(2026, 9, 30)),    # 2 休市工作日不得当交易日
        (datetime(2026, 10, 8, 15, 29), date(2026, 9, 30)),   # 3 复市日未收盘不认今天
        (datetime(2026, 10, 8, 15, 30), date(2026, 10, 8)),   # 4 收盘即认今天（边界含等号）
        (datetime(2026, 9, 25, 20, 0), date(2026, 9, 24)),    # 5 中秋休市
        (datetime(2026, 9, 26, 10, 0), date(2026, 9, 24)),    # 6 周末语义不回归
        (datetime(2026, 9, 29, 10, 0), date(2026, 9, 28)),    # 7 盘中看上一交易日
    ],
)
def test_last_closed_trading_day_from_calendar(table_only, ref, expected):
    result = tr.last_closed_trading_day(ref)
    assert result.date == expected
    assert result.source == tr.SOURCE_CALENDAR_TABLE
    assert result.degraded is False


def test_cutoff_is_configurable(table_only):
    """收盘基准可改：14:00 基准下 15:29 也认当天。"""
    result = tr.last_closed_trading_day(datetime(2026, 10, 8, 15, 29), cutoff=dtime(14, 0))
    assert result.date == date(2026, 10, 8)


# ── 用例 8-10：降级路径（FR-1 / FR-3）────────────────────────────────


def test_provider_used_when_table_cannot_answer(monkeypatch):
    """表为空/不覆盖 → 走 provider，且**不算降级**。"""
    monkeypatch.setattr(tr, "_read_calendar_table", lambda anchor: None)
    monkeypatch.setattr(tr, "_read_provider", _fake_reader(CALENDAR))

    result = tr.last_closed_trading_day(datetime(2026, 10, 4, 10, 18))
    assert (result.date, result.source, result.degraded) == (
        date(2026, 9, 30),
        tr.SOURCE_PROVIDER,
        False,
    )


def test_provider_exception_falls_back_to_weekday(monkeypatch, caplog):
    """provider 抛异常 → 周一至周五回退，**不抛异常**，且来源明确标注。"""
    monkeypatch.setattr(tr, "_read_calendar_table", lambda anchor: None)

    def _boom(*_a, **_k):
        raise RuntimeError("provider down")

    monkeypatch.setattr(tr, "_read_provider", _boom)

    result = tr.last_closed_trading_day(datetime(2026, 10, 4, 10, 18))
    assert (result.date, result.source, result.degraded) == (
        date(2026, 10, 2),  # 周一至周五口径的旧答案——正是被修掉的那个误报
        tr.SOURCE_WEEKDAY_FALLBACK,
        True,
    )


def test_provider_empty_falls_back_and_logs(monkeypatch):
    """provider 返回空 → 降级，且必须留痕（禁止静默降级）。

    断言方式：**替换 logger 做记录**，而不是抓 stdout/caplog ——
    本仓 structlog 走 stdout 打印（不进 stdlib logging 的 record 链），而 stdout 抓取
    受同批次其他测试对日志/流的配置影响（单跑能过、全量跑就空），属不稳定断言。
    """
    events: list = []

    class _SpyLogger:
        def warning(self, event, **_kw):
            events.append(event)

        def info(self, *_a, **_k):
            pass

    monkeypatch.setattr(tr, "logger", _SpyLogger())
    monkeypatch.setattr(tr, "_read_calendar_table", lambda anchor: None)
    monkeypatch.setattr(tr, "_read_provider", lambda *a, **k: None)

    result = tr.last_closed_trading_day(datetime(2026, 10, 4, 10, 18))

    assert result.source == tr.SOURCE_WEEKDAY_FALLBACK
    assert result.degraded is True
    assert "trading_day_weekday_fallback" in events


def test_table_error_falls_through_to_provider(monkeypatch):
    """表不可读（DB 挂了）也不该把探针带崩：继续走 provider。"""
    def _boom(anchor):
        raise RuntimeError("db down")

    monkeypatch.setattr(tr, "_read_calendar_table", _boom)
    monkeypatch.setattr(tr, "_read_provider", _fake_reader(CALENDAR))

    result = tr.last_closed_trading_day(datetime(2026, 10, 4, 10, 18))
    assert (result.date, result.source) == (date(2026, 9, 30), tr.SOURCE_PROVIDER)


# ── 入参守卫 ──────────────────────────────────────────────────────────


def test_bare_date_is_rejected():
    """裸 date 语义有歧义（某天 vs 某天 15:30）→ 明确拒绝，而不是猜。"""
    with pytest.raises(TypeError):
        tr.last_closed_trading_day(date(2026, 10, 4))  # type: ignore[arg-type]
