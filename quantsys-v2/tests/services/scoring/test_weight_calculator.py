"""权重计算器单元测试"""
import pytest
from application.services.scoring.weight_calculator import (
    base_weights, apply_regime, feature_pct_for, PROFILE_WEIGHT_ENDPOINTS,
)


NEUTRAL_REGIME = {'label': 'sideways', 'trend_strength': 0.5,
                  'market_risk': 0.4, 'liquidity_heat': 0.5}


class TestBaseWeights:
    def test_balanced_fixed(self):
        w = base_weights('balanced', None)
        assert w == {'technical': 0.5, 'fundamental': 0.3, 'capital': 0.2}

    def test_cyclical_has_cycle_dim(self):
        w = base_weights('cyclical', None)
        assert w['cycle'] == 0.30
        assert abs(sum(w.values()) - 1.0) < 1e-9

    def test_growth_interpolation(self):
        """growth 分位越高 fundamental 权重越大、technical 越小"""
        w_low = base_weights('growth', 0.0)
        w_high = base_weights('growth', 1.0)
        assert w_high['fundamental'] > w_low['fundamental']
        assert w_high['technical'] < w_low['technical']
        # 端点值
        assert w_low['technical'] == 0.45 and w_high['technical'] == 0.35
        assert w_low['fundamental'] == 0.30 and w_high['fundamental'] == 0.40


class TestApplyRegime:
    def test_neutral_regime_near_unchanged(self):
        """中性 regime（信号=中点）→ 权重基本不变"""
        w = {'technical': 0.5, 'fundamental': 0.3, 'capital': 0.2}
        out = apply_regime(w, NEUTRAL_REGIME)
        for k in w:
            assert abs(out[k] - w[k]) < 0.01

    def test_bull_raises_technical(self):
        """强趋势（trend_strength=1）→ 技术权重上升"""
        w = {'technical': 0.5, 'fundamental': 0.3, 'capital': 0.2}
        out = apply_regime(w, {'label': 'bull', 'trend_strength': 1.0,
                               'market_risk': 0.2, 'liquidity_heat': 0.8})
        assert out['technical'] > 0.5

    def test_high_risk_raises_fundamental(self):
        """高风险（market_risk=1）→ 基本面权重上升"""
        w = {'technical': 0.5, 'fundamental': 0.3, 'capital': 0.2}
        out = apply_regime(w, {'label': 'bear', 'trend_strength': 0.3,
                               'market_risk': 1.0, 'liquidity_heat': 0.2})
        assert out['fundamental'] > 0.3

    def test_cycle_dim_not_adjusted(self):
        """cycle 维度不参与 regime 修正（归一化前比例不变）"""
        w = {'technical': 0.25, 'fundamental': 0.20, 'capital': 0.25, 'cycle': 0.30}
        out = apply_regime(w, NEUTRAL_REGIME)
        assert abs(out['cycle'] - 0.30) < 0.01

    def test_clamp_and_normalize(self):
        """单维限幅 [0.15, 0.60] 且总和=1（限幅在归一化前）"""
        w = {'technical': 0.6, 'fundamental': 0.2, 'capital': 0.2}
        out = apply_regime(w, {'label': 'bull', 'trend_strength': 1.0,
                               'market_risk': 0.0, 'liquidity_heat': 1.0})
        # tech: 0.6×1.25=0.75 → 限幅 0.60；fund: 0.2×0.76=0.152；cap: 0.2×1.25=0.25
        assert abs(sum(out.values()) - 1.0) < 1e-9
        assert out['technical'] > 0.55   # 限幅生效（未达到 0.75/1.05≈0.714）
        assert out['fundamental'] >= 0.14


class TestFeaturePct:
    def test_feature_pct_mapping(self):
        assert feature_pct_for('growth', {'growth_pct': 0.9}) == 0.9
        assert feature_pct_for('value', {'value_pct': 0.8}) == 0.8
        assert feature_pct_for('cyclical', {'growth_pct': 0.9}) is None
        assert feature_pct_for('balanced', {}) is None
