"""
资金面评分器

数据：fund_flows 表近 5 日主力净流入 + K 线量比。
fund_flows 缺失时降级纯量能评分，reasons 注明（不许静默降级）。

⚠️ 单位约定：stock_fund_flow 金额字段为【万元】（采集时东财元÷10000），
本评分器内部 ×1e4 换算为元后与 market_cap（元）比较。

评分口径：
总分 = base(50) + 主力净流入(±30) + 流入加速(0-20) + 量比(-10~+20)
       + 量能趋势(0-15) + 共振(0-15)，clamp 0-100
"""
from typing import Dict, Any, List, Optional, Tuple
import logging
from .base_scorer import BaseScorer
from infrastructure.config.constants.scoring.scorer_params import (
    CapitalScorerConfig,
    DEFAULT_CAPITAL_SCORER_CONFIG,
)

logger = logging.getLogger(__name__)


class CapitalScorer(BaseScorer):
    """资金面评分器"""

    def __init__(self, config: Optional[CapitalScorerConfig] = None):
        """
        初始化资金面评分器

        Args:
            config: 评分器配置，None 时使用默认配置
        """
        super().__init__()
        self.config = config or DEFAULT_CAPITAL_SCORER_CONFIG

    def score(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Args:
            data: {
                fund_flows: [{main_net_inflow(万元), trade_date, ...}] 倒序，最新在前,
                market_cap: 流通市值（元），用于归一化,
                volume_ratio_5d, volume_ma5, volume_ma20, change_pct
            }

        Returns:
            {'total': float, 'breakdown': {...}, 'reasons': [str]}
        """
        cfg = self.config
        flows = list(data.get('fund_flows') or [])
        volume_ratio = self._f(data.get('volume_ratio_5d'), 1.0)
        volume_ma5 = self._f(data.get('volume_ma5'), 0.0)
        volume_ma20 = self._f(data.get('volume_ma20'), 0.0)
        change_pct = self._f(data.get('change_pct'), 0.0)
        market_cap = self._f(data.get('market_cap'), None)

        breakdown: Dict[str, Optional[float]] = {}
        reasons: List[str] = []
        degraded = len(flows) == 0

        if not degraded:
            flows, truncated = self._winsorize(flows, market_cap)
            if truncated:
                reasons.append('资金流异常值已截断')
            inflow, inflow_reasons = self._score_main_inflow(flows, market_cap)
            accel, accel_reasons = self._score_acceleration(flows)
            breakdown['main_inflow'] = inflow
            breakdown['acceleration'] = accel
            reasons.extend(inflow_reasons)
            reasons.extend(accel_reasons)
        else:
            breakdown['main_inflow'] = None
            breakdown['acceleration'] = None
            reasons.append('资金流数据缺失，按量能评分')

        vol_score = self._score_volume_ratio(volume_ratio)
        breakdown['volume_ratio'] = vol_score
        if vol_score > 0:
            reasons.append(f'成交量放大({volume_ratio:.1f}倍)')
        elif vol_score < 0:
            reasons.append(f'量能萎缩(量比{volume_ratio:.2f})')

        trend_score = cfg.volume_trend_max_score if (volume_ma20 > 0 and volume_ma5 > volume_ma20) else 0.0
        breakdown['volume_trend'] = trend_score
        if trend_score > 0:
            reasons.append('量能趋势向上(5日均量>20日均量)')

        resonance = 0.0
        if not degraded:
            total_inflow = sum(self._f(f.get('main_net_inflow'), 0.0) for f in flows)
            if total_inflow > cfg.resonance_inflow_positive and volume_ratio > cfg.resonance_volume_surge_threshold and change_pct > cfg.resonance_price_rise_threshold:
                resonance = cfg.resonance_max_bonus
                reasons.append('量价资共振：主力流入+放量+上涨')
        breakdown['resonance'] = resonance

        raw = sum(v for v in breakdown.values() if v is not None)
        total = max(cfg.min_score, min(cfg.max_score, cfg.base_score + raw))

        return {
            'total': round(total, 2),
            'breakdown': {k: (round(v, 2) if v is not None else None)
                          for k, v in breakdown.items()},
            'reasons': reasons,
        }

    # ---------- 子项 ----------

    def _score_main_inflow(
        self, flows: List[Dict], market_cap: Optional[float]
    ) -> Tuple[float, List[str]]:
        """主力净流入方向（±30）：5 日累计净流入相对流通市值归一化"""
        cfg = self.config
        amounts = [self._f(f.get('main_net_inflow'), 0.0) for f in flows]
        total_inflow = sum(amounts)  # 万元

        if market_cap and market_cap > 0:
            ratio = total_inflow * cfg.flow_unit / market_cap
        else:
            # 无市值数据：用绝对额粗判（累计 ±1 亿元 = ±10000 万元为满分线）
            ratio = total_inflow / cfg.inflow_fallback_threshold * cfg.inflow_full_ratio
        score = max(-1.0, min(1.0, ratio / cfg.inflow_full_ratio)) * cfg.inflow_max_score

        reasons = []
        yi = total_inflow / 10000.0  # 万元 → 亿元
        if total_inflow > 0:
            consecutive = 0
            for a in amounts:
                if a > 0:
                    consecutive += 1
                else:
                    break
            if consecutive >= cfg.consecutive_inflow_threshold:
                reasons.append(f'主力资金连续{consecutive}日净流入(累计{yi:.1f}亿)')
            else:
                reasons.append(f'主力资金净流入(累计{yi:.1f}亿)')
        elif total_inflow < 0:
            reasons.append(f'主力资金净流出(累计{yi:.1f}亿)')
        return score, reasons

    def _score_acceleration(self, flows: List[Dict]) -> Tuple[float, List[str]]:
        """流入加速（0-20）：近 2 日均值 > 前 3 日均值"""
        cfg = self.config
        if len(flows) < cfg.acceleration_min_days:
            return 0.0, []
        recent2 = sum(self._f(f.get('main_net_inflow'), 0.0) for f in flows[:cfg.acceleration_recent_days]) / cfg.acceleration_recent_days
        prev3 = sum(self._f(f.get('main_net_inflow'), 0.0) for f in flows[cfg.acceleration_recent_days:cfg.acceleration_min_days]) / cfg.acceleration_prev_days
        if prev3 > 0 and recent2 > prev3:
            return cfg.acceleration_max_score, ['资金流入加速(近2日均值>前3日均值)']
        if prev3 <= 0 and recent2 > 0:
            return cfg.acceleration_half_score, ['资金由流出转流入']
        return 0.0, []

    def _score_volume_ratio(self, ratio: float) -> float:
        """量比（-10~+20），口径与 TechnicalScorer 一致"""
        cfg = self.config
        if ratio > cfg.volume_ratio_surge_threshold:
            return min(cfg.volume_ratio_max_score, (ratio - 1) * cfg.volume_ratio_factor)
        if ratio < cfg.volume_ratio_shrink_threshold:
            return cfg.volume_ratio_shrink_penalty
        return 0.0

    def _winsorize(
        self, flows: List[Dict], market_cap: Optional[float]
    ) -> Tuple[List[Dict], bool]:
        """异常值截断：单日净流入 > 流通市值 20% → 截到边界"""
        cfg = self.config
        if not market_cap or market_cap <= 0:
            return flows, False
        limit = market_cap * cfg.outlier_ratio / cfg.flow_unit  # 万元
        truncated = False
        out = []
        for f in flows:
            v = self._f(f.get('main_net_inflow'), 0.0)
            if abs(v) > limit:
                f = dict(f)
                f['main_net_inflow'] = limit if v > 0 else -limit
                truncated = True
            out.append(f)
        return out, truncated

    @staticmethod
    def _f(value, default):
        if value is None:
            return default
        try:
            return float(value)
        except (TypeError, ValueError):
            return default
