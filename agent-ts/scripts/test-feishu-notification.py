#!/usr/bin/env python3
"""
测试飞书通知
"""
import os
import requests
from datetime import datetime

# 从环境变量读取webhook URL
webhook_url = os.getenv('FEISHU_WEBHOOK_URL', 'https://open.feishu.cn/open-apis/bot/v2/hook/b24be3a5-35fc-4142-90c2-3a3933172829')

# 构造消息
message = {
    "msg_type": "interactive",
    "card": {
        "header": {
            "title": {
                "tag": "plain_text",
                "content": "🌅 早盘分析测试通知"
            },
            "template": "blue"
        },
        "elements": [
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"**测试时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n**测试目的**: 验证调度器守护进程的飞书通知功能\n\n**系统状态**:\n- ✅ 调度器守护进程已启动\n- ✅ 三个定时任务已配置\n- ⏰ 下次早盘分析: 明天 09:00"
                }
            },
            {
                "tag": "hr"
            },
            {
                "tag": "note",
                "elements": [
                    {
                        "tag": "plain_text",
                        "content": "这是一条测试消息，验证飞书通知是否正常工作。"
                    }
                ]
            }
        ]
    }
}

print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
print("📤 发送飞书测试通知")
print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")
print(f"Webhook URL: {webhook_url}\n")

try:
    response = requests.post(webhook_url, json=message, timeout=10)
    response.raise_for_status()

    result = response.json()
    print(f"✅ 发送成功!")
    print(f"响应: {result}\n")

    if result.get('code') == 0:
        print("✅ 飞书通知发送成功，请检查飞书群查看消息。")
    else:
        print(f"⚠️  飞书返回非零状态码: {result}")

except Exception as e:
    print(f"❌ 发送失败: {e}\n")
    import traceback
    traceback.print_exc()

print("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
