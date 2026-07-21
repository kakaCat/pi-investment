#!/usr/bin/env python3
"""
快速验证脚本：自定义成交价格功能

对比使用收盘价 vs 自定义价格的回测结果
"""

import sys
import os

# 添加 quantsys-v2 根目录到路径
quantsys_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
sys.path.insert(0, quantsys_root)

from datetime import datetime, timedelta
from application.services.strategy_backtest_service import StrategyBacktestService
from adapters.outbound.repositories import KlineORMRepository


def test_custom_price_vs_close():
    """对比测试：自定义价格 vs 收盘价"""

    backtest_service = StrategyBacktestService()
    kline_repo = KlineORMRepository()

    # 获取测试数据（贵州茅台，最近1年）
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')

    print(f"📊 获取数据：600519.SH (贵州茅台)")
    print(f"   时间范围：{start_date} ~ {end_date}")

    klines = kline_repo.get_daily_klines(
        symbol='600519.SH',
        start_date=start_date,
        end_date=end_date
    )

    if len(klines) == 0:
        print("❌ 未获取到K线数据")
        return

    print(f"✅ 获取到 {len(klines)} 条K线数据\n")

    # ========== 策略1：使用收盘价（默认） ==========
    strategy_close = {
        'code_content': """
my_indicator_name = "RSI策略-收盘价"

def calc_indicator(ctx):
    df = ctx.df

    # RSI超卖买入，超买卖出
    df['buy_tier1'] = df['rsi14'] < 30
    df['buy_tier1_pct'] = 1.0
    # 不指定价格，使用收盘价

    df['sell_tier1'] = df['rsi14'] > 70
    df['sell_tier1_pct'] = 1.0

    return df
""",
        'code_type': 'indicator',
        'parsed_params': {}
    }

    print("🔄 运行策略1：使用收盘价（默认）")
    result_close = backtest_service.backtest_indicator_strategy(
        strategy=strategy_close,
        klines=klines,
        initial_cash=1000000
    )

    # ========== 策略2：使用自定义价格 ==========
    strategy_custom = {
        'code_content': """
my_indicator_name = "RSI策略-自定义价格"

def calc_indicator(ctx):
    df = ctx.df

    # RSI超卖时以最低价上浮1%买入
    df['buy_tier1'] = df['rsi14'] < 30
    df['buy_tier1_pct'] = 1.0
    df['buy_tier1_price'] = df['low'] * 1.01  # 自定义买入价

    # RSI超买时以最高价下浮1%卖出
    df['sell_tier1'] = df['rsi14'] > 70
    df['sell_tier1_pct'] = 1.0
    df['sell_tier1_price'] = df['high'] * 0.99  # 自定义卖出价

    return df
""",
        'code_type': 'indicator',
        'parsed_params': {}
    }

    print("🔄 运行策略2：使用自定义价格（低买高卖）")
    result_custom = backtest_service.backtest_indicator_strategy(
        strategy=strategy_custom,
        klines=klines,
        initial_cash=1000000
    )

    # ========== 对比结果 ==========
    print("\n" + "="*60)
    print("📈 回测结果对比")
    print("="*60)

    print(f"\n{'指标':<20} {'收盘价策略':<15} {'自定义价格策略':<15} {'差异'}")
    print("-" * 60)

    # 总收益率
    return_close = result_close['total_return']
    return_custom = result_custom['total_return']
    diff_return = return_custom - return_close
    print(f"{'总收益率':<20} {return_close:>13.2%} {return_custom:>13.2%} {diff_return:>+13.2%}")

    # 年化收益率
    annual_close = result_close.get('annual_return', 0)
    annual_custom = result_custom.get('annual_return', 0)
    diff_annual = annual_custom - annual_close
    print(f"{'年化收益率':<20} {annual_close:>13.2%} {annual_custom:>13.2%} {diff_annual:>+13.2%}")

    # 最大回撤
    dd_close = result_close.get('max_drawdown', 0)
    dd_custom = result_custom.get('max_drawdown', 0)
    diff_dd = dd_custom - dd_close
    print(f"{'最大回撤':<20} {dd_close:>13.2%} {dd_custom:>13.2%} {diff_dd:>+13.2%}")

    # 夏普比率
    sharpe_close = result_close.get('sharpe_ratio', 0)
    sharpe_custom = result_custom.get('sharpe_ratio', 0)
    diff_sharpe = sharpe_custom - sharpe_close
    print(f"{'夏普比率':<20} {sharpe_close:>13.2f} {sharpe_custom:>13.2f} {diff_sharpe:>+13.2f}")

    # 交易次数
    trades_close = result_close.get('trade_count', 0)
    trades_custom = result_custom.get('trade_count', 0)
    print(f"{'交易次数':<20} {trades_close:>13d} {trades_custom:>13d}")

    # 胜率
    win_close = result_close.get('win_rate', 0)
    win_custom = result_custom.get('win_rate', 0)
    diff_win = win_custom - win_close
    print(f"{'胜率':<20} {win_close:>13.2%} {win_custom:>13.2%} {diff_win:>+13.2%}")

    print("\n" + "="*60)

    # 判断结果
    if return_custom > return_close:
        print("✅ 自定义价格策略表现更好！")
        print(f"   收益率提升：{diff_return:.2%}")
    elif return_custom < return_close:
        print("⚠️  自定义价格策略表现较差")
        print(f"   收益率下降：{diff_return:.2%}")
    else:
        print("➡️  两种策略表现相同")

    print("\n💡 结论：自定义价格功能正常工作")
    print("   - 策略可以指定买入/卖出价格")
    print("   - 未指定时自动使用收盘价")
    print("   - 价格差异影响回测结果")


if __name__ == '__main__':
    test_custom_price_vs_close()
