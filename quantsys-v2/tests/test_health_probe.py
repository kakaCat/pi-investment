"""探针新鲜度判定与来源标注的回归用例（REQ-261004102115-d3de · FR-2 / FR-4）。

**不调 `main()`、不调 `send_alert`**，因此不触碰通知链路（notify-guard 汇总应为 egress=0）；
DB 与解析器都用假对象注入，零网络零数据库。
"""
from __future__ import annotations

from datetime import date, datetime

import pytest

from application.services.trading_day_resolver import (
    SOURCE_CALENDAR_TABLE,
    SOURCE_WEEKDAY_FALLBACK,
    TradingDayResult,
)
from tools import health_probe


class _Result:
    def __init__(self, value):
        self._value = value

    def scalar(self):
        return self._value


class _Conn:
    def __init__(self, scalars):
        self._scalars = list(scalars)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, *_args, **_kwargs):
        return _Result(self._scalars.pop(0))


class _Engine:
    def __init__(self, scalars):
        self._scalars = list(scalars)

    def connect(self):
        return _Conn(self._scalars)


@pytest.fixture
def fake_db(monkeypatch):
    """把 max(trade_date) / max(factor_date) 两次查询喂成固定值。"""

    def _install(kline_latest, factor_latest=None):
        from infrastructure.persistence.database import engine as engine_module

        scalars = [kline_latest, factor_latest if factor_latest is not None else kline_latest]
        monkeypatch.setattr(engine_module, "get_engine", lambda: _Engine(scalars))

    return _install


@pytest.fixture
def fixed_resolver(monkeypatch):
    def _install(expected: date, source: str = SOURCE_CALENDAR_TABLE, degraded: bool = False):
        monkeypatch.setattr(
            health_probe,
            "expected_trading_day",
            lambda ref=None: TradingDayResult(date=expected, source=source, degraded=degraded),
        )

    return _install


def test_fresh_when_kline_reaches_expected(fake_db, fixed_resolver):
    """国庆正例：数据停在 09-30 而应有日也是 09-30 → 不得报警。"""
    fixed_resolver(date(2026, 9, 30))
    fake_db(date(2026, 9, 30))

    check = health_probe.probe_freshness(max_lag_days=1)

    assert check["ok"] is True
    assert check["expected"] == "2026-09-30"
    assert check["expected_source"] == "calendar"
    assert check["expected_degraded"] is False
    assert check["lag_days"] == 0


def test_stale_when_kline_lags_expected(fake_db, fixed_resolver):
    """判据没被改空：真滞后时仍必须报警。"""
    fixed_resolver(date(2026, 9, 30))
    fake_db(date(2026, 9, 20))

    check = health_probe.probe_freshness(max_lag_days=1)

    assert check["ok"] is False
    assert check["lag_days"] == 10


def test_calendar_expected_uses_real_trading_day(fake_db, fixed_resolver):
    """复市日收盘后：应有日必须是当天的真实交易日，而不是周末回退。"""
    fixed_resolver(date(2026, 10, 8))
    fake_db(date(2026, 9, 30))

    check = health_probe.probe_freshness(max_lag_days=1)

    assert check["expected"] == "2026-10-08"
    assert check["ok"] is False  # 复市日数据还没到 → 该报


def test_alert_marks_degraded_judgement(fake_db, fixed_resolver):
    """降级口径必须在告警正文里看得见（禁止静默降级）。"""
    fixed_resolver(date(2026, 10, 2), source=SOURCE_WEEKDAY_FALLBACK, degraded=True)
    fake_db(date(2026, 9, 30))

    check = health_probe.probe_freshness(max_lag_days=1)
    payload = health_probe.build_alert([check], api_port=5001)

    assert check["expected_source"] == "weekday_fallback"
    assert "交易日历不可用" in payload["text"]


def test_alert_has_no_degraded_marker_when_calendar_ok(fake_db, fixed_resolver):
    fixed_resolver(date(2026, 9, 30))
    fake_db(date(2026, 9, 20))

    payload = health_probe.build_alert([health_probe.probe_freshness(max_lag_days=1)], api_port=5001)

    assert "交易日历不可用" not in payload["text"]
    assert "滞后 10 天" in payload["text"]
