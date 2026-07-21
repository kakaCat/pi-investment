"""
诊断 API 路由
"""
from flask import Blueprint, jsonify, request
import logging

from adapters.inbound.api.shared import (
    api_response,
    handle_api_error,
    sanitize_for_json,
    convert_keys_to_snake
)
from application.services.diagnosis_service import DiagnosisService

logger = logging.getLogger(__name__)

diagnosis_bp = Blueprint('diagnosis', __name__)


@diagnosis_bp.route('/api/diagnosis/run', methods=['POST'])
@handle_api_error
def run_diagnosis():
    """
    运行策略诊断

    Request Body:
    {
        "backtestId": "123",
        "symbol": "000001.SZ",
        "startDate": "2024-01-01",
        "endDate": "2024-12-31",
        "strategyName": "ma_cross",
        "benchmark": "000300.SH"
    }
    """
    raw_data = request.get_json() or {}
    data = convert_keys_to_snake(raw_data)

    # 验证必需参数
    required = ['symbol', 'start_date', 'end_date', 'strategy_name']
    for field in required:
        if field not in data:
            return jsonify({'error': f'缺少必需参数: {field}'}), 400

    # 运行诊断
    service = DiagnosisService()
    result = service.run_diagnosis(data)

    return jsonify(sanitize_for_json(result))


@diagnosis_bp.route('/api/diagnosis/health', methods=['GET'])
def diagnosis_health():
    """健康检查"""
    return jsonify({
        'status': 'ok',
        'service': 'diagnosis',
        'version': '1.0.0'
    })
