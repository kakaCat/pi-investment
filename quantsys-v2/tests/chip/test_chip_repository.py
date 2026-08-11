"""ChipRepository 集成测试 — quant_test 库，用合成 symbol TST001 自造数据、测后清理"""
from datetime import date

import numpy as np
import pytest
from sqlalchemy import text

from adapters.outbound.repositories.chip_repository import ChipRepository
from domain.chip_distribution.calculator import ChipDistribution

SYM = "TST001"
TEST_DATE = date(2026, 8, 3)


@pytest.fixture
def repo():
    r = ChipRepository()
    yield r
    # 清理：chip 两表 + 测试插入的 K 线（只删本测试插入的日期）
    r.session.execute(text(
        "DELETE FROM quant.chip_distribution_state WHERE symbol = :s"), {"s": SYM})
    r.session.execute(text(
        "DELETE FROM quant.chip_metrics WHERE symbol = :s"), {"s": SYM})
    r.session.execute(text(
        "DELETE FROM quant.daily_klines WHERE symbol = :s AND trade_date >= :d"),
        {"s": SYM, "d": TEST_DATE})
    r.session.commit()


@pytest.fixture
def seeded_klines(repo):
    """给 TST001 插入 3 根带换手率的 K 线"""
    rows = [
        (date(2026, 8, 3), 19.0, 21.0, 20.0, 5.0),
        (date(2026, 8, 4), 20.0, 22.0, 21.0, 6.0),
        (date(2026, 8, 5), 21.0, 23.0, 22.0, 7.0),
    ]
    for d, low, high, close, tr in rows:
        repo.session.execute(text("""
            INSERT INTO quant.daily_klines
                (symbol, trade_date, open, high, low, close, volume, amount, turnover_rate)
            VALUES (:s, :d, :o, :h, :l, :c, 1000000, 20000000, :tr)
            ON CONFLICT (symbol, trade_date) DO UPDATE SET
                low = EXCLUDED.low, high = EXCLUDED.high,
                close = EXCLUDED.close, turnover_rate = EXCLUDED.turnover_rate
        """), {"s": SYM, "d": d, "o": close, "h": high, "l": low, "c": close, "tr": tr})
    repo.session.commit()
    return rows


class TestKlineRead:
    def test_get_klines_ascending_with_fields(self, repo, seeded_klines):
        rows = repo.get_klines(SYM, after_date="2026-08-01")
        assert len(rows) == 3
        assert set(rows[0]) >= {"trade_date", "low", "high", "close", "volume", "turnover_rate"}
        dates = [r["trade_date"] for r in rows]
        assert dates == sorted(dates)

    def test_get_klines_after_date_exclusive(self, repo, seeded_klines):
        rows = repo.get_klines(SYM, after_date="2026-08-03")
        assert [str(r["trade_date"]) for r in rows] == ["2026-08-04", "2026-08-05"]

    def test_get_latest_close(self, repo, seeded_klines):
        assert repo.get_latest_close(SYM) == 22.0


class TestStateRoundtrip:
    def test_state_upsert_and_get(self, repo):
        d = ChipDistribution.empty(10.0, 30.0)
        d.apply_day(19.0, 21.0, 20.0, 30.0)
        repo.upsert_state(SYM, d, TEST_DATE)
        got = repo.get_state(SYM)
        assert got is not None
        assert got["last_trade_date"] == TEST_DATE
        d2 = ChipDistribution.from_bytes(got["price_min"], got["bin_width"], got["counts"])
        np.testing.assert_array_equal(d.counts, d2.counts)


class TestMetricsUpsert:
    def test_upsert_metrics_idempotent(self, repo):
        m = {
            "profit_ratio": 0.5, "avg_cost": 20.0,
            "cost_90_low": 18.0, "cost_90_high": 22.0,
            "cost_70_low": 19.0, "cost_70_high": 21.0,
            "peak_price": 20.0, "concentration": 0.1,
        }
        repo.upsert_metrics(SYM, TEST_DATE, m)
        repo.upsert_metrics(SYM, TEST_DATE, {**m, "profit_ratio": 0.6})
        row = repo.get_metrics(SYM, str(TEST_DATE))
        assert row["profit_ratio"] == 0.6


class TestHelpers:
    def test_get_circulating_mv(self, repo):
        mv = repo.get_circulating_mv(SYM)
        assert mv is None or mv > 0

    def test_pending_klines_detects_stale_state(self, repo, seeded_klines):
        # state 停在 08-03，K 线到 08-05 → TST001 应在 pending 列表
        d = ChipDistribution.empty(18.0, 24.0)
        repo.upsert_state(SYM, d, date(2026, 8, 3))
        pending = repo.get_symbols_with_pending_klines()
        symbols = [p["symbol"] for p in pending]
        assert SYM in symbols
