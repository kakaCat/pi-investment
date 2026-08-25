"""
W3: API 端点冒烟测试
确保重构后端点调用不 500

覆盖端点:
- /api/memory/search (GET)
- /api/memory (POST)
- /api/market/sectors (GET)
- /api/market/sector/{name} (GET)
- /api/portfolio/positions (GET)
- /api/simulation/accounts/{account_name}/trade (POST) - sell 校验路径（新 API）
- /api/backtest/run (POST)
- /api/risk/metrics (GET)
"""
import pytest
import requests
from typing import Dict, Any

BASE_URL = "http://localhost:5001"

def test_memory_search():
    """测试记忆搜索接口"""
    response = requests.get(f"{BASE_URL}/api/memory/search", params={"query": "test"}, timeout=10)
    assert response.status_code != 500, f"memory/search 返回 500: {response.text}"
    assert response.status_code == 200, f"memory/search 状态码: {response.status_code}"
    data = response.json()
    # 实际返回格式可能是 {"items": [...]} 或其他
    assert isinstance(data, dict), f"返回非字典: {type(data)}"

def test_memory_write():
    """测试记忆写入接口"""
    payload = {
        "content": "测试记忆写入 - W3 冒烟测试",
        "importance": 0.3,
        "namespace": "default"
    }
    response = requests.post(f"{BASE_URL}/api/memory", json=payload, timeout=10)
    assert response.status_code != 500, f"memory write 返回 500: {response.text}"
    assert response.status_code in [200, 201], f"memory write 状态码: {response.status_code}"
    data = response.json()
    assert isinstance(data, dict), f"返回非字典: {type(data)}"

def test_market_sectors():
    """测试板块列表接口"""
    response = requests.get(f"{BASE_URL}/api/market/sectors")
    assert response.status_code != 500, f"market/sectors 返回 500: {response.text}"
    data = response.json()
    assert "success" in data or "sectors" in data or "error" in data

def test_market_sector_detail():
    """测试单板块详情接口"""
    response = requests.get(f"{BASE_URL}/api/market/sector/白酒")
    assert response.status_code != 500, f"market/sector/白酒 返回 500: {response.text}"
    data = response.json()
    # 404 可接受（板块不存在），但不能 500
    assert response.status_code in [200, 404]

def test_portfolio_positions():
    """测试持仓列表接口"""
    response = requests.get(f"{BASE_URL}/api/portfolio/positions")
    assert response.status_code != 500, f"portfolio/positions 返回 500: {response.text}"
    data = response.json()
    assert "success" in data or "positions" in data or "error" in data

def test_simulation_trade_sell_validation():
    """测试卖出订单校验路径（新 API，不实际成交）"""
    # 故意提交一个无持仓的卖出单，测试校验逻辑不崩溃。
    # 显式传 price 绕过实时行情依赖；用不存在的 symbol 触发"无持仓"校验。
    payload = {
        "action": "sell",
        "symbol": "999999",  # 不存在的股票
        "shares": 100,
        "price": 10.0,
        "reason": "W3 冒烟测试 - 卖出校验路径",
    }
    response = requests.post(
        f"{BASE_URL}/api/simulation/accounts/agent_virtual/trade",
        json=payload, timeout=10,
    )
    # 期望返回业务错误（400/404/409/422，含非交易时段 422）而非服务器错误（500）
    assert response.status_code != 500, f"simulation/trade 返回 500: {response.text}"
    assert response.status_code in [200, 400, 404, 409, 422], (
        f"预期业务校验错误，实际: {response.status_code}: {response.text[:200]}"
    )

def test_backtest_run():
    """测试回测接口"""
    payload = {
        "strategy_id": 1,
        "symbols": ["600519"],
        "start_date": "2026-08-01",
        "end_date": "2026-08-25"
    }
    response = requests.post(f"{BASE_URL}/api/backtest/run", json=payload)
    # 回测可能因数据不足失败（400），但不应 500
    assert response.status_code != 500, f"backtest/run 返回 500: {response.text}"
    assert response.status_code in [200, 400, 422]

def test_risk_metrics():
    """测试风控指标接口"""
    response = requests.get(f"{BASE_URL}/api/risk/metrics")
    assert response.status_code != 500, f"risk/metrics 返回 500: {response.text}"
    data = response.json()
    assert "success" in data or "metrics" in data or "error" in data


if __name__ == "__main__":
    # 允许作为脚本直接运行
    import sys
    
    tests = [
        ("memory_search", test_memory_search),
        ("memory_write", test_memory_write),
        ("market_sectors", test_market_sectors),
        ("market_sector_detail", test_market_sector_detail),
        ("portfolio_positions", test_portfolio_positions),
        ("order_create_sell", test_simulation_trade_sell_validation),
        ("backtest_run", test_backtest_run),
        ("risk_metrics", test_risk_metrics),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_func in tests:
        try:
            test_func()
            print(f"✓ {name}")
            passed += 1
        except AssertionError as e:
            print(f"✗ {name}: {e}")
            failed += 1
        except Exception as e:
            print(f"✗ {name}: 异常 - {e}")
            failed += 1
    
    print(f"\n{'='*60}")
    print(f"W3 冒烟测试结果: {passed} 通过, {failed} 失败")
    print(f"{'='*60}")
    
    sys.exit(0 if failed == 0 else 1)
