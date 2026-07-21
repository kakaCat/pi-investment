#!/usr/bin/env python3
"""
执行完整的早盘分析工具任务
"""
import requests
import json
from datetime import datetime

print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
print("🌅 执行早盘分析工具任务")
print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

BASE_URL = "http://127.0.0.1:5001"
results = []

# ============================================================
# 工具1: 查看虚拟仓状态
# ============================================================
print("📊 工具1: portfolio_status")
print("─" * 80)

portfolio_data = None
try:
    resp = requests.get(f"{BASE_URL}/api/portfolio", timeout=5)
    data = resp.json()

    if data.get('success'):
        portfolio_data = data['data']
        print(f"✅ 查询成功")
        print(f"   💰 可用资金: ¥{portfolio_data['cash']:.2f}")
        print(f"   📊 持仓数量: {len(portfolio_data['holdings'])}只")
        print(f"   💼 总资产: ¥{portfolio_data['cash'] + portfolio_data['totalValue']:.2f}")

        if portfolio_data['cash'] == 0:
            print(f"   ⚠️  虚拟仓未初始化")

        results.append(('portfolio_status', True, portfolio_data))
    else:
        print(f"❌ 失败: {data.get('error')}")
        results.append(('portfolio_status', False, None))
except Exception as e:
    print(f"❌ 错误: {e}")
    results.append(('portfolio_status', False, None))

print()

# ============================================================
# 工具2: 初始化虚拟仓（如果需要）
# ============================================================
if portfolio_data and portfolio_data['cash'] == 0:
    print("💡 工具2: 初始化虚拟仓")
    print("─" * 80)
    print("   检测到虚拟仓未初始化，使用Python直接初始化...")

    try:
        # 使用Python脚本初始化
        import sys
        sys.path.append('/Users/mac/Documents/ai/pi-investment/quantsys-v2')

        from adapters.outbound.repositories import PortfolioRepository
        from datetime import datetime

        repo = PortfolioRepository()

        # 创建初始记录
        init_data = {
            'date': datetime.now().date(),
            'cash': 100000.0,
            'holdings': {},
            'total_value': 0.0,
            'total_cost': 0.0,
            'total_pnl': 0.0,
            'total_pnl_pct': 0.0,
            'updated_at': datetime.now()
        }

        # 直接写入数据库
        print("   正在初始化...")
        # 这里需要实际的数据库操作
        print("   ⚠️  需要通过TypeScript工具或数据库直接操作")
        print("   建议：使用agent-ts的portfolio_trade工具")

        results.append(('portfolio_init', False, 'needs_proper_api'))

    except Exception as e:
        print(f"   ❌ 初始化失败: {e}")
        results.append(('portfolio_init', False, str(e)))

    print()

# ============================================================
# 工具3: 获取股票池
# ============================================================
print("📋 工具3: pool_manage - 获取股票池")
print("─" * 80)

try:
    resp = requests.get(f"{BASE_URL}/api/pools", timeout=5)
    data = resp.json()

    if data.get('success'):
        pools = data['data']
        print(f"✅ 成功获取 {len(pools)} 个股票池")

        for i, pool in enumerate(pools[:3], 1):
            print(f"   {i}. {pool.get('name', '未命名')} - {pool.get('stock_count', 0)}只")

        if len(pools) > 3:
            print(f"   ... 还有 {len(pools) - 3} 个池")

        results.append(('pool_manage', True, len(pools)))
    else:
        print(f"❌ 失败: {data.get('error')}")
        results.append(('pool_manage', False, None))
except Exception as e:
    print(f"❌ 错误: {e}")
    results.append(('pool_manage', False, None))

print()

# ============================================================
# 工具4: 发送飞书通知
# ============================================================
print("📤 工具4: feishu_notify")
print("─" * 80)

# 生成报告
status_text = ""
if portfolio_data:
    status_text = f"""
**虚拟仓状态**:
💰 可用资金: ¥{portfolio_data['cash']:.2f}
📊 持仓数量: {len(portfolio_data['holdings'])}只
💼 总资产: ¥{portfolio_data['cash'] + portfolio_data['totalValue']:.2f}
"""
    if portfolio_data['cash'] == 0:
        status_text += "\n⚠️ 虚拟仓未初始化，无法执行交易"

pool_count = next((r[2] for r in results if r[0] == 'pool_manage' and r[1]), 0)
status_text += f"\n\n**股票池**: {pool_count}个"

report = f"""**早盘分析工具任务执行报告**

**时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

{status_text}

**执行状态**:
"""

for r in results:
    tool_name = r[0]
    status = "✅" if r[1] else "❌"
    report += f"\n{status} {tool_name}"

report += f"""

**说明**:
- 这是工具任务的手动执行演示
- 定时任务会在 09:00/12:30/18:00 自动执行
- 虚拟仓初始化后才能进行交易
"""

webhook_url = 'https://open.feishu.cn/open-apis/bot/v2/hook/b24be3a5-35fc-4142-90c2-3a3933172829'

message = {
    "msg_type": "interactive",
    "card": {
        "header": {
            "title": {
                "tag": "plain_text",
                "content": "🌅 早盘分析工具任务"
            },
            "template": "blue"
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
    resp = requests.post(webhook_url, json=message, timeout=10)
    result = resp.json()

    if result.get('code') == 0:
        print("✅ 飞书通知发送成功")
        print("   📱 请在飞书群查看")
        results.append(('feishu_notify', True, None))
    else:
        print(f"❌ 发送失败: {result}")
        results.append(('feishu_notify', False, None))
except Exception as e:
    print(f"❌ 错误: {e}")
    results.append(('feishu_notify', False, None))

print()

# ============================================================
# 总结
# ============================================================
print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
print("✅ 工具任务执行完成")
print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

success = sum(1 for r in results if r[1])
total = len(results)

print(f"\n📊 执行统计:")
print(f"   ✅ 成功: {success}/{total}")
print(f"   ❌ 失败: {total - success}/{total}")

print(f"\n💡 说明:")
print(f"   1. 定时任务每天会自动执行这些工具")
print(f"   2. 虚拟仓需要初始化才能交易")
print(f"   3. 所有操作都在模拟环境，不涉及真实资金")
print(f"   4. 结果会通过飞书通知")

print("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
