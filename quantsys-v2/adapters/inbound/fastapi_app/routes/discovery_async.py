"""策略发现 API - FastAPI 版（从 Flask discovery.py 迁移，响应契约保持一致）

结果存储在中立层 adapters/shared/discovery_state（Flask discovery.py 也再导出同一实例）。
"""
from typing import Any, Dict, Optional

from fastapi import APIRouter, Query, Body
from fastapi.responses import JSONResponse
import structlog

# 复用中立层的内存结果存储（同一单例，保证 parity）
from adapters.shared.discovery_state import _results_store

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["Discovery - 策略发现"])


@router.get('/api/discovery/result/{run_id}')
def get_discovery_result(run_id: str):
    """获取历史发现结果"""
    report = _results_store.get(run_id)
    if not report:
        return JSONResponse(status_code=404, content={'success': False, 'error': f'未找到结果: {run_id}'})
    return {'success': True, 'data': report.to_dict()}
