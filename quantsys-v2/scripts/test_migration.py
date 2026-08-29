#!/usr/bin/env python3
"""快速验证 P1-2 迁移"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_services_can_import():
    """测试服务层是否能正常导入"""
    print("1. 测试服务层导入...")

    try:
        from application.services.financial_analysis_service import FinancialAnalysisService
        print("   ✅ FinancialAnalysisService")
    except Exception as e:
        print(f"   ❌ FinancialAnalysisService: {e}")
        return False

    try:
        from application.services.hk_market_data_service import HKMarketDataService
        print("   ✅ HKMarketDataService")
    except Exception as e:
        print(f"   ❌ HKMarketDataService: {e}")
        return False

    try:
        from application.services.market_data_service import MarketDataService
        print("   ✅ MarketDataService")
    except Exception as e:
        print(f"   ❌ MarketDataService: {e}")
        return False

    try:
        from application.services.stock_data_service import StockDataService
        print("   ✅ StockDataService")
    except Exception as e:
        print(f"   ❌ StockDataService: {e}")
        return False

    try:
        from application.services.strategy_code_service import StrategyCodeService
        print("   ✅ StrategyCodeService")
    except Exception as e:
        print(f"   ❌ StrategyCodeService: {e}")
        return False

    try:
        from application.services.valuation_data_service import ValuationDataService
        print("   ✅ ValuationDataService")
    except Exception as e:
        print(f"   ❌ ValuationDataService: {e}")
        return False

    return True

def test_provider_manager():
    """测试 DataProviderManager 是否能正常工作"""
    print("\n2. 测试 DataProviderManager...")

    try:
        from adapters.outbound.datasources import get_data_provider_manager
        provider_manager = get_data_provider_manager()
        print(f"   ✅ DataProviderManager 实例化成功")
        print(f"   ✅ 类型: {type(provider_manager).__name__}")
        return True
    except Exception as e:
        print(f"   ❌ DataProviderManager: {e}")
        return False

def test_infrastructure_job():
    """测试基础设施层 Job 是否能正常导入"""
    print("\n3. 测试基础设施层...")

    try:
        from infrastructure.jobs import index_constituents_update_job
        print("   ✅ index_constituents_update_job")
        return True
    except Exception as e:
        print(f"   ❌ index_constituents_update_job: {e}")
        return False

def main():
    print("=" * 70)
    print("P1-2 迁移验证测试")
    print("=" * 70)

    results = []

    results.append(("服务层导入", test_services_can_import()))
    results.append(("DataProviderManager", test_provider_manager()))
    results.append(("基础设施层", test_infrastructure_job()))

    print("\n" + "=" * 70)
    print("测试结果汇总")
    print("=" * 70)

    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {name}")

    all_passed = all(result[1] for result in results)

    print("\n" + "=" * 70)
    if all_passed:
        print("🎉 所有测试通过！迁移成功！")
        return 0
    else:
        print("⚠️  部分测试失败，请检查错误信息")
        return 1

if __name__ == "__main__":
    sys.exit(main())
