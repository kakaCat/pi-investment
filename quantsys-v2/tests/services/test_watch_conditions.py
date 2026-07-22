"""盯盘条件判定器单测（纯函数）"""
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from application.services.watch_engine.conditions import (
    EvalContext, evaluate, validate_condition,
)


def make_quote(price=100.0, prev_close=98.0, volume=5_000_000, change_pct=None):
    return SimpleNamespace(price=price, prev_close=prev_close,
                           volume=volume, change_pct=change_pct)


NOW = datetime(2026, 7, 21, 10, 30)


class TestValidate:
    @pytest.mark.parametrize('cond', [
        {'type': 'price_break', 'params': {'direction': 'above', 'price': 1.0}},
        {'type': 'pct_change', 'params': {'direction': 'above', 'pct': 3.0}},
        {'type': 'pnl_pct', 'params': {'direction': 'below', 'pct': -8.0}},
        {'type': 'velocity', 'params': {'pct': 2.0, 'window_min': 5}},
        {'type': 'volume_surge', 'params': {'multiple': 2.0}},
    ])
    def test_valid_types(self, cond):
        validate_condition(cond)  # 不抛异常

    def test_unknown_type_rejected(self):
        with pytest.raises(ValueError, match='未知条件类型'):
            validate_condition({'type': 'magic', 'params': {}})

    def test_price_break_requires_price(self):
        with pytest.raises(ValueError):
            validate_condition({'type': 'price_break', 'params': {'direction': 'above'}})


class TestPriceBreak:
    def test_above_triggered(self):
        r = evaluate({'type': 'price_break', 'params': {'direction': 'above', 'price': 100.0}},
                     make_quote(price=100.0), EvalContext())
        assert r.triggered is True
        assert r.distance_ratio == 0.0

    def test_above_not_triggered_with_distance(self):
        r = evaluate({'type': 'price_break', 'params': {'direction': 'above', 'price': 100.0}},
                     make_quote(price=95.0), EvalContext())
        assert r.triggered is False
        assert r.distance_ratio == pytest.approx(0.05)

    def test_below_triggered(self):
        r = evaluate({'type': 'price_break', 'params': {'direction': 'below', 'price': 90.0}},
                     make_quote(price=89.5), EvalContext())
        assert r.triggered is True


class TestPctChange:
    def test_uses_prev_close(self):
        # (100-98)/98*100 ≈ 2.04%
        r = evaluate({'type': 'pct_change', 'params': {'direction': 'above', 'pct': 2.0}},
                     make_quote(), EvalContext())
        assert r.triggered is True
        assert r.value == pytest.approx(2.0408, abs=0.001)

    def test_below_direction(self):
        r = evaluate({'type': 'pct_change', 'params': {'direction': 'below', 'pct': -3.0}},
                     make_quote(price=94.0, prev_close=98.0), EvalContext())
        assert r.triggered is True  # -4.08% <= -3%

    def test_fallback_to_quote_change_pct(self):
        q = make_quote(prev_close=None, change_pct=3.5)
        r = evaluate({'type': 'pct_change', 'params': {'direction': 'above', 'pct': 3.0}},
                     q, EvalContext())
        assert r.triggered is True
        assert r.value == 3.5

    def test_no_data_returns_unavailable(self):
        q = make_quote(prev_close=None, change_pct=None)
        r = evaluate({'type': 'pct_change', 'params': {'direction': 'above', 'pct': 3.0}},
                     q, EvalContext())
        assert r.triggered is False
        assert r.distance_ratio is None


class TestPnlPct:
    def test_profit_trigger(self):
        ctx = EvalContext(cost_price=90.0)
        r = evaluate({'type': 'pnl_pct', 'params': {'direction': 'above', 'pct': 10.0}},
                     make_quote(price=100.0), ctx)
        assert r.triggered is True  # +11.1% >= 10%

    def test_loss_trigger(self):
        ctx = EvalContext(cost_price=110.0)
        r = evaluate({'type': 'pnl_pct', 'params': {'direction': 'below', 'pct': -8.0}},
                     make_quote(price=100.0), ctx)
        assert r.triggered is True  # -9.09% <= -8%

    def test_no_cost_price_unavailable(self):
        r = evaluate({'type': 'pnl_pct', 'params': {'direction': 'above', 'pct': 10.0}},
                     make_quote(), EvalContext(cost_price=None))
        assert r.triggered is False
        assert r.distance_ratio is None


class TestVelocity:
    def test_trigger_within_window(self):
        history = (
            (NOW - timedelta(minutes=4), 100.0),
            (NOW, 103.0),
        )
        ctx = EvalContext(price_history=history)
        r = evaluate({'type': 'velocity', 'params': {'pct': 2.5, 'window_min': 5}},
                     make_quote(price=103.0), ctx, now=NOW)
        assert r.triggered is True
        assert r.value == pytest.approx(3.0)

    def test_ignores_points_outside_window(self):
        history = (
            (NOW - timedelta(minutes=20), 80.0),   # 窗口外
            (NOW - timedelta(minutes=2), 100.0),
            (NOW, 101.0),
        )
        ctx = EvalContext(price_history=history)
        r = evaluate({'type': 'velocity', 'params': {'pct': 2.5, 'window_min': 5}},
                     make_quote(price=101.0), ctx, now=NOW)
        assert r.triggered is False
        assert r.value == pytest.approx(1.0)

    def test_insufficient_history(self):
        ctx = EvalContext(price_history=())
        r = evaluate({'type': 'velocity', 'params': {'pct': 2.5, 'window_min': 5}},
                     make_quote(), ctx, now=NOW)
        assert r.triggered is False
        assert r.distance_ratio is None


class TestVolumeSurge:
    def test_trigger(self):
        ctx = EvalContext(avg_volume_20d=10_000_000, elapsed_fraction=0.25)
        # 基准 = 1000万 * 0.25 = 250万；实际 500万 → 2.0x
        r = evaluate({'type': 'volume_surge', 'params': {'multiple': 2.0}},
                     make_quote(volume=5_000_000), ctx)
        assert r.triggered is True
        assert r.value == pytest.approx(2.0)

    def test_no_avg_volume_unavailable(self):
        ctx = EvalContext(avg_volume_20d=None)
        r = evaluate({'type': 'volume_surge', 'params': {'multiple': 2.0}},
                     make_quote(), ctx)
        assert r.triggered is False
        assert r.distance_ratio is None
