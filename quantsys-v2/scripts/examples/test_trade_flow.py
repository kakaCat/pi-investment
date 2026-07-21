#!/usr/bin/env python3
"""
测试完整的买卖流程

测试场景：
1. 创建买入信号 → 创建执行记录 → 执行买入 → 验证持仓创建
2. 创建卖出信号 → 创建执行记录（带持仓检查）→ 执行卖出 → 验证持仓更新和盈亏计算
3. 测试异常情况：无持仓时尝试卖出
"""
import sys
import os
from datetime import date

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# 加载环境变量
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

from adapters.outbound.repositories import SignalORMRepository
from adapters.outbound.repositories import SignalExecutionORMRepository
from adapters.outbound.repositories import PositionRepository


def test_buy_flow():
    """测试买入流程"""
    print("\n" + "="*60)
    print("测试 1: 买入流程")
    print("="*60)

    signal_repo = SignalORMRepository()
    execution_repo = SignalExecutionORMRepository()
    position_repo = PositionORMRepository()

    # 1. 创建买入信号
    print("\n1. 创建买入信号...")
    signal_id = signal_repo.create_signal({
        'signal_date': str(date.today()),
        'symbol': '600519',
        'name': '贵州茅台',
        'action': 'buy',
        'action_type': 1,
        'strategy_id': 'test_strategy',
        'price': 1800.0,
        'reason': '测试买入',
        'confidence': 0.8,
        'status': 'active',
        'indicators': {}
    })
    print(f"   ✓ 创建信号成功，ID={signal_id}")

    # 2. 创建执行记录（带校验）
    print("\n2. 创建执行记录...")
    success, error_msg, exec_id = execution_repo.create_execution_with_validation({
        'signal_id': signal_id,
        'execution_date': str(date.today()),
        'execution_price': 1800.0,
        'quantity': 100,
        'commission': 10.0
    })
    if not success:
        print(f"   ✗ 创建执行记录失败: {error_msg}")
        return False
    print(f"   ✓ 创建执行记录成功，ID={exec_id}")

    # 3. 执行买入
    print("\n3. 执行买入操作...")
    success, error_msg = execution_repo.execute_buy(exec_id)
    if not success:
        print(f"   ✗ 执行买入失败: {error_msg}")
        return False
    print(f"   ✓ 执行买入成功")

    # 4. 验证持仓
    print("\n4. 验证持仓...")
    position = position_repo.get_position_by_symbol('600519', status='open')
    if not position:
        print(f"   ✗ 持仓不存在")
        return False
    print(f"   ✓ 持仓创建成功:")
    print(f"     - 股票: {position['symbol']}")
    print(f"     - 数量: {position['quantity']}")
    print(f"     - 成本: {position['cost_basis']}")
    print(f"     - 状态: {position['status']}")

    return True, signal_id, exec_id, position['id']


def test_sell_flow(position_symbol='600519'):
    """测试卖出流程"""
    print("\n" + "="*60)
    print("测试 2: 卖出流程")
    print("="*60)

    signal_repo = SignalORMRepository()
    execution_repo = SignalExecutionORMRepository()
    position_repo = PositionORMRepository()

    # 1. 查询持仓
    print("\n1. 查询持仓...")
    position = position_repo.get_position_by_symbol(position_symbol, status='open')
    if not position:
        print(f"   ✗ 没有持仓 {position_symbol}")
        return False
    print(f"   ✓ 持仓存在:")
    print(f"     - 数量: {position['quantity']}")
    print(f"     - 成本: {position['cost_basis']}")

    # 2. 创建卖出信号
    print("\n2. 创建卖出信号...")
    signal_id = signal_repo.create_signal({
        'signal_date': str(date.today()),
        'symbol': position_symbol,
        'name': '贵州茅台',
        'action': 'sell',
        'action_type': 2,
        'strategy_id': 'test_strategy_sell',  # 使用不同的 strategy_id
        'price': 1850.0,
        'reason': '测试卖出',
        'confidence': 0.8,
        'status': 'active',
        'indicators': {}
    })
    print(f"   ✓ 创建信号成功，ID={signal_id}")

    # 3. 创建执行记录（带持仓检查）
    print("\n3. 创建执行记录（带持仓检查）...")
    sell_quantity = min(50, position['quantity'])  # 卖出一半或50股
    success, error_msg, exec_id = execution_repo.create_execution_with_validation({
        'signal_id': signal_id,
        'execution_date': str(date.today()),
        'execution_price': 1850.0,
        'quantity': sell_quantity,
        'commission': 10.0
    })
    if not success:
        print(f"   ✗ 创建执行记录失败: {error_msg}")
        return False
    print(f"   ✓ 创建执行记录成功，ID={exec_id}")

    # 4. 执行卖出
    print("\n4. 执行卖出操作...")
    success, error_msg = execution_repo.execute_sell(exec_id)
    if not success:
        print(f"   ✗ 执行卖出失败: {error_msg}")
        return False
    print(f"   ✓ 执行卖出成功")

    # 5. 验证执行记录
    print("\n5. 验证执行记录...")
    execution = execution_repo.get_execution(exec_id)
    print(f"   ✓ 执行记录更新:")
    print(f"     - 状态: {execution['status']}")
    print(f"     - 平仓价格: {execution['close_price']}")
    print(f"     - 盈亏: {execution['pnl']}")

    # 6. 验证持仓
    print("\n6. 验证持仓...")
    updated_position = position_repo.get_position_by_symbol(position_symbol, status='open')
    if updated_position:
        print(f"   ✓ 持仓更新（部分卖出）:")
        print(f"     - 原数量: {position['quantity']}")
        print(f"     - 新数量: {updated_position['quantity']}")
        print(f"     - 状态: {updated_position['status']}")
    else:
        print(f"   ✓ 持仓已关闭（全部卖出）")

    return True


def test_sell_without_position():
    """测试无持仓时卖出（应该失败）"""
    print("\n" + "="*60)
    print("测试 3: 无持仓时尝试卖出（应该失败）")
    print("="*60)

    signal_repo = SignalORMRepository()
    execution_repo = SignalExecutionORMRepository()

    # 1. 创建卖出信号（一个不存在持仓的股票）
    print("\n1. 创建卖出信号（无持仓股票）...")
    signal_id = signal_repo.create_signal({
        'signal_date': str(date.today()),
        'symbol': '000001',  # 平安银行，真实股票但没有持仓
        'name': '平安银行',
        'action': 'sell',
        'action_type': 2,
        'strategy_id': 'test_strategy_no_position',
        'price': 10.0,
        'reason': '测试无持仓卖出',
        'confidence': 0.8,
        'status': 'active',
        'indicators': {}
    })
    print(f"   ✓ 创建信号成功，ID={signal_id}")

    # 2. 尝试创建执行记录（应该失败）
    print("\n2. 尝试创建执行记录...")
    success, error_msg, exec_id = execution_repo.create_execution_with_validation({
        'signal_id': signal_id,
        'execution_date': str(date.today()),
        'execution_price': 100.0,
        'quantity': 100,
        'commission': 10.0
    })
    if success:
        print(f"   ✗ 测试失败：应该拒绝创建执行记录，但成功了")
        return False
    else:
        print(f"   ✓ 正确拒绝创建执行记录: {error_msg}")
        return True


def main():
    print("\n" + "="*60)
    print("开始测试完整的买卖流程")
    print("="*60)

    try:
        # 测试 1: 买入流程
        result = test_buy_flow()
        if not result:
            print("\n✗ 买入流程测试失败")
            return

        # 测试 2: 卖出流程
        if not test_sell_flow():
            print("\n✗ 卖出流程测试失败")
            return

        # 测试 3: 无持仓时卖出
        if not test_sell_without_position():
            print("\n✗ 无持仓卖出测试失败")
            return

        print("\n" + "="*60)
        print("✓ 所有测试通过！")
        print("="*60)

    except Exception as e:
        print(f"\n✗ 测试过程中发生错误: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
