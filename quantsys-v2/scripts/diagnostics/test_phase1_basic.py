"""
简化测试脚本 - Phase 1 基本验证
只测试类实例化和基本方法，不进行网络请求
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

from adapters.outbound.datasources.sources import IMFSource, OECDSource, BISSource, ECBSource, BOJSource


def test_instantiation():
    """测试所有数据源是否可以正常实例化"""
    print("\n" + "="*60)
    print("Phase 1 基本验证 - 类实例化测试")
    print("="*60)

    results = {}

    # Test IMF
    print("\n1. 测试 IMF 实例化...")
    try:
        imf = IMFSource()
        print(f"   ✅ IMFSource 实例化成功")
        print(f"   - 名称: {imf.name}")
        print(f"   - 需要 API Key: {imf.requires_api_key}")
        results["IMF"] = True
    except Exception as e:
        print(f"   ❌ IMFSource 实例化失败: {e}")
        results["IMF"] = False

    # Test OECD
    print("\n2. 测试 OECD 实例化...")
    try:
        oecd = OECDSource()
        print(f"   ✅ OECDSource 实例化成功")
        print(f"   - 名称: {oecd.name}")
        print(f"   - 需要 API Key: {oecd.requires_api_key}")
        results["OECD"] = True
    except Exception as e:
        print(f"   ❌ OECDSource 实例化失败: {e}")
        results["OECD"] = False

    # Test BIS
    print("\n3. 测试 BIS 实例化...")
    try:
        bis = BISSource()
        print(f"   ✅ BISSource 实例化成功")
        print(f"   - 名称: {bis.name}")
        print(f"   - 需要 API Key: {bis.requires_api_key}")
        results["BIS"] = True
    except Exception as e:
        print(f"   ❌ BISSource 实例化失败: {e}")
        results["BIS"] = False

    # Test ECB
    print("\n4. 测试 ECB 实例化...")
    try:
        ecb = ECBSource()
        print(f"   ✅ ECBSource 实例化成功")
        print(f"   - 名称: {ecb.name}")
        print(f"   - 需要 API Key: {ecb.requires_api_key}")
        results["ECB"] = True
    except Exception as e:
        print(f"   ❌ ECBSource 实例化失败: {e}")
        results["ECB"] = False

    # Test BOJ
    print("\n5. 测试 BOJ 实例化...")
    try:
        boj = BOJSource()
        print(f"   ✅ BOJSource 实例化成功")
        print(f"   - 名称: {boj.name}")
        print(f"   - 需要 API Key: {boj.requires_api_key}")
        results["BOJ"] = True
    except Exception as e:
        print(f"   ❌ BOJSource 实例化失败: {e}")
        results["BOJ"] = False

    # Summary
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
        print("\n🎉 所有数据源类实例化成功！")
        print("✅ Phase 1 代码迁移验证通过")
        print("\n⚠️  注意: 网络连接测试需要在有网络的环境中进行")
        return 0
    else:
        print(f"\n⚠️  {total - passed} 个数据源实例化失败")
        return 1


def test_abstract_methods():
    """测试抽象方法是否已实现"""
    print("\n" + "="*60)
    print("抽象方法实现验证")
    print("="*60)

    sources = {
        "IMF": IMFSource(),
        "OECD": OECDSource(),
        "BIS": BISSource(),
        "ECB": ECBSource(),
        "BOJ": BOJSource(),
    }

    required_methods = ["get_series", "search_series", "validate_config", "test_connection"]

    all_passed = True
    for name, source in sources.items():
        print(f"\n{name}:")
        for method in required_methods:
            if hasattr(source, method) and callable(getattr(source, method)):
                print(f"   ✅ {method}()")
            else:
                print(f"   ❌ {method}() - 未实现")
                all_passed = False

    if all_passed:
        print("\n✅ 所有必需方法都已实现")
    else:
        print("\n❌ 部分方法未实现")

    return 0 if all_passed else 1


if __name__ == "__main__":
    result1 = test_instantiation()
    result2 = test_abstract_methods()
    sys.exit(max(result1, result2))
