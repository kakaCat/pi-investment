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

    def test_evaluate_unknown_type_raises_value_error(self):
        with pytest.raises(ValueError, match='未知条件类型'):
            evaluate({'type': 'magic', 'params': {}}, make_quote(), EvalContext())

    @pytest.mark.parametrize('cond', [
        {'type': 'price_break', 'params': {'direction': 'above', 'price': -1}},
        {'type': 'velocity', 'params': {'pct': -1, 'window_min': 5}},
        {'type': 'velocity', 'params': {'pct': 2, 'window_min': 0}},
        {'type': 'volume_surge', 'params': {'multiple': 0}},
    ])
    def test_non_positive_params_rejected(self, cond):
        with pytest.raises(ValueError):
            validate_condition(cond)


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

    def test_elapsed_fraction_clamped(self):
        ctx = EvalContext(avg_volume_20d=10_000_000, elapsed_fraction=1.5)
        r = evaluate({'type': 'volume_surge', 'params': {'multiple': 2.0}},
                     make_quote(volume=25_000_000), ctx)
        assert r.value == pytest.approx(2.5)  # 按 1.0 折算而非 1.5


class TestVolumeSurgeDegraded:
    """B2：volume_surge 数据缺失 → degraded=True（而非普通未触发）"""

    def test_no_avg_volume_marks_degraded(self):
        ctx = EvalContext(avg_volume_20d=None)
        r = evaluate({'type': 'volume_surge', 'params': {'multiple': 2.0}},
                     make_quote(volume=5_000_000), ctx)
        assert r.triggered is False
        assert r.distance_ratio is None
        assert r.degraded is True

    def test_no_quote_volume_marks_degraded(self):
        ctx = EvalContext(avg_volume_20d=10_000_000)
        q = make_quote(volume=None)
        r = evaluate({'type': 'volume_surge', 'params': {'multiple': 2.0}}, q, ctx)
        assert r.triggered is False
        assert r.degraded is True

    def test_normal_not_triggered_not_degraded(self):
        # 有数据但量不足 → 普通未触发，不标 degraded（与 B 层硬过滤语义一致）
        ctx = EvalContext(avg_volume_20d=10_000_000, elapsed_fraction=0.25)
        r = evaluate({'type': 'volume_surge', 'params': {'multiple': 2.0}},
                     make_quote(volume=2_000_000), ctx)  # 2M / (10M*0.25)=0.8x
        assert r.triggered is False
        assert r.degraded is False


class TestCombined:
    def make_price_break(self, price, direction='above'):
        return {'type': 'price_break', 'params': {'price': price, 'direction': direction}}

    def make_volume_surge(self, multiple=2.0):
        return {'type': 'volume_surge', 'params': {'multiple': multiple}}

    def combined(self, operator, *conds):
        return {'type': 'combined', 'params': {'operator': operator,
                                               'conditions': list(conds)}}

    def test_validate_combined(self):
        c = self.combined('AND', self.make_price_break(5.13), self.make_volume_surge())
        validate_condition(c)

    def test_and_both_triggered(self):
        ctx = EvalContext(avg_volume_20d=10_000_000, elapsed_fraction=0.25)
        c = self.combined('AND', self.make_price_break(5.0), self.make_volume_surge(2.0))
        r = evaluate(c, make_quote(price=5.2, volume=6_000_000), ctx)
        assert r.triggered is True
        assert r.degraded is False

    def test_and_price_only_not_volume(self):
        # 上破但无量 → 不触发（B 层硬过滤核心场景）
        ctx = EvalContext(avg_volume_20d=10_000_000, elapsed_fraction=0.25)
        c = self.combined('AND', self.make_price_break(5.0), self.make_volume_surge(2.0))
        r = evaluate(c, make_quote(price=5.2, volume=1_000_000), ctx)  # 0.4x
        assert r.triggered is False
        assert r.degraded is False

    def test_and_price_triggered_volume_degraded_fail_open(self):
        """B2 核心：价格触发 + 放量数据缺失 → 组合触发但标 degraded（防静默失明）"""
        ctx = EvalContext(avg_volume_20d=None)  # 均量缺失
        c = self.combined('AND', self.make_price_break(5.0), self.make_volume_surge(2.0))
        r = evaluate(c, make_quote(price=5.2, volume=6_000_000), ctx)
        assert r.triggered is True
        assert r.degraded is True
        assert '数据缺失' in r.message or '未验证' in r.message

    def test_and_price_not_triggered_volume_degraded_not_triggered(self):
        """价格本身未触发 + 放量数据缺失 → 组合仍不触发（不以 degraded 误报）"""
        ctx = EvalContext(avg_volume_20d=None)
        c = self.combined('AND', self.make_price_break(6.0), self.make_volume_surge(2.0))
        r = evaluate(c, make_quote(price=5.2, volume=6_000_000), ctx)
        assert r.triggered is False

    def test_and_all_degraded_not_triggered(self):
        """全部子条件数据缺失 → 不触发（防凭空误报），标 degraded"""
        ctx = EvalContext(avg_volume_20d=None)
        c = self.combined('AND', self.make_volume_surge(2.0), self.make_volume_surge(3.0))
        # 两个 volume_surge 都无均量 → 双双无法评估
        r = evaluate(c, make_quote(price=100.0, volume=6_000_000), ctx)
        assert r.triggered is False
        assert r.degraded is True

    def test_or_one_real_trigger(self):
        ctx = EvalContext(avg_volume_20d=None)
        c = self.combined('OR', self.make_price_break(5.0), self.make_volume_surge(2.0))
        r = evaluate(c, make_quote(price=5.2, volume=6_000_000), ctx)
        assert r.triggered is True
        assert r.degraded is False  # 真实触发（价格维度），不标 degraded

    def test_or_none_real_trigger_with_degraded(self):
        ctx = EvalContext(avg_volume_20d=None)
        c = self.combined('OR', self.make_price_break(6.0), self.make_volume_surge(2.0))
        r = evaluate(c, make_quote(price=5.2, volume=6_000_000), ctx)
        assert r.triggered is False
        assert r.degraded is True  # 无真实触发但存在无法评估的子条件 → 提示可能有漏判
