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
from infrastructure.config.constants.scoring.scorer_params import (
    WeightCalculatorConfig,
    DEFAULT_WEIGHT_CALCULATOR_CONFIG,
)

# 全局默认配置实例
_default_config = DEFAULT_WEIGHT_CALCULATOR_CONFIG

# profile → 用哪个特征分位插值
_PROFILE_FEATURE_KEY = {'growth': 'growth_pct', 'value': 'value_pct'}


def base_weights(
    profile: str,
    feature_pct: Optional[float],
    config: Optional[WeightCalculatorConfig] = None
) -> Dict[str, float]:
    """profile 基础权重（growth/value 按特征分位插值）

    Args:
        profile: growth/value/cyclical/balanced
        feature_pct: 特征分位（growth→growth_pct, value→value_pct），None 按 0.5
        config: 权重计算配置，None 时使用默认配置
    """
    cfg = config or _default_config
    endpoints = cfg.profile_weight_endpoints.get(
        profile, cfg.profile_weight_endpoints['balanced'])
    pct = feature_pct if feature_pct is not None else cfg.default_feature_pct
    out: Dict[str, float] = {}
    for dim, spec in endpoints.items():
        if isinstance(spec, tuple):
            lo, hi = spec
            out[dim] = lo + (hi - lo) * pct
        else:
            out[dim] = float(spec)
    return out


def apply_regime(
    weights: Dict[str, float],
    regime_signals: Dict[str, float],
    config: Optional[WeightCalculatorConfig] = None
) -> Dict[str, float]:
    """regime 连续信号修正权重 → 限幅 → 归一化

    Args:
        weights: base_weights 输出
        regime_signals: {trend_strength, market_risk, liquidity_heat}（0-1）
        config: 权重计算配置，None 时使用默认配置
    """
    cfg = config or _default_config
    ts = float(regime_signals.get('trend_strength', cfg.technical_regime_mid))
    mr = float(regime_signals.get('market_risk', cfg.fundamental_regime_mid))
    lh = float(regime_signals.get('liquidity_heat', cfg.capital_regime_mid))

    adjusted = dict(weights)
    if 'technical' in adjusted:
        adjusted['technical'] *= (1 + cfg.technical_regime_coef * (ts - cfg.technical_regime_mid))
    if 'fundamental' in adjusted:
        adjusted['fundamental'] *= (1 + cfg.fundamental_regime_coef * (mr - cfg.fundamental_regime_mid))
    if 'capital' in adjusted:
        adjusted['capital'] *= (1 + cfg.capital_regime_coef * (lh - cfg.capital_regime_mid))
    # cycle 维度不修正

    for k in adjusted:
        adjusted[k] = min(cfg.max_weight, max(cfg.min_weight, adjusted[k]))

    total = sum(adjusted.values())
    if total <= 0:
        return dict(cfg.profile_weight_endpoints['balanced'])
    return {k: v / total for k, v in adjusted.items()}


def feature_pct_for(profile: str, signals: Dict[str, Any]) -> Optional[float]:
    """从分类器 signals 中取插值用的特征分位"""
    key = _PROFILE_FEATURE_KEY.get(profile)
    if key is None:
        return None
    return signals.get(key)
