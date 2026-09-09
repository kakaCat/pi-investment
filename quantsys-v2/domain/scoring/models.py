"""
评分系统领域模型

定义评分系统的核心领域模型，包括：
- ScoreResult: 评分结果
- FactorScore: 单因子评分
- IndustryPercentile: 行业内分位数
- ScoringContext: 评分上下文
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum


class ScoreDimension(Enum):
    """评分维度"""
    TECHNICAL = "technical"
    FUNDAMENTAL = "fundamental"
    CAPITAL = "capital"
    SENTIMENT = "sentiment"


class ScoringMethod(Enum):
    """评分方法"""
    ABSOLUTE = "absolute"           # 绝对值评分（旧）
    INDUSTRY_NEUTRAL = "industry_neutral"  # 行业中性化（新）
    SMOOTH = "smooth"               # 平滑化（新）


@dataclass
class IndustrySentiment:
    """行业景气度"""
    industry: str                   # 行业名称
    score: float                    # 景气度分数（-10 到 +10）
    reason: str                     # 原因说明
    updated_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict:
        return {
            'industry': self.industry,
            'score': self.score,
            'reason': self.reason,
            'updated_at': self.updated_at.isoformat(),
        }


@dataclass
class FactorScore:
    """单因子评分"""
    factor_name: str                # 因子名称（如 pe, roe, rsi）
    raw_value: float                # 原始值
    percentile: float               # 行业内分位数（0-1）
    score: float                    # 评分（0-100）
    weight: float                   # 权重
    direction: int                  # 方向（1=正向，-1=反向）
    
    def to_dict(self) -> Dict:
        return {
            'factor_name': self.factor_name,
            'raw_value': self.raw_value,
            'percentile': self.percentile,
            'score': self.score,
            'weight': self.weight,
            'direction': self.direction,
        }


@dataclass
class IndustryPercentile:
    """行业内分位数"""
    symbol: str                     # 股票代码
    sector: str                     # 行业
    factor_name: str                # 因子名称
    value: float                    # 因子值
    percentile: float               # 分位数（0-1）
    rank: int                       # 排名
    total: int                      # 行业总数
    
    def to_dict(self) -> Dict:
        return {
            'symbol': self.symbol,
            'sector': self.sector,
            'factor_name': self.factor_name,
            'value': self.value,
            'percentile': self.percentile,
            'rank': self.rank,
            'total': self.total,
        }


@dataclass
class ScoreResult:
    """评分结果"""
    symbol: str                     # 股票代码
    total_score: float              # 总分（0-100）
    dimension_scores: Dict[ScoreDimension, float]  # 各维度得分
    factor_scores: List[FactorScore]               # 单因子得分
    sector_percentiles: Dict[str, float]           # 行业内分位数
    scoring_method: ScoringMethod                  # 评分方法
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            'symbol': self.symbol,
            'total_score': self.total_score,
            'dimension_scores': {k.value: v for k, v in self.dimension_scores.items()},
            'factor_scores': [f.to_dict() for f in self.factor_scores],
            'sector_percentiles': self.sector_percentiles,
            'scoring_method': self.scoring_method.value,
            'timestamp': self.timestamp.isoformat(),
            'metadata': self.metadata,
        }


@dataclass
class ScoringContext:
    """评分上下文"""
    symbol: str                     # 股票代码
    sector: str                     # 行业
    factors: Dict[str, float]       # 因子值
    sector_factors: Optional[Dict[str, List[float]]] = None  # 同行业因子值
    scoring_method: ScoringMethod = ScoringMethod.INDUSTRY_NEUTRAL
    weights: Optional[Dict[str, float]] = None  # 自定义权重
    
    def get_sector_values(self, factor_name: str) -> List[float]:
        """获取同行业某因子的所有值"""
        if self.sector_factors and factor_name in self.sector_factors:
            return self.sector_factors[factor_name]
        return []
