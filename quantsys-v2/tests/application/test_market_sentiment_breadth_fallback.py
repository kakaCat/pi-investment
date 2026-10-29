"""市场宽度低覆盖时的真实快照回退（2026-10-29 自动买入阻塞修复）。

盘后/盘前日 K 只有几十只样本时，不能把它当全市场宽度；应回退到多源
最近交易快照。快照也不可用时仍保留小样本，由既有 coverage 守卫显式降级。
"""
from qs_intel.application.services.market_sentiment_service import MarketSentimentService


def _db_breadth(total=35):
    up, down, flat = 8, total - 9, 1
    return {
        "data_date": "2026-10-29",
        "up_count": up,
        "down_count": down,
        "flat_count": flat,
        "ratio": round(up / down, 4),
        "up_percentage": round(up / total * 100, 2),
    }


def _rt_breadth():
    return {
        "data_date": "2026-10-29",
        "up_count": 781,
        "down_count": 4727,
        "flat_count": 68,
        "ratio": 0.1652,
        "up_percentage": 14.01,
        "strength": "very_weak",
        "realtime": True,
        "source": "sina",
    }


class _Repo:
    def __init__(self, breadth):
        self._breadth = breadth

    def get_market_breadth(self):
        return self._breadth


def test_after_hours_low_coverage_db_uses_realtime_snapshot(monkeypatch):
    svc = MarketSentimentService(kline_repo=_Repo(_db_breadth()))
    monkeypatch.setattr(svc, "_is_intraday", lambda: False)
    monkeypatch.setattr(svc, "_realtime_breadth", _rt_breadth)

    result = svc._get_advance_decline_ratio()

    assert result["realtime"] is True
    assert result["source"] == "sina"
    assert result["up_count"] == 781
    assert result["down_count"] == 4727


def test_after_hours_sufficient_db_does_not_fetch_realtime(monkeypatch):
    svc = MarketSentimentService(kline_repo=_Repo(_db_breadth(total=5200)))
    monkeypatch.setattr(svc, "_is_intraday", lambda: False)

    def forbidden():
        raise AssertionError("日 K 覆盖充足时不应拉取实时快照")

    monkeypatch.setattr(svc, "_realtime_breadth", forbidden)
    result = svc._get_advance_decline_ratio()

    assert result["up_count"] == 8
    assert "realtime" not in result


def test_failed_realtime_fallback_preserves_small_sample_for_coverage_guard(monkeypatch):
    svc = MarketSentimentService(kline_repo=_Repo(_db_breadth()))
    monkeypatch.setattr(svc, "_is_intraday", lambda: False)
    monkeypatch.setattr(svc, "_realtime_breadth", lambda: None)

    result = svc._get_advance_decline_ratio()

    assert result["up_count"] == 8
    assert result["down_count"] == 26
    assert "realtime" not in result


def test_intraday_failed_snapshot_is_not_fetched_twice(monkeypatch):
    svc = MarketSentimentService(kline_repo=_Repo(_db_breadth()))
    monkeypatch.setattr(svc, "_is_intraday", lambda: True)
    calls = []

    def unavailable():
        calls.append(1)
        return None

    monkeypatch.setattr(svc, "_realtime_breadth", unavailable)
    result = svc._get_advance_decline_ratio()

    assert result["down_count"] == 26
    assert len(calls) == 1
