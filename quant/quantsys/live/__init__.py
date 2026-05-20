"""
实盘监控模块 - Live Monitoring

实时监控交易执行情况，检测异常并触发告警。

模块包含:
1. LiveMonitor - 实盘监控器
2. DriftDetector - 策略漂移检测器

使用示例:
    from quantsys.live import LiveMonitor, DriftDetector, MonitorConfig

    # 创建监控器
    config = MonitorConfig(
        signal_delay_warn_seconds=5.0,
        price_deviation_warn=0.003
    )
    monitor = LiveMonitor(config)

    # 检查信号延迟
    has_alert, severity, alert = monitor.check_signal_delay(
        signal_time, execution_time, strategy_id
    )

    # 检查价格偏差
    has_alert, severity, alert = monitor.check_price_deviation(
        expected_price, actual_price, symbol, strategy_id
    )

    # 检查策略漂移
    has_alert, severity, alert = monitor.check_strategy_drift(
        strategy_id, recent_performance
    )

    # 策略漂移检测
    detector = DriftDetector(rolling_days=20)
    detector.record_trade(strategy_id, trade)
    has_drift, metrics = detector.detect_drift(strategy_id)
"""

from quantsys.live.monitor import LiveMonitor, MonitorConfig, Alert
from quantsys.live.drift_detector import DriftDetector, DriftMetrics

__all__ = [
    'LiveMonitor',
    'MonitorConfig',
    'Alert',
    'DriftDetector',
    'DriftMetrics',
]
