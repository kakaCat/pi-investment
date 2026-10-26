"""档位计算（tier.py）单测 —— 纯函数，无任何 I/O。"""
from types import SimpleNamespace

import pytest

from qs_watch.application.services.watch_engine.v2 import tier


def rule(conditions, cost_price=None):
    return SimpleNamespace(id=1, symbol='600000', conditions=conditions,
                           cost_price=cost_price)


def test_tier_of_boundaries():
    assert tier.tier_of(0) == tier.TIER_FAST
    assert tier.tier_of(1.0) == tier.TIER_FAST          # 边界含 1%
    assert tier.tier_of(1.01) == tier.TIER_MID
    assert tier.tier_of(3.0) == tier.TIER_MID           # 边界含 3%
    assert tier.tier_of(3.01) == tier.TIER_SLOW
    assert tier.tier_of(None) is None


def test_distance_pct():
    assert tier.distance_pct(23.50, 23.80) == pytest.approx(1.2605, abs=1e-3)
    assert tier.distance_pct(None, 23.80) is None
    assert tier.distance_pct(23.50, 0) is None


def test_trigger_prices_price_break_and_staged():
    r = rule([
        {'type': 'price_break', 'params': {'price': 23.8, 'direction': 'above'}},
        {'type': 'staged_break', 'params': {'touch': {'price': 20.0, 'direction': 'below'}}},
    ])
    assert tier.trigger_prices(r) == [20.0, 23.8]


def test_trigger_prices_pnl_and_pct_change():
    r = rule([{'type': 'pnl_pct', 'params': {'pct': 15.0, 'direction': 'above'}}],
             cost_price=20.0)
    assert tier.trigger_prices(r) == [23.0]
    r2 = rule([{'type': 'pct_change', 'params': {'pct': -5.0, 'direction': 'below'}}])
    assert tier.trigger_prices(r2, prev_close=10.0) == [9.5]


def test_trigger_prices_combined_recursion():
    r = rule([{
        'type': 'combined',
        'params': {'operator': 'AND', 'conditions': [
            {'type': 'price_break', 'params': {'price': 10.0, 'direction': 'above'}},
            {'type': 'volume_surge', 'params': {'multiple': 1.5}},
        ]},
    }])
    assert tier.trigger_prices(r) == [10.0]      # 不可价格化的子条件被忽略


def test_trigger_prices_unpriceable_returns_empty():
    r = rule([{'type': 'rsi', 'params': {'threshold': 70, 'direction': 'above'}}])
    assert tier.trigger_prices(r) == []
    assert tier.tier_for(r, price=10.0) is None  # 算不出来 = 保持原档位


def test_tier_for_uses_nearest_line():
    r = rule([
        {'type': 'price_break', 'params': {'price': 24.0, 'direction': 'above'}},
        {'type': 'price_break', 'params': {'price': 21.0, 'direction': 'below'}},
    ])
    # 现价 23.5：距 24 只有 2.08%，距 21 有 11.9% → 取最近 → 中档
    assert tier.tier_for(r, price=23.5) == tier.TIER_MID


def test_normalize_tier():
    assert tier.normalize_tier(30) == 30
    assert tier.normalize_tier('600') == 600
    assert tier.normalize_tier(1800) == 1800
    assert tier.normalize_tier(45) is None
    assert tier.normalize_tier(None) is None
