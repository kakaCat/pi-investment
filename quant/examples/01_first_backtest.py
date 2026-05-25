"""
第一个回测示例 - RSI反转策略

演示如何使用QuantSys进行完整的策略回测
"""

import sys
sys.path.insert(0, '.')

from quantsys.data.db import Database
from quantsys.strategies.backtest import BacktestEngine
from quantsys.strategies.classic.rsi_reversal import RSIReversalStrategy
import pandas as pd

def get_stock_data(symbol: str, days: int = 730) -> pd.DataFrame:
    """从数据库读取股票数据"""
    import os
    db_path = os.path.join(os.path.expanduser('~'), '.pi-invest/stock-db/stocks.db')
    db = Database(db_path)
    conn = db._get_connection()

    query = """
        SELECT date, open, high, low, close, volume, amount
        FROM daily_klines
        WHERE symbol = ?
        ORDER BY date DESC
        LIMIT ?
    """

    df = pd.read_sql_query(query, conn, params=(symbol, days))
    df = df.sort_values('date').reset_index(drop=True)

    # 添加策略需要的列
    df['timestamp'] = pd.to_datetime(df['date'], format='mixed', errors='coerce')
    df['symbol'] = symbol

    return df

def main():
    print("=" * 60)
    print("QuantSys 第一个回测示例 - RSI反转策略")
    print("=" * 60)
    print()

    # 1. 获取数据
    print("📊 步骤1: 获取数据...")
    try:
        data = get_stock_data('000001', days=730)

        if len(data) == 0:
            print("❌ 数据库中没有数据，请先运行数据获取脚本")
            print("   运行: python quantsys/data/pipeline.py fetch")
            return

        print(f"✅ 成功获取数据: {len(data)}条记录")
        print(f"   日期范围: {data['date'].min()} 至 {data['date'].max()}")
    except Exception as e:
        print(f"❌ 数据获取失败: {e}")
        import traceback
        traceback.print_exc()
        return

    print()

    # 2. 创建策略
    print("🎯 步骤2: 创建RSI反转策略...")
    strategy = RSIReversalStrategy(params={
        'rsi_period': 14,
        'oversold_threshold': 30,
        'overbought_threshold': 70
    })
    print(f"✅ 策略参数: RSI周期=14, 超卖=30, 超买=70")
    print()

    # 3. 创建回测引擎
    print("⚙️  步骤3: 创建回测引擎...")
    engine = BacktestEngine(
        strategy=strategy,
        initial_capital=1000000,  # 100万初始资金
        commission=0.0003,        # 万三佣金
        slippage=0.001            # 千一滑点
    )
    print(f"✅ 初始资金: 1,000,000元")
    print()

    # 4. 运行回测
    print("🚀 步骤4: 运行回测...")
    print("-" * 60)

    result = engine.run(data)

    print("-" * 60)
    print()

    # 5. 显示结果
    print("📈 步骤5: 回测结果")
    print("=" * 60)
    print(f"总回报率:     {result['total_return']:.2%}")
    print(f"Sharpe比率:   {result['sharpe_ratio']:.2f}")
    print(f"最大回撤:     {result['max_drawdown']:.2%}")
    print(f"胜率:         {result['win_rate']:.2%}")
    print(f"总交易次数:   {result['total_trades']}")
    print(f"最终资金:     {result['final_capital']:,.0f}元")
    print("=" * 60)
    print()

    print("✅ 回测完成！")
    print()

if __name__ == '__main__':
    main()
