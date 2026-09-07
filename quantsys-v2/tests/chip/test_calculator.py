"""筹码分布计算器单测 — 合成 K 线，不依赖数据库"""
import numpy as np
import pytest

from domain.chip_distribution.calculator import ChipDistribution, N_BINS


def make_dist(price_min=10.0, price_max=30.0):
    return ChipDistribution.empty(price_min, price_max)


class TestApplyDay:
    def test_first_day_adds_turnover_mass(self):
        d = make_dist()
        d.apply_day(low=19.0, high=21.0, close=20.0, turnover_rate=5.0)  # 5%
        assert d.counts.sum() == pytest.approx(0.05, abs=1e-9)

    def test_decay_reduces_existing_chips(self):
        d = make_dist()
        d.apply_day(19.0, 21.0, 20.0, 50.0)   # sum = 0.5
        d.apply_day(19.0, 21.0, 20.0, 50.0)   # 0.5*0.5 + 0.5 = 0.75
        assert d.counts.sum() == pytest.approx(0.75, abs=1e-9)

    def test_invariant_holds_at_steady_state(self):
        """sum≈1 后每日保持 1（归一化不变式）"""
        d = make_dist()
        for _ in range(30):
            d.apply_day(19.0, 21.0, 20.0, 100.0)
        assert d.counts.sum() == pytest.approx(1.0, abs=1e-9)
        d.apply_day(18.0, 22.0, 20.0, 20.0)
        assert d.counts.sum() == pytest.approx(1.0, abs=1e-9)

    def test_full_turnover_erases_old_chips(self):
        """持续 100% 换手后，旧价位筹码趋近 0"""
        d = make_dist()
        d.apply_day(9.0, 11.0, 10.0, 100.0)       # 筹码全在 10 元附近
        for _ in range(10):
            d.apply_day(19.0, 21.0, 20.0, 100.0)  # 换到 20 元附近
        low_mass = d.mass_between(9.0, 11.0)
        assert low_mass < 0.01

    def test_turnover_capped_at_100(self):
        d = make_dist()
        d.apply_day(19.0, 21.0, 20.0, 150.0)  # 异常数据封顶
        assert d.counts.sum() == pytest.approx(1.0, abs=1e-9)

    def test_limit_up_single_price(self):
        """一字板 low==high：全部质量进单桶，不报错"""
        d = make_dist()
        d.apply_day(20.0, 20.0, 20.0, 10.0)
        assert d.counts.sum() == pytest.approx(0.1, abs=1e-9)

    def test_triangular_peak_at_typical_price(self):
        """三角分布峰值在典型价 (H+L+2C)/4"""
        d = make_dist()
        d.apply_day(10.0, 30.0, 12.0, 100.0)  # 典型价 = (30+10+24)/4 = 16
        peak_price = d.price_at_peak()
        assert abs(peak_price - 16.0) < 2.0


class TestMetrics:
    def test_profit_ratio(self):
        d = make_dist()
        d.apply_day(19.0, 21.0, 20.0, 100.0)  # 筹码全在 20 附近
        m = d.metrics(close=25.0)
        assert m["profit_ratio"] > 0.9
        m2 = d.metrics(close=15.0)
        assert m2["profit_ratio"] < 0.1

    def test_avg_cost(self):
        d = make_dist()
        d.apply_day(19.0, 21.0, 20.0, 100.0)
        m = d.metrics(close=20.0)
        assert abs(m["avg_cost"] - 20.0) < 1.0

    def test_cost_intervals_ordered(self):
        d = make_dist()
        for _ in range(20):
            d.apply_day(10.0, 30.0, 20.0, 20.0)
        m = d.metrics(close=20.0)
        assert m["cost_90_low"] <= m["cost_70_low"] <= m["cost_70_high"] <= m["cost_90_high"]
        assert 0 <= m["profit_ratio"] <= 1
        assert m["concentration"] >= 0

    def test_empty_distribution_metrics_safe(self):
        d = make_dist()
        m = d.metrics(close=20.0)
        assert m["profit_ratio"] is None  # 无筹码时指标为 None

    def test_metrics_keys_complete(self):
        d = make_dist()
        d.apply_day(19.0, 21.0, 20.0, 100.0)
        m = d.metrics(close=20.0)
        assert set(m) == {
            "profit_ratio", "avg_cost", "cost_90_low", "cost_90_high",
            "cost_70_low", "cost_70_high", "peak_price", "concentration",
        }


class TestSerialization:
    def test_roundtrip(self):
        d = make_dist()
        d.apply_day(19.0, 21.0, 20.0, 30.0)
        blob = d.to_bytes()
        d2 = ChipDistribution.from_bytes(d.price_min, d.bin_width, blob)
        np.testing.assert_array_equal(d.counts, d2.counts)

    def test_from_klines_builds_distribution(self):
        klines = [
            {"low": 19.0, "high": 21.0, "close": 20.0, "turnover_rate": 5.0},
            {"low": 20.0, "high": 22.0, "close": 21.0, "turnover_rate": 5.0},
        ]
        d = ChipDistribution.from_klines(klines)
        assert d.counts.sum() == pytest.approx(0.05 * 0.95 + 0.05, abs=1e-9)

    def test_from_klines_expands_range(self):
        """价格突破初始区间时自动重分桶"""
        klines = [
            {"low": 19.0, "high": 21.0, "close": 20.0, "turnover_rate": 50.0},
            {"low": 39.0, "high": 41.0, "close": 40.0, "turnover_rate": 50.0},
        ]
        d = ChipDistribution.from_klines(klines)
        assert d.price_min <= 19.0
        assert d.price_at_peak() > 30.0  # 峰移到 40 附近（各 50% 质量，峰在后一半）
