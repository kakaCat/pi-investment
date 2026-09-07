#!/usr/bin/env python3
"""
测试 Bug 1 修复：/api/risk/metrics 现在应该按 account_name 返回不同的指标
"""
import requests
import json

BASE_URL = "http://localhost:5001"

def test_risk_metrics_by_account():
    """测试不同账户返回不同的风险指标"""
    
    accounts = ["agent_virtual", "agent_a", "agent_b"]
    results = {}
    
    print("=== 测试 /api/risk/metrics 按账户过滤 ===\n")
    
    for account in accounts:
        print(f"查询账户: {account}")
        response = requests.post(
            f"{BASE_URL}/api/risk/metrics",
            json={"account_name": account, "days": 60},
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            if 'max_drawdown' in data:
                results[account] = data['max_drawdown']
                print(f"  ✓ maxDrawdown: {data['max_drawdown']}")
            else:
                print(f"  ✗ 响应中没有 max_drawdown")
                print(f"  响应: {json.dumps(data, indent=2)}")
        else:
            print(f"  ✗ 请求失败: {response.status_code}")
            print(f"  错误: {response.text}")
        print()
    
    # 验证结果
    print("\n=== 验证结果 ===\n")
    
    if len(results) < 2:
        print("⚠ 测试数据不足（至少需要2个账户有数据）")
        return False
    
    unique_values = len(set(results.values()))
    
    if unique_values == 1:
        print(f"✗ Bug 仍然存在：所有账户返回相同的 maxDrawdown = {list(results.values())[0]}")
        print("  这意味着后端仍然没有按 account_name 过滤数据")
        return False
    else:
        print(f"✓ Bug 已修复：{len(results)} 个账户返回了 {unique_values} 个不同的 maxDrawdown 值")
        for account, value in results.items():
            print(f"  {account}: {value}")
        return True

if __name__ == "__main__":
    try:
        success = test_risk_metrics_by_account()
        exit(0 if success else 1)
    except requests.exceptions.ConnectionError:
        print("\n✗ 无法连接到后端服务 (http://localhost:5001)")
        print("  请先启动 quantsys-v2 后端")
        exit(2)
    except Exception as e:
        print(f"\n✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
