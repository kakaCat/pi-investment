"""
Prometheus metrics endpoint for quantsys-v2

提供 /metrics 端点用于 Prometheus 抓取监控指标
"""
from flask import Blueprint, Response
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

metrics_bp = Blueprint('metrics', __name__)


@metrics_bp.route('/metrics', methods=['GET'])
def metrics():
    """Prometheus metrics endpoint

    Returns:
        Prometheus-formatted metrics
    """
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)
