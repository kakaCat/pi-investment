"""
量化系统可视化模块

生成各种图表：
1. 模型准确率趋势图
2. 回测权益曲线图
3. 策略胜率对比图
4. 特征重要性柱状图
"""
import os
import json
import pickle
from datetime import datetime, timedelta
from typing import List, Dict, Optional


def plot_model_accuracy_trend(days: int = 90, output_path: str = '.pi-invest/quant/charts/accuracy_trend.png') -> dict:
    """
    绘制模型准确率趋势图

    Args:
        days: 回溯天数
        output_path: 输出图片路径

    Returns:
        包含图片路径和统计信息的字典
    """
    try:
        import matplotlib
        matplotlib.use('Agg')  # 非交互式后端
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates
        from matplotlib import rcParams

        # 设置中文字体
        rcParams['font.sans-serif'] = ['Arial Unicode MS', 'SimHei', 'DejaVu Sans']
        rcParams['axes.unicode_minus'] = False
    except ImportError:
        return {
            "error": "matplotlib not installed. Run: pip install matplotlib"
        }

    # 加载训练历史（模拟数据，实际应从日志文件读取）
    # TODO: 实现训练历史记录功能
    training_history = _load_training_history(days)

    if not training_history:
        return {
            "error": "No training history found",
            "suggestion": "Train the model first using train_signal_model"
        }

    # 准备数据
    dates = [datetime.strptime(record['date'], '%Y-%m-%d') for record in training_history]
    accuracies = [record['accuracy'] for record in training_history]

    # 创建图表
    fig, ax = plt.subplots(figsize=(12, 6))

    # 绘制准确率曲线
    ax.plot(dates, accuracies, marker='o', linewidth=2, markersize=6, label='模型准确率')

    # 添加基准线
    ax.axhline(y=0.5, color='r', linestyle='--', alpha=0.5, label='随机基准 (50%)')
    ax.axhline(y=0.6, color='g', linestyle='--', alpha=0.5, label='良好水平 (60%)')

    # 设置标题和标签
    ax.set_title('量化模型准确率趋势', fontsize=16, fontweight='bold', pad=20)
    ax.set_xlabel('日期', fontsize=12)
    ax.set_ylabel('准确率 (%)', fontsize=12)

    # 格式化Y轴为百分比
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f'{y*100:.0f}%'))

    # 格式化X轴日期
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
    ax.xaxis.set_major_locator(mdates.DayLocator(interval=max(1, len(dates)//10)))
    plt.xticks(rotation=45, ha='right')

    # 添加网格
    ax.grid(True, alpha=0.3, linestyle='--')

    # 添加图例
    ax.legend(loc='best', fontsize=10)

    # 调整布局
    plt.tight_layout()

    # 保存图片
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()

    # 统计信息
    latest_accuracy = accuracies[-1] if accuracies else 0
    avg_accuracy = sum(accuracies) / len(accuracies) if accuracies else 0
    max_accuracy = max(accuracies) if accuracies else 0

    return {
        "success": True,
        "chart_path": output_path,
        "stats": {
            "latest_accuracy": round(latest_accuracy * 100, 2),
            "avg_accuracy": round(avg_accuracy * 100, 2),
            "max_accuracy": round(max_accuracy * 100, 2),
            "training_count": len(training_history)
        }
    }


def plot_equity_curve(backtest_result: dict, output_path: str = '.pi-invest/quant/charts/equity_curve.png') -> dict:
    """
    绘制回测权益曲线图

    Args:
        backtest_result: 回测结果数据
        output_path: 输出图片路径

    Returns:
        包含图片路径的字典
    """
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates
        from matplotlib import rcParams

        rcParams['font.sans-serif'] = ['Arial Unicode MS', 'SimHei', 'DejaVu Sans']
        rcParams['axes.unicode_minus'] = False
    except ImportError:
        return {"error": "matplotlib not installed"}

    if 'daily_equity' not in backtest_result or not backtest_result['daily_equity']:
        return {"error": "No daily equity data in backtest result"}

    # 准备数据
    daily_equity = backtest_result['daily_equity']
    dates = [datetime.strptime(d['date'], '%Y-%m-%d') for d in daily_equity]
    equity = [d['total_equity'] for d in daily_equity]
    drawdown = [d['drawdown'] for d in daily_equity]

    # 创建双Y轴图表
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10), sharex=True)

    # 上图：权益曲线
    ax1.plot(dates, equity, linewidth=2, color='#2E86AB', label='账户权益')
    ax1.fill_between(dates, equity, alpha=0.3, color='#2E86AB')

    # 添加买卖点标记
    if 'trades' in backtest_result:
        buy_dates = []
        buy_prices = []
        sell_dates = []
        sell_prices = []

        for trade in backtest_result['trades']:
            entry_date = datetime.strptime(trade['entry_date'], '%Y-%m-%d')
            exit_date = datetime.strptime(trade['exit_date'], '%Y-%m-%d')

            # 找到对应日期的权益值
            entry_equity = next((d['total_equity'] for d in daily_equity if d['date'] == trade['entry_date']), None)
            exit_equity = next((d['total_equity'] for d in daily_equity if d['date'] == trade['exit_date']), None)

            if entry_equity:
                buy_dates.append(entry_date)
                buy_prices.append(entry_equity)
            if exit_equity:
                sell_dates.append(exit_date)
                sell_prices.append(exit_equity)

        if buy_dates:
            ax1.scatter(buy_dates, buy_prices, color='red', marker='^', s=100, zorder=5, label='买入')
        if sell_dates:
            ax1.scatter(sell_dates, sell_prices, color='green', marker='v', s=100, zorder=5, label='卖出')

    ax1.set_title('回测权益曲线', fontsize=16, fontweight='bold', pad=20)
    ax1.set_ylabel('账户权益 (元)', fontsize=12)
    ax1.grid(True, alpha=0.3, linestyle='--')
    ax1.legend(loc='best', fontsize=10)

    # 下图：回撤曲线
    ax2.fill_between(dates, drawdown, alpha=0.5, color='#A23B72', label='回撤')
    ax2.plot(dates, drawdown, linewidth=1.5, color='#A23B72')
    ax2.set_title('回撤曲线', fontsize=14, pad=15)
    ax2.set_xlabel('日期', fontsize=12)
    ax2.set_ylabel('回撤 (%)', fontsize=12)
    ax2.yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f'{y:.1f}%'))
    ax2.grid(True, alpha=0.3, linestyle='--')
    ax2.legend(loc='best', fontsize=10)

    # 格式化X轴
    ax2.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
    ax2.xaxis.set_major_locator(mdates.DayLocator(interval=max(1, len(dates)//15)))
    plt.xticks(rotation=45, ha='right')

    # 调整布局
    plt.tight_layout()

    # 保存图片
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()

    return {
        "success": True,
        "chart_path": output_path,
        "stats": {
            "initial_capital": backtest_result.get('initial_capital', 0),
            "final_capital": backtest_result.get('final_capital', 0),
            "total_return": backtest_result.get('total_return', 0),
            "max_drawdown": backtest_result.get('max_drawdown', 0)
        }
    }


def plot_strategy_comparison(strategies_performance: List[dict], output_path: str = '.pi-invest/quant/charts/strategy_comparison.png') -> dict:
    """
    绘制策略胜率对比图

    Args:
        strategies_performance: 策略性能列表
        output_path: 输出图片路径

    Returns:
        包含图片路径的字典
    """
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        from matplotlib import rcParams

        rcParams['font.sans-serif'] = ['Arial Unicode MS', 'SimHei', 'DejaVu Sans']
        rcParams['axes.unicode_minus'] = False
    except ImportError:
        return {"error": "matplotlib not installed"}

    if not strategies_performance:
        return {"error": "No strategy performance data provided"}

    # 准备数据
    strategy_names = [s['strategy_name'][:15] for s in strategies_performance]  # 截断长名称
    win_rates = [s['win_rate'] for s in strategies_performance]
    total_signals = [s['total_signals'] for s in strategies_performance]
    avg_profits = [s['avg_profit_pct'] for s in strategies_performance]

    # 创建图表
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))

    # 左图：胜率对比
    colors = ['#06A77D' if wr >= 60 else '#F77E21' if wr >= 50 else '#D62246' for wr in win_rates]
    bars1 = ax1.barh(strategy_names, win_rates, color=colors, alpha=0.8)

    # 添加数值标签
    for i, (bar, wr, signals) in enumerate(zip(bars1, win_rates, total_signals)):
        ax1.text(wr + 1, i, f'{wr:.1f}% ({signals})', va='center', fontsize=9)

    ax1.set_xlabel('胜率 (%)', fontsize=12)
    ax1.set_title('策略胜率对比', fontsize=14, fontweight='bold', pad=15)
    ax1.axvline(x=50, color='gray', linestyle='--', alpha=0.5, label='50%基准')
    ax1.axvline(x=60, color='green', linestyle='--', alpha=0.5, label='60%良好')
    ax1.legend(loc='lower right', fontsize=9)
    ax1.grid(True, alpha=0.3, axis='x')

    # 右图：平均收益对比
    colors2 = ['#06A77D' if ap > 0 else '#D62246' for ap in avg_profits]
    bars2 = ax2.barh(strategy_names, avg_profits, color=colors2, alpha=0.8)

    # 添加数值标签
    for i, (bar, ap) in enumerate(zip(bars2, avg_profits)):
        ax2.text(ap + 0.1 if ap > 0 else ap - 0.1, i, f'{ap:.2f}%',
                va='center', ha='left' if ap > 0 else 'right', fontsize=9)

    ax2.set_xlabel('平均收益率 (%)', fontsize=12)
    ax2.set_title('策略平均收益对比', fontsize=14, fontweight='bold', pad=15)
    ax2.axvline(x=0, color='black', linestyle='-', linewidth=1)
    ax2.grid(True, alpha=0.3, axis='x')

    # 调整布局
    plt.tight_layout()

    # 保存图片
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()

    return {
        "success": True,
        "chart_path": output_path,
        "stats": {
            "best_strategy": max(strategies_performance, key=lambda s: s['win_rate'])['strategy_name'],
            "avg_win_rate": round(sum(win_rates) / len(win_rates), 2),
            "total_strategies": len(strategies_performance)
        }
    }


def plot_feature_importance(model_path: str = '.pi-invest/quant/models/signal_confidence.pkl',
                            output_path: str = '.pi-invest/quant/charts/feature_importance.png') -> dict:
    """
    绘制特征重要性柱状图

    Args:
        model_path: 模型文件路径
        output_path: 输出图片路径

    Returns:
        包含图片路径的字典
    """
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        from matplotlib import rcParams

        rcParams['font.sans-serif'] = ['Arial Unicode MS', 'SimHei', 'DejaVu Sans']
        rcParams['axes.unicode_minus'] = False
    except ImportError:
        return {"error": "matplotlib not installed"}

    # 加载模型
    if not os.path.exists(model_path):
        return {"error": f"Model not found: {model_path}"}

    try:
        with open(model_path, 'rb') as f:
            model = pickle.load(f)
    except Exception as e:
        return {"error": f"Failed to load model: {str(e)}"}

    # 获取特征重要性
    if not hasattr(model, 'feature_importances_'):
        return {"error": "Model does not have feature_importances_ attribute"}

    importances = model.feature_importances_

    # 特征名称（与feature_extractor.py中的顺序对应）
    feature_names = [
        'RSI', 'MACD', 'MACD信号', 'MACD柱',
        'MA5', 'MA10', 'MA20', 'MA60',
        '布林上轨', '布林中轨', '布林下轨',
        '成交量', '成交量MA5', '成交量MA10',
        '价格动量', '成交量动量',
        '置信度'
    ]

    # 确保长度匹配
    if len(importances) != len(feature_names):
        feature_names = [f'特征{i+1}' for i in range(len(importances))]

    # 排序
    indices = sorted(range(len(importances)), key=lambda i: importances[i], reverse=True)
    sorted_importances = [importances[i] for i in indices]
    sorted_names = [feature_names[i] for i in indices]

    # 只显示前15个最重要的特征
    top_n = min(15, len(sorted_importances))
    sorted_importances = sorted_importances[:top_n]
    sorted_names = sorted_names[:top_n]

    # 创建图表
    fig, ax = plt.subplots(figsize=(12, 8))

    # 绘制水平柱状图
    colors = plt.cm.viridis([i/top_n for i in range(top_n)])
    bars = ax.barh(range(top_n), sorted_importances, color=colors, alpha=0.8)

    # 添加数值标签
    for i, (bar, imp) in enumerate(zip(bars, sorted_importances)):
        ax.text(imp + 0.005, i, f'{imp*100:.2f}%', va='center', fontsize=9)

    # 设置标签
    ax.set_yticks(range(top_n))
    ax.set_yticklabels(sorted_names)
    ax.set_xlabel('重要性', fontsize=12)
    ax.set_title('特征重要性排名', fontsize=16, fontweight='bold', pad=20)
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f'{x*100:.0f}%'))

    # 添加网格
    ax.grid(True, alpha=0.3, axis='x')

    # 调整布局
    plt.tight_layout()

    # 保存图片
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()

    return {
        "success": True,
        "chart_path": output_path,
        "stats": {
            "top_feature": sorted_names[0],
            "top_importance": float(round(sorted_importances[0] * 100, 2)),
            "total_features": int(len(importances))
        }
    }


def _load_training_history(days: int) -> List[dict]:
    """
    加载训练历史记录（模拟数据）

    实际应该从日志文件或数据库读取
    """
    # TODO: 实现真实的训练历史记录
    # 这里生成模拟数据用于演示
    import random

    history = []
    base_date = datetime.now() - timedelta(days=days)

    for i in range(min(days // 7, 12)):  # 每周训练一次
        date = base_date + timedelta(days=i*7)
        accuracy = 0.55 + random.random() * 0.15  # 55%-70%之间

        history.append({
            'date': date.strftime('%Y-%m-%d'),
            'accuracy': accuracy,
            'samples': random.randint(80, 200)
        })

    return history
