"""
评分系统领域服务

包含核心业务逻辑：
- IndustryNeutralScorer: 行业中性化评分
- SmoothScorer: 平滑化评分
- CompositeScorer: 复合评分
"""

import math
from typing import Dict, List, Optional
import numpy as np
from ..models import (
    ScoreResult, ScoringContext, FactorScore, 
    IndustryPercentile, ScoreDimension, ScoringMethod
)
from ..ports import IndustryDataPort


class IndustryNeutralScorer:
    """
    行业中性化评分器
    
    核心思想：不使用绝对值，而是行业内相对排名（分位数）
    
    解决的问题：
    - 科技股 PE=50 vs 银行股 PE=5，绝对值比较导致科技股永远低分
    - 行业内相对比较，科技股 PE=50 如果行业内排名靠前，得分高
    """
    
    def __init__(self, industry_data_port: IndustryDataPort):
        """
        初始化行业中性化评分器
        
        Args:
            industry_data_port: 行业数据端口
        """
        self.industry_data_port = industry_data_port
    
    def calculate_percentile(
        self, 
        value: float, 
        sector_values: List[float]
    ) -> float:
        """
        计算分位数（0-1）
        
        方法：bisect 二分查找
        时间复杂度：O(log n)
        
        Args:
            value: 当前值
            sector_values: 同行业所有值
            
        Returns:
            float: 分位数（0-1），0=最低，1=最高
        """
        if not sector_values:
            return 0.5
        
        # 过滤无效值
        valid_values = [v for v in sector_values if v is not None and not math.isnan(v)]
        if not valid_values:
            return 0.5
        
        sorted_values = sorted(valid_values)
        
        # 使用 numpy 的 searchsorted 计算分位数
        rank = np.searchsorted(sorted_values, value, side='right')
        percentile = rank / len(sorted_values)
        
        return min(1.0, max(0.0, percentile))
    
    def score_factor(
        self,
        symbol: str,
        factor_name: str,
        value: float,
        sector: str,
        direction: int = 1,  # 1=正向（越高越好），-1=反向（越低越好）
        weight: float = 1.0
    ) -> FactorScore:
        """
        对单个因子进行行业中性化评分
        
        Args:
            symbol: 股票代码
            factor_name: 因子名称
            value: 因子值
            sector: 行业
            direction: 方向（1=正向，-1=反向）
            weight: 权重
            
        Returns:
            FactorScore: 因子评分
        """
        # 获取同行业所有值
        sector_values = self.industry_data_port.get_sector_factor_values(
            sector, factor_name
        )
        
        # 计算分位数
        percentile = self.calculate_percentile(value, sector_values)
        
        # 计算得分（0-100）
        # 正向因子：percentile 越高分越高
        # 反向因子：percentile 越低分越高（如 PE）
        if direction == 1:
            score = percentile * 100
        else:
            score = (1 - percentile) * 100
        
        return FactorScore(
            factor_name=factor_name,
            raw_value=value,
            percentile=percentile,
            score=score,
            weight=weight,
            direction=direction
        )
    
    def score_fundamental(
        self,
        context: ScoringContext
    ) -> Dict[str, FactorScore]:
        """
        基本面行业中性化评分
        
        因子：
        - PE（反向）：越低越好
        - PB（反向）：越低越好
        - ROE（正向）：越高越好
        - 营收增长率（正向）：越高越好
        - 净利润增长率（正向）：越高越好
        
        Args:
            context: 评分上下文
            
        Returns:
            Dict[str, FactorScore]: {factor_name: FactorScore}
        """
        factor_scores = {}
        
        # PE（反向，权重 40%）
        if 'pe' in context.factors:
            factor_scores['pe'] = self.score_factor(
                symbol=context.symbol,
                factor_name='pe',
                value=context.factors['pe'],
                sector=context.sector,
                direction=-1,  # 反向
                weight=0.40
            )
        
        # ROE（正向，权重 30%）
        if 'roe' in context.factors:
            factor_scores['roe'] = self.score_factor(
                symbol=context.symbol,
                factor_name='roe',
                value=context.factors['roe'],
                sector=context.sector,
                direction=1,  # 正向
                weight=0.30
            )
        
        # 营收增长率（正向，权重 30%）
        if 'revenue_growth' in context.factors:
            factor_scores['revenue_growth'] = self.score_factor(
                symbol=context.symbol,
                factor_name='revenue_growth',
                value=context.factors['revenue_growth'],
                sector=context.sector,
                direction=1,  # 正向
                weight=0.30
            )
        
        return factor_scores


class SmoothScorer:
    """
    平滑化评分器
    
    核心思想：用连续函数（tanh/sigmoid）替代离散事件（金叉/死叉）
    
    解决的问题：
    - MACD 金叉 +20 分，死叉 -15 分（突变 35 分）
    - 单日价格波动就可能触发金叉/死叉切换
    - 评分不稳定，同一天内可能剧烈波动
    """
    
    @staticmethod
    def tanh_score(value: float, scale: float = 50.0, max_score: float = 10.0) -> float:
        """
        tanh 平滑评分
        
        公式：score = max_score * tanh(value * scale)
        
        特点：
        - value=0 时得 0 分
        - value→+∞ 时得 +max_score 分
        - value→-∞ 时得 -max_score 分
        - 平滑过渡，无突变
        
        Args:
            value: 输入值（如 MACD 柱状图）
            scale: 缩放因子（控制平滑程度）
            max_score: 最大得分
            
        Returns:
            float: 评分（-max_score 到 +max_score）
        """
        return max_score * math.tanh(value * scale)
    
    @staticmethod
    def sigmoid_score(
        value: float, 
        center: float = 0.0, 
        scale: float = 1.0, 
        max_score: float = 15.0
    ) -> float:
        """
        sigmoid 平滑评分
        
        公式：score = max_score / (1 + exp(-(value - center) / scale))
        
        特点：
        - value=center 时得 max_score/2 分
        - value→+∞ 时得 +max_score 分
        - value→-∞ 时得 0 分
        - 单调递增，平滑过渡
        
        Args:
            value: 输入值（如 RSI）
            center: 中心点（如 RSI=50）
            scale: 缩放因子（控制平滑程度）
            max_score: 最大得分
            
        Returns:
            float: 评分（0 到 max_score）
        """
        return max_score / (1 + math.exp(-(value - center) / scale))
    
    def score_macd_smooth(self, factors: Dict) -> float:
        """
        MACD 平滑评分（±10分，不再突变）
        
        原理：
        - 不再区分金叉/死叉（离散事件）
        - 用 tanh 函数平滑过渡（连续函数）
        - hist 越大分越高，hist 越小分越低
        
        Args:
            factors: 包含 macd, macd_signal
            
        Returns:
            float: 评分（-10 到 +10）
        """
        macd = factors.get('macd', 0)
        signal = factors.get('macd_signal', 0)
        hist = macd - signal
        
        # tanh 平滑：hist=0 时得 0 分，hist→+∞ 时得 +10 分
        return self.tanh_score(hist, scale=50.0, max_score=10.0)
    
    def score_rsi_smooth(self, rsi: float) -> float:
        """
        RSI 平滑评分（±15分，连续过渡）
        
        原理：
        - RSI=50 为中性（0 分）
        - RSI<30 超卖（正分，最多+15分）
        - RSI>70 超买（负分，最多-15分）
        - 用 sigmoid 函数平滑过渡
        
        Args:
            rsi: RSI 指标值（0-100）
            
        Returns:
            float: 评分（-15 到 +15）
        """
        # 超卖区（RSI<30）：加分
        if rsi < 30:
            # sigmoid 平滑：RSI=0 时 +15 分，RSI=30 时 0 分
            # 使用 (30 - rsi) 作为输入，RSI=0 时输入=30，RSI=30 时输入=0
            return self.sigmoid_score(30 - rsi, center=15, scale=5, max_score=15)
        # 超买区（RSI>70）：扣分
        elif rsi > 70:
            # sigmoid 平滑：RSI=100 时 -15 分，RSI=70 时 0 分
            # 使用 (rsi - 70) 作为输入，RSI=100 时输入=30，RSI=70 时输入=0
            return -self.sigmoid_score(rsi - 70, center=15, scale=5, max_score=15)
        # 中性区（30-70）：0 分
        else:
            return 0.0
    
    def score_technical_smooth(self, factors: Dict) -> Dict[str, float]:
        """
        技术面平滑评分
        
        Args:
            factors: 技术指标字典
            
        Returns:
            Dict[str, float]: 各维度评分
        """
        return {
            'macd': self.score_macd_smooth(factors),
            'rsi': self.score_rsi_smooth(factors.get('rsi', 50)),
            # 其他指标...
        }


class CompositeScorer:
    """
    复合评分器
    
    核心思想：多维度等权合成，行业内分位数调整
    """
    
    def __init__(
        self,
        industry_neutral_scorer: IndustryNeutralScorer,
        smooth_scorer: SmoothScorer
    ):
        """
        初始化复合评分器
        
        Args:
            industry_neutral_scorer: 行业中性化评分器
            smooth_scorer: 平滑化评分器
        """
        self.industry_neutral_scorer = industry_neutral_scorer
        self.smooth_scorer = smooth_scorer
    
    def composite_score(self, context: ScoringContext) -> ScoreResult:
        """
        复合评分
        
        步骤：
        1. 基本面行业中性化评分
        2. 技术面平滑化评分
        3. 等权合成总分
        
        Args:
            context: 评分上下文
            
        Returns:
            ScoreResult: 评分结果
        """
        # 1. 基本面行业中性化评分
        fundamental_scores = self.industry_neutral_scorer.score_fundamental(context)
        
        # 2. 技术面平滑化评分
        technical_scores = self.smooth_scorer.score_technical_smooth(context.factors)
        
        # 3. 计算各维度得分
        dimension_scores = {}
        
        # 基本面得分（加权平均）
        if fundamental_scores:
            fundamental_total = sum(
                f.score * f.weight for f in fundamental_scores.values()
            )
            dimension_scores[ScoreDimension.FUNDAMENTAL] = fundamental_total
        
        # 技术面得分（简单相加）
        if technical_scores:
            technical_total = sum(technical_scores.values())
            # 映射到 0-100
            technical_total = max(0, min(100, 50 + technical_total))
            dimension_scores[ScoreDimension.TECHNICAL] = technical_total
        
        # 4. 合成总分（等权）
        if dimension_scores:
            total_score = sum(dimension_scores.values()) / len(dimension_scores)
        else:
            total_score = 50.0
        
        # 5. 构建结果
        return ScoreResult(
            symbol=context.symbol,
            total_score=total_score,
            dimension_scores=dimension_scores,
            factor_scores=list(fundamental_scores.values()),
            sector_percentiles={
                f.factor_name: f.percentile 
                for f in fundamental_scores.values()
            },
            scoring_method=context.scoring_method,
            metadata={
                'technical_breakdown': technical_scores,
            }
        )
