#!/usr/bin/env python3
"""
诊断指标IDE页面的问题

检查：
1. 指标名称不显示
2. 系统指标不显示
3. 搜索功能无效
4. K线图表不显示
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from application.services.strategy_code_service import StrategyCodeService
import json


def diagnose_indicator_list():
    """诊断指标列表问题"""
    print("=" * 70)
    print("诊断 1: 指标列表数据结构")
    print("=" * 70)

    service = StrategyCodeService()

    try:
        # 获取所有指标
        all_indicators = service.list_strategies(code_type='indicator')
        print(f"\n✓ 找到 {len(all_indicators)} 个指标")

        if len(all_indicators) > 0:
            # 检查第一个指标的数据结构
            first = all_indicators[0]
            print(f"\n第一个指标的数据结构:")
            print(f"  ID: {first.get('id')}")
            print(f"  strategy_name: {first.get('strategy_name')}")
            print(f"  name: {first.get('name')}")
            print(f"  code_type: {first.get('code_type')}")
            print(f"  strategy_type: {first.get('strategy_type')}")
            print(f"  category: {first.get('category')}")
            print(f"  is_public: {first.get('is_public')}")
            print(f"  validation_status: {first.get('validation_status')}")

            # 检查字段映射问题
            print(f"\n⚠️  问题分析:")
            if 'name' not in first and 'strategy_name' in first:
                print(f"  - 后端返回 'strategy_name'，但前端期望 'name'")
            if 'codeContent' not in first and 'code_content' in first:
                print(f"  - 后端返回 'code_content'，但前端期望 'codeContent'")

            # 检查分类过滤
            my_indicators = [i for i in all_indicators if i.get('strategy_type') == 'custom']
            system_indicators = [i for i in all_indicators if i.get('strategy_type') != 'custom']

            print(f"\n分类统计:")
            print(f"  我的指标 (strategy_type='custom'): {len(my_indicators)}")
            print(f"  系统指标 (strategy_type!='custom'): {len(system_indicators)}")

            if len(system_indicators) == 0:
                print(f"\n⚠️  问题: 没有系统指标！")
                print(f"  原因: 所有指标的 strategy_type 都是 'custom' 或为空")
                print(f"  解决方案: 需要创建系统内置指标，或修改过滤逻辑")

        else:
            print(f"\n⚠️  问题: 数据库中没有任何指标！")
            print(f"  解决方案: 需要先创建一些指标")

    except Exception as e:
        print(f"\n✗ 获取指标列表失败: {str(e)}")
        import traceback
        traceback.print_exc()


def diagnose_api_response_format():
    """诊断API响应格式"""
    print("\n" + "=" * 70)
    print("诊断 2: API 响应格式")
    print("=" * 70)

    print("\n后端 API 响应格式 (server.py:3625-3630):")
    print("""
    {
        'total': total,
        'page': page,
        'page_size': page_size,  # ⚠️ 下划线命名
        'items': indicators_page
    }
    """)

    print("\n经过 api_response() 转换后 (驼峰命名):")
    print("""
    {
        'total': total,
        'page': page,
        'pageSize': page_size,  # ✓ 驼峰命名
        'items': indicators_page
    }
    """)

    print("\n前端期望格式 (indicator.ts:62-63):")
    print("""
    .then(response => (response as any).items ?? [])
    """)

    print("\n✓ API 响应格式正确")


def diagnose_field_mapping():
    """诊断字段映射问题"""
    print("\n" + "=" * 70)
    print("诊断 3: 字段映射问题")
    print("=" * 70)

    print("\n数据库字段 -> 后端返回 -> 前端期望:")
    print("-" * 70)

    mappings = [
        ("strategy_name", "strategyName", "name", "❌ 不匹配"),
        ("code_content", "codeContent", "codeContent", "✓ 匹配"),
        ("code_type", "codeType", "codeType", "✓ 匹配"),
        ("strategy_type", "strategyType", "strategyType", "✓ 匹配"),
        ("is_public", "isPublic", "isPublic", "✓ 匹配"),
    ]

    for db_field, backend_field, frontend_field, status in mappings:
        print(f"  {db_field:20s} -> {backend_field:20s} -> {frontend_field:20s} {status}")

    print("\n⚠️  关键问题:")
    print("  - 数据库字段 'strategy_name' 转换为 'strategyName'")
    print("  - 但前端期望 'name' 字段")
    print("  - 导致指标名称不显示")


def diagnose_chart_issue():
    """诊断图表问题"""
    print("\n" + "=" * 70)
    print("诊断 4: K线图表不显示问题")
    print("=" * 70)

    print("\n当前实现 (index.vue:724-777):")
    print("  - 图表类型: 柱状图 (bar)")
    print("  - 数据来源: result.indicators (指标因子值)")
    print("  - 显示内容: 各个技术指标的数值")

    print("\n⚠️  问题:")
    print("  - 没有显示K线图 (candlestick)")
    print("  - 没有获取K线数据 (OHLC)")
    print("  - 只显示指标计算结果的柱状图")

    print("\n解决方案:")
    print("  1. 后端 API 需要返回K线数据 (open, high, low, close)")
    print("  2. 前端需要使用 ECharts candlestick 类型")
    print("  3. 在K线图上叠加指标线")


def main():
    """主诊断流程"""
    print("\n" + "=" * 70)
    print("指标IDE页面问题诊断")
    print("=" * 70)

    diagnose_indicator_list()
    diagnose_api_response_format()
    diagnose_field_mapping()
    diagnose_chart_issue()

    print("\n" + "=" * 70)
    print("诊断总结")
    print("=" * 70)

    print("\n发现的问题:")
    print("  1. ❌ 指标名称不显示: 字段映射错误 (strategyName vs name)")
    print("  2. ❌ 系统指标不显示: 没有系统内置指标数据")
    print("  3. ✓ 搜索功能: 前端逻辑正确，但因为名称字段错误导致搜索无效")
    print("  4. ❌ K线图表不显示: 当前只显示柱状图，未实现K线图")

    print("\n修复优先级:")
    print("  [高] 修复字段映射: strategyName -> name")
    print("  [高] 创建系统内置指标")
    print("  [中] 实现K线图显示功能")


if __name__ == '__main__':
    main()
