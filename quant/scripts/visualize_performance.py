#!/usr/bin/env python3
"""
每周绩效可视化脚本（可选增强功能）

功能：
1. 读取绩效报告 JSON
2. 生成可视化图表
3. 保存为 PNG 图片

依赖：
pip install matplotlib pandas

使用：
python3 scripts/visualize_performance.py
python3 scripts/visualize_performance.py --year 2026 --week 21
"""

import os
import sys
import json
import argparse
from datetime import datetime
from typing import Dict, List

try:
    import matplotlib
    matplotlib.use('Agg')  # 非交互式后端
    import matplotlib.pyplot as plt
    import matplotlib.font_manager as fm
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    print("警告: matplotlib 未安装，无法生成图表")
    print("安装方法: pip install matplotlib")


def setup_chinese_font():
    """设置中文字体"""
    try:
        # macOS 系统字体
        font_paths = [
            '/System/Library/Fonts/PingFang.ttc',
            '/System/Library/Fonts/STHeiti Light.ttc',
            '/Library/Fonts/Arial Unicode.ttf',
        ]

        for font_path in font_paths:
            if os.path.exists(font_path):
                plt.rcParams['font.sans-serif'] = [fm.FontProperties(fname=font_path).get_name()]
                plt.rcParams['axes.unicode_minus'] = False
                return True

        # 如果没有找到中文字体，使用默认
        print("警告: 未找到中文字体，图表中文可能显示为方框")
        return False
    except Exception as e:
        print(f"设置字体失败: {e}")
        return False


def plot_signal_distribution(data: Dict, output_path: str):
    """绘制信号分布图"""
    quality = data['signal_quality']

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

    # 1. 买入/卖出分布
    labels = ['买入', '卖出']
    sizes = [quality['buy_count'], quality['sell_count']]
    colors = ['#66c2a5', '#fc8d62']

    ax1.pie(sizes, labels=labels, colors=colors, autopct='%1.1f%%', startangle=90)
    ax1.set_title(f'信号类型分布 (总计: {quality["total"]})', fontsize=14, pad=20)

    # 2. 信心度分布
    conf_dist = quality['confidence_distribution']
    ranges = list(conf_dist.keys())
    counts = list(conf_dist.values())

    ax2.bar(ranges, counts, color='#8da0cb', alpha=0.8)
    ax2.set_xlabel('信心度区间', fontsize=12)
    ax2.set_ylabel('信号数量', fontsize=12)
    ax2.set_title('信心度分布', fontsize=14, pad=20)
    ax2.grid(axis='y', alpha=0.3)

    # 在柱子上显示数值
    for i, count in enumerate(counts):
        if count > 0:
            ax2.text(i, count, str(count), ha='center', va='bottom')

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()

    print(f"✓ 信号分布图已保存: {output_path}")


def plot_strategy_performance(data: Dict, output_path: str):
    """绘制策略表现图"""
    strategy_perf = data['strategy_performance']

    if not strategy_perf:
        print("跳过策略表现图（无数据）")
        return

    strategies = list(strategy_perf.keys())
    totals = [strategy_perf[s]['total'] for s in strategies]
    confidences = [strategy_perf[s]['avg_confidence'] for s in strategies]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

    # 1. 策略信号数量
    bars1 = ax1.barh(strategies, totals, color='#66c2a5', alpha=0.8)
    ax1.set_xlabel('信号数量', fontsize=12)
    ax1.set_title('各策略信号数量', fontsize=14, pad=20)
    ax1.grid(axis='x', alpha=0.3)

    # 在柱子上显示数值
    for i, bar in enumerate(bars1):
        width = bar.get_width()
        ax1.text(width, bar.get_y() + bar.get_height()/2,
                f'{int(width)}', ha='left', va='center', fontsize=10)

    # 2. 策略平均信心度
    colors = ['#e74c3c' if c < 0.4 else '#f39c12' if c < 0.6 else '#27ae60'
              for c in confidences]
    bars2 = ax2.barh(strategies, confidences, color=colors, alpha=0.8)
    ax2.set_xlabel('平均信心度', fontsize=12)
    ax2.set_title('各策略平均信心度', fontsize=14, pad=20)
    ax2.set_xlim(0, 1.0)
    ax2.grid(axis='x', alpha=0.3)

    # 添加参考线
    ax2.axvline(x=0.6, color='orange', linestyle='--', alpha=0.5, label='良好线(0.6)')
    ax2.axvline(x=0.8, color='green', linestyle='--', alpha=0.5, label='优秀线(0.8)')
    ax2.legend(loc='lower right', fontsize=9)

    # 在柱子上显示数值
    for i, bar in enumerate(bars2):
        width = bar.get_width()
        ax2.text(width, bar.get_y() + bar.get_height()/2,
                f'{width:.2f}', ha='left', va='center', fontsize=10)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()

    print(f"✓ 策略表现图已保存: {output_path}")


def plot_factor_usage(data: Dict, output_path: str):
    """绘制因子使用图"""
    factor_usage = data['factor_usage']
    most_used = factor_usage.get('most_used', {})

    if not most_used:
        print("跳过因子使用图（无数据）")
        return

    # 取前10个
    factors = list(most_used.keys())[:10]
    counts = list(most_used.values())[:10]

    fig, ax = plt.subplots(figsize=(10, 6))

    bars = ax.barh(factors, counts, color='#8da0cb', alpha=0.8)
    ax.set_xlabel('使用次数', fontsize=12)
    ax.set_title('因子使用频率 Top 10', fontsize=14, pad=20)
    ax.grid(axis='x', alpha=0.3)

    # 在柱子上显示数值
    for i, bar in enumerate(bars):
        width = bar.get_width()
        ax.text(width, bar.get_y() + bar.get_height()/2,
               f'{int(width)}', ha='left', va='center', fontsize=10)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()

    print(f"✓ 因子使用图已保存: {output_path}")


def plot_weekly_trend(reports_dir: str, output_path: str, weeks: int = 8):
    """绘制多周趋势图"""
    # 读取最近N周的报告
    report_files = []
    for filename in sorted(os.listdir(reports_dir)):
        if filename.startswith('performance_report_') and filename.endswith('.json'):
            report_files.append(os.path.join(reports_dir, filename))

    if len(report_files) < 2:
        print("跳过趋势图（历史数据不足）")
        return

    # 只取最近N周
    report_files = report_files[-weeks:]

    # 收集数据
    week_labels = []
    signal_counts = []
    avg_confidences = []
    buy_counts = []
    sell_counts = []

    for filepath in report_files:
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                week_labels.append(f"W{data['week']}")
                quality = data['signal_quality']
                signal_counts.append(quality['total'])
                avg_confidences.append(quality['avg_confidence'])
                buy_counts.append(quality['buy_count'])
                sell_counts.append(quality['sell_count'])
        except Exception as e:
            print(f"读取 {filepath} 失败: {e}")
            continue

    if not week_labels:
        print("跳过趋势图（无有效数据）")
        return

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))

    # 1. 信号数量趋势
    ax1.plot(week_labels, signal_counts, marker='o', linewidth=2,
            color='#3498db', label='总信号')
    ax1.plot(week_labels, buy_counts, marker='s', linewidth=1.5,
            color='#2ecc71', label='买入', alpha=0.7)
    ax1.plot(week_labels, sell_counts, marker='^', linewidth=1.5,
            color='#e74c3c', label='卖出', alpha=0.7)
    ax1.set_ylabel('信号数量', fontsize=12)
    ax1.set_title('信号数量趋势', fontsize=14, pad=20)
    ax1.legend(loc='best')
    ax1.grid(alpha=0.3)

    # 2. 平均信心度趋势
    ax2.plot(week_labels, avg_confidences, marker='o', linewidth=2,
            color='#9b59b6')
    ax2.axhline(y=0.6, color='orange', linestyle='--', alpha=0.5, label='良好线')
    ax2.axhline(y=0.8, color='green', linestyle='--', alpha=0.5, label='优秀线')
    ax2.set_xlabel('周次', fontsize=12)
    ax2.set_ylabel('平均信心度', fontsize=12)
    ax2.set_title('平均信心度趋势', fontsize=14, pad=20)
    ax2.set_ylim(0, 1.0)
    ax2.legend(loc='best')
    ax2.grid(alpha=0.3)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()

    print(f"✓ 趋势图已保存: {output_path}")


def generate_all_charts(year: int, week: int, quant_dir: str):
    """生成所有图表"""
    reports_dir = os.path.join(quant_dir, '.pi-invest', 'performance_reports')

    # 读取报告
    json_filename = f"performance_report_{year}-W{week:02d}.json"
    json_path = os.path.join(reports_dir, json_filename)

    if not os.path.exists(json_path):
        print(f"错误: 报告文件不存在: {json_path}")
        print("请先运行 weekly_performance.py 生成报告")
        return False

    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    print(f"\n正在为 {year}年第{week}周 生成可视化图表...")

    # 创建图表目录
    charts_dir = os.path.join(reports_dir, 'charts')
    os.makedirs(charts_dir, exist_ok=True)

    # 设置中文字体
    setup_chinese_font()

    # 生成各类图表
    prefix = f"{year}-W{week:02d}"

    try:
        plot_signal_distribution(data, os.path.join(charts_dir, f'{prefix}_signal_dist.png'))
        plot_strategy_performance(data, os.path.join(charts_dir, f'{prefix}_strategy_perf.png'))
        plot_factor_usage(data, os.path.join(charts_dir, f'{prefix}_factor_usage.png'))
        plot_weekly_trend(reports_dir, os.path.join(charts_dir, f'{prefix}_trend.png'))

        print(f"\n✅ 所有图表已生成到: {charts_dir}")
        return True

    except Exception as e:
        print(f"\n❌ 生成图表失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主函数"""
    if not MATPLOTLIB_AVAILABLE:
        print("\n错误: 缺少必要的依赖库")
        print("请安装: pip install matplotlib")
        sys.exit(1)

    parser = argparse.ArgumentParser(description='每周绩效可视化')
    parser.add_argument('--year', type=int, help='年份（默认：本年）')
    parser.add_argument('--week', type=int, help='周数（默认：本周）')
    parser.add_argument('--quant-dir', type=str,
                       default=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       help='Quant 项目目录')

    args = parser.parse_args()

    # 默认使用本周
    if args.year is None or args.week is None:
        now = datetime.now()
        year, week = now.isocalendar()[0], now.isocalendar()[1]
    else:
        year, week = args.year, args.week

    print("=" * 60)
    print("每周绩效可视化")
    print(f"分析周期: {year}年第{week}周")
    print("=" * 60)

    success = generate_all_charts(year, week, args.quant_dir)

    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
