"""
Repository Ports (接口定义)

Domain 层定义的 Repository 接口
Adapters 层的 Repository 实现必须符合这些接口

符合依赖倒置原则 (DIP)：
- 高层模块 (Domain) 定义接口
- 低层模块 (Adapters) 实现接口
- 双方都依赖抽象，不依赖具体
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from datetime import datetime
import polars as pl


class IKlineRepository(ABC):
    """K线数据仓储接口"""

    @abstractmethod
    def get_kline_data(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        period: str = 'daily'
    ) -> pl.DataFrame:
        """获取K线数据"""
        pass

    @abstractmethod
    def batch_get_kline(
        self,
        symbols: List[str],
        start_date: str,
        end_date: str,
        period: str = 'daily'
    ) -> Dict[str, pl.DataFrame]:
        """批量获取K线数据"""
        pass

    @abstractmethod
    def save_kline_data(self, df: pl.DataFrame) -> int:
        """保存K线数据"""
        pass


class ISignalRepository(ABC):
    """信号仓储接口"""

    @abstractmethod
    def create_signal(self, signal_data: Dict[str, Any]) -> int:
        """创建信号"""
        pass

    @abstractmethod
    def get_signals(
        self,
        symbol: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        signal_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """获取信号列表"""
        pass


class IPortfolioRepository(ABC):
    """组合仓储接口"""

    @abstractmethod
    def get_portfolio_history(
        self,
        portfolio_name: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """获取组合历史"""
        pass

    @abstractmethod
    def save_portfolio_snapshot(
        self,
        portfolio_name: str,
        snapshot_data: Dict[str, Any]
    ) -> int:
        """保存组合快照"""
        pass


class IRiskRepository(ABC):
    """风险仓储接口"""

    @abstractmethod
    def get_risk_metrics(
        self,
        symbol: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """获取风险指标"""
        pass

    @abstractmethod
    def save_risk_metrics(self, metrics: Dict[str, Any]) -> int:
        """保存风险指标"""
        pass


class IFactorRepository(ABC):
    """因子仓储接口"""

    @abstractmethod
    def get_factor_data(
        self,
        symbol: str,
        factor_names: Optional[List[str]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> pl.DataFrame:
        """获取因子数据"""
        pass

    @abstractmethod
    def batch_get_factors(
        self,
        symbols: List[str],
        factor_names: List[str],
        start_date: str,
        end_date: str
    ) -> Dict[str, pl.DataFrame]:
        """批量获取因子数据"""
        pass

    @abstractmethod
    def save_factor_data(self, df: pl.DataFrame) -> int:
        """保存因子数据"""
        pass


class IStrategyRepository(ABC):
    """策略仓储接口"""

    @abstractmethod
    def get_strategy(self, strategy_id: int) -> Optional[Dict[str, Any]]:
        """获取策略"""
        pass

    @abstractmethod
    def list_strategies(
        self,
        source: Optional[str] = None,
        code_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """列出策略"""
        pass

    @abstractmethod
    def create_strategy(self, strategy_data: Dict[str, Any]) -> int:
        """创建策略"""
        pass

    @abstractmethod
    def update_strategy(self, strategy_id: int, updates: Dict[str, Any]) -> bool:
        """更新策略"""
        pass
