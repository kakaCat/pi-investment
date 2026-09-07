"""
评分器基类

定义统一的评分接口，所有具体评分器必须继承此类。
"""

from abc import ABC, abstractmethod
from typing import Dict, Any


class BaseScorer(ABC):
    """
    评分器抽象基类

    所有评分器必须实现 score() 方法，返回标准化的评分结果。
    """

    @abstractmethod
    def score(self, data: Dict[str, Any]) -> Dict[str, float]:
        """
        计算评分

        Args:
            data: 输入数据字典，具体格式由子类定义

        Returns:
            评分结果字典，格式：
            {
                'total': 85.0,        # 总分 (0-100)
                'breakdown': {         # 评分明细
                    'sub_item_1': 20.0,
                    'sub_item_2': 15.0,
                    ...
                }
            }

        Raises:
            NotImplementedError: 子类必须实现此方法
        """
        pass
