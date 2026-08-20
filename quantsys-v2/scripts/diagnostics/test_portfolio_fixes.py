#!/usr/bin/env python3
"""
验证 PortfolioRepository 修复后的方法

测试三个新增/修复的方法：
1. get_order_by_id() - 别名方法
2. update_order() - 通用更新方法
3. get_trades() - 分页查询方法
"""

import sys
import os
from datetime import datetime

# 添加项目路径

from adapters.outbound.repositories import PortfolioORMRepository


def test_get_order_by_id():
    """测试 get_order_by_id() 方法"""
    print("\n" + "="*60)
    print("测试 1: get_order_by_id() 方法")
    print("="*60)

    repo = PortfolioORMRepository()

    try:
        # 先创建一个测试订单
        order_data = {
            'symbol': '000001.SZ',
            'name': '平安银行',
            'order_type': 'limit',
            'action': 'buy',
            'price': 10.5,
            'quantity': 100,
            'status': 'pending',
            'filled_quantity': 0,
            'avg_filled_price': 0.0,
            'reason': '测试订单',
            'signal_id': None,
            'expires_at': None
        }

        order_id = repo.create_order(order_data)
        print(f"✅ 创建测试订单成功，ID: {order_id}")

        # 测试 get_order_by_id()
        order = repo.get_order_by_id(order_id)

        if order:
            print(f"✅ get_order_by_id() 调用成功")
            print(f"   订单信息: {order['symbol']} {order['action']} {order['quantity']}股 @ {order['price']}")
            print(f"   状态: {order['status']}")
            return True
        else:
            print(f"❌ get_order_by_id() 返回 None")
            return False

    except Exception as e:
        print(f"❌ 测试失败: {str(e)}")
        return False


def test_update_order():
    """测试 update_order() 方法"""
    print("\n" + "="*60)
    print("测试 2: update_order() 方法")
    print("="*60)

    repo = PortfolioORMRepository()

    try:
        # 先创建一个测试订单
        order_data = {
            'symbol': '000002.SZ',
            'name': '万科A',
            'order_type': 'limit',
            'action': 'buy',
            'price': 15.0,
            'quantity': 200,
            'status': 'pending',
            'filled_quantity': 0,
            'avg_filled_price': 0.0,
            'reason': '测试订单',
            'signal_id': None,
            'expires_at': None
        }

        order_id = repo.create_order(order_data)
        print(f"✅ 创建测试订单成功，ID: {order_id}")
        print(f"   原始数据: 数量={order_data['quantity']}, 价格={order_data['price']}")

        # 测试更新订单
        update_fields = {
            'quantity': 300,
            'price': 16.5,
            'notes': '已修改'
        }

        success = repo.update_order(order_id, update_fields)

        if success:
            print(f"✅ update_order() 调用成功")

            # 验证更新结果
            updated_order = repo.get_order(order_id)
            print(f"   更新后数据: 数量={updated_order['quantity']}, 价格={updated_order['price']}")
            print(f"   备注: {updated_order.get('notes', 'N/A')}")

            # 验证字段是否正确更新
            if (updated_order['quantity'] == 300 and
                updated_order['price'] == 16.5 and
                updated_order.get('notes') == '已修改'):
                print(f"✅ 字段更新验证成功")
                return True
            else:
                print(f"❌ 字段更新验证失败")
                return False
        else:
            print(f"❌ update_order() 返回 False")
            return False

    except Exception as e:
        print(f"❌ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_get_trades():
    """测试 get_trades() 方法"""
    print("\n" + "="*60)
    print("测试 3: get_trades() 方法")
    print("="*60)

    repo = PortfolioORMRepository()

    try:
        # 测试基本查询
        trades = repo.get_trades(limit=10, offset=0)

        print(f"✅ get_trades() 调用成功")
        print(f"   返回记录数: {len(trades)}")

        if trades:
            print(f"   最新交易: {trades[0]['symbol']} {trades[0]['action']} {trades[0]['quantity']}股")
            print(f"   交易日期: {trades[0]['trade_date']}")
        else:
            print(f"   数据库中暂无交易记录")

        # 测试分页
        trades_page2 = repo.get_trades(limit=5, offset=5)
        print(f"✅ 分页查询成功，第2页记录数: {len(trades_page2)}")

        return True

    except Exception as e:
        print(f"❌ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_field_whitelist():
    """测试字段白名单验证"""
    print("\n" + "="*60)
    print("测试 4: update_order() 字段白名单验证")
    print("="*60)

    repo = PortfolioORMRepository()

    try:
        # 创建测试订单
        order_data = {
            'symbol': '600000.SH',
            'name': '浦发银行',
            'order_type': 'limit',
            'action': 'buy',
            'price': 8.0,
            'quantity': 100,
            'status': 'pending',
            'filled_quantity': 0,
            'avg_filled_price': 0.0,
            'reason': '测试订单',
            'signal_id': None,
            'expires_at': None
        }

        order_id = repo.create_order(order_data)
        print(f"✅ 创建测试订单成功，ID: {order_id}")

        # 测试非法字段（应该被过滤）
        update_fields = {
            'quantity': 200,
            'invalid_field': 'should be filtered',  # 非法字段
            'symbol': '999999.SZ'  # 不允许修改的字段
        }

        success = repo.update_order(order_id, update_fields)

        if success:
            updated_order = repo.get_order(order_id)

            # 验证只有合法字段被更新
            if updated_order['quantity'] == 200 and updated_order['symbol'] == '600000.SH':
                print(f"✅ 字段白名单验证成功")
                print(f"   quantity 已更新: {updated_order['quantity']}")
                print(f"   symbol 未被修改: {updated_order['symbol']}")
                return True
            else:
                print(f"❌ 字段白名单验证失败")
                return False
        else:
            print(f"❌ update_order() 返回 False")
            return False

    except Exception as e:
        print(f"❌ 测试失败: {str(e)}")
        return False


def main():
    """运行所有测试"""
    print("\n" + "="*60)
    print("PortfolioRepository 修复验证测试")
    print("="*60)
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    results = []

    # 运行测试
    results.append(("get_order_by_id()", test_get_order_by_id()))
    results.append(("update_order()", test_update_order()))
    results.append(("get_trades()", test_get_trades()))
    results.append(("字段白名单验证", test_field_whitelist()))

    # 汇总结果
    print("\n" + "="*60)
    print("测试结果汇总")
    print("="*60)

    passed = 0
    failed = 0

    for test_name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{test_name:30s} {status}")
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
    success = main()
    sys.exit(0 if success else 1)
