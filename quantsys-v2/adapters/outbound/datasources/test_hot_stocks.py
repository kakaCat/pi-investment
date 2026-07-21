"""测试热搜股票多数据源功能"""

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from adapters.outbound.datasources.hot_stock_source import get_hot_stock_source


def test_single_sources():
    """测试单个数据源"""
    print("\n" + "="*60)
    print("测试单个数据源")
    print("="*60)

    source = get_hot_stock_source()

    # 测试东方财富
    print("\n1. 测试东方财富数据源...")
    result = source.get_hot_stocks_eastmoney("A股")
    print(f"   结果: {'✓ 成功' if result.success else '✗ 失败'}")
    if result.success:
        print(f"   数据条数: {result.data.get('total', 0)}")
        print(f"   前3条: {result.data.get('stocks', [])[:3]}")
    else:
        print(f"   错误: {result.error}")

    # 测试雪球
    print("\n2. 测试雪球数据源...")
    result = source.get_hot_stocks_xueqiu("A股")
    print(f"   结果: {'✓ 成功' if result.success else '✗ 失败'}")
    if result.success:
        print(f"   数据条数: {result.data.get('total', 0)}")
    else:
        print(f"   错误: {result.error}")

    # 测试同花顺
    print("\n3. 测试同花顺数据源...")
    result = source.get_hot_stocks_ths("A股")
    print(f"   结果: {'✓ 成功' if result.success else '✗ 失败'}")
    if result.success:
        print(f"   数据条数: {result.data.get('total', 0)}")
    else:
        print(f"   错误: {result.error}")


def test_failover():
    """测试多数据源 failover"""
    print("\n" + "="*60)
    print("测试多数据源 Failover")
    print("="*60)

    source = get_hot_stock_source()

    print("\n执行 failover 测试...")
    result = source.get_hot_stocks_with_fallback("A股")

    print(f"\n最终结果: {'✓ 成功' if result['success'] else '✗ 失败'}")

    if result['success']:
        print(f"使用的数据源: {result.get('source', 'unknown')}")
        print(f"数据条数: {result['data'].get('total', 0)}")

        stocks = result['data'].get('stocks', [])
        if stocks:
            print(f"\n前5名热搜股票:")
            for i, stock in enumerate(stocks[:5], 1):
                print(f"  {i}. {stock}")
    else:
        print(f"错误信息: {result.get('error')}")
        print(f"尝试过的数据源: {result.get('tried_sources', [])}")


def test_via_service():
    """通过 market_data_service 测试"""
    print("\n" + "="*60)
    print("测试通过 MarketDataService")
    print("="*60)

    from application.services.market_data_service import market_data_service

    print("\n调用 market_data_service.get_hot_stocks()...")
    result = market_data_service.get_hot_stocks("A股")

    print(f"\n结果: {'✓ 成功' if result['success'] else '✗ 失败'}")

    if result['success']:
        print(f"使用的数据源: {result.get('source', 'unknown')}")
        print(f"数据条数: {result['data'].get('total', 0)}")

        stocks = result['data'].get('stocks', [])
        if stocks:
            print(f"\n前3名:")
            for i, stock in enumerate(stocks[:3], 1):
                print(f"  {i}. {stock}")
    else:
        print(f"错误: {result.get('error')}")


if __name__ == "__main__":
    print("\n" + "="*60)
    print("热搜股票多数据源测试")
    print("="*60)

    # 测试单个数据源
    test_single_sources()

    # 测试 failover
    test_failover()

    # 测试通过 service
    test_via_service()

    print("\n" + "="*60)
    print("测试完成")
    print("="*60)
