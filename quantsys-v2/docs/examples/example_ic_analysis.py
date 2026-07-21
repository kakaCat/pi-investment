"""
IC分析完整示例

演示如何使用ICAnalyzer进行因子IC分析：
1. 准备因子和收益数据
2. 计算IC时间序列
3. 计算IC统计指标
4. 因子质量评分
5. 可视化IC曲线
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

import numpy as np
import pandas as pd
from datetime import datetime
from domain.quantlib.factor_analysis.ic_analyzer import ICAnalyzer


def prepare_sample_data():
    """准备示例数据"""
    print("=" * 60)
    print("步骤1: 准备数据")
    print("=" * 60)

    # 生成日期和股票列表
    dates = pd.date_range('2023-01-01', '2023-12-31', freq='D')
    symbols = [f'stock_{i:03d}' for i in range(100)]

    print(f"日期范围: {dates[0]} 到 {dates[-1]}")
    print(f"股票数量: {len(symbols)}")
    print(f"总样本数: {len(dates)} × {len(symbols)} = {len(dates) * len(symbols)}")

    # 生成因子数据
    # 模拟一个有预测能力的因子（与未来收益正相关）
    np.random.seed(42)

    # 基础因子值
    base_factor = np.random.randn(len(dates), len(symbols))

    # 添加一些预测能力（与未来收益相关）
    future_signal = np.random.randn(len(dates), len(symbols))
    factor_data = pd.DataFrame(
        base_factor + 0.3 * future_signal,  # 添加预测信号
        index=dates,
        columns=symbols
    )

    # 生成收益数据（部分受因子影响）
    return_data = pd.DataFrame(
        0.3 * future_signal + np.random.randn(len(dates), len(symbols)) * 0.02,
        index=dates,
        columns=symbols
    )

    print(f"\n因子数据统计:")
    print(f"  均值: {factor_data.mean().mean():.4f}")
    print(f"  标准差: {factor_data.std().mean():.4f}")
    print(f"\n收益数据统计:")
    print(f"  均值: {return_data.mean().mean():.4f}")
    print(f"  标准差: {return_data.std().mean():.4f}")

    return factor_data, return_data


def calculate_ic_series(analyzer, factor_data, return_data):
    """计算IC时间序列"""
    print("\n" + "=" * 60)
    print("步骤2: 计算IC时间序列")
    print("=" * 60)

    # 计算不同预测期的IC
    periods = [1, 5, 10, 20]
    print(f"预测期: {periods} 天")

    ic_series = analyzer.calculate_ic_series(
        factor_data,
        return_data,
        periods=periods
    )

    print(f"\nIC时间序列形状: {ic_series.shape}")
    print(f"\n最近5天的IC值:")
    print(ic_series.tail())

    return ic_series


def calculate_statistics(analyzer, ic_series):
    """计算IC统计指标"""
    print("\n" + "=" * 60)
    print("步骤3: 计算IC统计指标")
    print("=" * 60)

    ic_stats = analyzer.calculate_ic_statistics(ic_series)

    print("\nIC统计指标:")
    print(ic_stats.to_string())

    # 解读关键指标
    print("\n指标解读:")
    for period in ic_stats.index:
        stats = ic_stats.loc[period]
        print(f"\n{period}:")
        print(f"  IC均值: {stats['IC_mean']:.4f} (越大越好，>0.03为良好)")
        print(f"  IC标准差: {stats['IC_std']:.4f} (越小越稳定)")
        print(f"  IC_IR: {stats['IC_IR']:.4f} (>1.0为良好)")
        print(f"  IC正比率: {stats['IC_positive_rate']:.2%} (>55%为良好)")
        print(f"  年化ICIR: {stats['ICIR_annual']:.4f} (>5.0为优秀)")

    return ic_stats


def evaluate_factor_quality(analyzer, ic_stats):
    """评估因子质量"""
    print("\n" + "=" * 60)
    print("步骤4: 因子质量评分")
    print("=" * 60)

    quality_scores = analyzer.get_factor_quality_score(ic_stats)

    print("\n因子质量评分:")
    for period, scores in quality_scores.items():
        print(f"\n{period}:")
        print(f"  IC均值评分: {scores['ic_mean_score']}/10")
        print(f"  IC_IR评分: {scores['ic_ir_score']}/10")
        print(f"  IC正比率评分: {scores['ic_pos_score']}/10")
        print(f"  综合评分: {scores['total_score']:.2f}/10")
        print(f"  质量等级: {scores['quality']}")

    # 推荐最佳预测期
    best_period = max(quality_scores.items(), key=lambda x: x[1]['total_score'])
    print(f"\n推荐预测期: {best_period[0]} (评分: {best_period[1]['total_score']:.2f})")

    return quality_scores


def visualize_ic(analyzer, ic_series):
    """可视化IC曲线"""
    print("\n" + "=" * 60)
    print("步骤5: 可视化IC曲线")
    print("=" * 60)

    try:
        import matplotlib
        matplotlib.use('Agg')  # 非交互式后端

        save_path = '/tmp/ic_analysis.png'
        analyzer.plot_ic_series(ic_series, save_path=save_path)
        print(f"\nIC曲线已保存到: {save_path}")
        print("图表包含:")
        print("  - IC时间序列图")
        print("  - IC累积值图")
    except Exception as e:
        print(f"\n可视化失败: {e}")
        print("提示: 需要安装matplotlib库")


def compare_multiple_factors():
    """对比多个因子的IC表现"""
    print("\n" + "=" * 60)
    print("高级示例: 对比多个因子")
    print("=" * 60)

    dates = pd.date_range('2023-01-01', '2023-12-31', freq='D')
    symbols = [f'stock_{i:03d}' for i in range(100)]

    # 生成收益数据
    np.random.seed(42)
    future_signal = np.random.randn(len(dates), len(symbols))
    return_data = pd.DataFrame(
        0.3 * future_signal + np.random.randn(len(dates), len(symbols)) * 0.02,
        index=dates,
        columns=symbols
    )

    # 创建3个不同质量的因子
    factors = {
        '优秀因子': pd.DataFrame(
            np.random.randn(len(dates), len(symbols)) + 0.5 * future_signal,
            index=dates, columns=symbols
        ),
        '良好因子': pd.DataFrame(
            np.random.randn(len(dates), len(symbols)) + 0.3 * future_signal,
            index=dates, columns=symbols
        ),
        '一般因子': pd.DataFrame(
            np.random.randn(len(dates), len(symbols)) + 0.1 * future_signal,
            index=dates, columns=symbols
        )
    }

    # 对比分析
    results = []
    for factor_name, factor_data in factors.items():
        analyzer = ICAnalyzer()
        ic_series = analyzer.calculate_ic_series(factor_data, return_data, periods=[5])
        ic_stats = analyzer.calculate_ic_statistics(ic_series)

        results.append({
            '因子名称': factor_name,
            'IC均值': ic_stats.loc['IC_5D', 'IC_mean'],
            'IC_IR': ic_stats.loc['IC_5D', 'IC_IR'],
            'IC正比率': ic_stats.loc['IC_5D', 'IC_positive_rate'],
            '年化ICIR': ic_stats.loc['IC_5D', 'ICIR_annual']
        })

    comparison_df = pd.DataFrame(results)
    print("\n因子对比结果:")
    print(comparison_df.to_string(index=False))

    # 排名
    comparison_df['综合排名'] = comparison_df['年化ICIR'].rank(ascending=False)
    print("\n按年化ICIR排名:")
    print(comparison_df.sort_values('年化ICIR', ascending=False).to_string(index=False))


def main():
    """主函数"""
    print("IC分析完整示例")
    print("=" * 60)

    # 1. 准备数据
    factor_data, return_data = prepare_sample_data()

    # 2. 创建分析器
    analyzer = ICAnalyzer()

    # 3. 计算IC时间序列
    ic_series = calculate_ic_series(analyzer, factor_data, return_data)

    # 4. 计算统计指标
    ic_stats = calculate_statistics(analyzer, ic_series)

    # 5. 评估因子质量
    quality_scores = evaluate_factor_quality(analyzer, ic_stats)

    # 6. 可视化
    visualize_ic(analyzer, ic_series)

    # 7. 高级示例：对比多个因子
    compare_multiple_factors()

    print("\n" + "=" * 60)
    print("示例完成！")
    print("=" * 60)
    print("\n关键要点:")
    print("1. IC均值反映因子的预测能力")
    print("2. IC_IR反映因子的稳定性")
    print("3. IC正比率反映因子的胜率")
    print("4. 年化ICIR是综合评价指标")
    print("5. 不同预测期适合不同的交易频率")


if __name__ == "__main__":
    main()
