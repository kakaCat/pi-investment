"""
因子正交化处理器

提供三种正交化方法：
1. Schmidt正交化：对基础因子做回归，使用残差
2. PCA主成分分析：提取正交的主成分
3. 对称正交化：使用QR分解保持对称性
"""

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.linear_model import LinearRegression
from scipy.linalg import qr
from typing import Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class FactorOrthogonalizer:
    """
    因子正交化处理器

    用于消除因子间的相关性，提高因子独立性
    """

    def __init__(self):
        self.correlation_matrix = None
        self.orthogonal_factors = None

    def calculate_correlation_matrix(
        self,
        factor_data: pd.DataFrame
    ) -> pd.DataFrame:
        """
        计算因子相关性矩阵

        Args:
            factor_data: 因子数据 (samples × factors)

        Returns:
            相关性矩阵
        """
        self.correlation_matrix = factor_data.corr()
        logger.info(f"Calculated correlation matrix: {factor_data.shape[1]} factors")
        return self.correlation_matrix

    def find_highly_correlated_pairs(
        self,
        threshold: float = 0.8
    ) -> List[Dict]:
        """
        找出高度相关的因子对

        Args:
            threshold: 相关性阈值

        Returns:
            高度相关的因子对列表
        """
        if self.correlation_matrix is None:
            raise ValueError("Correlation matrix not calculated")

        corr_matrix = self.correlation_matrix
        highly_correlated = []

        for i in range(len(corr_matrix.columns)):
            for j in range(i + 1, len(corr_matrix.columns)):
                corr_value = abs(corr_matrix.iloc[i, j])
                if corr_value > threshold:
                    highly_correlated.append({
                        'factor1': corr_matrix.columns[i],
                        'factor2': corr_matrix.columns[j],
                        'correlation': corr_matrix.iloc[i, j]
                    })

        logger.info(
            f"Found {len(highly_correlated)} highly correlated pairs "
            f"(threshold={threshold})"
        )
        return highly_correlated

    def schmidt_orthogonalization(
        self,
        factor_data: pd.DataFrame,
        base_factors: List[str]
    ) -> pd.DataFrame:
        """
        Schmidt正交化

        原理：
        - 选择基础因子（如市值、行业）
        - 其他因子对基础因子做回归
        - 使用残差作为正交化后的因子

        Args:
            factor_data: 因子数据
            base_factors: 基础因子列表

        Returns:
            正交化后的因子数据
        """
        if not base_factors:
            return factor_data.copy()

        orthogonal_factors = factor_data.copy()

        for factor in factor_data.columns:
            if factor in base_factors:
                continue

            # 对基础因子做回归
            X = factor_data[base_factors].values
            y = factor_data[factor].values

            # 去除NaN
            mask = ~(np.isnan(X).any(axis=1) | np.isnan(y))
            X_clean = X[mask]
            y_clean = y[mask]

            if len(X_clean) < 10:
                logger.warning(f"Not enough samples for factor {factor}")
                continue

            # 线性回归
            model = LinearRegression()
            model.fit(X_clean, y_clean)

            # 残差作为正交化因子
            residuals = y.copy()
            residuals[mask] = y_clean - model.predict(X_clean)
            orthogonal_factors[factor] = residuals

        self.orthogonal_factors = orthogonal_factors
        logger.info(
            f"Schmidt orthogonalization completed: "
            f"{len(base_factors)} base factors"
        )
        return orthogonal_factors

    def pca_orthogonalization(
        self,
        factor_data: pd.DataFrame,
        n_components: Optional[int] = None,
        variance_threshold: float = 0.95
    ) -> Tuple[pd.DataFrame, np.ndarray]:
        """
        PCA主成分分析

        原理：
        - 提取主成分
        - 主成分之间正交
        - 保留最重要的成分

        Args:
            factor_data: 因子数据
            n_components: 主成分数量，None表示自动选择
            variance_threshold: 累积方差阈值

        Returns:
            (主成分DataFrame, 解释方差比例)
        """
        # 标准化
        factor_standardized = (
            factor_data - factor_data.mean()
        ) / factor_data.std()

        # 去除NaN
        factor_clean = factor_standardized.dropna()

        if n_components is None:
            # 自动选择主成分数量
            pca_temp = PCA()
            pca_temp.fit(factor_clean)
            cumsum_variance = np.cumsum(pca_temp.explained_variance_ratio_)
            n_components = np.argmax(cumsum_variance >= variance_threshold) + 1

        # Clamp n_components to valid range
        max_components = min(factor_clean.shape[0], factor_clean.shape[1])
        n_components = min(n_components, max_components)

        # PCA变换
        pca = PCA(n_components=n_components)
        principal_components = pca.fit_transform(factor_clean)

        # 转换为DataFrame
        pc_names = [f'PC{i+1}' for i in range(n_components)]
        pc_df = pd.DataFrame(
            principal_components,
            index=factor_clean.index,
            columns=pc_names
        )

        self.orthogonal_factors = pc_df
        logger.info(
            f"PCA orthogonalization completed: "
            f"{n_components} components, "
            f"variance explained: {pca.explained_variance_ratio_.sum():.2%}"
        )

        return pc_df, pca.explained_variance_ratio_

    def symmetric_orthogonalization(
        self,
        factor_data: pd.DataFrame
    ) -> pd.DataFrame:
        """
        对称正交化

        原理：
        - 使用QR分解
        - 保持因子的对称性

        Args:
            factor_data: 因子数据

        Returns:
            正交化后的因子数据
        """
        # 标准化
        standardized = (
            factor_data - factor_data.mean()
        ) / factor_data.std()

        # 去除NaN
        factor_clean = standardized.dropna()

        # QR分解
        Q, R = qr(factor_clean.values)

        # Use only the first n columns (n = number of original factors)
        n_factors = factor_data.shape[1]
        Q_sliced = Q[:, :n_factors]

        # Q矩阵的列向量是正交的
        orthogonal_df = pd.DataFrame(
            Q_sliced,
            index=factor_clean.index,
            columns=factor_data.columns
        )

        self.orthogonal_factors = orthogonal_df
        logger.info("Symmetric orthogonalization completed")
        return orthogonal_df

    def plot_correlation_heatmap(
        self,
        factor_data: Optional[pd.DataFrame] = None,
        save_path: Optional[str] = None
    ):
        """
        绘制相关性热图

        Args:
            factor_data: 因子数据，None表示使用correlation_matrix
            save_path: 保存路径
        """
        import matplotlib.pyplot as plt
        import seaborn as sns

        if factor_data is not None:
            corr_matrix = factor_data.corr()
        elif self.correlation_matrix is not None:
            corr_matrix = self.correlation_matrix
        else:
            raise ValueError("No correlation matrix available")

        plt.figure(figsize=(12, 10))
        sns.heatmap(
            corr_matrix,
            annot=False,
            cmap='coolwarm',
            center=0,
            vmin=-1,
            vmax=1,
            square=True
        )
        plt.title('Factor Correlation Matrix')
        plt.tight_layout()

        if save_path:
            plt.savefig(save_path)
            logger.info(f"Correlation heatmap saved to {save_path}")
        else:
            plt.show()

    def compare_before_after(
        self,
        original_data: pd.DataFrame,
        orthogonal_data: pd.DataFrame
    ) -> Dict:
        """
        对比正交化前后的相关性

        Args:
            original_data: 原始因子数据
            orthogonal_data: 正交化后的因子数据

        Returns:
            对比统计
        """
        # 计算相关性矩阵
        corr_original = original_data.corr()
        corr_orthogonal = orthogonal_data.corr()

        # 提取上三角（不包括对角线）
        mask = np.triu(np.ones_like(corr_original, dtype=bool), k=1)
        corr_original_values = corr_original.values[mask]
        corr_orthogonal_values = corr_orthogonal.values[mask]

        stats = {
            'original': {
                'mean_abs_corr': np.abs(corr_original_values).mean(),
                'max_abs_corr': np.abs(corr_original_values).max(),
                'high_corr_count': (np.abs(corr_original_values) > 0.8).sum()
            },
            'orthogonal': {
                'mean_abs_corr': np.abs(corr_orthogonal_values).mean(),
                'max_abs_corr': np.abs(corr_orthogonal_values).max(),
                'high_corr_count': (np.abs(corr_orthogonal_values) > 0.8).sum()
            }
        }

        logger.info(
            f"Correlation reduction: "
            f"{stats['original']['mean_abs_corr']:.3f} -> "
            f"{stats['orthogonal']['mean_abs_corr']:.3f}"
        )

        return stats


# 使用示例
def example_usage():
    """使用示例"""
    # 1. 准备数据
    np.random.seed(42)
    n_samples = 1000
    n_factors = 10

    # 创建相关的因子数据
    base = np.random.randn(n_samples, 3)
    factors = np.column_stack([
        base,
        base[:, 0] + np.random.randn(n_samples) * 0.5,  # 与第1个因子相关
        base[:, 1] + np.random.randn(n_samples) * 0.5,  # 与第2个因子相关
        np.random.randn(n_samples, 5)  # 独立因子
    ])

    factor_names = [f'factor_{i+1}' for i in range(n_factors)]
    factor_data = pd.DataFrame(factors, columns=factor_names)

    # 2. 创建正交化器
    orthogonalizer = FactorOrthogonalizer()

    # 3. 计算相关性矩阵
    corr_matrix = orthogonalizer.calculate_correlation_matrix(factor_data)
    print("Correlation Matrix:")
    print(corr_matrix)

    # 4. 找出高度相关的因子对
    high_corr_pairs = orthogonalizer.find_highly_correlated_pairs(threshold=0.7)
    print(f"\nHighly correlated pairs: {len(high_corr_pairs)}")
    for pair in high_corr_pairs:
        print(f"  {pair['factor1']} <-> {pair['factor2']}: {pair['correlation']:.3f}")

    # 5. Schmidt正交化
    base_factors = ['factor_1', 'factor_2', 'factor_3']
    orthogonal_schmidt = orthogonalizer.schmidt_orthogonalization(
        factor_data,
        base_factors
    )
    print("\nSchmidt Orthogonalization:")
    print(orthogonal_schmidt.corr())

    # 6. PCA正交化
    orthogonal_pca, variance_ratio = orthogonalizer.pca_orthogonalization(
        factor_data,
        variance_threshold=0.95
    )
    print("\nPCA Orthogonalization:")
    print(f"Components: {orthogonal_pca.shape[1]}")
    print(f"Variance explained: {variance_ratio.sum():.2%}")

    # 7. 对比正交化前后
    stats = orthogonalizer.compare_before_after(factor_data, orthogonal_schmidt)
    print("\nBefore vs After:")
    print(f"Original mean abs corr: {stats['original']['mean_abs_corr']:.3f}")
    print(f"Orthogonal mean abs corr: {stats['orthogonal']['mean_abs_corr']:.3f}")


if __name__ == "__main__":
    example_usage()
