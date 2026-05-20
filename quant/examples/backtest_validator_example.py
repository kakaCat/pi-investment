"""
回测基线验证器示例

演示如何使用回测基线验证器确保策略经过充分的历史数据验证。
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from quantsys.backtest import (
    BacktestValidator,
    ValidatorConfig,
    IssueSeverity
)
import pandas as pd
import numpy as np
from datetime import datetime, timedelta


def example_basic_validation():
    """示例1: 基础验证"""
    print("=" * 60)
    print("示例 1: 基础验证")
    print("=" * 60)

    # 创建验证器
    validator = BacktestValidator()

    # 创建6年的回测数据
    start_date = datetime(2018, 1, 1)
    dates = pd.date_range(start=start_date, periods=252*6, freq='D')

    # 模拟权益曲线（稳定增长）
    equity = pd.Series(
        np.linspace(100000, 180000, len(dates)),
        index=dates
    )

    # 模拟交易记录
    trades = []
    for i in range(150):
        trade_date = start_date + timedelta(days=i*15)
        trades.append({
            'date': trade_date,
            'symbol': '600036.SH',
            'pnl': np.random.normal(500, 200),
            'return_pct': np.random.normal(0.02, 0.01)
        })

    # 执行验证
    result = validator.validate(equity, trades)

    print(f"\n验证结果: {'✅ 通过' if result.passed else '❌ 未通过'}")
    print(f"\n摘要:")
    for key, value in result.summary.items():
        print(f"  {key}: {value}")

    print(f"\n问题列表:")
    for issue in result.issues:
        icon = "❌" if issue.severity == IssueSeverity.ERROR else "⚠️" if issue.severity == IssueSeverity.WARNING else "ℹ️"
        print(f"  {icon} [{issue.severity.value.upper()}] {issue.message}")


def example_insufficient_history():
    """示例2: 历史数据不足"""
    print("\n" + "=" * 60)
    print("示例 2: 历史数据不足")
    print("=" * 60)

    validator = BacktestValidator()

    # 只有3年的数据（不足5年）
    start_date = datetime(2021, 1, 1)
    dates = pd.date_range(start=start_date, periods=252*3, freq='D')
    equity = pd.Series(np.linspace(100000, 130000, len(dates)), index=dates)

    trades = [{'date': datetime.now(), 'pnl': 100} for _ in range(80)]

    result = validator.validate(equity, trades)

    print(f"\n验证结果: {'✅ 通过' if result.passed else '❌ 未通过'}")
    print(f"\n错误:")
    for error in result.get_errors():
        print(f"  ❌ {error.message}")
        if error.details:
            for key, value in error.details.items():
                print(f"     - {key}: {value}")


def example_market_regime_coverage():
    """示例3: 市场周期覆盖检查"""
    print("\n" + "=" * 60)
    print("示例 3: 市场周期覆盖检查")
    print("=" * 60)

    validator = BacktestValidator()

    # 创建包含不同市场状态的权益曲线
    dates = pd.date_range(start='2018-01-01', periods=252*6, freq='D')

    # 前2年：牛市（上涨30%）
    bull_period = np.linspace(100000, 130000, 252*2)
    # 中间2年：熊市（下跌20%）
    bear_period = np.linspace(130000, 104000, 252*2)
    # 后2年：震荡市（小幅波动）
    sideways_base = np.linspace(104000, 108000, 252*2)
    sideways_period = sideways_base + np.random.normal(0, 1000, len(sideways_base))

    equity_values = np.concatenate([bull_period, bear_period, sideways_period])
    equity = pd.Series(equity_values, index=dates)

    trades = [{'date': datetime.now(), 'pnl': 100} for _ in range(150)]

    result = validator.validate(equity, trades)

    print(f"\n验证结果: {'✅ 通过' if result.passed else '❌ 未通过'}")
    print(f"\n市场周期检查:")
    regime_issues = [i for i in result.issues if i.category == 'market_regime']
    for issue in regime_issues:
        icon = "✅" if issue.severity == IssueSeverity.INFO else "⚠️"
        print(f"  {icon} {issue.message}")
        if issue.details and 'regimes' in issue.details:
            print(f"     检测到的市场状态: {', '.join(issue.details['regimes'])}")


def example_data_quality_check():
    """示例4: 数据质量检查"""
    print("\n" + "=" * 60)
    print("示例 4: 数据质量检查")
    print("=" * 60)

    validator = BacktestValidator()

    dates = pd.date_range(start='2018-01-01', periods=252*6, freq='D')
    equity = pd.Series(np.linspace(100000, 150000, len(dates)), index=dates)

    # 创建有问题的价格数据
    # 1. 数据缺失（只保留60%的数据）
    price_dates = dates[::2]  # 每2天取1天
    prices = np.linspace(50, 60, len(price_dates))

    # 2. 添加异常价格跳变
    prices[100] = 80  # 异常跳变 +40%
    prices[200] = 40  # 异常跳变 -33%

    price_data = pd.DataFrame({'close': prices}, index=price_dates)

    trades = [{'date': datetime.now(), 'pnl': 100} for _ in range(150)]

    result = validator.validate(equity, trades, price_data)

    print(f"\n验证结果: {'✅ 通过' if result.passed else '❌ 未通过'}")
    print(f"\n数据质量问题:")
    quality_issues = [i for i in result.issues if i.category == 'data_quality']
    for issue in quality_issues:
        print(f"  ⚠️ {issue.message}")
        if issue.details:
            for key, value in issue.details.items():
                if key != 'dates':  # 跳过日期列表
                    print(f"     - {key}: {value}")


def example_performance_validation():
    """示例5: 性能指标验证"""
    print("\n" + "=" * 60)
    print("示例 5: 性能指标验证")
    print("=" * 60)

    # 创建带性能要求的验证器
    config = ValidatorConfig(
        min_history_years=3.0,
        min_sharpe_ratio=1.0,
        max_drawdown_threshold=0.20
    )
    validator = BacktestValidator(config)

    dates = pd.date_range(start='2020-01-01', periods=252*4, freq='D')

    # 创建有大回撤的权益曲线
    equity_values = np.linspace(100000, 150000, len(dates))
    # 在中间制造一个30%的回撤
    mid_point = len(dates) // 2
    equity_values[mid_point:mid_point+100] *= 0.7

    equity = pd.Series(equity_values, index=dates)
    trades = [{'date': datetime.now(), 'pnl': 100} for _ in range(120)]

    result = validator.validate(equity, trades)

    print(f"\n验证结果: {'✅ 通过' if result.passed else '❌ 未通过'}")
    print(f"\n性能指标问题:")
    perf_issues = [i for i in result.issues if i.category == 'performance']
    for issue in perf_issues:
        print(f"  ⚠️ {issue.message}")


def example_validation_profiles():
    """示例6: 使用预定义配置文件"""
    print("\n" + "=" * 60)
    print("示例 6: 使用预定义配置文件")
    print("=" * 60)

    # 创建测试数据
    dates = pd.date_range(start='2015-01-01', periods=252*8, freq='D')
    equity = pd.Series(np.linspace(100000, 200000, len(dates)), index=dates)
    trades = [{'date': datetime.now(), 'pnl': 100} for _ in range(250)]

    profiles = ['strict', 'moderate', 'relaxed']

    for profile_name in profiles:
        print(f"\n配置文件: {profile_name.upper()}")
        print("-" * 40)

        validator = BacktestValidator()
        config = validator.create_profile(profile_name)
        validator.config = config

        result = validator.validate(equity, trades)

        print(f"  验证结果: {'✅ 通过' if result.passed else '❌ 未通过'}")
        print(f"  配置:")
        print(f"    - 最小历史年限: {config.min_history_years}年")
        print(f"    - 最小交易次数: {config.min_trade_count}")
        print(f"    - 要求牛市: {config.require_bull_market}")
        print(f"    - 要求熊市: {config.require_bear_market}")
        print(f"    - 最小夏普比率: {config.min_sharpe_ratio}")

        errors = result.get_errors()
        warnings = result.get_warnings()
        print(f"  结果: {len(errors)}个错误, {len(warnings)}个警告")


def example_complete_validation_report():
    """示例7: 完整验证报告"""
    print("\n" + "=" * 60)
    print("示例 7: 完整验证报告")
    print("=" * 60)

    validator = BacktestValidator()

    # 创建完整的回测数据
    dates = pd.date_range(start='2017-01-01', periods=252*7, freq='D')

    # 模拟真实的权益曲线（有波动）
    np.random.seed(42)
    returns = np.random.normal(0.0005, 0.015, len(dates))
    equity = pd.Series(100000 * (1 + returns).cumprod(), index=dates)

    # 模拟交易
    trades = []
    trade_interval = len(dates) // 180  # 动态计算间隔
    for i in range(180):
        idx = min(i * trade_interval, len(dates) - 1)
        trade_date = dates[idx]
        trades.append({
            'date': trade_date,
            'symbol': '600036.SH',
            'pnl': np.random.normal(800, 400),
            'return_pct': np.random.normal(0.015, 0.01)
        })

    # 模拟价格数据
    price_data = pd.DataFrame({
        'close': np.linspace(50, 65, len(dates)) + np.random.normal(0, 1, len(dates))
    }, index=dates)

    result = validator.validate(equity, trades, price_data)

    print(f"\n{'='*60}")
    print(f"回测验证报告")
    print(f"{'='*60}")
    print(f"\n总体结果: {'✅ 通过' if result.passed else '❌ 未通过'}")

    print(f"\n摘要信息:")
    print(f"  回测周期: {result.summary.get('start_date')} 至 {result.summary.get('end_date')}")
    print(f"  历史年限: {result.summary.get('history_years')}年")
    print(f"  数据点数: {result.summary.get('data_points')}")
    print(f"  交易次数: {result.summary.get('trade_count')}")

    print(f"\n问题统计:")
    print(f"  错误: {result.summary.get('errors')}")
    print(f"  警告: {result.summary.get('warnings')}")
    print(f"  信息: {result.summary.get('info')}")

    if result.get_errors():
        print(f"\n❌ 错误详情:")
        for error in result.get_errors():
            print(f"  - {error.message}")

    if result.get_warnings():
        print(f"\n⚠️  警告详情:")
        for warning in result.get_warnings():
            print(f"  - {warning.message}")

    print(f"\n{'='*60}")


if __name__ == '__main__':
    # 运行所有示例
    example_basic_validation()
    example_insufficient_history()
    example_market_regime_coverage()
    example_data_quality_check()
    example_performance_validation()
    example_validation_profiles()
    example_complete_validation_report()

    print("\n" + "=" * 60)
    print("✅ 所有示例运行完成！")
    print("=" * 60)
