"""
因子基类定义
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
import pandas as pd
import numpy as np


class BaseFactor(ABC):
    """因子基类"""

    def __init__(self, name: str, description: str, category: str = "unknown"):
        """
        Args:
            name: 因子名称
            description: 因子描述
            category: 因子类别 (technical/fundamental)
        """
        self.name = name
        self.description = description
        self.category = category
        self._cache = {}

    @abstractmethod
    def calculate(self, data: pd.DataFrame) -> pd.Series:
        """
        计算因子值

        Args:
            data: 包含OHLCV数据的DataFrame，必须包含列:
                  - date/datetime: 日期
                  - open: 开盘价
                  - high: 最高价
                  - low: 最低价
                  - close: 收盘价
                  - volume: 成交量

        Returns:
            pd.Series: 因子值序列，索引与输入data对齐
        """
        raise NotImplementedError(f"Factor {self.name} must implement calculate()")

    def validate(self, result: pd.Series) -> bool:
        """
        验证因子计算结果的有效性

        Args:
            result: 因子计算结果

        Returns:
            bool: 是否有效
        """
        if result is None or len(result) == 0:
            return False

        # 检查是否全为NaN
        if result.isna().all():
            return False

        # 检查是否包含无穷大
        if np.isinf(result).any():
            return False

        return True

    def get_metadata(self) -> Dict[str, Any]:
        """获取因子元数据"""
        return {
            'name': self.name,
            'description': self.description,
            'category': self.category,
        }

    def __repr__(self) -> str:
        return f"<Factor: {self.name} ({self.category})>"


class TechnicalFactor(BaseFactor):
    """技术因子基类"""

    def __init__(self, name: str, description: str, period: Optional[int] = None):
        """
        Args:
            name: 因子名称
            description: 因子描述
            period: 计算周期（如MA的天数）
        """
        super().__init__(name, description, category="technical")
        self.period = period

    def get_metadata(self) -> Dict[str, Any]:
        metadata = super().get_metadata()
        if self.period is not None:
            metadata['period'] = self.period
        return metadata


class FundamentalFactor(BaseFactor):
    """基本面因子基类"""

    def __init__(self, name: str, description: str):
        super().__init__(name, description, category="fundamental")

    def calculate(self, data: pd.DataFrame) -> pd.Series:
        """
        基本面因子计算

        Args:
            data: 包含财务数据的DataFrame，列名取决于具体因子

        Returns:
            pd.Series: 因子值
        """
        raise NotImplementedError(f"Factor {self.name} must implement calculate()")
