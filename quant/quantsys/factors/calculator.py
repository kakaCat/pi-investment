"""
因子计算引擎
"""
from typing import Dict, List, Optional, Union
import pandas as pd
import numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

from .base import BaseFactor


class FactorCalculator:
    """因子计算引擎"""

    def __init__(self, max_workers: int = 4):
        """
        Args:
            max_workers: 并行计算的最大线程数
        """
        self.factors: Dict[str, BaseFactor] = {}
        self.max_workers = max_workers

    def register(self, factor: BaseFactor) -> None:
        """
        注册因子

        Args:
            factor: 因子实例
        """
        self.factors[factor.name] = factor

    def register_batch(self, factors: List[BaseFactor]) -> None:
        """批量注册因子"""
        for factor in factors:
            self.register(factor)

    def calculate_single(
        self,
        factor_name: str,
        data: pd.DataFrame,
        validate: bool = True
    ) -> Optional[pd.Series]:
        """
        计算单个因子

        Args:
            factor_name: 因子名称
            data: 输入数据
            validate: 是否验证结果

        Returns:
            因子值序列，如果计算失败返回None
        """
        if factor_name not in self.factors:
            raise ValueError(f"Factor {factor_name} not registered")

        factor = self.factors[factor_name]

        try:
            start_time = time.time()
            result = factor.calculate(data)
            elapsed = time.time() - start_time

            if validate and not factor.validate(result):
                print(f"Warning: Factor {factor_name} validation failed")
                return None

            # 性能检查
            if elapsed > 1.0:
                print(f"Warning: Factor {factor_name} took {elapsed:.2f}s (> 1s)")

            return result

        except Exception as e:
            print(f"Error calculating factor {factor_name}: {e}")
            return None

    def calculate_batch(
        self,
        factor_names: List[str],
        data: pd.DataFrame,
        parallel: bool = True
    ) -> pd.DataFrame:
        """
        批量计算因子

        Args:
            factor_names: 因子名称列表
            data: 输入数据
            parallel: 是否并行计算

        Returns:
            DataFrame，每列为一个因子
        """
        results = {}

        if parallel and len(factor_names) > 1:
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                future_to_factor = {
                    executor.submit(self.calculate_single, name, data): name
                    for name in factor_names
                }

                for future in as_completed(future_to_factor):
                    factor_name = future_to_factor[future]
                    try:
                        result = future.result()
                        if result is not None:
                            # 处理返回DataFrame的因子（如MACD, KDJ, BollingerBands）
                            if isinstance(result, pd.DataFrame):
                                for col in result.columns:
                                    results[f"{factor_name}_{col}"] = result[col]
                            else:
                                results[factor_name] = result
                    except Exception as e:
                        print(f"Error in parallel calculation of {factor_name}: {e}")
        else:
            for factor_name in factor_names:
                result = self.calculate_single(factor_name, data)
                if result is not None:
                    # 处理返回DataFrame的因子
                    if isinstance(result, pd.DataFrame):
                        for col in result.columns:
                            results[f"{factor_name}_{col}"] = result[col]
                    else:
                        results[factor_name] = result

        return pd.DataFrame(results)

    def calculate_all(
        self,
        data: pd.DataFrame,
        category: Optional[str] = None
    ) -> pd.DataFrame:
        """
        计算所有已注册因子

        Args:
            data: 输入数据
            category: 只计算指定类别的因子 (technical/fundamental)

        Returns:
            DataFrame，每列为一个因子
        """
        if category:
            factor_names = [
                name for name, factor in self.factors.items()
                if factor.category == category
            ]
        else:
            factor_names = list(self.factors.keys())

        return self.calculate_batch(factor_names, data)

    def get_factor_list(self, category: Optional[str] = None) -> List[Dict]:
        """
        获取因子列表

        Args:
            category: 筛选类别

        Returns:
            因子元数据列表
        """
        factors = self.factors.values()
        if category:
            factors = [f for f in factors if f.category == category]

        return [f.get_metadata() for f in factors]

    def __len__(self) -> int:
        return len(self.factors)

    def __repr__(self) -> str:
        return f"<FactorCalculator: {len(self.factors)} factors registered>"
