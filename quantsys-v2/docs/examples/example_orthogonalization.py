"""
因子正交化完整示例

演示如何使用FactorOrthogonalizer消除因子间的相关性：
1. 计算因子相关性矩阵
2. 识别高度相关的因子对
3. Schmidt正交化
4. PCA正交化
5. 对称正交化
6. 对比正交化效果
"""

import sys
import os

import numpy as np
import pandas as pd
from domain.quantlib.factor_analysis.orthogonalizer import FactorOrthogonalizer


def create_correlated_factors():
    """创建相关的因子数据"""
    print("=" * 60)
    print("步骤1: 创建相关因子数据")
    print("=" * 60)

    np.random.seed(42)
    n_samples = 1000
    n_factors = 10

    # 创建基础因子
    base_factors = np.random.randn(n_samples, 3)

    # 创建相关因子
    factors = np.column_stack([
        base_factors[:, 0],  # factor_1: 基础因子
        base_factors[:, 1],  # factor_2: 基础因子
        base_factors[:, 2],  # factor_3: 基础因子
        base_factors[:, 0] + np.random.randn(n_samples) * 0.3,  # factor_4: 与factor_1高度相关
        base_factors[:, 1] + np.random.randn(n_samples) * 0.3,  # factor_5: 与factor_2高度相关
        base_factors[:, 0] * 0.5 + base_factors[:, 1] * 0.5 + np.random.randn(n_samples) * 0.2,  # factor_6: 混合
        np.random.randn(n_samples),  # factor_7: 独立因子
        np.random.randn(n_samples),  # factor_8: 独立因子
        np.random.randn(n_samples),  # factor_9: 独立因子
        np.random.randn(n_samples),  # factor_10: 独立因子
    ])

    factor_names = [f'factor_{i+1}' for i in range(n_factors)]
    factor_data = pd.DataFrame(factors, columns=factor_names)

    print(f"样本数: {n_samples}")
    print(f"因子数: {n_factors}")
    print(f"\n因子统计:")
    print(factor_data.describe())

    return factor_data


def analyze_correlation(orthogonalizer, factor_data):
    """分析因子相关性"""
    print("\n" + "=" * 60)
    print("步骤2: 分析因子相关性")
    print("=" * 60)

    # 计算相关性矩阵
    corr_matrix = orthogonalizer.calculate_correlation_matrix(factor_data)

    print("\n相关性矩阵:")
    print(corr_matrix.round(3))

    # 找出高度相关的因子对
    high_corr_pairs = orthogonalizer.find_highly_correlated_pairs(threshold=0.7)

    print(f"\n高度相关的因子对 (相关性 > 0.7): {len(high_corr_pairs)}个")
    for pair in high_corr_pairs:
        print(f"  {pair['factor1']} <-> {pair['factor2']}: {pair['correlation']:.3f}")

    # 统计相关性分布
    corr_values = corr_matrix.values[np.triu_indices_from(corr_matrix.values, k=1)]
    print(f"\n相关性统计:")
    print(f"  平均绝对相关性: {np.abs(corr_values).mean():.3f}")
    print(f"  最大绝对相关性: {np.abs(corr_values).max():.3f}")
    print(f"  高相关对数 (>0.8): {(np.abs(corr_values) > 0.8).sum()}")

    return corr_matrix, high_corr_pairs


def schmidt_orthogonalization_demo(orthogonalizer, factor_data):
    """Schmidt正交化演示"""
    print("\n" + "=" * 60)
    print("步骤3: Schmidt正交化")
    print("=" * 60)

    print("\n方法说明:")
    print("- 选择基础因子（如市值、行业等风格因子）")
    print("- 其他因子对基础因子做回归")
    print("- 使用残差作为正交化后的因子")
    print("- 优点: 保留基础因子的原始含义")

    # 选择基础因子
    base_factors = ['factor_1', 'factor_2', 'factor_3']
    print(f"\n基础因子: {base_factors}")

    # 正交化
    orthogonal_schmidt = orthogonalizer.schmidt_orthogonalization(
        factor_data,
        base_factors
    )

    print("\n正交化后的相关性矩阵:")
    corr_after = orthogonal_schmidt.corr()
    print(corr_after.round(3))

    # 统计效果
    corr_values_after = corr_after.values[np.triu_indices_from(corr_after.values, k=1)]
    print(f"\n正交化效果:")
    print(f"  平均绝对相关性: {np.abs(corr_values_after).mean():.3f}")
    print(f"  最大绝对相关性: {np.abs(corr_values_after).max():.3f}")
    print(f"  高相关对数 (>0.8): {(np.abs(corr_values_after) > 0.8).sum()}")

    return orthogonal_schmidt


def pca_orthogonalization_demo(orthogonalizer, factor_data):
    """PCA正交化演示"""
    print("\n" + "=" * 60)
    print("步骤4: PCA正交化")
    print("=" * 60)

    print("\n方法说明:")
    print("- 提取主成分")
    print("- 主成分之间完全正交")
    print("- 保留最重要的成分")
    print("- 优点: 最大化方差解释，完全正交")

    # PCA正交化
    orthogonal_pca, variance_ratio = orthogonalizer.pca_orthogonalization(
        factor_data,
        variance_threshold=0.95
    )

    print(f"\n主成分数量: {orthogonal_pca.shape[1]}")
    print(f"累积方差解释: {variance_ratio.sum():.2%}")

    print("\n各主成分方差解释比例:")
    for i, ratio in enumerate(variance_ratio):
        print(f"  PC{i+1}: {ratio:.2%}")

    # 验证正交性
    corr_pca = orthogonal_pca.corr()
    print("\nPCA因子相关性矩阵 (应接近单位矩阵):")
    print(corr_pca.round(3))

    off_diagonal = corr_pca.values[~np.eye(corr_pca.shape[0], dtype=bool)]
    print(f"\n非对角线元素平均值: {np.abs(off_diagonal).mean():.6f} (应接近0)")

    return orthogonal_pca, variance_ratio


def symmetric_orthogonalization_demo(orthogonalizer, factor_data):
    """对称正交化演示"""
    print("\n" + "=" * 60)
    print("步骤5: 对称正交化")
    print("=" * 60)

    print("\n方法说明:")
    print("- 使用QR分解")
    print("- 保持因子的对称性")
    print("- 所有因子地位平等")
    print("- 优点: 不偏向任何因子")

    # 对称正交化
    orthogonal_symmetric = orthogonalizer.symmetric_orthogonalization(factor_data)

    print("\n正交化后的相关性矩阵:")
    corr_symmetric = orthogonal_symmetric.corr()
    print(corr_symmetric.round(3))

    # 验证正交性
    off_diagonal = corr_symmetric.values[~np.eye(corr_symmetric.shape[0], dtype=bool)]
    print(f"\n非对角线元素平均值: {np.abs(off_diagonal).mean():.6f}")

    return orthogonal_symmetric


def compare_methods(orthogonalizer, factor_data, orthogonal_schmidt, orthogonal_pca, orthogonal_symmetric):
    """对比不同正交化方法"""
    print("\n" + "=" * 60)
    print("步骤6: 对比不同方法")
    print("=" * 60)

    methods = {
        '原始因子': factor_data,
        'Schmidt正交化': orthogonal_schmidt,
        'PCA正交化': orthogonal_pca,
        '对称正交化': orthogonal_symmetric
    }

    comparison_results = []

    for method_name, data in methods.items():
        corr_matrix = data.corr()
        corr_values = corr_matrix.values[np.triu_indices_from(corr_matrix.values, k=1)]

        comparison_results.append({
            '方法': method_name,
            '因子数': data.shape[1],
            '平均绝对相关性': np.abs(corr_values).mean(),
            '最大绝对相关性': np.abs(corr_values).max(),
            '高相关对数(>0.8)': (np.abs(corr_values) > 0.8).sum(),
            '中相关对数(0.5-0.8)': ((np.abs(corr_values) > 0.5) & (np.abs(corr_values) <= 0.8)).sum()
        })

    comparison_df = pd.DataFrame(comparison_results)
    print("\n方法对比:")
    print(comparison_df.to_string(index=False))

    # 详细对比Schmidt方法
    print("\n\nSchmidt正交化详细效果:")
    stats = orthogonalizer.compare_before_after(factor_data, orthogonal_schmidt)
    print(f"原始因子:")
    print(f"  平均绝对相关性: {stats['original']['mean_abs_corr']:.3f}")
    print(f"  最大绝对相关性: {stats['original']['max_abs_corr']:.3f}")
    print(f"  高相关对数: {stats['original']['high_corr_count']}")
    print(f"\n正交化后:")
    print(f"  平均绝对相关性: {stats['orthogonal']['mean_abs_corr']:.3f}")
    print(f"  最大绝对相关性: {stats['orthogonal']['max_abs_corr']:.3f}")
    print(f"  高相关对数: {stats['orthogonal']['high_corr_count']}")
    print(f"\n相关性降低: {(1 - stats['orthogonal']['mean_abs_corr'] / stats['original']['mean_abs_corr']) * 100:.1f}%")


def practical_example():
    """实际应用示例"""
    print("\n" + "=" * 60)
    print("实际应用示例: 多因子模型")
    print("=" * 60)

    print("\n场景: 构建多因子选股模型")
    print("问题: 动量因子和反转因子高度相关")

    # 创建模拟的多因子数据
    np.random.seed(42)
    n_stocks = 500
    n_days = 252

    # 模拟因子数据
    momentum_5d = np.random.randn(n_stocks)
    momentum_20d = momentum_5d * 0.8 + np.random.randn(n_stocks) * 0.2  # 高度相关
    reversal_5d = -momentum_5d * 0.6 + np.random.randn(n_stocks) * 0.4  # 负相关
    value_factor = np.random.randn(n_stocks)
    quality_factor = np.random.randn(n_stocks)

    factor_data = pd.DataFrame({
        'momentum_5d': momentum_5d,
        'momentum_20d': momentum_20d,
        'reversal_5d': reversal_5d,
        'value': value_factor,
        'quality': quality_factor
    })

    print("\n原始因子相关性:")
    print(factor_data.corr().round(3))

    # 正交化
    orthogonalizer = FactorOrthogonalizer()

    # 方案1: 以价值因子为基础
    base_factors = ['value', 'quality']
    orthogonal_factors = orthogonalizer.schmidt_orthogonalization(
        factor_data,
        base_factors
    )

    print("\n正交化后相关性 (以价值和质量为基础):")
    print(orthogonal_factors.corr().round(3))

    print("\n结果解读:")
    print("- 价值和质量因子保持原样")
    print("- 动量和反转因子已去除与价值、质量的相关性")
    print("- 可以安全地在多因子模型中使用")


def main():
    """主函数"""
    print("因子正交化完整示例")
    print("=" * 60)

    # 1. 创建相关因子数据
    factor_data = create_correlated_factors()

    # 2. 创建正交化器
    orthogonalizer = FactorOrthogonalizer()

    # 3. 分析相关性
    corr_matrix, high_corr_pairs = analyze_correlation(orthogonalizer, factor_data)

    # 4. Schmidt正交化
    orthogonal_schmidt = schmidt_orthogonalization_demo(orthogonalizer, factor_data)

    # 5. PCA正交化
    orthogonal_pca, variance_ratio = pca_orthogonalization_demo(orthogonalizer, factor_data)

    # 6. 对称正交化
    orthogonal_symmetric = symmetric_orthogonalization_demo(orthogonalizer, factor_data)

    # 7. 对比方法
    compare_methods(orthogonalizer, factor_data, orthogonal_schmidt, orthogonal_pca, orthogonal_symmetric)

    # 8. 实际应用示例
    practical_example()

    print("\n" + "=" * 60)
    print("示例完成！")
    print("=" * 60)
    print("\n关键要点:")
    print("1. Schmidt正交化: 适合有明确基础因子的场景")
    print("2. PCA正交化: 适合降维和提取主要信息")
    print("3. 对称正交化: 适合所有因子地位平等的场景")
    print("4. 选择方法要根据具体业务需求")
    print("5. 正交化可以提高多因子模型的稳定性")


if __name__ == "__main__":
    main()
