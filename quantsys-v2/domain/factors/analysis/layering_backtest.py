"""
因子分层回测

按因子值分N层，计算每层收益，分析单调性
用于评估因子的区分能力
"""

import numpy as np
import pandas as pd
from typing import Optional, Dict
import logging

logger = logging.getLogger(__name__)


class FactorLayeringBacktest:
    """
    因子分层回测

    方法：
    - 按因子值分N层（通常5层或10层）
    - 计算每层的平均收益
    - 分析单调性（因子值越大，收益越高）
    - 计算多空组合收益（最高层 - 最低层）
    """

    def __init__(self, n_quantiles: int = 5):
        """
        Args:
            n_quantiles: 分层数量
        """
        self.n_quantiles = n_quantiles
        self.layer_returns = None
        self.layer_stats = None

    def backtest(
        self,
        factor_data: pd.DataFrame,
        return_data: pd.DataFrame,
        holding_period: int = 20
    ) -> pd.DataFrame:
        """
        分层回测

        Args:
            factor_data: 因子值 (dates × stocks)
            return_data: 收益率 (dates × stocks)
            holding_period: 持有期（天数）

        Returns:
            每层收益 DataFrame (dates × layers)
        """
        layer_returns_list = []
        dates = []

        for i, date in enumerate(factor_data.index[:-holding_period]):
            # 当日因子值
            factor_values = factor_data.loc[date]

            # 分层
            try:
                quantiles = pd.qcut(
                    factor_values,
                    q=self.n_quantiles,
                    labels=False,
                    duplicates='drop'
                )
            except ValueError as e:
                logger.warning(f"Failed to quantile cut on {date}: {e}")
                continue

            # 未来收益
            future_idx = i + holding_period
            if future_idx >= len(factor_data.index):
                break

            future_date = factor_data.index[future_idx]
            forward_returns = return_data.loc[future_date]

            # 计算每层平均收益
            layer_returns = []
            for layer in range(self.n_quantiles):
                mask = (quantiles == layer)
                if mask.sum() > 0:
                    layer_return = forward_returns[mask].mean()
                    layer_returns.append(layer_return)
                else:
                    layer_returns.append(np.nan)

            layer_returns_list.append(layer_returns)
            dates.append(date)

        # 转换为DataFrame
        layer_names = [f'Layer_{i+1}' for i in range(self.n_quantiles)]
        self.layer_returns = pd.DataFrame(
            layer_returns_list,
            index=dates,
            columns=layer_names
        )

        logger.info(
            f"Backtest completed: {len(dates)} periods, "
            f"{self.n_quantiles} layers"
        )
        return self.layer_returns

    def calculate_layer_statistics(
        self,
        layer_returns: Optional[pd.DataFrame] = None
    ) -> pd.DataFrame:
        """
        计算分层统计

        Args:
            layer_returns: 分层收益，None表示使用self.layer_returns

        Returns:
            统计指标 DataFrame
        """
        if layer_returns is None:
            if self.layer_returns is None:
                raise ValueError("No layer returns available")
            layer_returns = self.layer_returns

        stats = {}

        for col in layer_returns.columns:
            returns = layer_returns[col].dropna()

            if len(returns) == 0:
                continue

            stats[col] = {
                'mean_return': returns.mean(),
                'std_return': returns.std(),
                'sharpe_ratio': returns.mean() / returns.std() * np.sqrt(252) if returns.std() > 0 else 0,
                'win_rate': (returns > 0).sum() / len(returns),
                'cumulative_return': (1 + returns).prod() - 1,
                'max_return': returns.max(),
                'min_return': returns.min()
            }

        self.layer_stats = pd.DataFrame(stats).T
        logger.info("Calculated layer statistics")
        return self.layer_stats

    def calculate_long_short_returns(
        self,
        layer_returns: Optional[pd.DataFrame] = None
    ) -> pd.Series:
        """
        计算多空组合收益（最高层 - 最低层）

        Args:
            layer_returns: 分层收益

        Returns:
            多空收益序列
        """
        if layer_returns is None:
            if self.layer_returns is None:
                raise ValueError("No layer returns available")
            layer_returns = self.layer_returns

        # 最高层 - 最低层
        long_short = layer_returns.iloc[:, -1] - layer_returns.iloc[:, 0]

        logger.info(
            f"Long-short returns: mean={long_short.mean():.4f}, "
            f"sharpe={long_short.mean() / long_short.std() * np.sqrt(252):.2f}"
        )

        return long_short

    def check_monotonicity(
        self,
        layer_stats: Optional[pd.DataFrame] = None
    ) -> Dict:
        """
        检查单调性

        Args:
            layer_stats: 分层统计

        Returns:
            单调性检查结果
        """
        if layer_stats is None:
            if self.layer_stats is None:
                raise ValueError("No layer statistics available")
            layer_stats = self.layer_stats

        mean_returns = layer_stats['mean_return'].values

        # 检查是否单调递增
        is_monotonic_increasing = all(
            mean_returns[i] <= mean_returns[i+1]
            for i in range(len(mean_returns) - 1)
        )

        # 检查是否单调递减
        is_monotonic_decreasing = all(
            mean_returns[i] >= mean_returns[i+1]
            for i in range(len(mean_returns) - 1)
        )

        # 计算单调性得分（相邻层收益差的符号一致性）
        diffs = np.diff(mean_returns)
        if len(diffs) > 0:
            monotonicity_score = np.abs(np.sum(np.sign(diffs))) / len(diffs)
        else:
            monotonicity_score = 0

        result = {
            'is_monotonic_increasing': is_monotonic_increasing,
            'is_monotonic_decreasing': is_monotonic_decreasing,
            'monotonicity_score': monotonicity_score,
            'mean_returns': mean_returns.tolist()
        }

        logger.info(
            f"Monotonicity check: score={monotonicity_score:.2f}, "
            f"increasing={is_monotonic_increasing}, "
            f"decreasing={is_monotonic_decreasing}"
        )

        return result

    def plot_layer_performance(
        self,
        layer_returns: Optional[pd.DataFrame] = None,
        save_path: Optional[str] = None
    ):
        """
        绘制分层表现

        Args:
            layer_returns: 分层收益
            save_path: 保存路径
        """
        import matplotlib.pyplot as plt

        if layer_returns is None:
            if self.layer_returns is None:
                raise ValueError("No layer returns available")
            layer_returns = self.layer_returns

        fig, axes = plt.subplots(3, 1, figsize=(15, 12))

        # 1. 累积收益
        (1 + layer_returns).cumprod().plot(ax=axes[0])
        axes[0].set_title('Cumulative Returns by Layer')
        axes[0].set_ylabel('Cumulative Return')
        axes[0].legend()
        axes[0].grid(True, alpha=0.3)

        # 2. 平均收益柱状图
        if self.layer_stats is not None:
            self.layer_stats['mean_return'].plot(kind='bar', ax=axes[1])
            axes[1].set_title('Average Returns by Layer')
            axes[1].set_ylabel('Average Return')
            axes[1].axhline(y=0, color='r', linestyle='--', alpha=0.5)
            axes[1].grid(True, alpha=0.3)

        # 3. 多空收益
        long_short = self.calculate_long_short_returns(layer_returns)
        (1 + long_short).cumprod().plot(ax=axes[2])
        axes[2].set_title('Long-Short Portfolio (Top - Bottom)')
        axes[2].set_ylabel('Cumulative Return')
        axes[2].grid(True, alpha=0.3)

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path)
            logger.info(f"Layer performance plot saved to {save_path}")
        else:
            plt.show()

    def get_factor_effectiveness_score(
        self,
        layer_stats: Optional[pd.DataFrame] = None
    ) -> Dict:
        """
        计算因子有效性评分

        评分标准：
        - 单调性得分
        - 多空收益
        - 多空夏普比率
        - 胜率

        Returns:
            有效性评分
        """
        if layer_stats is None:
            if self.layer_stats is None:
                raise ValueError("No layer statistics available")
            layer_stats = self.layer_stats

        # 单调性
        monotonicity = self.check_monotonicity(layer_stats)
        monotonicity_score = monotonicity['monotonicity_score'] * 10

        # 多空收益
        long_short = self.calculate_long_short_returns()
        long_short_return = long_short.mean()
        long_short_sharpe = long_short.mean() / long_short.std() * np.sqrt(252) if long_short.std() > 0 else 0
        long_short_win_rate = (long_short > 0).sum() / len(long_short)

        # 多空收益评分
        if long_short_return > 0.001:
            return_score = 10
        elif long_short_return > 0.0005:
            return_score = 8
        elif long_short_return > 0:
            return_score = 6
        else:
            return_score = 4

        # 夏普比率评分
        if long_short_sharpe > 2.0:
            sharpe_score = 10
        elif long_short_sharpe > 1.5:
            sharpe_score = 8
        elif long_short_sharpe > 1.0:
            sharpe_score = 6
        else:
            sharpe_score = 4

        # 综合评分
        total_score = (
            monotonicity_score * 0.3 +
            return_score * 0.3 +
            sharpe_score * 0.4
        )

        result = {
            'monotonicity_score': monotonicity_score,
            'return_score': return_score,
            'sharpe_score': sharpe_score,
            'total_score': total_score,
            'long_short_return': long_short_return,
            'long_short_sharpe': long_short_sharpe,
            'long_short_win_rate': long_short_win_rate,
            'effectiveness': self._get_effectiveness_label(total_score)
        }

        return result

    def _get_effectiveness_label(self, score: float) -> str:
        """获取有效性标签"""
        if score >= 9:
            return '非常有效'
        elif score >= 7:
            return '有效'
        elif score >= 5:
            return '一般'
        else:
            return '无效'


# 使用示例
def example_usage():
    """使用示例"""
    # 1. 准备数据
    np.random.seed(42)
    dates = pd.date_range('2023-01-01', '2023-12-31', freq='D')
    symbols = [f'stock_{i}' for i in range(100)]

    # 模拟因子数据（有一定预测能力）
    factor_data = pd.DataFrame(
        np.random.randn(len(dates), len(symbols)),
        index=dates,
        columns=symbols
    )

    # 模拟收益数据（与因子有一定相关性）
    return_data = pd.DataFrame(
        factor_data.values * 0.001 + np.random.randn(len(dates), len(symbols)) * 0.02,
        index=dates,
        columns=symbols
    )

    # 2. 创建分层回测器
    backtester = FactorLayeringBacktest(n_quantiles=5)

    # 3. 执行回测
    layer_returns = backtester.backtest(
        factor_data,
        return_data,
        holding_period=20
    )
    print("Layer Returns:")
    print(layer_returns.head())

    # 4. 计算统计指标
    layer_stats = backtester.calculate_layer_statistics()
    print("\nLayer Statistics:")
    print(layer_stats)

    # 5. 检查单调性
    monotonicity = backtester.check_monotonicity()
    print(f"\nMonotonicity Score: {monotonicity['monotonicity_score']:.2f}")

    # 6. 计算多空收益
    long_short = backtester.calculate_long_short_returns()
    print(f"\nLong-Short Return: {long_short.mean():.4f}")
    print(f"Long-Short Sharpe: {long_short.mean() / long_short.std() * np.sqrt(252):.2f}")

    # 7. 计算有效性评分
    effectiveness = backtester.get_factor_effectiveness_score()
    print(f"\nFactor Effectiveness: {effectiveness['effectiveness']}")
    print(f"Total Score: {effectiveness['total_score']:.2f}")

    # 8. 绘制图表
    # backtester.plot_layer_performance(save_path='layer_performance.png')


if __name__ == "__main__":
    example_usage()
