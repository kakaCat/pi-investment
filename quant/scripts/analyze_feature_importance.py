#!/usr/bin/env python3
"""
分析模型中哪些因子最重要

使用方法：
python scripts/analyze_feature_importance.py
"""

import os
import sys
import pickle
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def load_model(model_path: str):
    """加载训练好的模型"""
    if not os.path.exists(model_path):
        print(f"❌ 模型文件不存在: {model_path}")
        return None

    with open(model_path, 'rb') as f:
        model = pickle.load(f)

    print(f"✅ 模型加载成功: {type(model).__name__}")
    return model


def get_feature_names(model_path: str = None):
    """获取特征名称"""
    # 尝试从训练报告中读取特征名称
    if model_path:
        model_dir = os.path.dirname(model_path)
        report_path = os.path.join(model_dir, 'training_report_latest.json')

        if os.path.exists(report_path):
            try:
                import json
                with open(report_path, 'r') as f:
                    report = json.load(f)
                    if 'feature_names' in report:
                        print(f"✅ 从训练报告读取到 {len(report['feature_names'])} 个特征名称")
                        return report['feature_names']
            except Exception as e:
                print(f"⚠️  无法读取训练报告: {e}")
        else:
            print(f"⚠️  训练报告不存在: {report_path}")
    else:
        print("⚠️  未提供 model_path")

    # 降级：返回通用特征名称
    print("⚠️  使用通用特征名称")
    return [f'feature_{i}' for i in range(38)]  # 默认38个特征


def analyze_feature_importance(model, model_path: str = None):
    """分析特征重要性"""
    feature_names = get_feature_names(model_path)

    # 获取特征重要性
    if hasattr(model, 'feature_importances_'):
        importances = model.feature_importances_
    elif hasattr(model, 'coef_'):
        importances = np.abs(model.coef_[0])
    else:
        print("❌ 模型不支持特征重要性分析")
        return None

    # 创建DataFrame
    df = pd.DataFrame({
        'Feature': feature_names,
        'Importance': importances
    })

    # 排序
    df = df.sort_values('Importance', ascending=False)

    # 计算百分比（处理全0的情况）
    total_importance = df['Importance'].sum()
    if total_importance > 0:
        df['Percentage'] = df['Importance'] / total_importance * 100
        df['Cumulative'] = df['Percentage'].cumsum()
    else:
        # 如果所有重要性都是0，平均分配
        df['Percentage'] = 100.0 / len(df)
        df['Cumulative'] = df['Percentage'].cumsum()

    return df


def plot_feature_importance(df, top_n=15):
    """绘制特征重要性图表"""
    plt.figure(figsize=(12, 8))

    # 取前N个特征
    df_top = df.head(top_n)

    # 绘制条形图
    plt.barh(range(len(df_top)), df_top['Importance'])
    plt.yticks(range(len(df_top)), df_top['Feature'])
    plt.xlabel('Importance Score')
    plt.title(f'Top {top_n} Most Important Features')
    plt.gca().invert_yaxis()

    # 添加百分比标签
    for i, (idx, row) in enumerate(df_top.iterrows()):
        plt.text(row['Importance'], i, f" {row['Percentage']:.1f}%",
                va='center', fontsize=9)

    plt.tight_layout()

    # 保存图表
    output_dir = Path(__file__).parent.parent / '.pi-invest'
    output_path = output_dir / 'feature_importance.png'
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"\n📊 图表已保存: {output_path}")

    plt.close()


def main():
    print("=" * 60)
    print("特征重要性分析")
    print("=" * 60)

    # 模型路径
    model_path = Path(__file__).parent.parent / 'quantsys' / 'ml' / 'models' / 'xgboost_model.pkl'

    # 加载模型
    model = load_model(str(model_path))
    if model is None:
        print("\n💡 请先训练模型:")
        print("   cd quant")
        print("   python -m quantsys.ml.training.trainer")
        return

    # 分析特征重要性
    print("\n分析特征重要性...")
    df = analyze_feature_importance(model)

    if df is None:
        return

    # 显示结果
    print("\n" + "=" * 60)
    print("📊 特征重要性排名")
    print("=" * 60)
    print(df.to_string(index=False))

    # 显示Top 10
    print("\n" + "=" * 60)
    print("🏆 Top 10 最重要的因子")
    print("=" * 60)
    for i, (idx, row) in enumerate(df.head(10).iterrows(), 1):
        print(f"{i:2d}. {row['Feature']:20s} | "
              f"重要性: {row['Importance']:.4f} | "
              f"占比: {row['Percentage']:5.2f}% | "
              f"累计: {row['Cumulative']:5.2f}%")

    # 80/20法则分析
    top_20_percent = df[df['Cumulative'] <= 80]
    print(f"\n💡 80/20法则: 前 {len(top_20_percent)} 个因子贡献了 80% 的预测能力")

    # 绘制图表
    plot_feature_importance(df, top_n=15)

    # 保存到文件
    output_dir = Path(__file__).parent.parent / '.pi-invest'
    output_path = output_dir / 'feature_importance.csv'
    df.to_csv(output_path, index=False)
    print(f"📄 详细数据已保存: {output_path}")


if __name__ == '__main__':
    main()
