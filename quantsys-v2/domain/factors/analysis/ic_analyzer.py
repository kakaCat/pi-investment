"""
因子IC/IR分析器

IC (Information Coefficient): 因子值与未来收益的相关系数
IR (Information Ratio): IC均值 / IC标准差

用于评估因子的预测能力和稳定性
"""
import structlog
logger = structlog.get_logger(__name__)

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)


class ICAnalyzer:
    """
    因子IC（Information Coefficient）分析器

    IC指标：
    - IC: 因子值与未来收益的Spearman相关系数
    - IC_mean: IC均值
    - IC_std: IC标准差
    - IC_IR: IC信息比率 = IC_mean / IC_std
    - ICIR: 年化IC信息比率
    - IC_positive_rate: IC为正的比例
    """

    def __init__(self):
        self.ic_series = None
        self.ic_stats = None

    def calculate_ic(
        self,
        factor_values: np.ndarray,
        forward_returns: np.ndarray
    ) -> float:
        """
        计算单期IC

        Args:
            factor_values: 因子值 (N stocks)
            forward_returns: 未来收益 (N stocks)

        Returns:
            IC值（Spearman相关系数）
        """
        # 去除NaN
        mask = ~(np.isnan(factor_values) | np.isnan(forward_returns))
        factor_clean = factor_values[mask]
        returns_clean = forward_returns[mask]

        if len(factor_clean) < 10:  # 样本太少
            return np.nan

        try:
            ic, pvalue = spearmanr(factor_clean, returns_clean)
            return ic
        except Exception as e:
            logger.error(f"Failed to calculate IC: {e}")
            return np.nan

    def calculate_ic_series(
        self,
        factor_data: pd.DataFrame,
        return_data: pd.DataFrame,
        periods: List[int] = [1, 5, 10, 20]
    ) -> pd.DataFrame:
        """
        计算IC时间序列

        Args:
            factor_data: 因子数据 (dates × stocks)
            return_data: 收益数据 (dates × stocks)
            periods: 预测周期列表（天数）

        Returns:
            IC时间序列 DataFrame (dates × periods)
        """
        ic_results = {}

        for period in periods:
            ic_list = []
            dates = []

            for i, date in enumerate(factor_data.index[:-period]):
                # 当日因子值
                factor_values = factor_data.loc[date].values

                # 未来period天的收益
                future_idx = i + period
                if future_idx >= len(factor_data.index):
                    break

                future_date = factor_data.index[future_idx]
                forward_returns = return_data.loc[future_date].values

                # 计算IC
                ic = self.calculate_ic(factor_values, forward_returns)
                ic_list.append(ic)
                dates.append(date)

            ic_results[f'IC_{period}D'] = pd.Series(ic_list, index=dates)

        self.ic_series = pd.DataFrame(ic_results)
        logger.info(f"Calculated IC series for {len(periods)} periods")
        return self.ic_series

    def calculate_ic_statistics(
        self,
        ic_series: Optional[pd.DataFrame] = None
    ) -> pd.DataFrame:
        """
        计算IC统计指标

        Args:
            ic_series: IC时间序列，如果为None则使用self.ic_series

        Returns:
            IC统计指标 DataFrame
        """
        if ic_series is None:
            if self.ic_series is None:
                raise ValueError("No IC series available")
            ic_series = self.ic_series

        stats = {}

        for col in ic_series.columns:
            ic_values = ic_series[col].dropna()

            if len(ic_values) == 0:
                continue

            ic_mean = ic_values.mean()
            ic_std = ic_values.std()

            stats[col] = {
                'IC_mean': ic_mean,
                'IC_std': ic_std,
                'IC_IR': ic_mean / ic_std if ic_std > 0 else 0,
                'IC_positive_rate': (ic_values > 0).sum() / len(ic_values),
                'IC_abs_mean': ic_values.abs().mean(),
                'ICIR_annual': ic_mean / ic_std * np.sqrt(252) if ic_std > 0 else 0,
                'IC_max': ic_values.max(),
                'IC_min': ic_values.min()
            }

        self.ic_stats = pd.DataFrame(stats).T
        logger.info("Calculated IC statistics")
        return self.ic_stats

    def plot_ic_series(
        self,
        ic_series: Optional[pd.DataFrame] = None,
        save_path: Optional[str] = None
    ):
        """
        绘制IC时间序列

        Args:
            ic_series: IC时间序列
            save_path: 保存路径
        """
        import matplotlib.pyplot as plt

        if ic_series is None:
            if self.ic_series is None:
                raise ValueError("No IC series available")
            ic_series = self.ic_series

        fig, axes = plt.subplots(2, 1, figsize=(15, 10))

        # IC时间序列
        ic_series.plot(ax=axes[0], alpha=0.7)
        axes[0].axhline(y=0, color='r', linestyle='--', alpha=0.5)
        axes[0].set_title('IC Time Series')
        axes[0].set_ylabel('IC')
        axes[0].legend()
        axes[0].grid(True, alpha=0.3)

        # IC累积值
        ic_series.cumsum().plot(ax=axes[1], alpha=0.7)
        axes[1].set_title('Cumulative IC')
        axes[1].set_ylabel('Cumulative IC')
        axes[1].legend()
        axes[1].grid(True, alpha=0.3)

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path)
            logger.info(f"IC plot saved to {save_path}")
        else:
            plt.show()

    def get_factor_quality_score(
        self,
        ic_stats: Optional[pd.DataFrame] = None
    ) -> Dict[str, float]:
        """
        计算因子质量评分

        评分标准：
        - IC_mean > 0.05: 优秀
        - IC_mean > 0.03: 良好
        - IC_mean > 0.01: 一般
        - IC_IR > 1.5: 优秀
        - IC_IR > 1.0: 良好
        - IC_positive_rate > 0.6: 优秀

        Returns:
            质量评分字典
        """
        if ic_stats is None:
            if self.ic_stats is None:
                raise ValueError("No IC statistics available")
            ic_stats = self.ic_stats

        scores = {}

        for period in ic_stats.index:
            stats = ic_stats.loc[period]

            # IC均值评分
            ic_mean = stats['IC_mean']
            if ic_mean > 0.05:
                ic_mean_score = 10
            elif ic_mean > 0.03:
                ic_mean_score = 8
            elif ic_mean > 0.01:
                ic_mean_score = 6
            else:
                ic_mean_score = 4

            # IC_IR评分
            ic_ir = stats['IC_IR']
            if ic_ir > 1.5:
                ic_ir_score = 10
            elif ic_ir > 1.0:
                ic_ir_score = 8
            elif ic_ir > 0.5:
                ic_ir_score = 6
            else:
                ic_ir_score = 4

            # IC正比率评分
            ic_pos_rate = stats['IC_positive_rate']
            if ic_pos_rate > 0.6:
                ic_pos_score = 10
            elif ic_pos_rate > 0.55:
                ic_pos_score = 8
            elif ic_pos_rate > 0.5:
                ic_pos_score = 6
            else:
                ic_pos_score = 4

            # 综合评分
            total_score = (ic_mean_score * 0.4 +
                          ic_ir_score * 0.4 +
                          ic_pos_score * 0.2)

            scores[period] = {
                'ic_mean_score': ic_mean_score,
                'ic_ir_score': ic_ir_score,
                'ic_pos_score': ic_pos_score,
                'total_score': total_score,
                'quality': self._get_quality_label(total_score)
            }

        return scores

    def _get_quality_label(self, score: float) -> str:
        """获取质量标签"""
        if score >= 9:
            return '优秀'
        elif score >= 7:
            return '良好'
        elif score >= 5:
            return '一般'
        else:
            return '较差'


# 使用示例
def example_usage():
    """使用示例"""
    # 1. 准备数据
    dates = pd.date_range('2023-01-01', '2023-12-31', freq='D')
    symbols = [f'stock_{i}' for i in range(100)]

    # 模拟因子数据
    factor_data = pd.DataFrame(
        np.random.randn(len(dates), len(symbols)),
        index=dates,
        columns=symbols
    )

    # 模拟收益数据
    return_data = pd.DataFrame(
        np.random.randn(len(dates), len(symbols)) * 0.02,
        index=dates,
        columns=symbols
    )

    # 2. 创建分析器
    analyzer = ICAnalyzer()

    # 3. 计算IC时间序列
    ic_series = analyzer.calculate_ic_series(
        factor_data,
        return_data,
        periods=[1, 5, 10, 20]
    )
    logger.info('IC Series:')
    logger.info(ic_series.head())

    # 4. 计算IC统计指标
    ic_stats = analyzer.calculate_ic_statistics()
    logger.info('\nIC Statistics:')
    logger.info(ic_stats)

    # 5. 计算因子质量评分
    quality_scores = analyzer.get_factor_quality_score()
    logger.info('\nFactor Quality Scores:')
    for period, scores in quality_scores.items():
        logger.info(f"{period}: {scores['quality']} (Score: {scores['total_score']:.2f})")

    # 6. 绘制IC图表
    # analyzer.plot_ic_series(save_path='ic_analysis.png')


if __name__ == "__main__":
    example_usage()
