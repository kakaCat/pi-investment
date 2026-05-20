"""
Demo: Show confidence calibration in action with sample signals.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from quantsys.utils.confidence_calibration import (
    calibrate_rsi_confidence,
    calibrate_ma_confidence,
    calibrate_bollinger_confidence,
    calibrate_macd_confidence,
    calibrate_kdj_confidence,
    calibrate_stop_loss_confidence,
    calibrate_take_profit_confidence
)


def print_header(title):
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def demo_rsi_signals():
    print_header("RSI 信号置信度示例")

    print("\n买入信号 (超卖):")
    print(f"{'RSI值':>8} | {'原始逻辑':>12} | {'贝叶斯校准':>12} | {'说明':>20}")
    print("-" * 70)

    test_cases = [
        (5, "极度超卖"),
        (10, "严重超卖"),
        (15, "超卖"),
        (20, "接近超卖"),
        (25, "轻微超卖"),
        (30, "刚触发阈值")
    ]

    for rsi, desc in test_cases:
        old_conf = min((30 - rsi) / 10, 1.0)
        new_conf = calibrate_rsi_confidence(rsi, 30, 'buy')
        print(f"{rsi:>8} | {old_conf:>11.2%} | {new_conf:>11.2%} | {desc:>20}")

    print("\n卖出信号 (超买):")
    print(f"{'RSI值':>8} | {'原始逻辑':>12} | {'贝叶斯校准':>12} | {'说明':>20}")
    print("-" * 70)

    test_cases = [
        (70, "刚触发阈值"),
        (75, "轻微超买"),
        (80, "超买"),
        (85, "严重超买"),
        (90, "极度超买"),
        (95, "极端超买")
    ]

    for rsi, desc in test_cases:
        old_conf = min((rsi - 70) / 10, 1.0)
        new_conf = calibrate_rsi_confidence(rsi, 70, 'sell')
        print(f"{rsi:>8} | {old_conf:>11.2%} | {new_conf:>11.2%} | {desc:>20}")


def demo_ma_signals():
    print_header("均线交叉信号置信度示例")

    print(f"\n{'MA分离度':>10} | {'原始逻辑':>12} | {'贝叶斯校准':>12} | {'说明':>20}")
    print("-" * 70)

    test_cases = [
        (0.001, "刚刚交叉"),
        (0.005, "轻微分离"),
        (0.01, "明显分离"),
        (0.02, "强势分离"),
        (0.05, "极强分离"),
        (0.10, "极端分离")
    ]

    for diff, desc in test_cases:
        old_conf = min(diff * 10, 1.0)
        new_conf = calibrate_ma_confidence(diff)
        print(f"{diff*100:>9.2f}% | {old_conf:>11.2%} | {new_conf:>11.2%} | {desc:>20}")


def demo_bollinger_signals():
    print_header("布林带信号置信度示例")

    print(f"\n{'距离带宽':>10} | {'原始逻辑':>12} | {'贝叶斯校准':>12} | {'说明':>20}")
    print("-" * 70)

    test_cases = [
        (0.0, "刚触及"),
        (0.005, "轻微突破"),
        (0.01, "明显突破"),
        (0.02, "强势突破"),
        (0.03, "极强突破"),
        (0.05, "极端突破")
    ]

    for dist, desc in test_cases:
        old_conf = min(dist / dist if dist > 0 else 0, 1.0)
        new_conf = calibrate_bollinger_confidence(dist)
        print(f"{dist*100:>9.2f}% | {old_conf:>11.2%} | {new_conf:>11.2%} | {desc:>20}")


def demo_stop_loss_take_profit():
    print_header("止损/止盈信号置信度示例")

    print("\n止损信号:")
    print(f"{'亏损幅度':>10} | {'原始逻辑':>12} | {'贝叶斯校准':>12} | {'说明':>20}")
    print("-" * 70)

    test_cases = [
        (0.02, "轻微亏损"),
        (0.05, "达到止损"),
        (0.08, "较大亏损"),
        (0.10, "严重亏损"),
        (0.15, "极端亏损")
    ]

    for loss, desc in test_cases:
        old_conf = 1.0  # 原来硬编码为 100%
        new_conf = calibrate_stop_loss_confidence(loss)
        print(f"{loss*100:>9.1f}% | {old_conf:>11.2%} | {new_conf:>11.2%} | {desc:>20}")

    print("\n止盈信号:")
    print(f"{'盈利幅度':>10} | {'原始逻辑':>12} | {'贝叶斯校准':>12} | {'说明':>20}")
    print("-" * 70)

    test_cases = [
        (0.05, "小幅盈利"),
        (0.10, "达到止盈"),
        (0.15, "较好盈利"),
        (0.20, "优秀盈利"),
        (0.30, "极佳盈利")
    ]

    for profit, desc in test_cases:
        old_conf = 1.0  # 原来硬编码为 100%
        new_conf = calibrate_take_profit_confidence(profit)
        print(f"{profit*100:>9.1f}% | {old_conf:>11.2%} | {new_conf:>11.2%} | {desc:>20}")


def demo_comparison():
    print_header("修复前后对比")

    print("\n问题：原系统中的 100% 置信度信号")
    print("-" * 70)
    print("❌ 止损信号: confidence = 1.0 (100%)")
    print("❌ 止盈信号: confidence = 1.0 (100%)")
    print("❌ RSI 极端值: confidence 可达 1.0 (100%)")
    print("❌ MACD 大幅分离: confidence 可达 1.0 (100%)")

    print("\n修复：贝叶斯校准后的置信度")
    print("-" * 70)
    print("✅ 止损信号: confidence ≤ 0.75 (75%)")
    print("✅ 止盈信号: confidence ≤ 0.75 (75%)")
    print("✅ 所有策略信号: confidence ≤ 0.85 (85%)")
    print("✅ 置信度随信号强度平滑变化")

    print("\n关键改进:")
    print("-" * 70)
    print("1. 防止过度自信 - 最大置信度限制在 85%")
    print("2. 平滑校准 - 使用 Sigmoid 函数，避免阶跃变化")
    print("3. 统一标准 - 所有策略使用相同的校准机制")
    print("4. 防御性信号 - 止损/止盈置信度上限更低 (75%)")


def main():
    print("\n" + "=" * 70)
    print("  信号置信度贝叶斯校准 - 演示")
    print("=" * 70)

    demo_rsi_signals()
    demo_ma_signals()
    demo_bollinger_signals()
    demo_stop_loss_take_profit()
    demo_comparison()

    print("\n" + "=" * 70)
    print("  演示完成")
    print("=" * 70)
    print("\n核心要点:")
    print("  • 没有任何信号可以达到 100% 置信度")
    print("  • 置信度上限: 策略信号 85%, 止损/止盈 75%")
    print("  • 置信度随信号强度平滑增长")
    print("  • 更加合理和可解释的置信度分布")
    print()


if __name__ == '__main__':
    main()
