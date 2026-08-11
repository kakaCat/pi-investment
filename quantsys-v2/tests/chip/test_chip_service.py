"""ChipDistributionService 单测 — fake repository，不连数据库"""
import pytest

from domain.chip_distribution.calculator import ChipDistribution
from domain.chip_distribution.service import ChipDistributionService


class FakeRepo:
    def __init__(self, klines=None, state=None, circulating_mv=None, median_turnover=2.0):
        self._klines = klines or {}
        self._state = state or {}
        self._mv = circulating_mv
        self._median = median_turnover
        self.saved_states = {}
        self.saved_metrics = []

    def get_klines(self, symbol, after_date=None):
        rows = self._klines.get(symbol, [])
        if after_date:
            rows = [r for r in rows if str(r["trade_date"]) > str(after_date)]
        return rows

    def get_latest_close(self, symbol):
        rows = self._klines.get(symbol, [])
        return rows[-1]["close"] if rows else None

    def get_state(self, symbol):
        return self._state.get(symbol)

    def get_circulating_mv(self, symbol):
        return self._mv

    def get_median_turnover(self, trade_date):
        return self._median

    def upsert_state(self, symbol, dist, last_trade_date):
        self.saved_states[symbol] = (dist, last_trade_date)
        self._state[symbol] = {
            "price_min": dist.price_min, "bin_width": dist.bin_width,
            "counts": dist.to_bytes(), "last_trade_date": last_trade_date,
        }

    def upsert_metrics(self, symbol, trade_date, metrics):
        self.saved_metrics.append((symbol, trade_date, metrics))

    def get_symbols_with_pending_klines(self):
        return []


def kline(date, low, high, close, turnover=None, volume=1e6):
    return {"trade_date": date, "low": low, "high": high, "close": close,
            "volume": volume, "turnover_rate": turnover}


KLINES = [
    kline("2026-08-03", 19.0, 21.0, 20.0, turnover=5.0),
    kline("2026-08-04", 20.0, 22.0, 21.0, turnover=5.0),
    kline("2026-08-05", 21.0, 23.0, 22.0, turnover=5.0),
]


class TestUpdateSymbol:
    def test_bootstrap_from_full_history(self):
        repo = FakeRepo(klines={"600519.SH": KLINES})
        svc = ChipDistributionService(repo)
        result = svc.update_symbol("600519.SH")
        assert result["days_applied"] == 3
        assert "600519.SH" in repo.saved_states
        # 最后一天收盘价算指标
        assert repo.saved_metrics[-1][1] == "2026-08-05"
        assert 0 <= repo.saved_metrics[-1][2]["profit_ratio"] <= 1

    def test_incremental_from_state(self):
        d = ChipDistribution.empty(19.0, 23.0)
        d.apply_day(19.0, 21.0, 20.0, 5.0)
        repo = FakeRepo(
            klines={"600519.SH": KLINES},
            state={"600519.SH": {
                "price_min": d.price_min, "bin_width": d.bin_width,
                "counts": d.to_bytes(), "last_trade_date": "2026-08-03",
            }},
        )
        svc = ChipDistributionService(repo)
        result = svc.update_symbol("600519.SH")
        assert result["days_applied"] == 2  # 只补 08-04/08-05

    def test_no_new_klines_noop(self):
        d = ChipDistribution.empty(19.0, 23.0)
        repo = FakeRepo(
            klines={"600519.SH": KLINES},
            state={"600519.SH": {
                "price_min": d.price_min, "bin_width": d.bin_width,
                "counts": d.to_bytes(), "last_trade_date": "2026-08-05",
            }},
        )
        svc = ChipDistributionService(repo)
        result = svc.update_symbol("600519.SH")
        assert result["days_applied"] == 0
        assert repo.saved_metrics == []

    def test_unknown_symbol_returns_error(self):
        repo = FakeRepo()
        svc = ChipDistributionService(repo)
        result = svc.update_symbol("000000.XX")
        assert result["days_applied"] == 0
        assert "error" in result


class TestTurnoverFallback:
    def test_missing_turnover_uses_circulating_mv(self):
        # 流通市值 20亿，收盘 20 元 → 流通股 1亿股；volume 500万股 → 换手 5%
        rows = [kline("2026-08-05", 19.0, 21.0, 20.0, turnover=None, volume=5e6)]
        repo = FakeRepo(klines={"600519.SH": rows}, circulating_mv=2e9)
        svc = ChipDistributionService(repo)
        svc.update_symbol("600519.SH")
        dist, _ = repo.saved_states["600519.SH"]
        assert dist.counts.sum() == pytest.approx(0.05, abs=1e-9)

    def test_missing_turnover_and_mv_uses_market_median(self):
        rows = [kline("2026-08-05", 19.0, 21.0, 20.0, turnover=None)]
        repo = FakeRepo(klines={"600519.SH": rows}, circulating_mv=None, median_turnover=3.0)
        svc = ChipDistributionService(repo)
        svc.update_symbol("600519.SH")
        dist, _ = repo.saved_states["600519.SH"]
        assert dist.counts.sum() == pytest.approx(0.03, abs=1e-9)


class TestGetDistribution:
    def test_curve_and_metrics(self):
        repo = FakeRepo(klines={"600519.SH": KLINES})
        svc = ChipDistributionService(repo)
        svc.update_symbol("600519.SH")
        out = svc.get_distribution("600519.SH")
        assert out["symbol"] == "600519.SH"
        assert out["as_of"] == "2026-08-05"
        assert len(out["curve"]) > 0
        assert abs(sum(p["weight"] for p in out["curve"]) - 1.0) < 1e-6
        assert set(out["metrics"]) >= {"profit_ratio", "avg_cost", "peak_price"}

    def test_symbol_normalization(self):
        repo = FakeRepo(klines={"600519.SH": KLINES})
        svc = ChipDistributionService(repo)
        svc.update_symbol("600519")  # 无后缀 → 自动补 .SH
        assert "600519.SH" in repo.saved_states
