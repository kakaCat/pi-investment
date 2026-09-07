"""
Team A: 风险管理模块接口定义
负责人: 风控工程师
版本: 1.0
"""
from abc import ABC, abstractmethod
from typing import Dict, List
import pandas as pd
import numpy as np


class IRiskCalculator(ABC):
    """风险计算器接口"""

    @abstractmethod
    def calculate_var(self,
                     returns: pd.Series,
                     confidence: float = 0.95) -> float:
        """
        计算VaR (Value at Risk)

        Args:
            returns: 收益率序列
            confidence: 置信水平 (0.95 = 95%)

        Returns:
            VaR值（负数表示损失）

        Example:
            >>> calculator = VaRCalculator()
            >>> returns = pd.Series([0.01, -0.02, 0.03, -0.01])
            >>> var = calculator.calculate_var(returns, 0.95)
            >>> print(f"95% VaR: {var:.4f}")
        """
        pass

    @abstractmethod
    def calculate_cvar(self,
                      returns: pd.Series,
                      confidence: float = 0.95) -> float:
        """
        计算CVaR (Conditional VaR / Expected Shortfall)

        Args:
            returns: 收益率序列
            confidence: 置信水平

        Returns:
            CVaR值（负数，应该比VaR更负）
        """
        pass

    @abstractmethod
    def calculate_risk_metrics(self,
                              portfolio_returns: pd.Series) -> Dict[str, float]:
        """
        计算完整风险指标集

        Args:
            portfolio_returns: 组合收益率序列

        Returns:
            {
                'var_95': float,      # 95% VaR
                'var_99': float,      # 99% VaR
                'cvar_95': float,     # 95% CVaR
                'cvar_99': float,     # 99% CVaR
                'max_drawdown': float,  # 最大回撤
                'sharpe_ratio': float   # 夏普比率
            }
        """
        pass


class IRiskMonitor(ABC):
    """风险监控接口"""

    @abstractmethod
    def get_realtime_metrics(self) -> Dict:
        """
        获取实时风险指标

        Returns:
            {
                'timestamp': str,
                'var_95': float,
                'cvar_95': float,
                'current_drawdown': float,
                'alerts': List[Dict]
            }
        """
        pass

    @abstractmethod
    def check_risk_limits(self, position: Dict) -> Dict:
        """
        检查风险限额

        Args:
            position: {
                'symbol': str,
                'quantity': int,
                'price': float
            }

        Returns:
            {
                'passed': bool,
                'violations': List[str],
                'details': Dict
            }
        """
        pass


class IRiskAttribution(ABC):
    """风险归因接口"""

    @abstractmethod
    def factor_attribution(self,
                          portfolio_returns: pd.Series,
                          factor_returns: pd.DataFrame) -> pd.DataFrame:
        """
        因子归因分析

        Args:
            portfolio_returns: 组合收益率
            factor_returns: 因子收益率矩阵

        Returns:
            DataFrame with columns: ['factor', 'contribution', 'percentage']
        """
        pass

    @abstractmethod
    def sector_attribution(self, holdings: List[Dict]) -> pd.DataFrame:
        """
        行业归因分析

        Args:
            holdings: 持仓列表

        Returns:
            DataFrame with columns: ['sector', 'risk', 'percentage']
        """
        pass
