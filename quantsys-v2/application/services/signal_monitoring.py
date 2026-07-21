"""
信号监控服务

监控信号处理性能和质量。
"""
from typing import Dict, Any
from collections import defaultdict
from datetime import datetime


class SignalMonitor:
    """监控信号处理性能和质量"""

    def __init__(self):
        self.metrics = defaultdict(lambda: {
            'count': 0,
            'success': 0,
            'failure': 0,
            'warnings': 0,
            'total_time': 0.0,
            'errors': []
        })

    def record_signal_processing(
        self,
        strategy_name: str,
        symbol: str,
        success: bool,
        duration: float,
        warnings: list = None,
        error: str = None
    ):
        """
        记录信号处理结果

        Args:
            strategy_name: 策略名称
            symbol: 股票代码
            success: 是否成功
            duration: 处理时间（秒）
            warnings: 警告列表
            error: 错误信息
        """
        key = f"{strategy_name}:{symbol}"
        m = self.metrics[key]

        m['count'] += 1
        m['total_time'] += duration

        if success:
            m['success'] += 1
        else:
            m['failure'] += 1
            if error:
                m['errors'].append({
                    'timestamp': datetime.now().isoformat(),
                    'error': error
                })

        if warnings:
            m['warnings'] += len(warnings)

    def get_metrics(self, strategy_name: str = None) -> Dict[str, Any]:
        """
        获取监控指标

        Args:
            strategy_name: 策略名称（可选，不传则返回所有）

        Returns:
            指标字典
        """
        if strategy_name:
            return {k: v for k, v in self.metrics.items() if k.startswith(strategy_name)}
        return dict(self.metrics)

    def get_summary(self) -> Dict[str, Any]:
        """
        获取汇总统计

        Returns:
            汇总统计字典
        """
        total_count = sum(m['count'] for m in self.metrics.values())
        total_success = sum(m['success'] for m in self.metrics.values())
        total_failure = sum(m['failure'] for m in self.metrics.values())
        total_warnings = sum(m['warnings'] for m in self.metrics.values())
        total_time = sum(m['total_time'] for m in self.metrics.values())

        return {
            'total_signals': total_count,
            'success_rate': total_success / total_count if total_count > 0 else 0,
            'failure_count': total_failure,
            'warning_count': total_warnings,
            'avg_processing_time': total_time / total_count if total_count > 0 else 0,
            'strategies_monitored': len(self.metrics)
        }


# 全局监控实例
signal_monitor = SignalMonitor()
