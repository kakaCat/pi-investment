#!/usr/bin/env python
"""
测试通知系统双模式功能
验证直接发送通知是否正常工作
"""
import sys
import os

# 添加 quantsys-v2 到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'quantsys-v2'))

from application.services.agent_notification_service import AgentNotificationService

def test_direct_send():
    """测试直接发送通知"""
    print("=" * 60)
    print("测试通知系统双模式 - 直接发送模式")
    print("=" * 60)

    service = AgentNotificationService()

    # 测试 1: 股池变化通知
    print("\n[测试 1] 股池变化通知（模拟）")
    result = service.send_notification(
        title='📊 股池变化通知 (2026-09-02)',
        content='账户：agent_virtual\n变化股池：价值成长池 (+3-2), 低估值池 (+1-0)',
        channel='reports',  # 使用报告群
        priority='normal'
    )
    print(f"  结果: {'✅ 成功' if result else '❌ 失败'}")

    # 测试 2: 盘前摘要通知
    print("\n[测试 2] 盘前摘要通知（模拟）")
    result = service.send_notification(
        title='📈 盘前摘要 (2026-09-02)',
        content="""日期：2026-09-02
市场风格：价值
生成信号数：5""",
        channel='reports',  # 使用报告群
        priority='normal'
    )
    print(f"  结果: {'✅ 成功' if result else '❌ 失败'}")

    # 测试 3: 市场异动告警
    print("\n[测试 3] 市场异动告警（模拟）")
    result = service.send_notification(
        title='🚨 大盘异动告警',
        content="""⚠️ 上证指数跌幅 -3.5%，超过阈值 -3.0%

当前持仓数：12
持仓代码：600519, 000858, 002475

风险提示：大盘异动，请关注持仓""",
        channel='alerts',  # 使用告警群
        priority='high'
    )
    print(f"  结果: {'✅ 成功' if result else '❌ 失败'}")

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)
    print("\n请检查飞书群是否收到以上 3 条通知")
    print("- 报告群：应收到 2 条（股池变化、盘前摘要）")
    print("- 告警群：应收到 1 条（市场异动告警）")
    print("\n如果收到，说明直接发送模式工作正常 ✅")

if __name__ == '__main__':
    test_direct_send()
