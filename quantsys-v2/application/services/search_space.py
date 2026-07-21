"""
参数搜索空间
用于生成参数网格进行策略优化
"""
from typing import Dict, List
from itertools import product


class SearchSpace:
    """参数搜索空间"""

    def __init__(self, param_ranges: Dict[str, List]):
        """
        初始化搜索空间

        Args:
            param_ranges: 参数范围字典，例如 {'fast': [5, 10, 20], 'slow': [20, 50]}
        """
        self.param_ranges = param_ranges

    def generate_grid(self) -> List[Dict]:
        """
        生成参数网格（笛卡尔积）

        Returns:
            参数组合列表，例如 [{'fast': 5, 'slow': 20}, {'fast': 5, 'slow': 50}, ...]
        """
        if not self.param_ranges:
            return []

        # 获取参数名和值列表
        param_names = list(self.param_ranges.keys())
        param_values = [self.param_ranges[name] for name in param_names]

        # 生成笛卡尔积
        grid = []
        for combination in product(*param_values):
            param_dict = dict(zip(param_names, combination))
            grid.append(param_dict)

        return grid
