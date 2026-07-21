#!/usr/bin/env python3
"""
执行完整的工具任务流程（可靠版）
使用requests库，避免502问题
"""
import sys
import json
from datetime import datetime

try:
    import requests
except ImportError:
    print("❌ 需要安装requests库: pip install requests")
    sys.exit(1)

print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
print("🚀 工具任务执行报告")
print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
print(f"\n时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"\n执行结果:\n")

results = []
total_start = datetime.now()

# ============================================================
# 工具任务1: portfolio_status - 查看虚拟仓状态
# ============================================================
try:
    start = datetime.now()
    response = requests.get('http://127.0.0.1:5001/api/portfolio', timeout=5)
    duration = (datetime.now() - start).total_seconds() * 1000

    if response.status_code == 200:
        data = response.json()
        if data.get('success'):
            portfolio = data['data']
            status = f"✅ portfolio_status ({duration:.0f}ms)"
            print(f"• {status}")
            print(f"  - 可用资金: ¥{portfolio['cash']:.2f}")
            print(f"  - 持仓数量: {len(portfolio['holdings'])}只")
            print(f"  - 总资产: ¥{portfolio['totalValue']:.2f}")
            print(f"  - 总盈亏: ¥{portfolio['totalPnl']:.2f} ({portfolio['totalPnlPct']:.2f}%)")
            results.append({'tool': 'portfolio_status', 'success': True, 'duration': duration})
        else:
            print(f"• ⚠️  portfolio_status (失败: {data.get('error')})")
            results.append({'tool': 'portfolio_status', 'success': False})
    else:
        print(f"• ❌ portfolio_status (HTTP {response.status_code})")
        results.append({'tool': 'portfolio_status', 'success': False})
except Exception as e:
    print(f"• ❌ portfolio_status ({str(e)})")
    results.append({'tool': 'portfolio_status', 'success': False, 'error': str(e)})

# ============================================================
# 工具任务2: pool_manage - 获取股票池列表
# ============================================================
try:
    start = datetime.now()
    response = requests.get('http://127.0.0.1:5001/api/pools', timeout=5)
    duration = (datetime.now() - start).total_seconds() * 1000

    if response.status_code == 200:
        data = response.json()
        if data.get('success'):
            pools = data['data']
            status = f"✅ pool_manage ({duration:.0f}ms)"
            print(f"• {status}")
            print(f"  - 股票池数量: {len(pools)}个")

            for pool in pools[:3]:
                print(f"  - {pool.get('name', '未命名')} ({pool.get('id', 'N/A')}) - {pool.get('symbol_count', 0)}只股票")

            if len(pools) > 3:
                print(f"  - ... 还有 {len(pools) - 3} 个池")

            results.append({'tool': 'pool_manage', 'success': True, 'duration': duration})
        else:
            print(f"• ⚠️  pool_manage (失败: {data.get('error')})")
            results.append({'tool': 'pool_manage', 'success': False})
    else:
        print(f"• ❌ pool_manage (HTTP {response.status_code})")
        results.append({'tool': 'pool_manage', 'success': False})
except Exception as e:
    print(f"• ❌ pool_manage ({str(e)})")
    results.append({'tool': 'pool_manage', 'success': False, 'error': str(e)})

# ============================================================
# 工具任务3: health_check - 后端健康检查
# ============================================================
try:
    start = datetime.now()
    response = requests.get('http://127.0.0.1:5001/api/health', timeout=5)
    duration = (datetime.now() - start).total_seconds() * 1000

    if response.status_code == 200:
        data = response.json()
        if data.get('status') == 'ok':
            status = f"✅ health_check ({duration:.0f}ms)"
            print(f"• {status}")
            print(f"  - 数据库连接: {'✅ 正常' if data.get('db_connected') else '❌ 异常'}")
            if 'db_info' in data:
                db_info = data['db_info']
                print(f"  - 数据库类型: {db_info.get('provider', 'N/A')}")
                print(f"  - 股票数量: {db_info.get('stock_count', 0)}")

            results.append({'tool': 'health_check', 'success': True, 'duration': duration})
        else:
            print(f"• ⚠️  health_check (状态异常)")
            results.append({'tool': 'health_check', 'success': False})
    else:
        print(f"• ❌ health_check (HTTP {response.status_code})")
        results.append({'tool': 'health_check', 'success': False})
except Exception as e:
    print(f"• ❌ health_check ({str(e)})")
    results.append({'tool': 'health_check', 'success': False, 'error': str(e)})

# ============================================================
# 总结
# ============================================================
total_duration = (datetime.now() - total_start).total_seconds() * 1000
success_count = sum(1 for r in results if r.get('success'))
fail_count = len(results) - success_count

print(f"\n总结:")
print(f"- 成功: {success_count} 个")
print(f"- 失败: {fail_count} 个")
print(f"- 总耗时: {total_duration:.0f}ms")
print(f"\n这是一次工具任务流程测试。")

sys.exit(0 if fail_count == 0 else 1)
