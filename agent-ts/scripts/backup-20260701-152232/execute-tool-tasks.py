#!/usr/bin/env python3
"""
执行完整的工具任务流程
模拟早盘分析的真实场景
"""
import requests
import json
from datetime import datetime

print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
print("🚀 执行工具任务流程")
print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

results = []

# ============================================================
# 工具任务1: 查看虚拟仓状态
# ============================================================
print("📊 工具任务1: portfolio_status - 查看虚拟仓")
print("─" * 80)

try:
    start = datetime.now()
    response = requests.get('http://127.0.0.1:5001/api/portfolio', timeout=5)
    duration = (datetime.now() - start).total_seconds() * 1000

    data = response.json()

    if data.get('success'):
        portfolio = data['data']
        print(f"✅ 执行成功 ({duration:.0f}ms)")
        print(f"  可用资金: ¥{portfolio['cash']:.2f}")
        print(f"  持仓数量: {len(portfolio['holdings'])}只")
        print(f"  总资产: ¥{portfolio['totalValue']:.2f}")
        print(f"  总盈亏: ¥{portfolio['totalPnl']:.2f} ({portfolio['totalPnlPct']:.2f}%)")

        results.append({
            'tool': 'portfolio_status',
            'success': True,
            'duration': duration,
            'data': portfolio
        })
    else:
        print(f"⚠️  失败: {data.get('error')}")
        results.append({'tool': 'portfolio_status', 'success': False})

except Exception as e:
    print(f"❌ 错误: {e}")
    results.append({'tool': 'portfolio_status', 'success': False, 'error': str(e)})

print()

# ============================================================
# 工具任务2: 获取股票池列表
# ============================================================
print("📋 工具任务2: pool_manage - 获取股票池")
print("─" * 80)

try:
    start = datetime.now()
    response = requests.get('http://127.0.0.1:5001/api/pools', timeout=5)
    duration = (datetime.now() - start).total_seconds() * 1000

    data = response.json()

    if data.get('success'):
        pools = data['data']
        print(f"✅ 执行成功 ({duration:.0f}ms)")
        print(f"  股票池数量: {len(pools)}个")

        for pool in pools[:3]:  # 显示前3个
            print(f"  • {pool.get('name', '未命名')} ({pool.get('id', 'N/A')}) - {pool.get('stock_count', 0)}只股票")

        if len(pools) > 3:
            print(f"  ... 还有 {len(pools) - 3} 个池")

        results.append({
            'tool': 'pool_manage',
            'success': True,
            'duration': duration,
            'data': {'pool_count': len(pools)}
        })
    else:
        print(f"⚠️  失败: {data.get('error')}")
        results.append({'tool': 'pool_manage', 'success': False})

except Exception as e:
    print(f"❌ 错误: {e}")
    results.append({'tool': 'pool_manage', 'success': False, 'error': str(e)})

print()

# ============================================================
# 工具任务3: 获取市场数据
# ============================================================
print("📈 工具任务3: market_data - 获取市场指数")
print("─" * 80)

try:
    start = datetime.now()
    response = requests.get('http://127.0.0.1:5001/api/market/indices', timeout=5)
    duration = (datetime.now() - start).total_seconds() * 1000

    data = response.json()

    if data.get('success'):
        indices = data['data']
        print(f"✅ 执行成功 ({duration:.0f}ms)")

        for idx in indices[:3]:
            print(f"  • {idx.get('name', 'N/A')}: {idx.get('price', 0):.2f} ({idx.get('change_pct', 0):+.2f}%)")

        results.append({
            'tool': 'market_data',
            'success': True,
            'duration': duration,
            'data': {'index_count': len(indices)}
        })
    else:
        print(f"⚠️  失败: {data.get('error')}")
        results.append({'tool': 'market_data', 'success': False})

except Exception as e:
    print(f"❌ 错误: {e}")
    results.append({'tool': 'market_data', 'success': False, 'error': str(e)})

print()

# ============================================================
# 工具任务4: 发送飞书通知
# ============================================================
print("📤 工具任务4: feishu_notify - 发送通知")
print("─" * 80)

# 汇总报告
report = f"""**工具任务执行报告**

**时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

**执行结果**:
"""

for r in results:
    status = "✅" if r.get('success') else "❌"
    tool_name = r['tool']
    duration = f"{r.get('duration', 0):.0f}ms" if 'duration' in r else "N/A"
    report += f"\n• {status} {tool_name} ({duration})"

report += f"""

**总结**:
- 成功: {sum(1 for r in results if r.get('success'))} 个
- 失败: {sum(1 for r in results if not r.get('success'))} 个
- 总耗时: {sum(r.get('duration', 0) for r in results):.0f}ms

这是一次工具任务流程测试。
"""

webhook_url = 'https://open.feishu.cn/open-apis/bot/v2/hook/b24be3a5-35fc-4142-90c2-3a3933172829'

message = {
    "msg_type": "interactive",
    "card": {
        "header": {
            "title": {
                "tag": "plain_text",
                "content": "🔧 工具任务执行报告"
            },
            "template": "green"
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
    response = requests.post(webhook_url, json=message, timeout=10)
    duration = (datetime.now() - start).total_seconds() * 1000

    result = response.json()

    if result.get('code') == 0:
        print(f"✅ 执行成功 ({duration:.0f}ms)")
        print("  飞书通知已发送")
        results.append({'tool': 'feishu_notify', 'success': True, 'duration': duration})
    else:
        print(f"⚠️  失败: {result}")
        results.append({'tool': 'feishu_notify', 'success': False})

except Exception as e:
    print(f"❌ 错误: {e}")
    results.append({'tool': 'feishu_notify', 'success': False, 'error': str(e)})

print()

# ============================================================
# 总结
# ============================================================
print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
print("✅ 工具任务流程执行完成")
print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
print()
print("📊 执行统计:")
print(f"  总任务数: {len(results)}")
print(f"  成功: {sum(1 for r in results if r.get('success'))}")
print(f"  失败: {sum(1 for r in results if not r.get('success'))}")
print(f"  总耗时: {sum(r.get('duration', 0) for r in results):.0f}ms")
print()
print("💡 这些工具在定时任务中会被Agent AI自动调用")
print("   明天 09:00 早盘分析任务会执行类似的流程")
