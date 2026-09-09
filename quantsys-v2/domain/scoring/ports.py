"""
评分系统端口（接口定义）

定义评分系统的核心端口，包括：
- ScoringEnginePort: 评分引擎端口
- IndustryDataPort: 行业数据端口
- FactorRepositoryPort: 因子仓库端口
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from .models import ScoreResult, ScoringContext, IndustryPercentile


class ScoringEnginePort(ABC):
    """评分引擎端口"""
    
    @abstractmethod
    def score(self, context: ScoringContext) -> ScoreResult:
        """
        计算评分
        
        Args:
            context: 评分上下文
            
        Returns:
            ScoreResult: 评分结果
        """
        pass
    
    @abstractmethod
    def score_batch(self, contexts: List[ScoringContext]) -> List[ScoreResult]:
        """
        批量评分
        
        Args:
            contexts: 评分上下文列表
            
        Returns:
            List[ScoreResult]: 评分结果列表
        """
        pass


class IndustryDataPort(ABC):
    """行业数据端口"""
    
    @abstractmethod
    def get_sector(self, symbol: str) -> str:
        """
        获取股票所属行业
        
        Args:
            symbol: 股票代码
            
        Returns:
            str: 行业名称
        """
        pass
    
    @abstractmethod
    def get_sector_stocks(self, sector: str) -> List[str]:
        """
        获取行业内的所有股票
        
        Args:
            sector: 行业名称
            
        Returns:
            List[str]: 股票代码列表
        """
        pass
    
    @abstractmethod
    def get_sector_factor_values(
        self, 
        sector: str, 
        factor_name: str,
        symbols: Optional[List[str]] = None
    ) -> List[float]:
        """
        获取行业内某因子的所有值
        
        Args:
            sector: 行业名称
            factor_name: 因子名称
            symbols: 股票代码列表（可选，默认全部）
            
        Returns:
            List[float]: 因子值列表
        """
        pass


class FactorRepositoryPort(ABC):
    """因子仓库端口"""
    
    @abstractmethod
    def get_factor_value(self, symbol: str, factor_name: str) -> Optional[float]:
        """
        获取单只股票的因子值
        
        Args:
            symbol: 股票代码
            factor_name: 因子名称
            
        Returns:
            Optional[float]: 因子值，不存在返回 None
        """
        pass
    
    @abstractmethod
    def get_factor_values(
        self, 
        symbols: List[str], 
        factor_name: str
    ) -> Dict[str, float]:
        """
        批量获取因子值
        
        Args:
            symbols: 股票代码列表
            factor_name: 因子名称
            
        Returns:
            Dict[str, float]: {symbol: factor_value}
        """
        pass
