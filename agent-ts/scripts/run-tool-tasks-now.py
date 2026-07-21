#!/usr/bin/env python3
"""
执行工具任务 - 忽略代理的简化版本
"""
import sys
import json
import os
from datetime import datetime

# 强制清除所有代理设置
for key in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'ALL_PROXY', 'all_proxy']:
    os.environ.pop(key, None)

try:
    import requests
    # 创建一个会话，明确禁用代理
    session = requests.Session()
    session.trust_env = False  # 不信任环境变量
except ImportError:
    print("❌ 需要安装requests: pip install requests")
    sys.exit(1)

print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
print("🚀 工具任务执行报告")
print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
print(f"\n时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"\n执行结果:\n")

results = []
total_start = datetime.now()

# 工具任务1: portfolio_status
try:
    start = datetime.now()
    resp = session.get('http://127.0.0.1:5001/api/portfolio', timeout=5)
    duration = (datetime.now() - start).total_seconds() * 1000
    
    data = resp.json()
    if data.get('success'):
        portfolio = data['data']
        print(f"• ✅ portfolio_status ({duration:.0f}ms)")
        print(f"  - 可用资金: ¥{portfolio['cash']:.2f}")
        print(f"  - 持仓: {len(portfolio['holdings'])}只")
        print(f"  - 总资产: ¥{portfolio['totalValue']:.2f}")
        results.append(('portfolio_status', True, duration))
    else:
        print(f"• ❌ portfolio_status (失败)")
        results.append(('portfolio_status', False, duration))
except Exception as e:
    print(f"• ❌ portfolio_status ({str(e)[:50]})")
    results.append(('portfolio_status', False, 0))

# 工具任务2: pool_manage
try:
    start = datetime.now()
    resp = session.get('http://127.0.0.1:5001/api/pools', timeout=5)
    duration = (datetime.now() - start).total_seconds() * 1000
    
    data = resp.json()
    if data.get('success'):
        pools = data['data']
        print(f"• ✅ pool_manage ({duration:.0f}ms)")
        print(f"  - 股票池数量: {len(pools)}个")
        results.append(('pool_manage', True, duration))
    else:
        print(f"• ❌ pool_manage (失败)")
        results.append(('pool_manage', False, duration))
except Exception as e:
    print(f"• ❌ pool_manage ({str(e)[:50]})")
    results.append(('pool_manage', False, 0))

# 工具任务3: health_check
try:
    start = datetime.now()
    resp = session.get('http://127.0.0.1:5001/api/health', timeout=5)
    duration = (datetime.now() - start).total_seconds() * 1000
    
    data = resp.json()
    if data.get('status') == 'ok':
        print(f"• ✅ health_check ({duration:.0f}ms)")
        print(f"  - 数据库: {'✅' if data.get('db_connected') else '❌'}")
        results.append(('health_check', True, duration))
    else:
        print(f"• ❌ health_check (状态异常)")
        results.append(('health_check', False, duration))
except Exception as e:
    print(f"• ❌ health_check ({str(e)[:50]})")
    results.append(('health_check', False, 0))

# 总结
total_duration = (datetime.now() - total_start).total_seconds() * 1000
success_count = sum(1 for _, success, _ in results if success)
fail_count = len(results) - success_count

print(f"\n总结:")
print(f"- 成功: {success_count} 个")
print(f"- 失败: {fail_count} 个")
print(f"- 总耗时: {total_duration:.0f}ms")
print(f"\n这是一次工具任务流程测试。")

sys.exit(0 if fail_count == 0 else 1)
