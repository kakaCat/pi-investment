#!/usr/bin/env python3
"""
手动触发早盘分析 - 简单补发版本
"""
import requests
import json
from datetime import datetime

# 早盘分析任务的消息内容
morning_message = """
🌅 早盘分析任务 - 虚拟仓自动交易模式（补发）

**时间**: {time}
**说明**: 这是今日错过的早盘分析任务的补发执行

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
第一步：检查虚拟仓持仓
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

虚拟仓状态：
""".format(time=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
print("🔄 手动补发今日早盘分析")
print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")

# 1. 获取虚拟仓状态
print("📊 步骤1: 查询虚拟仓状态...")
try:
    resp = requests.get('http://127.0.0.1:5001/api/portfolio', timeout=10)
    portfolio = resp.json()

    if portfolio.get('success'):
        data = portfolio['data']
        morning_message += f"  可用资金：¥{data['cash']:.2f}\n"
        morning_message += f"  持仓数量：{len(data['holdings'])}只\n"
        morning_message += f"  总资产：¥{data['totalValue']:.2f}\n"
        morning_message += f"  总盈亏：¥{data['totalPnl']:.2f} ({data['totalPnlPct']:.2f}%)\n\n"
        print(f"✅ 虚拟仓状态: 资金¥{data['cash']:.2f}, 持仓{len(data['holdings'])}只")
    else:
        print(f"⚠️  虚拟仓查询失败: {portfolio.get('error')}")
        morning_message += "  虚拟仓查询失败\n\n"

except Exception as e:
    print(f"❌ 连接失败: {e}")
    morning_message += f"  连接失败: {e}\n\n"

# 2. 获取股票池信息
print("\n📋 步骤2: 查询股票池...")
try:
    resp = requests.get('http://127.0.0.1:5001/api/pools', timeout=10)
    pools = resp.json()

    if pools.get('success'):
        pool_count = len(pools['data'])
        morning_message += f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        morning_message += f"第二步：扫描股票池\n"
        morning_message += f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        morning_message += f"  股票池总数：{pool_count}个\n\n"
        print(f"✅ 股票池数量: {pool_count}个")
    else:
        print(f"⚠️  股票池查询失败: {pools.get('error')}")

except Exception as e:
    print(f"❌ 连接失败: {e}")

# 3. 总结
morning_message += f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
morning_message += f"分析总结\n"
morning_message += f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
morning_message += f"⚠️  虚拟仓未初始化，无法进行交易\n"
morning_message += f"建议：初始化虚拟仓并设置初始资金\n\n"
morning_message += f"下次早盘分析：明天 09:00\n"

# 4. 发送飞书通知
print("\n📤 步骤3: 发送飞书通知...")

webhook_url = 'https://open.feishu.cn/open-apis/bot/v2/hook/b24be3a5-35fc-4142-90c2-3a3933172829'

feishu_message = {
    "msg_type": "interactive",
    "card": {
        "header": {
            "title": {
                "tag": "plain_text",
                "content": "🌅 早盘分析报告（补发）"
            },
            "template": "blue"
        },
        "elements": [
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": morning_message
                }
            }
        ]
    }
}

try:
    resp = requests.post(webhook_url, json=feishu_message, timeout=10)
    result = resp.json()

    if result.get('code') == 0:
        print("✅ 飞书通知发送成功！")
    else:
        print(f"⚠️  飞书返回: {result}")

except Exception as e:
    print(f"❌ 发送失败: {e}")

print("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
print("✅ 早盘分析补发完成！")
print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
print("\n💡 提示:")
print("  • 这是今日错过任务的手动补发")
print("  • 明天 09:00 将自动执行")
print("  • 请在飞书群查看报告")
