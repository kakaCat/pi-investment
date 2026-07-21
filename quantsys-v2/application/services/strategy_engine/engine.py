"""
策略编排引擎

串联三层流水线：行业轮动 → 多因子精选 → ML置信过滤 → 组合构建
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
import logging

import pandas as pd

from .sector_rotation import SectorRotation, SectorScore
from .factor_selection import FactorSelector, StockScore
from .ml_filter import MLFilter, MLVote

logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    market: str
    sectors: List[str] = field(default_factory=list)
    sector_scores: List[Dict] = field(default_factory=list)
    candidates: Dict[str, List[str]] = field(default_factory=dict)
    final_portfolio: List[str] = field(default_factory=list)
    allocation: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    ml_pass_rate: float = 0.0
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


class StrategyEngine:
    """混合策略编排器"""

    SINGLE_STOCK_MAX_PCT = 0.15

    def __init__(self):
        self.a_rotation = SectorRotation(market="A")
        self.hk_rotation = SectorRotation(market="HK")
        self.a_selector = FactorSelector(market="A")
        self.hk_selector = FactorSelector(market="HK")
        self.a_ml_filter = MLFilter(market="A")
        self.hk_ml_filter = MLFilter(market="HK")

    def run(
        self,
        market: str = "A",
        sector_data: Dict = None,
        stock_data: Any = None,
        ml_predictions: Dict = None
    ) -> PipelineResult:
        """执行完整流水线。"""
        result = PipelineResult(market=market)

        try:
            sector_scores = self._run_sector_rotation_scores(market, sector_data)
            result.sectors = [s.sector_name for s in sector_scores]
            result.sector_scores = [
                {
                    "sector_name": s.sector_name,
                    "composite_score": s.composite_score,
                    **s.detail,
                }
                for s in sector_scores
            ]
            logger.info(f"[{market}] 行业轮动结果: {result.sectors}")

            result.candidates = self._run_factor_selection(market, stock_data, result.sectors)
            all_candidates = [s for stocks in result.candidates.values() for s in stocks]
            logger.info(f"[{market}] 因子精选候选: {len(all_candidates)}只")

            ml_filter = self.a_ml_filter if market == "A" else self.hk_ml_filter
            passed = self._run_ml_filter(ml_filter, all_candidates, ml_predictions)
            result.final_portfolio = passed
            result.ml_pass_rate = len(passed) / len(all_candidates) if all_candidates else 0.0
            logger.info(f"[{market}] ML过滤后: {len(passed)}只 (通过率 {result.ml_pass_rate:.0%})")

            if all_candidates and result.ml_pass_rate < MLFilter.MIN_PASS_RATE:
                result.warnings.append(
                    f"ML通过率仅 {result.ml_pass_rate:.0%}，低于 {MLFilter.MIN_PASS_RATE:.0%}，"
                    "建议暂停ML层，仅使用因子层结果"
                )
                result.final_portfolio = all_candidates

            final_by_sector = self._group_by_sector(result.final_portfolio, result.candidates)
            result.allocation = self._build_portfolio(final_by_sector)

        except Exception as e:
            logger.error(f"[{market}] 流水线执行失败: {e}", exc_info=True)
            result.errors.append(str(e))

        return result

    def _run_sector_rotation_scores(self, market: str, data: Dict = None) -> List[SectorScore]:
        """执行行业轮动，返回前3行业评分。"""
        if not data:
            logger.warning(f"[{market}] 无行业数据")
            return []

        rotator = self.a_rotation if market == "A" else self.hk_rotation
        scores = rotator.score(
            momentum=data.get("momentum", {}),
            sector_flow=data.get("flow", {}),
            relative_strength=data.get("strength", {})
        )
        scores = rotator.apply_consecutive_penalty(scores)
        return rotator.top_n(scores, n=3)

    def _run_sector_rotation(self, market: str, data: Dict = None) -> List[str]:
        """执行行业轮动，返回前3行业名称"""
        return [s.sector_name for s in self._run_sector_rotation_scores(market, data)]

    def _run_factor_selection(
        self,
        market: str,
        data: Any = None,
        sectors: List[str] = None
    ) -> Dict[str, List[str]]:
        """因子精选，按行业返回股票列表"""
        if data is None:
            return {}
        # 支持 list-of-dicts (来自 JSON API)
        if isinstance(data, list):
            data = pd.DataFrame(data)

        if hasattr(data, 'empty') and data.empty:
            return {}

        selector = self.a_selector if market == "A" else self.hk_selector
        scores = selector.score(data)
        grouped = selector.top_n_per_industry(scores, n=5)

        if sectors:
            return {s: [stock.symbol for stock in grouped.get(s, [])]
                    for s in sectors if s in grouped}

        return {k: [stock.symbol for stock in v] for k, v in grouped.items()}

    def _run_ml_filter(
        self,
        ml_filter: MLFilter,
        candidates: List[str],
        predictions: Dict = None
    ) -> List[str]:
        """ML置信过滤"""
        if not candidates:
            return []
        if not predictions:
            logger.warning("无ML预测数据，所有候选通过")
            return candidates

        return ml_filter.filter(candidates, predictions)

    def _group_by_sector(
        self,
        symbols: List[str],
        sector_map: Dict[str, List[str]]
    ) -> Dict[str, List[str]]:
        """将最终选中的股票按行业分组"""
        grouped: Dict[str, List[str]] = {}
        for sector, stocks in sector_map.items():
            filtered = [s for s in stocks if s in symbols]
            if filtered:
                grouped[sector] = filtered
        return grouped

    def _build_portfolio(
        self,
        sector_candidates: Dict[str, List[str]],
        total_capital: float = 100000
    ) -> Dict[str, Dict[str, Any]]:
        """等权构建组合。"""
        if not sector_candidates:
            return {}

        n_sectors = len(sector_candidates)
        capital_per_sector = total_capital / n_sectors

        allocation = {}
        for sector, stocks in sector_candidates.items():
            capital_per_stock = capital_per_sector / len(stocks)
            pct = capital_per_stock / total_capital

            if pct > self.SINGLE_STOCK_MAX_PCT:
                capital_per_stock = total_capital * self.SINGLE_STOCK_MAX_PCT
                pct = self.SINGLE_STOCK_MAX_PCT

            for symbol in stocks:
                allocation[symbol] = {
                    "capital": round(capital_per_stock, 2),
                    "pct": round(pct, 4),
                    "sector": sector,
                }

        return allocation
