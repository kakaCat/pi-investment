"""accumulation_scorer 门禁测试（2026-11-10 Phase 2，w-191eb58c）

守护点：
1. 验证组合（波动压缩+缩量+趴着+温和流入）必须 validated_combo=True；
2. 追涨形态（放量+大涨）必须低分且 validated=False——两种哲学不得混同；
3. 数据不全（K线不足/资金流缺失）返回 None 诚实降级，禁止打 0 分冒充。
"""
import numpy as np
import pandas as pd
import pytest

from application.services.scoring.accumulation_scorer import (
    extract_features, score_one,
    VOL_PCT_THRESHOLD, VOLUME_RATIO_THRESHOLD, MOM20_ABS_THRESHOLD,
)


def _mk_klines(n=200, vol_level=0.02, quiet_tail=30, trend=0.0, seed=3):
    rng = np.random.default_rng(seed)
    rets = rng.normal(trend, vol_level, n)
    close = 100 * np.exp(np.cumsum(rets))
    # 尾部 25 天确定性横盘（低波随机游走 20 日仍会漂移出 ±3%，不算"趴着"）
    close[-25:] = close[-26]
    volume = rng.integers(2_000_000, 4_000_000, n).astype(float)
    # 只缩最后 3 天的量：量比=当日量/20日均量，长尾巴会拉低分母导致 vr 假回升
    volume[-3:] = volume[-3:] * 0.4
    dates = pd.date_range('2025-01-01', periods=n, freq='B')
    return [{'trade_date': str(d.date()), 'close': float(c), 'volume': float(v)}
            for d, c, v in zip(dates, close, volume)]


def test_validated_combo_passes():
    kl = _mk_klines()
    feats = extract_features(kl, mf5=1000.0)  # 5日净流入 1000 万
    assert feats is not None
    # 合成数据尾部低波+缩量+横盘，应满足验证组合
    assert feats['vol_pct'] < VOL_PCT_THRESHOLD
    assert feats['volume_ratio'] < VOLUME_RATIO_THRESHOLD
    assert abs(feats['mom20']) < MOM20_ABS_THRESHOLD
    r = score_one(feats)
    assert r['validated_combo'] is True
    assert r['total'] >= 70


def test_chase_profile_scores_low():
    """放量上涨形态：蓄势分必须低且 validated=False（与追涨哲学互斥）。"""
    r = score_one({'vol_pct': 0.9, 'volume_ratio': 2.0, 'mom20': 0.15, 'mf5': 5000.0})
    assert r['validated_combo'] is False
    assert r['total'] < 30


def test_missing_data_returns_none():
    """K线不足 140 根 / 资金流缺失 → None，不打 0 分冒充。"""
    assert extract_features(_mk_klines(n=100), mf5=1000.0) is None
    assert extract_features(_mk_klines(), mf5=None) is None
    assert score_one({'vol_pct': None, 'volume_ratio': 0.7, 'mom20': 0.0, 'mf5': 100.0}) is None


def test_outflow_kills_inflow_score():
    """主力净流出时资金项不得分。"""
    base = {'vol_pct': 0.1, 'volume_ratio': 0.6, 'mom20': 0.0}
    assert score_one({**base, 'mf5': 500.0})['breakdown']['gentle_inflow'] > 0
    assert score_one({**base, 'mf5': -500.0})['breakdown']['gentle_inflow'] == 0
    assert score_one({**base, 'mf5': -500.0})['validated_combo'] is False
