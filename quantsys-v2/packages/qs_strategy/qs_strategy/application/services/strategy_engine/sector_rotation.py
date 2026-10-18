"""
行业轮动评分引擎

A股: 动量40% + 资金流35% + 相对强弱25%
港股: 南向资金40% + 动量35% + 相对强弱25%
"""
from dataclasses import dataclass, field
from typing import Dict, List
import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)


@dataclass
class SectorScore:
    sector_name: str
    composite_score: float
    detail: Dict[str, float] = field(default_factory=dict)


class SectorRotation:
    """行业轮动评分器"""

    A_WEIGHTS = {"momentum": 0.40, "flow": 0.35, "strength": 0.25}
    HK_WEIGHTS = {"momentum": 0.35, "flow": 0.40, "strength": 0.25}

    MOMENTUM_PERIODS = [4, 8, 12]
    CONSECUTIVE_PENALTY_THRESHOLD = 4
    PENALTY_FACTOR = 0.8

    def __init__(self, market: str = "A"):
        if market not in ("A", "HK"):
            raise ValueError(f"market must be 'A' or 'HK', got {market}")
        self.market = market
        self.weights = self.A_WEIGHTS if market == "A" else self.HK_WEIGHTS
        self.consecutive_top_count: Dict[str, int] = {}

    def score(
        self,
        momentum: Dict[str, float],
        sector_flow: Dict[str, float],
        relative_strength: Dict[str, float]
    ) -> List[SectorScore]:
        """对所有行业进行综合评分。"""
        sectors = sorted(set(momentum.keys()) | set(sector_flow.keys()) | set(relative_strength.keys()))
        results = []

        for sector in sectors:
            m = momentum.get(sector, 0.0)
            f = sector_flow.get(sector, 0.0)
            s = relative_strength.get(sector, 0.0)

            composite = (
                m * self.weights["momentum"] +
                f * self.weights["flow"] +
                s * self.weights["strength"]
            )

            results.append(SectorScore(
                sector_name=sector,
                composite_score=round(composite, 4),
                detail={"momentum": m, "flow": f, "strength": s}
            ))

        results.sort(key=lambda x: x.composite_score, reverse=True)
        return results

    def _normalize(self, series: pd.Series) -> pd.Series:
        """Z-score标准化"""
        if series.std() == 0:
            return pd.Series(0.0, index=series.index)
        return (series - series.mean()) / series.std()

    def top_n(self, scores: List[SectorScore], n: int = 3) -> List[SectorScore]:
        """返回前N行业（按综合得分降序）"""
        sorted_scores = sorted(scores, key=lambda x: x.composite_score, reverse=True)
        return sorted_scores[:n]

    def apply_consecutive_penalty(self, scores: List[SectorScore]) -> List[SectorScore]:
        """对连续排名第一的行业打折扣"""
        result = []
        for s in scores:
            count = self.consecutive_top_count.get(s.sector_name, 0)
            if count >= self.CONSECUTIVE_PENALTY_THRESHOLD:
                s.composite_score = round(s.composite_score * self.PENALTY_FACTOR, 4)
                logger.info(f"行业 {s.sector_name} 连续{count}周第一，打{self.PENALTY_FACTOR}折")
            result.append(s)
        result.sort(key=lambda x: x.composite_score, reverse=True)
        return result

    def update_consecutive_count(self, top_sector: str, all_sectors: List[str]):
        """更新连续排名计数"""
        for sector in all_sectors:
            if sector == top_sector:
                self.consecutive_top_count[sector] = self.consecutive_top_count.get(sector, 0) + 1
            else:
                self.consecutive_top_count[sector] = 0
