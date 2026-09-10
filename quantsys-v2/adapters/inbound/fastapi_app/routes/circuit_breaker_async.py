"""组合级回撤熔断 API（M4 硬拦截，2026-09-10，w-f4aa1f6a）

GET  /api/risk/circuit-breaker?account_name=  查状态
POST /api/risk/circuit-breaker                设置/解除（M4 工具双写）
"""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Query
import structlog

from adapters.inbound.fastapi_app.shared import api_response, error_response
from application.services import portfolio_breaker_service

logger = structlog.get_logger(__name__)
router = APIRouter(tags=["Risk - 组合熔断"])


@router.get('/api/risk/circuit-breaker')
def get_circuit_breaker(account_name: str = Query('agent_virtual')):
    try:
        return api_response(portfolio_breaker_service.get_status(account_name))
    except Exception as e:  # noqa: BLE001
        logger.error('circuit-breaker 查询失败', error=str(e))
        return error_response({'success': False, 'error': str(e)}, 500)


@router.post('/api/risk/circuit-breaker')
def set_circuit_breaker(payload: Dict[str, Any] = Body(...)):
    account_name = str(payload.get('account_name') or 'agent_virtual')
    active = payload.get('active')
    if not isinstance(active, bool):
        return error_response({'success': False, 'error': 'active 必须为布尔值'}, 400)
    try:
        status = portfolio_breaker_service.set_status(
            account_name=account_name,
            active=active,
            triggered_drawdown=payload.get('triggered_drawdown'),
            actions_taken=payload.get('actions_taken'),
            unblock_condition=payload.get('unblock_condition'),
            note=payload.get('note'),
        )
        return api_response(status)
    except Exception as e:  # noqa: BLE001
        logger.error('circuit-breaker 设置失败', error=str(e))
        return error_response({'success': False, 'error': str(e)}, 500)
