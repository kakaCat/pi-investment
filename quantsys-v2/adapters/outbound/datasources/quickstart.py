#!/usr/bin/env python3
"""
Quick start script for testing the new data sources.

Run this script to verify that the data sources are working correctly.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from adapters.outbound.datasources.sources import AkShareSource, FREDSource, WorldBankSource
from adapters.outbound.datasources.config import DataSourceConfig


def print_section(title):
    """Print a section header."""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def test_akshare():
    """Test AkShare data source."""
    print_section("Testing AkShare (A股/港股数据)")

    source = AkShareSource()

    # Test 1: Connection
    print("\n1. 测试连接...")
    result = source.test_connection()
    print(f"   状态: {'✓ 成功' if result.success else '✗ 失败'}")
    if not result.success:
        print(f"   错误: {result.error}")
        return

    # Test 2: Stock info
    print("\n2. 获取股票信息 (平安银行 000001.SZ)...")
    result = source.get_stock_info("000001.SZ")
    if result.success:
        print(f"   ✓ 股票名称: {result.data.get('name', 'N/A')}")
        print(f"   ✓ 市场: {result.data.get('market', 'N/A')}")
        print(f"   ✓ 行业: {result.data.get('industry', 'N/A')}")
    else:
        print(f"   ✗ 失败: {result.error}")

    # Test 3: Klines
    print("\n3. 获取K线数据 (最近5天)...")
    result = source.get_klines("000001.SZ", period="daily",
                               start_date="20240520", end_date="20240524")
    if result.success:
        print(f"   ✓ 获取 {result.count} 条K线数据")
        if result.data:
            latest = result.data[-1]
            print(f"   ✓ 最新: {latest.get('date')} 收盘价 {latest.get('close')}")
    else:
        print(f"   ✗ 失败: {result.error}")


def test_fred():
    """Test FRED data source."""
    print_section("Testing FRED (美联储经济数据)")

    # Check configuration
    if not DataSourceConfig.is_configured("fred"):
        print("\n⚠️  FRED API key 未配置")
        print("   请设置环境变量: export FRED_API_KEY=your_key_here")
        print("   免费申请: https://fred.stlouisfed.org/docs/api/api_key.html")
        return

    source = FREDSource()

    # Test 1: Connection
    print("\n1. 测试连接...")
    result = source.test_connection()
    print(f"   状态: {'✓ 成功' if result.success else '✗ 失败'}")
    if not result.success:
        print(f"   错误: {result.error}")
        return

    # Test 2: Get GDP series
    print("\n2. 获取GDP数据 (2023-2024)...")
    result = source.get_series("GDP", start_date="2023-01-01", end_date="2024-12-31")
    if result.success:
        print(f"   ✓ 序列: {result.data.get('title', 'N/A')}")
        print(f"   ✓ 单位: {result.data.get('units', 'N/A')}")
        print(f"   ✓ 数据点: {result.data.get('observation_count', 0)}")
        if result.data.get('observations'):
            latest = result.data['observations'][-1]
            print(f"   ✓ 最新: {latest['date']} = {latest['value']}")
    else:
        print(f"   ✗ 失败: {result.error}")

    # Test 3: Search
    print("\n3. 搜索 'unemployment' 相关序列...")
    result = source.search_series("unemployment", limit=3)
    if result.success:
        print(f"   ✓ 找到 {result.count} 个序列")
        for i, series in enumerate(result.data[:3], 1):
            print(f"   {i}. {series['id']}: {series['title'][:50]}...")
    else:
        print(f"   ✗ 失败: {result.error}")


def test_world_bank():
    """Test World Bank data source."""
    print_section("Testing World Bank (世界银行商品价格)")

    source = WorldBankSource()

    # Test 1: Connection
    print("\n1. 测试连接...")
    result = source.test_connection()
    print(f"   状态: {'✓ 成功' if result.success else '✗ 失败'}")
    if not result.success:
        print(f"   错误: {result.error}")
        return

    # Test 2: List commodities
    print("\n2. 列出可用商品...")
    result = source.list_commodities()
    if result.success:
        print(f"   ✓ 共 {result.count} 种商品")
        categories = {}
        for c in result.data:
            cat = c['category']
            categories[cat] = categories.get(cat, 0) + 1
        for cat, count in categories.items():
            print(f"   - {cat}: {count} 种")
    else:
        print(f"   ✗ 失败: {result.error}")

    # Test 3: Get oil prices
    print("\n3. 获取石油价格 (2024)...")
    result = source.get_oil_prices(start_year=2024, end_year=2024)
    if result.success:
        print(f"   ✓ 类别: {result.data.get('category', 'N/A')}")
        print(f"   ✓ 单位: {result.data.get('unit', 'N/A')}")
        for oil_type, data in result.data.get('data', {}).items():
            if data and len(data) > 0:
                print(f"   - {oil_type}: {len(data)} 条记录")
    else:
        print(f"   ✗ 失败: {result.error}")

    # Test 4: Get gold price
    print("\n4. 获取黄金价格 (2024)...")
    result = source.get_commodity_price("gold", start_year=2024, end_year=2024)
    if result.success:
        print(f"   ✓ 商品: {result.data.get('commodity', 'N/A')}")
        data = result.data.get('data', [])
        if data:
            print(f"   ✓ 数据点: {len(data)}")
            if len(data) > 0:
                latest = data[-1]
                print(f"   ✓ 最新: {latest.get('date')} = ${latest.get('value')}")
    else:
        print(f"   ✗ 失败: {result.error}")


def check_configuration():
    """Check configuration status."""
    print_section("配置检查")

    status = DataSourceConfig.validate_all()

    print("\n数据源配置状态:")
    for source, message in status.items():
        icon = "✓" if "✓" in message else "✗" if "✗" in message else "ℹ"
        print(f"  {icon} {source:20s}: {message}")

    print("\n提示:")
    print("  - AkShare: 无需配置，直接使用")
    print("  - World Bank: 无需配置，直接使用")
    print("  - FRED: 需要免费API key (https://fred.stlouisfed.org/docs/api/api_key.html)")


def main():
    """Main entry point."""
    print("\n" + "=" * 60)
    print("  数据源快速测试")
    print("  Data Sources Quick Test")
    print("=" * 60)

    # Check configuration
    check_configuration()

    # Test each source
    try:
        test_akshare()
    except Exception as e:
        print(f"\n✗ AkShare 测试失败: {e}")

    try:
        test_fred()
    except Exception as e:
        print(f"\n✗ FRED 测试失败: {e}")

    try:
        test_world_bank()
    except Exception as e:
        print(f"\n✗ World Bank 测试失败: {e}")

    # Summary
    print_section("测试完成")
    print("\n下一步:")
    print("  1. 查看详细文档: data_sources/README.md")
    print("  2. 查看使用示例: data_sources/examples.py")
    print("  3. 运行单元测试: pytest tests/test_data_sources.py -v")
    print("  4. 集成到你的代码中")
    print("\n" + "=" * 60 + "\n")


if __name__ == "__main__":
    main()
