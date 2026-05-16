#!/usr/bin/env python3
"""
测试 Python 端超时装饰器
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'python'))

from akshare_bridge import get_macro_data, get_market_news, get_stock_fund_flow
import time

def test_timeout_decorator():
    print("🧪 测试 Python 端超时装饰器\n")

    tests = [
        ("get_macro_data", lambda: get_macro_data(["pmi"]), 50),
        ("get_market_news", lambda: get_market_news(5), 50),
        ("get_stock_fund_flow", lambda: get_stock_fund_flow("600519"), 30),
    ]

    for name, func, expected_timeout in tests:
        print(f"📝 测试 {name} (预期超时: {expected_timeout}秒)")
        start = time.time()

        try:
            result = func()
            elapsed = time.time() - start

            if isinstance(result, dict) and result.get('error'):
                print(f"   ⚠️  返回错误: {result['error']}")
            else:
                print(f"   ✅ 成功")

            print(f"   ⏱️  耗时: {elapsed:.2f}秒")

        except TimeoutError as e:
            elapsed = time.time() - start
            print(f"   ⏱️  超时: {elapsed:.2f}秒")
            print(f"   ✅ 超时装饰器生效")
        except Exception as e:
            elapsed = time.time() - start
            print(f"   ❌ 异常: {e}")
            print(f"   ⏱️  耗时: {elapsed:.2f}秒")

        print()

if __name__ == "__main__":
    test_timeout_decorator()
