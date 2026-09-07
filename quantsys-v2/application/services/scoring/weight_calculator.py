"""
动态权重计算

两段式：
1. base_weights: profile 基础权重，growth/value 按特征分位在端点间插值（权重随特征
   强度连续变化，不是死表）
2. apply_regime: regime 连续信号修正（趋势强度→技术、市场风险→基本面、量能热度→
   资金），cycle 维度不修正；单维限幅 [0.15, 0.60] 后归一化

调用方显式传 weights 时本模块不被调用（显式 > 隐式）。
"""
from typing import Dict, Optional, Any

# 端点 = (分位0时权重, 分位1时权重)；标量 = 固定权重
PROFILE_WEIGHT_ENDPOINTS: Dict[str, Dict[str, Any]] = {
    'growth':   {'technical': (0.45, 0.35), 'fundamental': (0.30, 0.40),
                 'capital': (0.25, 0.25)},
    'value':    {'technical': (0.30, 0.20), 'fundamental': (0.45, 0.55),
                 'capital': (0.25, 0.25)},
    'cyclical': {'technical': 0.25, 'fundamental': 0.20,
                 'capital': 0.25, 'cycle': 0.30},
    'balanced': {'technical': 0.50, 'fundamental': 0.30, 'capital': 0.20},
}

# profile → 用哪个特征分位插值
_PROFILE_FEATURE_KEY = {'growth': 'growth_pct', 'value': 'value_pct'}

# regime 修正系数与中性点
_TECH_COEF, _TECH_MID = 0.5, 0.5     # trend_strength
_FUND_COEF, _FUND_MID = 0.6, 0.4     # market_risk
_CAP_COEF, _CAP_MID = 0.5, 0.5       # liquidity_heat

_MIN_W, _MAX_W = 0.15, 0.60


def base_weights(profile: str, feature_pct: Optional[float]) -> Dict[str, float]:
    """profile 基础权重（growth/value 按特征分位插值）

    Args:
        profile: growth/value/cyclical/balanced
        feature_pct: 特征分位（growth→growth_pct, value→value_pct），None 按 0.5
    """
    endpoints = PROFILE_WEIGHT_ENDPOINTS.get(
        profile, PROFILE_WEIGHT_ENDPOINTS['balanced'])
    pct = feature_pct if feature_pct is not None else 0.5
    out: Dict[str, float] = {}
    for dim, spec in endpoints.items():
        if isinstance(spec, tuple):
            lo, hi = spec
            out[dim] = lo + (hi - lo) * pct
        else:
            out[dim] = float(spec)
    return out


def apply_regime(
    weights: Dict[str, float], regime_signals: Dict[str, float]
) -> Dict[str, float]:
    """regime 连续信号修正权重 → 限幅 → 归一化

    Args:
        weights: base_weights 输出
        regime_signals: {trend_strength, market_risk, liquidity_heat}（0-1）
    """
    ts = float(regime_signals.get('trend_strength', _TECH_MID))
    mr = float(regime_signals.get('market_risk', _FUND_MID))
    lh = float(regime_signals.get('liquidity_heat', _CAP_MID))

    adjusted = dict(weights)
    if 'technical' in adjusted:
        adjusted['technical'] *= (1 + _TECH_COEF * (ts - _TECH_MID))
    if 'fundamental' in adjusted:
        adjusted['fundamental'] *= (1 + _FUND_COEF * (mr - _FUND_MID))
    if 'capital' in adjusted:
        adjusted['capital'] *= (1 + _CAP_COEF * (lh - _CAP_MID))
    # cycle 维度不修正

    for k in adjusted:
        adjusted[k] = min(_MAX_W, max(_MIN_W, adjusted[k]))

    total = sum(adjusted.values())
    if total <= 0:
        return dict(PROFILE_WEIGHT_ENDPOINTS['balanced'])
    return {k: v / total for k, v in adjusted.items()}


def feature_pct_for(profile: str, signals: Dict[str, Any]) -> Optional[float]:
    """从分类器 signals 中取插值用的特征分位"""
    key = _PROFILE_FEATURE_KEY.get(profile)
    if key is None:
        return None
    return signals.get(key)
