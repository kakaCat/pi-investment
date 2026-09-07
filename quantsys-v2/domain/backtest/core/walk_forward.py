"""
Walk-Forward分析 - Team C
滚动窗口回测，避免过拟合
"""
import sys
import os

import pandas as pd
import numpy as np
from typing import Dict, List, Any
import logging

logger = logging.getLogger(__name__)


class WalkForwardAnalysis:
    """
    Walk-Forward分析

    方法:
    1. 将数据分为多个滚动窗口
    2. 在训练窗口优化参数
    3. 在测试窗口验证性能
    4. 滚动前进，重复过程
    """

    def __init__(self,
                 train_period: int = 252,
                 test_period: int = 63,
                 step_size: int = 21):
        """
        Args:
            train_period: 训练期长度（天）
            test_period: 测试期长度（天）
            step_size: 滚动步长（天）
        """
        self.train_period = train_period
        self.test_period = test_period
        self.step_size = step_size

        logger.info(f"WalkForwardAnalysis: train={train_period}, test={test_period}, step={step_size}")

    def run(self,
            data: pd.DataFrame,
            strategy_func: callable,
            param_grid: Dict[str, List]) -> Dict:
        """
        运行Walk-Forward分析

        Args:
            data: 历史数据
            strategy_func: 策略函数 func(data, **params) -> metrics
            param_grid: 参数网格 {'param1': [v1, v2], 'param2': [v3, v4]}

        Returns:
            {
                'periods': List[Dict],  # 每个周期的结果
                'avg_return': float,
                'avg_sharpe': float,
                'stability': float,
                'best_params_frequency': Dict
            }
        """
        logger.info(f"Running Walk-Forward analysis on {len(data)} rows")

        periods = []
        start_idx = 0

        while start_idx + self.train_period + self.test_period <= len(data):
            # 训练集
            train_data = data.iloc[start_idx:start_idx + self.train_period]

            # 测试集
            test_data = data.iloc[
                start_idx + self.train_period:
                start_idx + self.train_period + self.test_period
            ]

            # 在训练集上优化参数
            best_params, train_metrics = self._optimize_params(
                train_data, strategy_func, param_grid
            )

            # 在测试集上验证
            test_metrics = strategy_func(test_data, **best_params)

            period_result = {
                'train_start': train_data.index[0],
                'train_end': train_data.index[-1],
                'test_start': test_data.index[0],
                'test_end': test_data.index[-1],
                'best_params': best_params,
                'train_return': train_metrics.get('return', 0),
                'train_sharpe': train_metrics.get('sharpe', 0),
                'test_return': test_metrics.get('return', 0),
                'test_sharpe': test_metrics.get('sharpe', 0)
            }

            periods.append(period_result)

            logger.info(
                f"Period {len(periods)}: test_return={period_result['test_return']:.2%}, "
                f"test_sharpe={period_result['test_sharpe']:.2f}"
            )

            # 滚动窗口
            start_idx += self.step_size

        # 汇总结果
        summary = self._aggregate_results(periods)

        return {
            'periods': periods,
            **summary
        }

    def _optimize_params(self,
                        train_data: pd.DataFrame,
                        strategy_func: callable,
                        param_grid: Dict[str, List]) -> tuple:
        """
        在训练集上优化参数

        Returns:
            (best_params, best_metrics)
        """
        from itertools import product

        # 生成所有参数组合
        param_names = list(param_grid.keys())
        param_values = list(param_grid.values())
        param_combinations = list(product(*param_values))

        best_sharpe = -np.inf
        best_params = None
        best_metrics = None

        for param_combo in param_combinations:
            params = dict(zip(param_names, param_combo))

            try:
                metrics = strategy_func(train_data, **params)
                sharpe = metrics.get('sharpe', -np.inf)

                if sharpe > best_sharpe:
                    best_sharpe = sharpe
                    best_params = params
                    best_metrics = metrics
            except Exception as e:
                logger.warning(f"Strategy failed with params {params}: {e}")
                continue

        if best_params is None:
            # 使用默认参数
            best_params = {k: v[0] for k, v in param_grid.items()}
            best_metrics = {'return': 0, 'sharpe': 0}

        return best_params, best_metrics

    def _aggregate_results(self, periods: List[Dict]) -> Dict:
        """汇总结果"""
        if not periods:
            return {
                'avg_return': 0,
                'avg_sharpe': 0,
                'stability': 0,
                'best_params_frequency': {}
            }

        test_returns = [p['test_return'] for p in periods]
        test_sharpes = [p['test_sharpe'] for p in periods]

        # 统计最佳参数频率
        params_frequency = {}
        for period in periods:
            params_str = str(sorted(period['best_params'].items()))
            params_frequency[params_str] = params_frequency.get(params_str, 0) + 1

        # 稳定性 = 正收益期数 / 总期数
        positive_periods = sum(1 for r in test_returns if r > 0)
        stability = positive_periods / len(periods)

        return {
            'avg_return': float(np.mean(test_returns)),
            'std_return': float(np.std(test_returns)),
            'avg_sharpe': float(np.mean(test_sharpes)),
            'std_sharpe': float(np.std(test_sharpes)),
            'stability': float(stability),
            'win_rate': float(positive_periods / len(periods)),
            'n_periods': len(periods),
            'best_params_frequency': params_frequency
        }

    def plot_results(self, results: Dict) -> None:
        """
        绘制Walk-Forward结果

        Args:
            results: run()的返回结果
        """
        try:
            import matplotlib.pyplot as plt

            periods = results['periods']

            # 提取数据
            test_returns = [p['test_return'] for p in periods]
            test_sharpes = [p['test_sharpe'] for p in periods]
            period_labels = [f"P{i+1}" for i in range(len(periods))]

            # 创建图表
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))

            # 测试收益率
            ax1.bar(period_labels, test_returns, color=['g' if r > 0 else 'r' for r in test_returns])
            ax1.axhline(y=0, color='black', linestyle='--', linewidth=0.5)
            ax1.set_title('Walk-Forward Test Returns by Period')
            ax1.set_ylabel('Return')
            ax1.grid(True, alpha=0.3)

            # 测试夏普比率
            ax2.plot(period_labels, test_sharpes, marker='o', linewidth=2)
            ax2.axhline(y=0, color='black', linestyle='--', linewidth=0.5)
            ax2.set_title('Walk-Forward Test Sharpe Ratio by Period')
            ax2.set_ylabel('Sharpe Ratio')
            ax2.set_xlabel('Period')
            ax2.grid(True, alpha=0.3)

            plt.tight_layout()
            plt.savefig('walk_forward_results.png', dpi=150)
            logger.info("Walk-Forward plot saved to walk_forward_results.png")

        except ImportError:
            logger.warning("matplotlib not available, skipping plot")
