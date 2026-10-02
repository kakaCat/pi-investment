#!/usr/bin/env python3
"""
测试 /api/stocks/resolve API 修复

修复的问题：
1. resolve_stock() - Stock对象用字典方式访问
2. enrich_stock_data() - Stock对象用字典方式访问
3. get_stock_list() - Stock对象用字典方式访问（过滤和搜索）

修复方法：
- 将 stock['symbol'] 改为 stock.symbol
- enrich_stock_data() 支持Dict和ORM对象两种类型
- get_stock_list() 的过滤逻辑同时支持两种类型
"""
import requests
import json

BASE_URL = "http://127.0.0.1:5001"

def test_resolve_stock():
    """测试股票解析API"""
    print("Testing /api/stocks/resolve...")

    # 测试存在的股票
    response = requests.post(
        f"{BASE_URL}/api/stocks/resolve",
        json={"code": "600519"},
        headers={"Content-Type": "application/json"}
    )

    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")

    if response.status_code == 200:
        data = response.json()
        assert data.get('found') == True
        assert 'symbol' in data
        assert 'name' in data
        print("✅ Test passed: resolve_stock works correctly")
    else:
        print(f"❌ Test failed: {response.json()}")

    # 测试不存在的股票
    response = requests.post(
        f"{BASE_URL}/api/stocks/resolve",
        json={"code": "999999"},
        headers={"Content-Type": "application/json"}
    )
    print(f"\nNon-existent stock status: {response.status_code}")
    if response.status_code == 404:
        print("✅ Test passed: 404 for non-existent stock")

def test_search_stocks():
    """测试股票搜索API"""
    print("\n\nTesting /api/stocks/search...")

    response = requests.get(
        f"{BASE_URL}/api/stocks/search",
        params={"q": "贵州茅台", "pageSize": 5}
    )

    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"Found {data.get('total', 0)} stocks")
        if data.get('stocks'):
            print(f"First result: {data['stocks'][0]}")
            print("✅ Test passed: search_stocks works correctly")
    else:
        print(f"❌ Test failed: {response.json()}")

def test_list_stocks():
    """测试股票列表API"""
    print("\n\nTesting /api/stocks/list...")

    response = requests.get(
        f"{BASE_URL}/api/stocks/list",
        params={"market": "A", "pageSize": 5}
    )

    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"Total count: {data.get('count', 0)}")
        if data.get('stocks'):
            print(f"First result: {data['stocks'][0]}")
            print("✅ Test passed: list_stocks works correctly")
    else:
        print(f"❌ Test failed: {response.json()}")

if __name__ == "__main__":
    print("=" * 60)
    print("Stock API Fix Verification")
    print("=" * 60)

    try:
        test_resolve_stock()
        test_search_stocks()
        test_list_stocks()
    except requests.exceptions.ConnectionError:
        print("\n❌ Cannot connect to API server at", BASE_URL)
        print("Please start the server first:")
        print("  cd quantsys-v2")
        print("  python adapters/inbound/api/server.py")
    except Exception as e:
        print(f"\n❌ Error: {e}")
