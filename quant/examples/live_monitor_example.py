"""
实盘监控示例

演示如何使用实盘监控器检测交易执行异常。
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from quantsys.live import LiveMonitor, MonitorConfig, DriftDetector
from datetime import datetime, timedelta
import time


def example_signal_delay():
    """示例1: 信号延迟检测"""
    print("=" * 60)
    print("示例 1: 信号延迟检测")
    print("=" * 60)

    config = MonitorConfig(
        signal_delay_warn_seconds=5.0,
        signal_delay_critical_seconds=15.0
    )
    monitor = LiveMonitor(config)

    # 场景1: 正常延迟
    print("\n场景1: 正常延迟 (2秒)")
    signal_time = datetime.now()
    execution_time = signal_time + timedelta(seconds=2)

    has_alert, severity, alert = monitor.check_signal_delay(
        signal_time, execution_time, 'ma_cross'
    )
    print(f"  结果: {'有告警' if has_alert else '无告警'}")

    # 场景2: 预警级别延迟
    print("\n场景2: 预警级别延迟 (8秒)")
    signal_time = datetime.now()
    execution_time = signal_time + timedelta(seconds=8)

    has_alert, severity, alert = monitor.check_signal_delay(
        signal_time, execution_time, 'ma_cross'
    )
    print(f"  结果: {severity} - {alert.message if alert else '无告警'}")

    # 场景3: 严重延迟
    print("\n场景3: 严重延迟 (20秒)")
    signal_time = datetime.now()
    execution_time = signal_time + timedelta(seconds=20)

    has_alert, severity, alert = monitor.check_signal_delay(
        signal_time, execution_time, 'ma_cross'
    )
    print(f"  结果: {severity} - {alert.message if alert else '无告警'}")


def example_price_deviation():
    """示例2: 价格偏差检测"""
    print("\n" + "=" * 60)
    print("示例 2: 价格偏差检测")
    print("=" * 60)

    config = MonitorConfig(
        price_deviation_warn=0.003,      # 0.3%
        price_deviation_critical=0.008   # 0.8%
    )
    monitor = LiveMonitor(config)

    # 场景1: 正常偏差
    print("\n场景1: 正常偏差 (0.1%)")
    has_alert, severity, alert = monitor.check_price_deviation(
        expected_price=50.0,
        actual_price=50.05,  # 偏差0.1%
        symbol='600036.SH',
        strategy_id='ma_cross'
    )
    print(f"  预期价格: 50.0")
    print(f"  实际价格: 50.05")
    print(f"  结果: {'有告警' if has_alert else '无告警'}")

    # 场景2: 预警级别偏差
    print("\n场景2: 预警级别偏差 (0.5%)")
    has_alert, severity, alert = monitor.check_price_deviation(
        expected_price=50.0,
        actual_price=50.25,  # 偏差0.5%
        symbol='600036.SH',
        strategy_id='ma_cross'
    )
    print(f"  预期价格: 50.0")
    print(f"  实际价格: 50.25")
    print(f"  结果: {severity} - {alert.message if alert else '无告警'}")

    # 场景3: 严重偏差
    print("\n场景3: 严重偏差 (1.0%)")
    has_alert, severity, alert = monitor.check_price_deviation(
        expected_price=50.0,
        actual_price=50.50,  # 偏差1.0%
        symbol='600036.SH',
        strategy_id='ma_cross'
    )
    print(f"  预期价格: 50.0")
    print(f"  实际价格: 50.50")
    print(f"  结果: {severity} - {alert.message if alert else '无告警'}")


def example_strategy_drift():
    """示例3: 策略漂移检测"""
    print("\n" + "=" * 60)
    print("示例 3: 策略漂移检测")
    print("=" * 60)

    monitor = LiveMonitor()

    # 设置基线
    baseline = {
        'win_rate': 0.65,
        'profit_loss_ratio': 2.0,
        'max_drawdown': 0.10
    }
    monitor.update_strategy_baseline('ma_cross', baseline)

    print(f"\n基线表现:")
    print(f"  胜率: {baseline['win_rate']:.2%}")
    print(f"  盈亏比: {baseline['profit_loss_ratio']:.2f}")
    print(f"  最大回撤: {baseline['max_drawdown']:.2%}")

    # 场景1: 表现正常
    print("\n场景1: 表现正常")
    recent = {
        'win_rate': 0.63,
        'profit_loss_ratio': 1.9,
        'max_drawdown': 0.11
    }
    has_alert, severity, alert = monitor.check_strategy_drift('ma_cross', recent)
    print(f"  当前胜率: {recent['win_rate']:.2%}")
    print(f"  结果: {'有告警' if has_alert else '无告警'}")

    # 场景2: 胜率明显下降
    print("\n场景2: 胜率明显下降")
    recent = {
        'win_rate': 0.50,  # 下降15%
        'profit_loss_ratio': 1.9,
        'max_drawdown': 0.11
    }
    has_alert, severity, alert = monitor.check_strategy_drift('ma_cross', recent)
    print(f"  当前胜率: {recent['win_rate']:.2%} (下降 {baseline['win_rate'] - recent['win_rate']:.2%})")
    print(f"  结果: {severity} - {alert.message if alert else '无告警'}")


def example_drift_detector():
    """示例4: 策略漂移检测器"""
    print("\n" + "=" * 60)
    print("示例 4: 策略漂移检测器")
    print("=" * 60)

    detector = DriftDetector(
        rolling_days=20,
        baseline_days=60,
        win_rate_threshold=0.08
    )

    # 模拟历史交易（基线期）
    print("\n模拟历史交易（基线期）:")
    base_date = datetime.now() - timedelta(days=80)
    for i in range(50):
        trade = {
            'date': base_date + timedelta(days=i),
            'pnl': 1000 if i % 3 != 0 else -500,  # 胜率约67%
            'return_pct': 0.02 if i % 3 != 0 else -0.01
        }
        detector.record_trade('ma_cross', trade)

    print(f"  记录了50笔历史交易")

    # 模拟最近交易（表现下降）
    print("\n模拟最近交易（表现下降）:")
    recent_date = datetime.now() - timedelta(days=20)
    for i in range(20):
        trade = {
            'date': recent_date + timedelta(days=i),
            'pnl': 800 if i % 2 == 0 else -600,  # 胜率约50%
            'return_pct': 0.015 if i % 2 == 0 else -0.012
        }
        detector.record_trade('ma_cross', trade)

    print(f"  记录了20笔最近交易")

    # 检测漂移
    print("\n检测策略漂移:")
    has_drift, metrics = detector.detect_drift('ma_cross')

    if has_drift:
        print(f"  ⚠️  检测到策略漂移!")
        print(f"\n  基线表现:")
        for key, value in metrics.baseline.items():
            print(f"    {key}: {value:.4f}")

        print(f"\n  当前表现:")
        for key, value in metrics.current.items():
            print(f"    {key}: {value:.4f}")

        print(f"\n  漂移原因:")
        for reason in metrics.drift_reasons:
            print(f"    - {reason}")
    else:
        print(f"  ✅ 未检测到策略漂移")


def example_auto_actions():
    """示例5: 自动告警动作"""
    print("\n" + "=" * 60)
    print("示例 5: 自动告警动作")
    print("=" * 60)

    # 自定义告警回调
    def alert_callback(alert):
        print(f"\n  📢 告警回调触发:")
        print(f"     类型: {alert.alert_type}")
        print(f"     严重程度: {alert.severity}")
        print(f"     消息: {alert.message}")

    config = MonitorConfig(
        auto_reduce_position_on_warn=True,
        auto_pause_on_critical=True
    )
    monitor = LiveMonitor(config, alert_callback=alert_callback)

    print("\n触发严重告警（自动暂停策略）:")
    signal_time = datetime.now()
    execution_time = signal_time + timedelta(seconds=20)

    monitor.check_signal_delay(signal_time, execution_time, 'ma_cross')

    print(f"\n策略状态:")
    print(f"  ma_cross 是否暂停: {monitor.is_strategy_paused('ma_cross')}")


def example_statistics():
    """示例6: 监控统计"""
    print("\n" + "=" * 60)
    print("示例 6: 监控统计")
    print("=" * 60)

    monitor = LiveMonitor()

    # 模拟多个告警
    for i in range(5):
        signal_time = datetime.now()
        execution_time = signal_time + timedelta(seconds=8)
        monitor.check_signal_delay(signal_time, execution_time, 'ma_cross')

    for i in range(3):
        monitor.check_price_deviation(50.0, 50.25, '600036.SH', 'rsi')

    # 获取统计
    stats = monitor.get_statistics()

    print(f"\n监控统计:")
    print(f"  总告警数: {stats['total_alerts']}")
    print(f"  按类型统计: {stats['alerts_by_type']}")
    print(f"  按策略统计: {stats['alerts_by_strategy']}")
    print(f"  暂停的策略: {stats['paused_strategies']}")

    # 查询告警
    print(f"\n最近的告警:")
    recent_alerts = monitor.get_alerts(hours=1)
    for alert in recent_alerts[:3]:
        print(f"  - [{alert.severity}] {alert.message}")


if __name__ == '__main__':
    # 运行所有示例
    example_signal_delay()
    example_price_deviation()
    example_strategy_drift()
    example_drift_detector()
    example_auto_actions()
    example_statistics()

    print("\n" + "=" * 60)
    print("所有示例运行完成！")
    print("=" * 60)
