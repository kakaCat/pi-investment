"""
评分引擎（应用层）

协调领域服务，提供统一的评分接口。
"""

from typing import Dict, List, Optional
import logging

from domain.scoring.models import (
    ScoreResult, ScoringContext, ScoreDimension, ScoringMethod
)
from domain.scoring.services import (
    IndustryNeutralScorer, SmoothScorer, CompositeScorer
)
from domain.scoring.ports import IndustryDataPort

logger = logging.getLogger(__name__)


class ScoringEngine:
    """
    评分引擎（应用层）
    
    职责：
    1. 协调领域服务（IndustryNeutralScorer、SmoothScorer、CompositeScorer）
    2. 提供统一的评分接口
    3. 处理评分上下文构建
    """
    
    def __init__(self, industry_data_port: IndustryDataPort):
        """
        初始化评分引擎
        
        Args:
            industry_data_port: 行业数据端口
        """
        self.industry_neutral_scorer = IndustryNeutralScorer(industry_data_port)
        self.smooth_scorer = SmoothScorer()
        self.composite_scorer = CompositeScorer(
            self.industry_neutral_scorer,
            self.smooth_scorer
        )
        self.industry_data_port = industry_data_port
    
    def score_stock(
        self,
        symbol: str,
        factors: Dict[str, float],
        scoring_method: ScoringMethod = ScoringMethod.INDUSTRY_NEUTRAL
    ) -> ScoreResult:
        """
        对单只股票评分
        
        Args:
            symbol: 股票代码
            factors: 因子值字典
            scoring_method: 评分方法
            
        Returns:
            ScoreResult: 评分结果
        """
        # 1. 获取行业
        sector = self.industry_data_port.get_sector(symbol)
        
        # 2. 构建评分上下文
        context = ScoringContext(
            symbol=symbol,
            sector=sector,
            factors=factors,
            scoring_method=scoring_method
        )
        
        # 3. 复合评分
        result = self.composite_scorer.composite_score(context)
        
        logger.info(
            f"评分完成: {symbol} ({sector}) "
            f"总分={result.total_score:.2f} "
            f"方法={scoring_method.value}"
        )
        
        return result
    
    def score_batch(
        self,
        symbols: List[str],
        factors_dict: Dict[str, Dict[str, float]],
        scoring_method: ScoringMethod = ScoringMethod.INDUSTRY_NEUTRAL
    ) -> List[ScoreResult]:
        """
        批量评分
        
        Args:
            symbols: 股票代码列表
            factors_dict: {symbol: factors}
            scoring_method: 评分方法
            
        Returns:
            List[ScoreResult]: 评分结果列表
        """
        results = []
        
        for symbol in symbols:
            if symbol not in factors_dict:
                logger.warning(f"跳过 {symbol}: 无因子数据")
                continue
            
            result = self.score_stock(
                symbol=symbol,
                factors=factors_dict[symbol],
                scoring_method=scoring_method
            )
            results.append(result)
        
        return results
    
    def compare_stocks(
        self,
        symbols: List[str],
        factors_dict: Dict[str, Dict[str, float]]
    ) -> Dict[str, any]:
        """
        比较多只股票
        
        Args:
            symbols: 股票代码列表
            factors_dict: {symbol: factors}
            
        Returns:
            Dict: 比较结果
        """
        results = self.score_batch(symbols, factors_dict)
        
        # 按总分排序
        sorted_results = sorted(
            results,
            key=lambda x: x.total_score,
            reverse=True
        )
        
        return {
            'ranking': [
                {
                    'symbol': r.symbol,
                    'total_score': r.total_score,
                    'sector': r.metadata.get('sector', 'unknown'),
                }
                for r in sorted_results
            ],
            'details': [r.to_dict() for r in sorted_results],
        }
