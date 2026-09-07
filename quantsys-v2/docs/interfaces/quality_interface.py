"""
Team D: 工程质量模块接口定义
负责人: 架构师
版本: 1.0
"""
from abc import ABC, abstractmethod
from typing import Dict, List
import pandas as pd


class IDataCleaner(ABC):
    """数据清洗接口"""

    @abstractmethod
    def clean(self, df: pd.DataFrame) -> pd.DataFrame:
        """清洗数据"""
        pass

    @abstractmethod
    def validate(self, df: pd.DataFrame) -> Dict[str, bool]:
        """验证数据质量"""
        pass
