#!/usr/bin/env python
"""
飞书通知功能测试脚本
"""
import sys
import os
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.feishu_notifier import FeishuNotifier
import logging

logging.basicConfig(level=logging.INFO)

def test_text_message():
    """测试文本消息"""
    print("\n" + "="*70)
    print("测试1: 发送简单文本消息")
    print("="*70)

    webhook_url = os.getenv('FEISHU_WEBHOOK_URL')
    if not webhook_url:
        print("❌ 未配置FEISHU_WEBHOOK_URL环境变量")
        return False

    notifier = FeishuNotifier(webhook_url)

    success = notifier.send_text("🎉 V13策略飞书通知测试 - 文本消息")

    if success:
        print("✅ 文本消息发送成功")
    else:
        print("❌ 文本消息发送失败")

    return success


def test_rebalance_notification():
    """测试调仓通知"""
    print("\n" + "="*70)
    print("测试2: 发送调仓通知")
    print("="*70)

    webhook_url = os.getenv('FEISHU_WEBHOOK_URL')
    if not webhook_url:
        print("❌ 未配置FEISHU_WEBHOOK_URL环境变量")
        return False

    notifier = FeishuNotifier(webhook_url)

    # 模拟调仓数据
    test_data = {
        'date': '2026-06-30',
        'total_value': 100928.71,
        'cash': 46176.71,
        'cumulative_return': 0.0093,
        'positions': 6,
        'top_stocks': [
            ('301292', 0.1581, 0.125, '(¥78.96，价格太高买不起)'),
            ('300383', 0.1394, 0.125, '(¥12.11，买入)'),
            ('300255', 0.1304, 0.125, '(¥22.81，买入)'),
            ('301666', 0.1117, 0.125, '(¥657.99，价格太高买不起)'),
            ('300179', 0.1103, 0.125, '(¥57.38，保留持仓)'),
            ('300953', 0.1064, 0.125, '(¥128.20，价格太高买不起)'),
            ('301626', 0.0999, 0.125, '(¥345.20，价格太高买不起)'),
            ('300394', 0.0954, 0.125, '(¥318.00，价格太高买不起)'),
        ],
        'buy_trades': [
            ('300383', 400, 12.11),
            ('300255', 200, 22.81),
        ],
        'sell_trades': [
            ('300342', 200, 44.38),
            ('300364', 400, 23.45),
        ]
    }

    success = notifier.send_rebalance_notification(test_data)

    if success:
        print("✅ 调仓通知发送成功")
    else:
        print("❌ 调仓通知发送失败")

    return success


def test_verification_notification():
    """测试验证通知"""
    print("\n" + "="*70)
    print("测试3: 发送验证通知")
    print("="*70)

    webhook_url = os.getenv('FEISHU_WEBHOOK_URL')
    if not webhook_url:
        print("❌ 未配置FEISHU_WEBHOOK_URL环境变量")
        return False

    notifier = FeishuNotifier(webhook_url)

    # 模拟验证数据
    test_data = {
        'rebalance_date': '2026-06-30',
        'verify_date': '2026-07-07',
        'predictions': [
            ('300383', 0.1394, 0.082),  # 预测+13.94%, 实际+8.2%
            ('300255', 0.1304, 0.051),  # 预测+13.04%, 实际+5.1%
            ('300179', 0.1103, -0.023), # 预测+11.03%, 实际-2.3%
        ],
        'initial_value': 100928.71,
        'current_value': 102156.34,
        'period_return': 0.0122,
        'index_return': 0.0085,
        'cycle': 1
    }

    success = notifier.send_verification_notification(test_data)

    if success:
        print("✅ 验证通知发送成功")
    else:
        print("❌ 验证通知发送失败")

    return success


def test_risk_alert():
    """测试风险预警"""
    print("\n" + "="*70)
    print("测试4: 发送风险预警")
    print("="*70)

    webhook_url = os.getenv('FEISHU_WEBHOOK_URL')
    if not webhook_url:
        print("❌ 未配置FEISHU_WEBHOOK_URL环境变量")
        return False

    notifier = FeishuNotifier(webhook_url)

    # 模拟风险数据
    test_data = {
        'trigger': '累计收益跌破-5%',
        'total_value': 94523.45,
        'cumulative_return': -0.0548,
        'weekly_return': -0.032,
        'index_return': -0.012,
        'win_rate': 0.333,
        'avg_return': -0.021,
        'losing_stocks': ['300342', '300364', '300420']
    }

    success = notifier.send_risk_alert(test_data)

    if success:
        print("✅ 风险预警发送成功")
    else:
        print("❌ 风险预警发送失败")

    return success


def test_weekly_report():
    """测试周报"""
    print("\n" + "="*70)
    print("测试5: 发送周报")
    print("="*70)

    webhook_url = os.getenv('FEISHU_WEBHOOK_URL')
    if not webhook_url:
        print("❌ 未配置FEISHU_WEBHOOK_URL环境变量")
        return False

    notifier = FeishuNotifier(webhook_url)

    # 模拟周报数据
    test_data = {
        'week': 1,
        'start_date': '2026-06-23',
        'end_date': '2026-06-27',
        'initial_value': 100000.00,
        'final_value': 100928.71,
        'weekly_return': 0.0093,
        'rebalance_count': 1,
        'trade_count': 6,
        'win_count': 4,
        'total_stocks': 6,
        'avg_position_return': 0.015,
        'max_drawdown': -0.023,
        'position_level': 0.75,
        'stop_loss_count': 0,
        'index_return': 0.012,
        'excess_return': -0.0027,
        'next_rebalance_date': '2026-06-30',
        'observation_progress': '1/3'
    }

    success = notifier.send_weekly_report(test_data)

    if success:
        print("✅ 周报发送成功")
    else:
        print("❌ 周报发送失败")

    return success


def test_final_summary():
    """测试总结报告"""
    print("\n" + "="*70)
    print("测试6: 发送观察期总结报告")
    print("="*70)

    webhook_url = os.getenv('FEISHU_WEBHOOK_URL')
    if not webhook_url:
        print("❌ 未配置FEISHU_WEBHOOK_URL环境变量")
        return False

    notifier = FeishuNotifier(webhook_url)

    # 模拟总结数据
    test_data = {
        'start_date': '2026-06-23',
        'end_date': '2026-07-14',
        'initial_capital': 100000.00,
        'final_value': 103456.78,
        'cumulative_return': 0.0346,
        'max_drawdown': -0.021,
        'rebalance_count': 3,
        'total_trades': 18,
        'winning_trades': 11,
        'win_rate': 0.611,
        'avg_win': 0.062,
        'avg_loss': -0.031,
        'verified_stocks': 24,
        'correct_predictions': 15,
        'prediction_accuracy': 0.625,
        'avg_prediction_error': 0.043,
        'strategy_return': 0.0346,
        'index_return': 0.021,
        'excess_return': 0.0136,
        'criterion_1': True,
        'criterion_2': True,
        'criterion_3': True,
        'criterion_4': True,
        'passed_count': 4,
        'conclusion': '模型有效！',
        'suggestion': '✅ 可以继续使用V13策略\n✅ 建议优化：添加价格过滤，避免高价股\n⚠️ 持续监控：每月复盘一次'
    }

    success = notifier.send_final_summary(test_data)

    if success:
        print("✅ 总结报告发送成功")
    else:
        print("❌ 总结报告发送失败")

    return success


def main():
    """运行所有测试"""
    import sys

    print("\n" + "="*70)
    print("V13策略飞书通知功能测试")
    print("="*70)

    # 检查环境变量
    webhook_url = os.getenv('FEISHU_WEBHOOK_URL')
    if not webhook_url:
        print("\n❌ 错误: 未配置FEISHU_WEBHOOK_URL环境变量")
        print("\n请设置环境变量:")
        print("  export FEISHU_WEBHOOK_URL='https://open.feishu.cn/open-apis/bot/v2/hook/xxxxx'")
        print("\n或在.env文件中添加:")
        print("  FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/xxxxx")
        return

    print(f"\n✅ Webhook已配置: {webhook_url[:50]}...")

    # 检查是否为自动模式
    auto_mode = '--auto' in sys.argv or not sys.stdin.isatty()

    if auto_mode:
        print("\n🤖 自动模式: 连续运行所有测试（每个测试间隔2秒）")
    else:
        print("\n👤 交互模式: 每个测试后按回车继续")

    # 运行测试
    results = []

    results.append(("文本消息", test_text_message()))
    if not auto_mode:
        input("\n按回车继续下一个测试...")
    else:
        import time
        time.sleep(2)

    results.append(("调仓通知", test_rebalance_notification()))
    if not auto_mode:
        input("\n按回车继续下一个测试...")
    else:
        time.sleep(2)

    results.append(("验证通知", test_verification_notification()))
    if not auto_mode:
        input("\n按回车继续下一个测试...")
    else:
        time.sleep(2)

    results.append(("风险预警", test_risk_alert()))
    if not auto_mode:
        input("\n按回车继续下一个测试...")
    else:
        time.sleep(2)

    results.append(("周报", test_weekly_report()))
    if not auto_mode:
        input("\n按回车继续下一个测试...")
    else:
        time.sleep(2)

    results.append(("总结报告", test_final_summary()))

    # 总结
    print("\n" + "="*70)
    print("测试结果总结")
    print("="*70)

    for name, success in results:
        status = "✅ 通过" if success else "❌ 失败"
        print(f"{name}: {status}")

    total = len(results)
    passed = sum(1 for _, success in results if success)

    print("\n" + "="*70)
    print(f"总计: {passed}/{total} 项测试通过")
    print("="*70)

    if passed == total:
        print("\n🎉 所有测试通过！飞书通知功能正常")
    else:
        print(f"\n⚠️ {total - passed} 项测试失败，请检查配置")


if __name__ == '__main__':
    main()
