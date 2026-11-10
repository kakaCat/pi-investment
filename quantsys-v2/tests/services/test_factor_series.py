"""factor_series 门禁测试（2026-11-10 P0.1，w-191eb58c）

历史 bug：旧 factor_analyze 端点对任意因子名返回同一 20 日动量代理值，
MACD/RSI/PE/ROE 的 IC 完全相同（实测 icMean=0.6093 四因子一致）。
本测试是防回归门禁：
1. 不同因子名必须产出不同序列（同一输入 K 线）；
2. 未支持因子（含 pe/pb/roe 等无历史快照的基本面因子）必须返回 None，禁止冒充；
3. RSI/MACD 的已知方向 sanity check。
"""
import numpy as np
import pandas as pd
import pytest

from domain.factors.analysis.factor_series import compute_factor_series


def _mk_klines(n=120, seed=7, trend=0.001):
    """合成日K：随机游走 + 轻微趋势，确定性种子。"""
    rng = np.random.default_rng(seed)
    rets = rng.normal(trend, 0.02, n)
    close = 100 * np.exp(np.cumsum(rets))
    volume = rng.integers(1_000_000, 5_000_000, n).astype(float)
    dates = pd.date_range('2026-01-01', periods=n, freq='B')
    return pd.DataFrame({'trade_date': dates, 'close': close, 'volume': volume})


def test_different_factors_produce_different_series():
    """门禁：同一输入下 rsi/macd/momentum/volatility 两两不得相同。"""
    df = _mk_klines()
    series = {
        name: compute_factor_series(df, name)
        for name in ('rsi', 'macd', 'momentum', 'volatility', 'ma_bias', 'volume_ratio')
    }
    assert all(s is not None for s in series.values())
    names = list(series)
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a = series[names[i]].dropna()
            b = series[names[j]].dropna()
            n = min(len(a), len(b))
            assert n > 20
            assert not np.allclose(a.values[-n:], b.values[-n:]), (
                f'{names[i]} 与 {names[j]} 产出相同序列——疑似因子名被映射到同一代理（历史 bug 回归）'
            )


def test_unsupported_factor_returns_none():
    """诚实降级：pe/pb/roe/未知因子返回 None，禁止拿别的因子冒充。"""
    df = _mk_klines()
    for name in ('pe', 'pb', 'roe', 'turnover', 'nonexistent_factor', ''):
        assert compute_factor_series(df, name) is None


def test_rsi_sanity_on_monotonic_uptrend():
    """单调上涨序列的 RSI 应接近 100。"""
    n = 60
    df = pd.DataFrame({
        'close': np.linspace(100, 130, n),
        'volume': np.full(n, 1e6),
    })
    rsi = compute_factor_series(df, 'rsi')
    assert rsi.dropna().iloc[-1] > 95


def test_macd_hist_sign_matches_trend():
    """持续上涨后 MACD 柱应为正，持续下跌后应为负。"""
    n = 80
    up = pd.DataFrame({'close': np.linspace(100, 120, n)})
    down = pd.DataFrame({'close': np.linspace(120, 100, n)})
    assert compute_factor_series(up, 'macd').iloc[-1] > 0
    assert compute_factor_series(down, 'macd').iloc[-1] < 0
