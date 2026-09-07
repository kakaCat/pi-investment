"""
做市策略完整示例

演示高频交易做市策略的实现：
1. 订单簿管理
2. 做市报价计算
3. 库存控制
4. 风险管理
5. 策略回测
"""

import sys
import os

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from domain.quantlib.hft_strategies.market_making import (
    OrderBook,
    MarketMakingStrategy,
    StatisticalArbitrageStrategy
)


def orderbook_basics():
    """订单簿基础"""
    print("=" * 60)
    print("步骤1: 订单簿基础")
    print("=" * 60)

    # 创建订单簿
    orderbook = OrderBook(depth=5)

    # 模拟盘口数据
    bids = [
        (50000, 10),  # (价格, 数量)
        (49999, 20),
        (49998, 15),
        (49997, 25),
        (49996, 30)
    ]

    asks = [
        (50001, 12),
        (50002, 18),
        (50003, 22),
        (50004, 28),
        (50005, 35)
    ]

    orderbook.update(bids, asks)

    print("\n订单簿状态:")
    print("\n卖盘 (Asks):")
    for price, volume in reversed(orderbook.asks):
        print(f"  {price:>8.2f}  {volume:>6}")

    print("\n" + "-" * 25)

    print("\n买盘 (Bids):")
    for price, volume in orderbook.bids:
        print(f"  {price:>8.2f}  {volume:>6}")

    # 关键指标
    best_bid = orderbook.get_best_bid()
    best_ask = orderbook.get_best_ask()
    mid_price = orderbook.get_mid_price()
    spread = orderbook.get_spread()
    imbalance = orderbook.get_imbalance()

    print("\n关键指标:")
    print(f"  最优买价: {best_bid[0]:.2f} (数量: {best_bid[1]})")
    print(f"  最优卖价: {best_ask[0]:.2f} (数量: {best_ask[1]})")
    print(f"  中间价: {mid_price:.2f}")
    print(f"  买卖价差: {spread:.2f} ({spread/mid_price:.4%})")
    print(f"  订单簿不平衡度: {imbalance:.4f}")

    print("\n不平衡度解读:")
    if imbalance > 0.1:
        print("  → 买盘强势，价格可能上涨")
    elif imbalance < -0.1:
        print("  → 卖盘强势，价格可能下跌")
    else:
        print("  → 买卖盘平衡")

    return orderbook


def market_making_basics(orderbook):
    """做市策略基础"""
    print("\n" + "=" * 60)
    print("步骤2: 做市策略基础")
    print("=" * 60)

    print("\n策略说明:")
    print("  - 在买卖两侧同时挂单")
    print("  - 赚取买卖价差")
    print("  - 控制库存风险")
    print("  - 根据市场状况动态调整报价")

    # 创建做市策略
    strategy = MarketMakingStrategy(
        symbol='BTC/USDT',
        min_spread=0.0002,      # 最小价差 0.02%
        target_spread=0.0005,   # 目标价差 0.05%
        max_inventory=1000,     # 最大库存
        order_size=100,         # 单次下单量
        inventory_penalty=0.0001  # 库存惩罚系数
    )

    print(f"\n策略参数:")
    print(f"  交易品种: {strategy.symbol}")
    print(f"  最小价差: {strategy.min_spread:.4%}")
    print(f"  目标价差: {strategy.target_spread:.4%}")
    print(f"  最大库存: {strategy.max_inventory}")
    print(f"  单次下单量: {strategy.order_size}")

    # 更新订单簿
    strategy.order_book = orderbook

    # 生成做市订单
    orders = strategy.generate_orders()

    print(f"\n生成的做市订单: {len(orders)}个")
    for i, order in enumerate(orders, 1):
        print(f"\n订单{i}:")
        print(f"  方向: {order['side'].upper()}")
        print(f"  价格: {order['price']:.2f}")
        print(f"  数量: {order['quantity']}")
        print(f"  类型: {order['type']}")

    return strategy, orders


def inventory_management_demo(strategy):
    """库存管理演示"""
    print("\n" + "=" * 60)
    print("步骤3: 库存管理")
    print("=" * 60)

    print("\n库存管理原则:")
    print("  - 库存过多时，降低买价、提高卖价，促进卖出")
    print("  - 库存过少时，提高买价、降低卖价，促进买入")
    print("  - 目标：保持库存接近0")

    mid_price = 50000
    spread = 10
    imbalance = 0

    print("\n不同库存水平下的报价:")
    print("库存水平    买价偏移    卖价偏移")
    print("-" * 45)

    inventory_levels = [-800, -400, 0, 400, 800]
    for inventory in inventory_levels:
        strategy.inventory = inventory

        bid_price, ask_price = strategy.calculate_quote_prices(
            mid_price, spread, imbalance
        )

        bid_offset = bid_price - mid_price
        ask_offset = ask_price - mid_price

        print(f"{inventory:>8}    {bid_offset:>10.2f}    {ask_offset:>10.2f}")

    print("\n观察:")
    print("  - 库存为正时，买价下降、卖价上升")
    print("  - 库存为负时，买价上升、卖价下降")
    print("  - 库存为0时，报价对称")


def simulate_market_making():
    """模拟做市交易"""
    print("\n" + "=" * 60)
    print("步骤4: 模拟做市交易")
    print("=" * 60)

    # 创建策略
    strategy = MarketMakingStrategy(
        symbol='BTC/USDT',
        min_spread=0.0002,
        target_spread=0.0005,
        max_inventory=1000,
        order_size=100
    )

    print("\n模拟100次交易...")

    np.random.seed(42)
    base_price = 50000

    for i in range(100):
        # 模拟价格波动
        price_change = np.random.randn() * 10
        current_price = base_price + price_change

        # 模拟订单簿
        bids = [(current_price - j, 10 + j*2) for j in range(1, 6)]
        asks = [(current_price + j, 12 + j*2) for j in range(1, 6)]
        strategy.order_book.update(bids, asks)

        # 生成订单
        orders = strategy.generate_orders()

        # 模拟成交
        if orders and np.random.rand() < 0.3:  # 30%成交概率
            order = np.random.choice(orders)
            fill_price = order['price']
            fill_quantity = order['quantity']

            strategy.on_fill(order, fill_price, fill_quantity)

    # 统计结果
    stats = strategy.get_statistics()

    print("\n交易统计:")
    print(f"  总交易次数: {stats['total_trades']}")
    print(f"  买入次数: {stats['buy_trades']}")
    print(f"  卖出次数: {stats['sell_trades']}")
    print(f"  平均买价: {stats['avg_buy_price']:.2f}")
    print(f"  平均卖价: {stats['avg_sell_price']:.2f}")
    print(f"  平均价差: {stats['avg_sell_price'] - stats['avg_buy_price']:.2f}")
    print(f"\n  总盈亏: {stats['total_pnl']:.2f}")
    print(f"  平均每笔盈亏: {stats['avg_pnl_per_trade']:.2f}")
    print(f"  当前库存: {stats['current_inventory']}")
    print(f"  最大库存: {stats['max_inventory']}")

    return strategy


def statistical_arbitrage_demo():
    """统计套利策略演示"""
    print("\n" + "=" * 60)
    print("步骤5: 统计套利策略")
    print("=" * 60)

    print("\n策略说明:")
    print("  - 寻找相关性强的品种对")
    print("  - 计算价差序列")
    print("  - 价差偏离均值时建仓")
    print("  - 价差回归时平仓")

    # 创建策略
    strategy = StatisticalArbitrageStrategy(
        symbol_a='ETH/USDT',
        symbol_b='BTC/USDT',
        lookback_period=60,
        entry_threshold=2.0,
        exit_threshold=0.5,
        max_position=1000
    )

    print(f"\n策略参数:")
    print(f"  品种A: {strategy.symbol_a}")
    print(f"  品种B: {strategy.symbol_b}")
    print(f"  回溯期: {strategy.lookback_period}")
    print(f"  入场阈值: {strategy.entry_threshold} 标准差")
    print(f"  出场阈值: {strategy.exit_threshold} 标准差")

    # 模拟价格序列
    print("\n模拟价格序列...")
    np.random.seed(42)

    # 生成相关的价格序列
    n = 200
    common_factor = np.random.randn(n)
    price_a = 3000 + np.cumsum(common_factor * 30 + np.random.randn(n) * 10)
    price_b = 50000 + np.cumsum(common_factor * 500 + np.random.randn(n) * 100)

    # 更新价格
    for i in range(n):
        strategy.update_prices(price_a[i], price_b[i])

        if i >= strategy.lookback_period:
            # 生成信号
            signal = strategy.generate_signal()

            if signal:
                print(f"\n时间步 {i}:")
                print(f"  动作: {signal['action']}")
                print(f"  方向: {signal['direction']}")
                print(f"  Z-score: {signal['z_score']:.2f}")

                if signal['action'] == 'open':
                    print(f"  对冲比率: {signal['hedge_ratio']:.4f}")
                    print(f"  {strategy.symbol_a}: {signal['quantity_a']}")
                    print(f"  {strategy.symbol_b}: {signal['quantity_b']}")

                    # 模拟成交
                    strategy.on_fill(strategy.symbol_a, signal['quantity_a'], price_a[i])
                    strategy.on_fill(strategy.symbol_b, signal['quantity_b'], price_b[i])

    print(f"\n最终状态:")
    print(f"  持仓A: {strategy.position_a}")
    print(f"  持仓B: {strategy.position_b}")
    print(f"  盈亏: {strategy.pnl:.2f}")


def risk_management_tips():
    """风险管理技巧"""
    print("\n" + "=" * 60)
    print("风险管理技巧")
    print("=" * 60)

    print("\n1. 库存风险:")
    print("  - 设置最大库存限制")
    print("  - 库存过大时停止报价")
    print("  - 使用库存惩罚调整报价")
    print("  - 定期平仓降低库存")

    print("\n2. 价差风险:")
    print("  - 设置最小价差阈值")
    print("  - 价差过小时不报价")
    print("  - 根据波动率动态调整价差")

    print("\n3. 市场风险:")
    print("  - 监控订单簿不平衡度")
    print("  - 单边市场时减少报价")
    print("  - 设置止损限制")

    print("\n4. 技术风险:")
    print("  - 监控延迟和滑点")
    print("  - 设置订单超时机制")
    print("  - 实时监控持仓和盈亏")

    print("\n5. 参数优化:")
    print("  - 回测不同参数组合")
    print("  - 根据市场状况调整参数")
    print("  - 定期评估策略表现")


def performance_metrics():
    """性能指标"""
    print("\n" + "=" * 60)
    print("做市策略性能指标")
    print("=" * 60)

    print("\n关键指标:")
    print("\n1. 盈利指标:")
    print("  - 总盈亏")
    print("  - 平均每笔盈亏")
    print("  - 盈利交易比例")
    print("  - 日均盈利")

    print("\n2. 风险指标:")
    print("  - 最大库存")
    print("  - 库存周转率")
    print("  - 最大回撤")
    print("  - 夏普比率")

    print("\n3. 效率指标:")
    print("  - 成交率")
    print("  - 平均持仓时间")
    print("  - 资金利用率")
    print("  - 订单成交比")

    print("\n4. 市场影响:")
    print("  - 平均价差贡献")
    print("  - 流动性提供量")
    print("  - 市场份额")

    # 示例计算
    print("\n示例计算:")
    total_pnl = 10000
    total_trades = 500
    winning_trades = 320
    max_inventory = 800
    avg_inventory = 200

    print(f"  总盈亏: {total_pnl:,.0f}")
    print(f"  总交易: {total_trades}")
    print(f"  平均每笔: {total_pnl/total_trades:.2f}")
    print(f"  胜率: {winning_trades/total_trades:.1%}")
    print(f"  最大库存: {max_inventory}")
    print(f"  平均库存: {avg_inventory}")
    print(f"  库存周转: {total_trades/2/avg_inventory:.2f}次")


def main():
    """主函数"""
    print("做市策略完整示例")
    print("=" * 60)

    # 1. 订单簿基础
    orderbook = orderbook_basics()

    # 2. 做市策略基础
    strategy, orders = market_making_basics(orderbook)

    # 3. 库存管理
    inventory_management_demo(strategy)

    # 4. 模拟做市交易
    strategy = simulate_market_making()

    # 5. 统计套利策略
    statistical_arbitrage_demo()

    # 6. 风险管理技巧
    risk_management_tips()

    # 7. 性能指标
    performance_metrics()

    print("\n" + "=" * 60)
    print("示例完成！")
    print("=" * 60)
    print("\n关键要点:")
    print("1. 做市策略赚取买卖价差")
    print("2. 库存管理是核心风险控制手段")
    print("3. 根据市场状况动态调整报价")
    print("4. 统计套利利用价差回归")
    print("5. 高频策略需要低延迟基础设施")
    print("6. 持续监控和优化至关重要")


if __name__ == "__main__":
    main()
