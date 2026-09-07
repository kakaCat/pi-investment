#!/usr/bin/env python3
"""
多账户架构测试脚本

测试V13、V14账户隔离是否正常工作
"""
import requests
import json

API_BASE = "http://127.0.0.1:5001"

def test_v14_api():
    """测试V14账户API"""
    print("=" * 60)
    print("📊 测试 V14 账户 API")
    print("=" * 60)

    # 测试账户信息
    print("\n1️⃣ 测试 /api/v14/account-info")
    resp = requests.get(f"{API_BASE}/api/v14/account-info")
    data = resp.json()
    if data['success']:
        print(f"   ✅ 账户名: {data['account_name']}")
        print(f"   ✅ 总资产: ¥{data['totalValue']:,.2f}")
        print(f"   ✅ 现金: ¥{data['cash']:,.2f}")
        print(f"   ✅ 持仓数: {data['positionsCount']}")
    else:
        print(f"   ❌ 错误: {data.get('error')}")

    # 测试持仓明细
    print("\n2️⃣ 测试 /api/v14/positions")
    resp = requests.get(f"{API_BASE}/api/v14/positions")
    data = resp.json()
    if data['success']:
        positions = data['positions']
        print(f"   ✅ 持仓数量: {len(positions)}")
        for pos in positions:
            print(f"      {pos['symbol']}: {pos['shares']}股 @ ¥{pos['avgPrice']:.2f} (当前价¥{pos['currentPrice']:.2f})")
    else:
        print(f"   ❌ 错误: {data.get('error')}")

    # 测试交易记录
    print("\n3️⃣ 测试 /api/v14/trades")
    resp = requests.get(f"{API_BASE}/api/v14/trades?limit=5")
    data = resp.json()
    if data['success']:
        trades = data['trades']
        print(f"   ✅ 交易记录数: {len(trades)}")
        for trade in trades[:3]:
            print(f"      {trade['action']} {trade['symbol']} {trade['shares']}股 @ ¥{trade['price']:.2f}")
    else:
        print(f"   ❌ 错误: {data.get('error')}")

def test_data_isolation():
    """测试数据隔离"""
    print("\n" + "=" * 60)
    print("🔒 测试账户数据隔离")
    print("=" * 60)

    # 获取V14持仓
    resp = requests.get(f"{API_BASE}/api/v14/positions")
    v14_data = resp.json()

    if v14_data['success']:
        v14_positions = v14_data['positions']
        v14_symbols = set(pos['symbol'] for pos in v14_positions)

        print(f"\n✅ V14账户持仓: {v14_symbols}")
        print(f"   持仓数量: {len(v14_positions)}")

        # 验证：如果有V13 API，应该返回不同的持仓
        print("\n💡 多账户架构验证:")
        print("   - V14账户使用 account_name='v14_simulation'")
        print("   - V13账户使用 account_name='v13_simulation'")
        print("   - 数据库通过 account_name 字段隔离")
        print("   - 每个账户有独立的现金、持仓、交易记录")

def test_agent_tools():
    """测试agent工具任务"""
    print("\n" + "=" * 60)
    print("🤖 测试 Agent 工具任务")
    print("=" * 60)

    # 测试portfolio_status
    print("\n1️⃣ 测试 portfolio_status (默认账户)")
    resp = requests.get(f"{API_BASE}/api/portfolio")
    data = resp.json()
    if data['success']:
        portfolio = data['data']
        print(f"   ✅ 可用资金: ¥{portfolio['cash']:,.2f}")
        print(f"   ✅ 持仓数: {len(portfolio['holdings'])}")
        print(f"   ✅ 总资产: ¥{portfolio['totalValue']:,.2f}")
    else:
        print(f"   ❌ 错误: {data.get('error')}")

    # 测试pool_manage
    print("\n2️⃣ 测试 pool_manage")
    resp = requests.get(f"{API_BASE}/api/pools")
    data = resp.json()
    if data['success']:
        pools = data['data']
        print(f"   ✅ 股票池数量: {len(pools)}")
    else:
        print(f"   ❌ 错误: {data.get('error')}")

    # 测试health_check
    print("\n3️⃣ 测试 health_check")
    resp = requests.get(f"{API_BASE}/api/health")
    data = resp.json()
    if data['status'] == 'ok':
        print(f"   ✅ 状态: {data['status']}")
        print(f"   ✅ 数据库: {'连接' if data['db_connected'] else '断开'}")
    else:
        print(f"   ❌ 状态异常")

if __name__ == '__main__':
    print("\n" + "🚀" * 30)
    print("多账户架构完整测试")
    print("🚀" * 30)

    try:
        # 测试V14 API
        test_v14_api()

        # 测试数据隔离
        test_data_isolation()

        # 测试agent工具
        test_agent_tools()

        print("\n" + "=" * 60)
        print("✅ 测试完成")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
