"""
统一测试脚本 - Phase 1 宏观经济数据源
测试所有新迁移的数据源：IMF, OECD, BIS, ECB, BOJ
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

from adapters.outbound.datasources.sources import IMFSource, OECDSource, BISSource, ECBSource, BOJSource


def test_imf():
    """测试 IMF 数据源"""
    print("\n" + "="*60)
    print("测试 IMF (国际货币基金组织)")
    print("="*60)

    imf = IMFSource()

    # 1. 测试连接
    print("\n1. 测试连接...")
    result = imf.test_connection()
    print(f"   连接状态: {'✅ 成功' if result.success else '❌ 失败'}")
    if not result.success:
        print(f"   错误: {result.error}")
        return False

    # 2. 测试经济指标
    print("\n2. 测试经济指标 (美国储备资产)...")
    result = imf.get_economic_indicators(
        countries="US",
        symbols="reserve_assets",
        frequency="quarter"
    )
    print(f"   状态: {'✅ 成功' if result.success else '❌ 失败'}")
    print(f"   数据量: {result.count} 条")

    # 3. 测试贸易统计
    print("\n3. 测试贸易统计 (美国出口)...")
    result = imf.get_direction_of_trade(
        countries="US",
        direction="exports",
        frequency="annual"
    )
    print(f"   状态: {'✅ 成功' if result.success else '❌ 失败'}")
    print(f"   数据量: {result.count} 条")

    return True


def test_oecd():
    """测试 OECD 数据源"""
    print("\n" + "="*60)
    print("测试 OECD (经合组织)")
    print("="*60)

    oecd = OECDSource()

    # 1. 测试连接
    print("\n1. 测试连接...")
    result = oecd.test_connection()
    print(f"   连接状态: {'✅ 成功' if result.success else '❌ 失败'}")
    if not result.success:
        print(f"   错误: {result.error}")
        return False

    # 2. 测试 GDP 数据
    print("\n2. 测试 GDP 数据 (美国季度)...")
    result = oecd.get_gdp(countries="USA", frequency="Q")
    print(f"   状态: {'✅ 成功' if result.success else '❌ 失败'}")
    print(f"   数据量: {result.count} 条")

    # 3. 测试 CPI 数据
    print("\n3. 测试 CPI 数据 (美国月度)...")
    result = oecd.get_cpi(countries="USA", frequency="M")
    print(f"   状态: {'✅ 成功' if result.success else '❌ 失败'}")
    print(f"   数据量: {result.count} 条")

    return True


def test_bis():
    """测试 BIS 数据源"""
    print("\n" + "="*60)
    print("测试 BIS (国际清算银行)")
    print("="*60)

    bis = BISSource()

    # 1. 测试连接
    print("\n1. 测试连接...")
    result = bis.test_connection()
    print(f"   连接状态: {'✅ 成功' if result.success else '❌ 失败'}")
    if not result.success:
        print(f"   错误: {result.error}")
        return False

    # 2. 测试数据集列表
    print("\n2. 测试数据集列表...")
    result = bis.list_datasets()
    print(f"   状态: {'✅ 成功' if result.success else '❌ 失败'}")
    print(f"   可用数据集: {result.count} 个")

    return True


def test_ecb():
    """测试 ECB 数据源"""
    print("\n" + "="*60)
    print("测试 ECB (欧洲央行)")
    print("="*60)

    ecb = ECBSource()

    # 1. 测试连接
    print("\n1. 测试连接...")
    result = ecb.test_connection()
    print(f"   连接状态: {'✅ 成功' if result.success else '❌ 失败'}")
    if not result.success:
        print(f"   错误: {result.error}")
        return False

    # 2. 测试汇率数据
    print("\n2. 测试汇率数据 (EUR/USD 日度)...")
    result = ecb.get_exchange_rates(currencies="USD", frequency="D")
    print(f"   状态: {'✅ 成功' if result.success else '❌ 失败'}")
    print(f"   数据量: {result.count} 条")

    return True


def test_boj():
    """测试 BOJ 数据源"""
    print("\n" + "="*60)
    print("测试 BOJ (日本央行)")
    print("="*60)

    boj = BOJSource()

    # 1. 测试连接
    print("\n1. 测试连接...")
    result = boj.test_connection()
    print(f"   连接状态: {'✅ 成功' if result.success else '❌ 失败'}")
    if not result.success:
        print(f"   错误: {result.error}")
        return False

    # 2. 测试汇率数据
    print("\n2. 测试汇率数据 (USD/JPY)...")
    result = boj.get_exchange_rate(currency="USD")
    print(f"   状态: {'✅ 成功' if result.success else '❌ 失败'}")
    print(f"   数据量: {result.count} 条")

    return True


def main():
    """运行所有测试"""
    print("\n" + "="*60)
    print("Phase 1 数据源迁移 - 统一测试")
    print("="*60)
    print("\n测试 5 个新迁移的宏观经济数据源...")

    results = {
        "IMF": False,
        "OECD": False,
        "BIS": False,
        "ECB": False,
        "BOJ": False,
    }

    # 运行测试
    try:
        results["IMF"] = test_imf()
    except Exception as e:
        print(f"\n❌ IMF 测试失败: {e}")

    try:
        results["OECD"] = test_oecd()
    except Exception as e:
        print(f"\n❌ OECD 测试失败: {e}")

    try:
        results["BIS"] = test_bis()
    except Exception as e:
        print(f"\n❌ BIS 测试失败: {e}")

    try:
        results["ECB"] = test_ecb()
    except Exception as e:
        print(f"\n❌ ECB 测试失败: {e}")

    try:
        results["BOJ"] = test_boj()
    except Exception as e:
        print(f"\n❌ BOJ 测试失败: {e}")

    # 汇总结果
    print("\n" + "="*60)
    print("测试结果汇总")
    print("="*60)

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for name, success in results.items():
        status = "✅ 通过" if success else "❌ 失败"
        print(f"{name:10s}: {status}")

    print(f"\n总计: {passed}/{total} 通过 ({passed/total*100:.0f}%)")

    if passed == total:
        print("\n🎉 所有测试通过！Phase 1 迁移成功！")
        return 0
    else:
        print(f"\n⚠️  {total - passed} 个数据源测试失败，请检查错误信息")
        return 1


if __name__ == "__main__":
    sys.exit(main())
