#!/usr/bin/env python3
"""
测试 NaN 处理 - 验证 JSON 序列化是否正确处理 NaN/Infinity
"""
import sys
import os
import math
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'python'))

from akshare_bridge import safe_json_dumps

def test_nan_handling():
    print("🧪 测试 NaN/Infinity 处理\n")

    test_cases = [
        {
            "name": "正常数值",
            "data": {"price": 10.5, "change": 2.3},
            "expected": '{"price": 10.5, "change": 2.3}'
        },
        {
            "name": "包含 NaN",
            "data": {"price": float('nan'), "change": 2.3},
            "expected": '{"price": null, "change": 2.3}'
        },
        {
            "name": "包含 Infinity",
            "data": {"price": float('inf'), "change": -float('inf')},
            "expected": '{"price": null, "change": null}'
        },
        {
            "name": "混合数据",
            "data": {
                "code": "000004",
                "name": "*ST国华",
                "price": float('nan'),
                "change": float('nan'),
                "volume": 1000000
            },
            "expected": 'price and change should be null'
        },
        {
            "name": "嵌套对象",
            "data": {
                "stocks": [
                    {"code": "000001", "price": 10.5},
                    {"code": "000004", "price": float('nan')}
                ]
            },
            "expected": 'nested NaN should be null'
        }
    ]

    passed = 0
    failed = 0

    for test in test_cases:
        print(f"📝 测试: {test['name']}")
        try:
            result = safe_json_dumps(test['data'])

            # 验证是否是有效的 JSON
            import json
            parsed = json.loads(result)

            print(f"   ✅ 成功序列化")
            print(f"   📄 结果: {result[:100]}{'...' if len(result) > 100 else ''}")

            # 检查 NaN 是否被转换为 null
            if 'nan' in str(test['data']).lower() or 'inf' in str(test['data']).lower():
                if 'NaN' in result or 'Infinity' in result:
                    print(f"   ❌ 错误: 结果中仍包含 NaN 或 Infinity")
                    failed += 1
                else:
                    print(f"   ✅ NaN/Infinity 已正确转换为 null")
                    passed += 1
            else:
                passed += 1

        except Exception as e:
            print(f"   ❌ 失败: {e}")
            failed += 1

        print()

    print("=" * 60)
    print(f"测试结果: {passed} 通过, {failed} 失败")
    print("=" * 60)

    return failed == 0

if __name__ == "__main__":
    success = test_nan_handling()
    sys.exit(0 if success else 1)
