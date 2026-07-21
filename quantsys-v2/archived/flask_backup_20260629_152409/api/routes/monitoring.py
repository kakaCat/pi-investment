"""
监控 API
"""
from flask import Blueprint, request, jsonify
from application.services.signal_monitoring import signal_monitor

monitoring_bp = Blueprint('monitoring', __name__)


@monitoring_bp.route('/api/monitoring/signals/metrics', methods=['GET'])
def get_signal_metrics():
    """
    获取信号处理监控指标

    GET /api/monitoring/signals/metrics?strategy=VolatilityBreakoutStrategy
    """
    strategy_name = request.args.get('strategy')

    summary = signal_monitor.get_summary()
    metrics = signal_monitor.get_metrics(strategy_name)

    # 计算平均时间
    by_strategy = {}
    for key, m in metrics.items():
        by_strategy[key] = {
            **m,
            'avg_time': m['total_time'] / m['count'] if m['count'] > 0 else 0
        }

    return jsonify({
        'summary': summary,
        'by_strategy': by_strategy
    })


@monitoring_bp.route('/api/monitoring/signals/health', methods=['GET'])
def get_signal_health():
    """
    信号处理健康检查

    GET /api/monitoring/signals/health
    """
    summary = signal_monitor.get_summary()

    checks = {
        'success_rate': {
            'status': 'pass' if summary['success_rate'] >= 0.95 else 'fail',
            'value': summary['success_rate'],
            'threshold': 0.95
        },
        'avg_processing_time': {
            'status': 'pass' if summary['avg_processing_time'] <= 0.1 else 'fail',
            'value': summary['avg_processing_time'],
            'threshold': 0.1
        },
        'recent_failures': {
            'status': 'pass' if summary['failure_count'] <= 10 else 'fail',
            'value': summary['failure_count'],
            'threshold': 10
        }
    }

    # 判断整体状态
    failed_checks = sum(1 for c in checks.values() if c['status'] == 'fail')
    if failed_checks == 0:
        status = 'healthy'
    elif failed_checks <= 1:
        status = 'degraded'
    else:
        status = 'unhealthy'

    return jsonify({
        'status': status,
        'checks': checks
    })
