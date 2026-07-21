#!/usr/bin/env python3
"""
Test script for new data sources (Yahoo Finance, Binance, Polygon).
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from adapters.outbound.datasources.sources import YahooFinanceSource, BinanceSource, PolygonSource
from adapters.outbound.datasources.config import DataSourceConfig


def print_section(title):
    """Print a section header."""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def test_yahoo_finance():
    """Test Yahoo Finance data source."""
    print_section("Testing Yahoo Finance (美股数据)")

    source = YahooFinanceSource()

    # Test 1: Connection
    print("\n1. 测试连接...")
    result = source.test_connection()
    print(f"   状态: {'✓ 成功' if result.success else '✗ 失败'}")
    if not result.success:
        print(f"   错误: {result.error}")
        return

    # Test 2: Stock info
    print("\n2. 获取股票信息 (Apple AAPL)...")
    result = source.get_stock_info("AAPL")
    if result.success:
        print(f"   ✓ 名称: {result.data.get('name', 'N/A')}")
        print(f"   ✓ 价格: ${result.data.get('price', 0):.2f}")
        print(f"   ✓ 涨跌: {result.data.get('change_percent', 0):.2f}%")
        print(f"   ✓ 市值: ${result.data.get('market_cap', 0):,.0f}")
    else:
        print(f"   ✗ 失败: {result.error}")

    # Test 3: Klines
    print("\n3. 获取K线数据 (最近5天)...")
    result = source.get_klines("AAPL", period="daily",
                               start_date="20240520", end_date="20240524")
    if result.success:
        print(f"   ✓ 获取 {result.count} 条K线数据")
        if result.data:
            latest = result.data[-1]
            print(f"   ✓ 最新: {latest.get('date')} 收盘价 ${latest.get('close', 0):.2f}")
    else:
        print(f"   ✗ 失败: {result.error}")

    # Test 4: Search
    print("\n4. 搜索股票 'Tesla'...")
    result = source.search_symbols("Tesla", limit=3)
    if result.success:
        print(f"   ✓ 找到 {result.count} 个结果")
        for item in result.data[:3]:
            print(f"   - {item['symbol']}: {item['name']}")
    else:
        print(f"   ✗ 失败: {result.error}")


def test_binance():
    """Test Binance data source."""
    print_section("Testing Binance (加密货币)")

    source = BinanceSource()

    # Test 1: Connection
    print("\n1. 测试连接...")
    result = source.test_connection()
    print(f"   状态: {'✓ 成功' if result.success else '✗ 失败'}")
    if not result.success:
        print(f"   错误: {result.error}")
        return

    # Test 2: Crypto info
    print("\n2. 获取加密货币信息 (BTC/USDT)...")
    result = source.get_stock_info("BTCUSDT")
    if result.success:
        print(f"   ✓ 交易对: {result.data.get('symbol', 'N/A')}")
        print(f"   ✓ 价格: ${result.data.get('price', 0):,.2f}")
        print(f"   ✓ 24h涨跌: {result.data.get('change_percent', 0):.2f}%")
        print(f"   ✓ 24h成交量: {result.data.get('volume_24h', 0):,.2f}")
    else:
        print(f"   ✗ 失败: {result.error}")

    # Test 3: Klines
    print("\n3. 获取K线数据 (最近5天)...")
    result = source.get_klines("BTCUSDT", period="daily",
                               start_date="20240520", end_date="20240524")
    if result.success:
        print(f"   ✓ 获取 {result.count} 条K线数据")
        if result.data:
            latest = result.data[-1]
            print(f"   ✓ 最新: {latest.get('date')} 收盘价 ${latest.get('close', 0):,.2f}")
    else:
        print(f"   ✗ 失败: {result.error}")

    # Test 4: Multiple quotes
    print("\n4. 获取多个加密货币报价...")
    result = source.get_realtime_quote(["BTCUSDT", "ETHUSDT", "BNBUSDT"])
    if result.success:
        print(f"   ✓ 获取 {result.count} 个报价")
        for symbol, quote in result.data.items():
            print(f"   - {symbol}: ${quote['price']:,.2f}")
    else:
        print(f"   ✗ 失败: {result.error}")


def test_polygon():
    """Test Polygon data source."""
    print_section("Testing Polygon.io (美股高级数据)")

    # Check configuration
    if not DataSourceConfig.is_configured("polygon"):
        print("\n⚠️  Polygon API key 未配置")
        print("   请设置环境变量: export POLYGON_API_KEY=your_key_here")
        print("   免费申请: https://polygon.io/")
        return

    source = PolygonSource()

    # Test 1: Connection
    print("\n1. 测试连接...")
    result = source.test_connection()
    print(f"   状态: {'✓ 成功' if result.success else '✗ 失败'}")
    if not result.success:
        print(f"   错误: {result.error}")
        return

    # Test 2: Stock info
    print("\n2. 获取股票详情 (Apple AAPL)...")
    result = source.get_stock_info("AAPL")
    if result.success:
        print(f"   ✓ 名称: {result.data.get('name', 'N/A')}")
        print(f"   ✓ 市场: {result.data.get('market', 'N/A')}")
        print(f"   ✓ 交易所: {result.data.get('primary_exchange', 'N/A')}")
    else:
        print(f"   ✗ 失败: {result.error}")

    # Test 3: Klines
    print("\n3. 获取K线数据 (最近5天)...")
    result = source.get_klines("AAPL", period="daily",
                               start_date="20240520", end_date="20240524")
    if result.success:
        print(f"   ✓ 获取 {result.count} 条K线数据")
        if result.data:
            latest = result.data[-1]
            print(f"   ✓ 最新: {latest.get('date')} 收盘价 ${latest.get('close', 0):.2f}")
    else:
        print(f"   ✗ 失败: {result.error}")


def main():
    """Main entry point."""
    print("\n" + "=" * 60)
    print("  新数据源测试")
    print("  New Data Sources Test")
    print("=" * 60)

    # Test each source
    try:
        test_yahoo_finance()
    except Exception as e:
        print(f"\n✗ Yahoo Finance 测试失败: {e}")

    try:
        test_binance()
    except Exception as e:
        print(f"\n✗ Binance 测试失败: {e}")

    try:
        test_polygon()
    except Exception as e:
        print(f"\n✗ Polygon 测试失败: {e}")

    # Summary
    print_section("测试完成")
    print("\n新增数据源:")
    print("  ✓ Yahoo Finance - 美股数据（免费）")
    print("  ✓ Binance - 加密货币（免费）")
    print("  ⚠ Polygon.io - 美股高级数据（需要API key）")
    print("\n总计数据源: 6个")
    print("  - AkShare (A股/港股)")
    print("  - FRED (美国经济数据)")
    print("  - World Bank (商品价格)")
    print("  - Yahoo Finance (美股)")
    print("  - Binance (加密货币)")
    print("  - Polygon.io (美股高级)")
    print("\n" + "=" * 60 + "\n")


if __name__ == "__main__":
    main()
