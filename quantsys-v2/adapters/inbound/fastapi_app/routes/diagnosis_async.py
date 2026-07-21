"""诊断 API - FastAPI 版（从 Flask diagnosis.py 迁移，响应契约保持一致）

Flask 用 jsonify(sanitize_for_json(result)) 直接返回（非 api_response），故同样处理。
"""
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body
import structlog

from adapters.inbound.fastapi_app.shared import (
    error_response, handle_api_error, sanitize_for_json, convert_keys_to_snake,
)
from application.services.diagnosis_service import DiagnosisService

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["Diagnosis - 诊断"])


@router.post('/api/diagnosis/run')
@handle_api_error
def run_diagnosis(payload: Optional[Dict[str, Any]] = Body(None)):
    """运行策略诊断"""
    raw_data = payload or {}
    data = convert_keys_to_snake(raw_data)
    required = ['symbol', 'start_date', 'end_date', 'strategy_name']
    for field in required:
        if field not in data:
            return error_response({'error': f'缺少必需参数: {field}'}, 400)
    service = DiagnosisService()
    result = service.run_diagnosis(data)
    return sanitize_for_json(result)


@router.get('/api/diagnosis/health')
def diagnosis_health():
    """健康检查"""
    return {'status': 'ok', 'service': 'diagnosis', 'version': '1.0.0'}
