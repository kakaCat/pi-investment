#!/usr/bin/env python3
"""
通过 API 验证交易模块修复效果

测试修复后的三个方法：
1. GET /api/orders/detail/{id} - 使用 get_order_by_id()
2. POST /api/orders/update/{id} - 使用 update_order()
3. GET /api/trades/list - 使用 get_trades()
"""

import os
import requests
import json
from datetime import datetime

BASE_URL = os.environ.get("QUANTSYS_API_URL", "http://127.0.0.1:5001")


def test_api_health():
    """测试 API 健康状态"""
    print("\n" + "="*60)
    print("预检查: API 健康状态")
    print("="*60)

    try:
        response = requests.get(f"{BASE_URL}/api/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ API 服务正常运行")
            print(f"   数据库连接: {data.get('db_connected', False)}")
            print(f"   版本: {data.get('db_info', {}).get('version', 'unknown')}")
            return True
        else:
            print(f"❌ API 返回错误状态码: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print(f"❌ 无法连接到 API 服务 ({BASE_URL})")
        print(f"   请确保后端服务已启动: cd quantsys-v2 && python -m api.server")
        return False
    except Exception as e:
        print(f"❌ 健康检查失败: {str(e)}")
        return False


def test_get_order_detail():
    """测试 GET /api/orders/detail/{id} - 使用 get_order_by_id()"""
    print("\n" + "="*60)
    print("测试 1: GET /api/orders/detail/{id}")
    print("="*60)

    try:
        # 先创建一个测试订单
        create_data = {
            "symbol": "000001.SZ",
            "action": "buy",
            "orderType": "limit",
            "quantity": 100,
            "price": 10.5,
            "notes": "API测试订单"
        }

        response = requests.post(f"{BASE_URL}/api/orders/create", json=create_data, timeout=10)

        if response.status_code != 200:
            print(f"❌ 创建订单失败: {response.status_code}")
            print(f"   响应: {response.text}")
            return False

        result = response.json()
        if not result.get('success'):
            print(f"❌ 创建订单失败: {result.get('error', 'unknown')}")
            return False

        order_id = result.get('data', {}).get('order_id')
        print(f"✅ 创建测试订单成功，ID: {order_id}")

        # 测试获取订单详情 (使用 get_order_by_id)
        response = requests.get(f"{BASE_URL}/api/orders/detail/{order_id}", timeout=10)

        if response.status_code != 200:
            print(f"❌ 获取订单详情失败: {response.status_code}")
            print(f"   响应: {response.text}")
            return False

        result = response.json()
        if not result.get('success'):
            print(f"❌ 获取订单详情失败: {result.get('error', 'unknown')}")
            return False

        order = result.get('data', {})
        print(f"✅ get_order_by_id() 方法工作正常")
        print(f"   订单信息: {order.get('symbol')} {order.get('action')} {order.get('quantity')}股")
        print(f"   价格: {order.get('price')}, 状态: {order.get('status')}")

        return True

    except Exception as e:
        print(f"❌ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_update_order():
    """测试 POST /api/orders/update/{id} - 使用 update_order()"""
    print("\n" + "="*60)
    print("测试 2: POST /api/orders/update/{id}")
    print("="*60)

    try:
        # 先创建一个测试订单
        create_data = {
            "symbol": "000002.SZ",
            "action": "buy",
            "orderType": "limit",
            "quantity": 200,
            "price": 15.0,
            "notes": "待修改订单"
        }

        response = requests.post(f"{BASE_URL}/api/orders/create", json=create_data, timeout=10)
        result = response.json()

        if not result.get('success'):
            print(f"❌ 创建订单失败: {result.get('error', 'unknown')}")
            return False

        order_id = result.get('data', {}).get('order_id')
        print(f"✅ 创建测试订单成功，ID: {order_id}")
        print(f"   原始: 数量={create_data['quantity']}, 价格={create_data['price']}")

        # 测试更新订单 (使用 update_order)
        update_data = {
            "quantity": 300,
            "price": 16.5,
            "notes": "已通过API修改"
        }

        response = requests.post(f"{BASE_URL}/api/orders/update/{order_id}", json=update_data, timeout=10)

        if response.status_code != 200:
            print(f"❌ 更新订单失败: {response.status_code}")
            print(f"   响应: {response.text}")
            return False

        result = response.json()
        if not result.get('success'):
            print(f"❌ 更新订单失败: {result.get('error', 'unknown')}")
            return False

        updated_order = result.get('data', {}).get('order', {})
        print(f"✅ update_order() 方法工作正常")
        print(f"   更新后: 数量={updated_order.get('quantity')}, 价格={updated_order.get('price')}")
        print(f"   备注: {updated_order.get('notes')}")

        # 验证字段是否正确更新
        if (updated_order.get('quantity') == 300 and
            updated_order.get('price') == 16.5 and
            updated_order.get('notes') == '已通过API修改'):
            print(f"✅ 字段更新验证成功")
            return True
        else:
            print(f"❌ 字段更新验证失败")
            return False

    except Exception as e:
        print(f"❌ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_get_trades_list():
    """测试 GET /api/trades/list - 使用 get_trades()"""
    print("\n" + "="*60)
    print("测试 3: GET /api/trades/list")
    print("="*60)

    try:
        # 测试基本查询
        response = requests.get(f"{BASE_URL}/api/trades/list",
                               params={"page": 1, "pageSize": 10},
                               timeout=10)

        if response.status_code != 200:
            print(f"❌ 获取交易列表失败: {response.status_code}")
            print(f"   响应: {response.text}")
            return False

        result = response.json()
        if not result.get('success'):
            print(f"❌ 获取交易列表失败: {result.get('error', 'unknown')}")
            return False

        data = result.get('data', {})
        items = data.get('items', [])

        print(f"✅ get_trades() 方法工作正常")
        print(f"   返回记录数: {len(items)}")
        print(f"   总记录数: {data.get('total', 0)}")

        if items:
            first_trade = items[0]
            print(f"   最新交易: {first_trade.get('symbol')} {first_trade.get('action')} {first_trade.get('quantity')}股")
        else:
            print(f"   数据库中暂无交易记录")

        # 测试分页
        response2 = requests.get(f"{BASE_URL}/api/trades/list",
                                params={"page": 2, "pageSize": 5},
                                timeout=10)

        if response2.status_code == 200:
            result2 = response2.json()
            if result2.get('success'):
                print(f"✅ 分页查询成功")
                return True

        return True

    except Exception as e:
        print(f"❌ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """运行所有测试"""
    print("\n" + "="*60)
    print("交易模块 API 修复验证测试")
    print("="*60)
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"API地址: {BASE_URL}")

    # 预检查
    if not test_api_health():
        print("\n" + "="*60)
        print("❌ API 服务未运行，测试终止")
        print("="*60)
        return False

    results = []

    # 运行测试
    results.append(("GET /api/orders/detail/{id}", test_get_order_detail()))
    results.append(("POST /api/orders/update/{id}", test_update_order()))
    results.append(("GET /api/trades/list", test_get_trades_list()))

    # 汇总结果
    print("\n" + "="*60)
    print("测试结果汇总")
    print("="*60)

    passed = 0
    failed = 0

    for test_name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{test_name:40s} {status}")
        if result:
            passed += 1
        else:
            failed += 1

    print("\n" + "-"*60)
    print(f"总计: {len(results)} 个测试")
    print(f"通过: {passed} 个")
    print(f"失败: {failed} 个")
    print(f"成功率: {passed/len(results)*100:.1f}%")
    print("="*60 + "\n")

    return failed == 0


if __name__ == '__main__':
    import sys
    success = main()
    sys.exit(0 if success else 1)
