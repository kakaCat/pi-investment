"""信号 5/10/20 日回填：批量取数、缺数诊断与受控重算回归。"""
from datetime import datetime, timedelta

import pytest

from infrastructure.services.service_factory import ServiceFactory
from qs_market_data.application.services import trading_calendar_service as calendar_module
from qs_sourcing.adapters.outbound.repositories import signal_tracking_repository as repo_module
from qs_sourcing.application.services.signal_tracking_service import SignalTrackingService


DAYS = [
    (datetime(2026, 1, 2) + timedelta(days=offset)).strftime("%Y-%m-%d")
    for offset in range(36)
    if (datetime(2026, 1, 2) + timedelta(days=offset)).weekday() < 5
]


def test_real_repository_backfill_contract_is_not_overridden():
    """主区并行合入同名旧方法时，mock 测试全绿但线上仍会用旧签名。"""
    import inspect

    params = inspect.signature(
        repo_module.SignalTrackingRepository.get_signals_pending_backfill
    ).parameters
    assert {'symbol', 'include_filled', 'start_date'} <= set(params)


def _signal(**overrides):
    value = {
        "id": 1,
        "signal_date": DAYS[0],
        "symbol": "002027",
        "grade": "A",
        "source": "watch_rule",
        "price": 5.26,
        "price_5d": None,
        "price_10d": None,
        "price_20d": None,
        "return_5d": None,
        "return_10d": None,
        "return_20d": None,
        "hit_5d": None,
        "hit_10d": None,
        "hit_20d": None,
    }
    value.update(overrides)
    return value


class FakeRepo:
    def __init__(self, signals):
        self.signals = signals
        self.updates = []
        self.pending_calls = []

    def get_signals_by_date(self, _date):
        return self.signals

    def get_signals_pending_backfill(self, **kwargs):
        self.pending_calls.append(kwargs)
        return self.signals

    def update_signal_performance(self, signal_id, updates):
        self.updates.append((signal_id, dict(updates)))
        target = next(s for s in self.signals if s["id"] == signal_id)
        target.update(updates)


class FakeKlines:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def get_daily_klines_batch(self, symbols, start_date, end_date, raise_on_error=False):
        self.calls.append((symbols, start_date, end_date, raise_on_error))
        return {"002027": self.rows}


def _wire(monkeypatch, repo, klines, days=DAYS):
    calendar_calls = []

    class FakeCalendar:
        def get_trading_days(self, start_date, end_date):
            calendar_calls.append((start_date, end_date))
            return [datetime.strptime(d, "%Y-%m-%d").date() for d in days]

    monkeypatch.setattr(repo_module, "SignalTrackingRepository", lambda _db: repo)
    monkeypatch.setattr(ServiceFactory, "get_kline_repository", staticmethod(lambda: klines))
    monkeypatch.setattr(calendar_module, "TradingCalendarService", FakeCalendar)
    return calendar_calls


def test_matured_updates_and_missing_kline_are_reported_then_idempotent(monkeypatch):
    repo = FakeRepo([_signal()])
    klines = FakeKlines([{"trade_date": DAYS[5], "close": 5.49}])
    calendar_calls = _wire(monkeypatch, repo, klines)
    service = SignalTrackingService()

    first = service.update_performance()

    assert first["updated"] == 1
    assert first["details"] == {"5d": 1, "10d": 0, "20d": 0}
    assert first["complete"] is False
    assert first["diagnostics"]["missing_kline"] == 2
    assert {b["target_date"] for b in first["diagnostics"]["blocked"]} == {DAYS[10], DAYS[20]}
    assert len(calendar_calls) == 1
    assert len(klines.calls) == 1
    assert klines.calls[0][3] is True
    assert repo.signals[0]["return_5d"] == pytest.approx(5.49 / 5.26 - 1)

    second = service.update_performance()
    assert second["updated"] == 0
    assert second["diagnostics"]["missing_kline"] == 2
    assert len(repo.updates) == 1, "已填 5d 不得重复写，缺数也不得制造更新"


def test_not_matured_does_not_query_klines(monkeypatch):
    repo = FakeRepo([_signal(signal_date=DAYS[-1])])
    klines = FakeKlines([])
    _wire(monkeypatch, repo, klines)

    result = SignalTrackingService().update_performance()

    assert result["updated"] == 0
    assert result["complete"] is True
    assert result["diagnostics"]["not_due"] == 3
    assert klines.calls == []


def test_refresh_recomputes_non_null_corrupted_values_with_scope(monkeypatch):
    repo = FakeRepo([_signal(price_5d=5.01, price_10d=5.10, price_20d=5.29)])
    klines = FakeKlines([
        {"trade_date": DAYS[5], "close": 5.49},
        {"trade_date": DAYS[10], "close": 5.49},
        {"trade_date": DAYS[20], "close": 5.49},
    ])
    _wire(monkeypatch, repo, klines)
    service = SignalTrackingService()

    with pytest.raises(ValueError, match="必须同时限定"):
        service.update_performance(refresh=True)

    result = service.update_performance(symbol="002027", refresh=True)

    assert result["updated"] == 1
    assert result["details"] == {"5d": 1, "10d": 1, "20d": 1}
    assert repo.signals[0]["price_20d"] == 5.49
    assert repo.signals[0]["return_20d"] == pytest.approx(5.49 / 5.26 - 1)
    assert repo.pending_calls[-1]["include_filled"] is True


def test_explicit_lookback_is_a_real_filter_and_default_keeps_old_backlog(monkeypatch):
    repo = FakeRepo([_signal()])
    klines = FakeKlines([])
    _wire(monkeypatch, repo, klines)
    service = SignalTrackingService()

    service.update_performance(lookback_days=30)
    assert repo.pending_calls[-1]["start_date"] is not None

    service.update_performance()
    assert repo.pending_calls[-1]["start_date"] is None


def test_single_owner_signal_backfill_not_in_internal_job_registry():
    from qs_ops.application.jobs.signal_jobs import SIGNAL_JOBS

    assert "signal_perf_backfill_daily" not in {job.name for job in SIGNAL_JOBS}
