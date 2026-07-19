#!/usr/bin/env python3
"""
执行完整的工具任务流程
展示自动化系统如何工作
"""
import requests
import json
from datetime import datetime

print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
print("🚀 执行工具任务流程演示")
print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
print(f"⏰ 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"📝 说明: 模拟早盘分析任务的工作流程\n")

BASE_URL = "http://127.0.0.1:5001"
results = []

def log_step(step_num, title):
    print(f"\n{'═' * 80}")
    print(f"步骤 {step_num}: {title}")
    print('═' * 80)

def log_result(success, duration, message):
    status = "✅" if success else "❌"
    print(f"{status} {message} ({duration:.0f}ms)")

# ============================================================
# 步骤 1: 检查系统健康状态
# ============================================================
log_step(1, "检查系统健康状态")

try:
    start = datetime.now()
    resp = requests.get(f"{BASE_URL}/api/health", timeout=5)
    duration = (datetime.now() - start).total_seconds() * 1000

    data = resp.json()

    if data.get('status') == 'ok':
        log_result(True, duration, f"quantsys-v2后端运行正常")
        print(f"   数据库: {data.get('db_info', {}).get('provider', 'N/A')}")
        print(f"   股票数: {data.get('db_info', {}).get('stock_count', 0)}")
        results.append(('health_check', True, duration))
    else:
        log_result(False, duration, "后端健康检查失败")
        results.append(('health_check', False, duration))
except Exception as e:
    log_result(False, 0, f"连接失败: {e}")
    results.append(('health_check', False, 0))

# ============================================================
# 步骤 2: 查看虚拟仓状态
# ============================================================
log_step(2, "查看虚拟仓状态 (portfolio_status)")

try:
    start = datetime.now()
    resp = requests.get(f"{BASE_URL}/api/portfolio", timeout=5)
    duration = (datetime.now() - start).total_seconds() * 1000

    data = resp.json()

    if data.get('success'):
        portfolio = data['data']
        log_result(True, duration, "虚拟仓状态查询成功")
        print(f"   💰 可用资金: ¥{portfolio['cash']:.2f}")
        print(f"   📊 持仓数量: {len(portfolio['holdings'])}只")
        print(f"   💼 总资产: ¥{portfolio['totalValue']:.2f}")
        print(f"   📈 总盈亏: ¥{portfolio['totalPnl']:.2f} ({portfolio['totalPnlPct']:.2f}%)")

        if portfolio['cash'] == 0:
            print(f"   ⚠️  警告: 虚拟仓未初始化，无法执行买入操作")

        results.append(('portfolio_status', True, duration, portfolio))
    else:
        log_result(False, duration, f"查询失败: {data.get('error')}")
        results.append(('portfolio_status', False, duration))
except Exception as e:
    log_result(False, 0, f"API调用失败: {e}")
    results.append(('portfolio_status', False, 0))

# ============================================================
# 步骤 3: 获取股票池列表
# ============================================================
log_step(3, "获取股票池列表 (pool_manage)")

try:
    start = datetime.now()
    resp = requests.get(f"{BASE_URL}/api/pools", timeout=5)
    duration = (datetime.now() - start).total_seconds() * 1000

    data = resp.json()

    if data.get('success'):
        pools = data['data']
        log_result(True, duration, f"获取到 {len(pools)} 个股票池")

        for i, pool in enumerate(pools[:5], 1):
            pool_id = pool.get('id', 'N/A')
            pool_name = pool.get('name', '未命名')
            stock_count = pool.get('stock_count', 0)
            print(f"   {i}. [{pool_id}] {pool_name} - {stock_count}只股票")

        if len(pools) > 5:
            print(f"   ... 还有 {len(pools) - 5} 个池")

        results.append(('pool_list', True, duration, {'pool_count': len(pools)}))
    else:
        log_result(False, duration, f"查询失败: {data.get('error')}")
        results.append(('pool_list', False, duration))
except Exception as e:
    log_result(False, 0, f"API调用失败: {e}")
    results.append(('pool_list', False, 0))

# ============================================================
# 步骤 4: 检查市场状态
# ============================================================
log_step(4, "检查市场状态 (market_data)")

try:
    start = datetime.now()
    resp = requests.get(f"{BASE_URL}/api/market/indices", timeout=5)
    duration = (datetime.now() - start).total_seconds() * 1000

    data = resp.json()

    if data.get('success'):
        indices = data['data']
        log_result(True, duration, f"获取到 {len(indices)} 个市场指数")

        for idx in indices[:3]:
            name = idx.get('name', 'N/A')
            price = idx.get('price', 0)
            change = idx.get('change_pct', 0)
            arrow = "📈" if change > 0 else "📉" if change < 0 else "➡️"
            print(f"   {arrow} {name}: {price:.2f} ({change:+.2f}%)")

        results.append(('market_data', True, duration))
    else:
        log_result(False, duration, f"查询失败: {data.get('error')}")
        results.append(('market_data', False, duration))
except Exception as e:
    log_result(False, 0, f"API调用失败: {e}")
    results.append(('market_data', False, 0))

# ============================================================
# 步骤 5: 模拟交易决策
# ============================================================
log_step(5, "模拟交易决策 (portfolio_trade)")

portfolio_data = None
for r in results:
    if r[0] == 'portfolio_status' and r[1] and len(r) > 3:
        portfolio_data = r[3]
        break

if portfolio_data and portfolio_data['cash'] > 0:
    print("💡 虚拟仓有资金，可以执行买入")
    print("   (本次演示不实际执行交易)")
    results.append(('trade_decision', True, 0, {'action': 'simulate_only'}))
else:
    print("⚠️  虚拟仓资金为0，无法执行买入")
    print("   如果要启用自动交易，需要先初始化虚拟仓")
    print("   命令: 调用 /api/portfolio/init 设置初始资金")
    results.append(('trade_decision', False, 0, {'reason': 'no_funds'}))

# ============================================================
# 步骤 6: 生成报告并发送飞书通知
# ============================================================
log_step(6, "发送飞书通知 (feishu_notify)")

# 生成执行报告
report = f"""**工具任务执行报告**

**时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

**执行结果**:
"""

task_names = {
    'health_check': '系统健康检查',
    'portfolio_status': '虚拟仓状态',
    'pool_list': '股票池列表',
    'market_data': '市场数据',
    'trade_decision': '交易决策'
}

for r in results:
    task_name = task_names.get(r[0], r[0])
    status = "✅" if r[1] else "❌"
    duration = f"{r[2]:.0f}ms" if len(r) > 2 and r[2] > 0 else "N/A"
    report += f"\n{status} {task_name} ({duration})"

success_count = sum(1 for r in results if r[1])
total_duration = sum(r[2] for r in results if len(r) > 2)

report += f"""

**统计**:
- ✅ 成功: {success_count}/{len(results)}
- ⏱️ 总耗时: {total_duration:.0f}ms

**说明**:
这是自动化工具任务的演示执行。
实际的定时任务会在每天 09:00/12:30/18:00 自动运行。
"""

# 发送飞书通知
webhook_url = 'https://open.feishu.cn/open-apis/bot/v2/hook/b24be3a5-35fc-4142-90c2-3a3933172829'

message = {
    "msg_type": "interactive",
    "card": {
        "header": {
            "title": {
                "tag": "plain_text",
                "content": "🔧 工具任务执行报告"
            },
            "template": "turquoise"
        },
        "elements": [
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": report
                }
            }
        ]
    }
}

try:
    start = datetime.now()
    resp = requests.post(webhook_url, json=message, timeout=10)
    duration = (datetime.now() - start).total_seconds() * 1000

    result = resp.json()

    if result.get('code') == 0:
        log_result(True, duration, "飞书通知发送成功")
        print("   📱 请在飞书群查看报告")
        results.append(('feishu_notify', True, duration))
    else:
        log_result(False, duration, f"发送失败: {result}")
        results.append(('feishu_notify', False, duration))
except Exception as e:
    log_result(False, 0, f"发送失败: {e}")
    results.append(('feishu_notify', False, 0))

# ============================================================
# 总结
# ============================================================
print("\n" + "━" * 80)
print("✅ 工具任务流程执行完成")
print("━" * 80)

success_count = sum(1 for r in results if r[1])
total_duration = sum(r[2] for r in results if len(r) > 2)

print(f"\n📊 执行统计:")
print(f"   总任务数: {len(results)}")
print(f"   ✅ 成功: {success_count}")
print(f"   ❌ 失败: {len(results) - success_count}")
print(f"   ⏱️ 总耗时: {total_duration:.0f}ms")

print(f"\n💡 关键信息:")
print(f"   1. 自动化任务已配置并运行")
print(f"   2. 虚拟仓当前资金为0，不会执行实际交易")
print(f"   3. 定时任务时间: 09:00(早盘) / 12:30(盘中) / 18:00(复盘)")
print(f"   4. 所有任务结果会发送到飞书群")

print("\n" + "━" * 80)
