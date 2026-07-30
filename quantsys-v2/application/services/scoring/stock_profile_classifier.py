"""
股票类型分类器（程序化，无行业名单/无配置文件）

从财务时间序列计算三个连续指标：
- earnings_volatility: 近 8 季度毛利率标准差（pp）→ 周期特征
- growth_strength:     营收增速 × 毛利率 / 100      → 成长特征
- value_strength:      ROE / PE                     → 价值特征

分类规则（按优先级）：
1. earnings_volatility ≥ 8pp        → cyclical（周期股基本面会伪装成 value，先看波动）
2. growth_strength 池内分位 ≥ 0.70  → growth（相对分位，自适应池子尺度）
3. value_strength 池内分位 ≥ 0.70   → value
4. 其余/数据不足                    → balanced
"""
from typing import Dict, Any, List, Optional
from statistics import pstdev
import logging

logger = logging.getLogger(__name__)


class StockProfileClassifier:
    """逐股程序化分类"""

    CYCLICAL_VOLATILITY_PP = 8.0
    TOP_PERCENTILE = 0.70      # 分位 ≥0.70 = 池内前 30%
    MIN_QUARTERS = 4

    def classify_batch(
        self,
        symbols: List[str],
        quarterly_map: Dict[str, List[Dict]],
        fundamentals_map: Dict[str, Optional[Dict]],
    ) -> Dict[str, Dict[str, Any]]:
        """
        Returns:
            {symbol: {'profile': str, 'signals': {...}, 'reason': str}}
        """
        raw: Dict[str, Dict[str, Any]] = {}
        for s in symbols:
            quarters = quarterly_map.get(s) or []
            fund = fundamentals_map.get(s) or {}
            raw[s] = {
                'earnings_volatility_pp': self._earnings_volatility(quarters),
                'growth_strength': self._growth_strength(fund),
                'value_strength': self._value_strength(fund),
                'quarters_available': len([q for q in quarters
                                           if q.get('gross_margin') is not None]),
            }

        growth_pct = self._percentiles(
            {s: v['growth_strength'] for s, v in raw.items()})
        value_pct = self._percentiles(
            {s: v['value_strength'] for s, v in raw.items()})

        result: Dict[str, Dict[str, Any]] = {}
        for s in symbols:
            sig = raw[s]
            ev = sig['earnings_volatility_pp']
            g_pct = growth_pct.get(s)
            v_pct = value_pct.get(s)

            if sig['quarters_available'] < self.MIN_QUARTERS:
                profile, reason = 'balanced', '季度数据不足4期，按平衡型处理'
            elif ev is not None and ev >= self.CYCLICAL_VOLATILITY_PP:
                profile = 'cyclical'
                reason = f'盈利波动率{ev:.1f}pp≥{self.CYCLICAL_VOLATILITY_PP:.0f}pp，判定为周期股'
            elif g_pct is not None and g_pct >= self.TOP_PERCENTILE:
                profile = 'growth'
                reason = f'成长强度池内分位{g_pct:.0%}，判定为成长股'
            elif v_pct is not None and v_pct >= self.TOP_PERCENTILE:
                profile = 'value'
                reason = f'价值强度池内分位{v_pct:.0%}，判定为价值股'
            else:
                profile, reason = 'balanced', '无显著类型特征，按平衡型处理'

            result[s] = {
                'profile': profile,
                'signals': {
                    'earnings_volatility_pp': (round(ev, 2)
                                               if ev is not None else None),
                    'growth_pct': (round(g_pct, 2)
                                   if g_pct is not None else None),
                    'value_pct': (round(v_pct, 2)
                                  if v_pct is not None else None),
                },
                'reason': reason,
            }
        return result

    # ---------- 指标 ----------

    def _earnings_volatility(self, quarters: List[Dict]) -> Optional[float]:
        values = [float(q['gross_margin']) for q in quarters
                  if q.get('gross_margin') is not None]
        if len(values) < self.MIN_QUARTERS:
            return None
        return pstdev(values)

    def _growth_strength(self, fund: Dict) -> Optional[float]:
        rg = self._f(fund.get('revenue_growth'))
        gm = self._f(fund.get('gross_margin'))
        if rg is None or gm is None:
            return None
        return rg * gm / 100.0

    def _value_strength(self, fund: Dict) -> Optional[float]:
        pe = self._f(fund.get('pe_ratio'))
        roe = self._f(fund.get('roe'))
        if pe is None or pe <= 0 or roe is None:
            return None
        return roe / pe

    @staticmethod
    def _percentiles(values: Dict[str, Optional[float]]) -> Dict[str, float]:
        """池内相对分位（0-1），None 不参与"""
        valid = {s: v for s, v in values.items() if v is not None}
        n = len(valid)
        if n < 2:
            return {}
        sorted_vals = sorted(valid.values())
        out = {}
        for s, v in valid.items():
            rank = sum(1 for x in sorted_vals if x < v)
            out[s] = rank / (n - 1)
        return out

    @staticmethod
    def _f(value) -> Optional[float]:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
