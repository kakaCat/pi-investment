"""
W3: API 端点冒烟测试
确保重构后端点调用不 500

覆盖端点（2026-10-05 · REQ-261004202231-bb99：/api/memory* 全部随 v2 记忆子系统下线，
本文件不再覆盖记忆端点；记忆能力归 agent 侧 agent-os）:
- /api/market/sectors (GET)
- /api/market/sector/{name} (GET)
- /api/simulation/accounts/{account_name} (GET)（持仓+汇总，2026-09-10 起替代已删除的 /api/portfolio/positions|summary）
- /api/simulation/accounts/{account_name}/trade (POST) - sell 校验路径（新 API）
- /api/backtest/run (POST)
- /api/risk/metrics (GET)
"""
import requests
from typing import Dict, Any

BASE_URL = "http://localhost:5001"

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
    """测试持仓+账户状态接口（/api/portfolio/positions 已于 2026-09-10 删除，打 successor 端点）"""
    response = requests.get(f"{BASE_URL}/api/simulation/accounts/agent_virtual")
    assert response.status_code != 500, f"simulation/accounts 返回 500: {response.text}"
    data = response.json()
    assert "success" in data or "positions" in data or "error" in data

def test_simulation_trade_sell_validation():
    """测试卖出订单校验路径（新 API，不实际成交）"""
    # 故意提交一个无持仓的卖出单，测试校验逻辑不崩溃。
    # 显式传 price 绕过实时行情依赖；用不存在的 symbol 触发"无持仓"校验。
    payload = {
        "action": "SELL",
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
