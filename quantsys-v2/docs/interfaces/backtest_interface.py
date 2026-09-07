"""
Team C: 回测增强模块接口定义
负责人: 量化研究员
版本: 1.0
"""
from abc import ABC, abstractmethod
from typing import Dict, List
import pandas as pd
import numpy as np


class IMarketImpact(ABC):
    """市场冲击模型接口"""

    @abstractmethod
    def calculate_impact(self,
                        order_size: float,
                        adv: float,
                        price: float,
                        execution_time: float = 1.0) -> Dict[str, float]:
        """
        计算市场冲击成本

        Returns:
            {
                'permanent_impact': float,
                'temporary_impact': float,
                'total_impact': float,
                'impact_bps': float
            }
        """
        pass

    @abstractmethod
    def optimal_execution_schedule(self,
                                   total_shares: int,
                                   total_time: float) -> np.ndarray:
        """计算最优执行策略"""
        pass
