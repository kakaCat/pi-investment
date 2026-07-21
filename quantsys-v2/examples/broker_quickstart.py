"""
Quick Start Example for Broker Abstraction Layer

This example demonstrates how to use the broker abstraction layer in quantsys-v2.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from brokers import BrokerRegistry, OrderSide, OrderType, UnifiedOrder


def example_1_basic_usage():
    """示例 1: 基础用法 - 获取行情"""
    print("=" * 60)
    print("示例 1: 获取实时行情")
    print("=" * 60)

    # 获取券商注册表
    registry = BrokerRegistry.instance()

    # 获取 AkShare 券商
    broker = registry.get('akshare')
    print(f"券商: {broker.get_name()} (ID: {broker.get_id()})")

    # 获取行情（需要网络连接）
    symbols = ['600000', '000001']
    print(f"\n查询股票: {symbols}")

    response = broker.get_quotes(symbols)

    if response.success:
        print("\n行情数据:")
        for quote in response.data:
            print(f"  {quote.symbol}: ¥{quote.last_price:.2f} "
                  f"({quote.change_pct:+.2f}%)")
    else:
        print(f"错误: {response.error}")


def example_2_list_brokers():
    """示例 2: 列举所有券商"""
    print("\n" + "=" * 60)
    print("示例 2: 列举所有可用券商")
    print("=" * 60)

    registry = BrokerRegistry.instance()

    # 列举所有券商
    all_brokers = registry.list_brokers()
    print(f"\n可用券商数量: {len(all_brokers)}")
    print(f"券商列表: {all_brokers}")

    # 获取详细信息
    profiles = registry.list_broker_profiles()
    print("\n券商详情:")
    for profile in profiles:
        print(f"  - {profile['name']} ({profile['id']})")
        print(f"    地区: {profile['region']}, 货币: {profile['currency']}")
        print(f"    交易支持: {'是' if profile['is_trading'] else '否'}")


def example_3_broker_profile():
    """示例 3: 查看券商配置"""
    print("\n" + "=" * 60)
    print("示例 3: 查看券商配置")
    print("=" * 60)

    registry = BrokerRegistry.instance()
    broker = registry.get('akshare')

    profile = broker.get_profile()

    print(f"\n券商: {profile.display_name}")
    print(f"ID: {profile.id}")
    print(f"地区: {profile.region}")
    print(f"货币: {profile.currency}")
    print(f"支持的交易所: {', '.join(profile.supported_exchanges)}")
    print(f"默认自选股: {', '.join(profile.default_watchlist[:5])}")
    print(f"费率信息: {profile.brokerage_info}")


def example_4_search_symbols():
    """示例 4: 搜索股票"""
    print("\n" + "=" * 60)
    print("示例 4: 搜索股票")
    print("=" * 60)

    registry = BrokerRegistry.instance()
    broker = registry.get('akshare')

    query = "平安"
    print(f"\n搜索关键词: {query}")

    response = broker.search_symbols(query)

    if response.success:
        print(f"\n找到 {len(response.data)} 个结果:")
        for i, result in enumerate(response.data[:5], 1):
            print(f"  {i}. {result['name']} ({result['symbol']})")
            print(f"     交易所: {result['exchange']}, "
                  f"价格: ¥{result['last_price']:.2f}")
    else:
        print(f"错误: {response.error}")


def example_5_unified_order():
    """示例 5: 创建统一订单（仅演示，不实际下单）"""
    print("\n" + "=" * 60)
    print("示例 5: 创建统一订单结构")
    print("=" * 60)

    # 创建买入订单
    order = UnifiedOrder(
        symbol='600000',
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=100,
        price=1800.0,
        exchange='SSE'
    )

    print("\n订单信息:")
    print(f"  股票代码: {order.symbol}")
    print(f"  方向: {order.side.value}")
    print(f"  类型: {order.order_type.value}")
    print(f"  数量: {order.quantity}")
    print(f"  价格: ¥{order.price}")
    print(f"  交易所: {order.exchange}")

    # 转换为字典
    order_dict = order.to_dict()
    print("\n订单字典:")
    for key, value in order_dict.items():
        if value is not None:
            print(f"  {key}: {value}")


def example_6_error_handling():
    """示例 6: 错误处理"""
    print("\n" + "=" * 60)
    print("示例 6: 错误处理")
    print("=" * 60)

    registry = BrokerRegistry.instance()

    # 尝试获取不存在的券商
    broker = registry.get('nonexistent')
    if broker is None:
        print("\n✓ 正确处理: 券商不存在返回 None")

    # 尝试在数据源券商上执行交易操作
    akshare = registry.get('akshare')
    from domain.brokers.trading_types import BrokerCredentials

    creds = BrokerCredentials(broker_id='akshare')
    order = UnifiedOrder(
        symbol='600000',
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=100
    )

    response = akshare.place_order(creds, order)
    if not response.success:
        print(f"\n✓ 正确处理: {response.error}")


def main():
    """运行所有示例"""
    print("\n" + "=" * 60)
    print("Broker Abstraction Layer - Quick Start Examples")
    print("=" * 60)

    try:
        # 示例 1: 基础用法
        # example_1_basic_usage()  # 需要网络连接，注释掉

        # 示例 2: 列举券商
        example_2_list_brokers()

        # 示例 3: 券商配置
        example_3_broker_profile()

        # 示例 4: 搜索股票
        # example_4_search_symbols()  # 需要网络连接，注释掉

        # 示例 5: 统一订单
        example_5_unified_order()

        # 示例 6: 错误处理
        example_6_error_handling()

        print("\n" + "=" * 60)
        print("所有示例运行完成！")
        print("=" * 60)

    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
