"""市场预警 API - FastAPI 版（新建，agent alerts.check / alerts.statistics）

基于 GameAlertService 的博弈预警（对手行为 + 操纵检测）。
agent market_alert 工具期望 {success, data: alerts[]} 与 {success, data: statistics}。
"""
from typing import Any, Dict

from fastapi import APIRouter
import structlog

from adapters.inbound.fastapi_app.shared import error_response
from adapters.shared.services import game_alert_service

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["Alerts - 市场预警"])


def _service():
    return game_alert_service


@router.get('/api/alerts/check')
def check_alerts():
    """检查市场预警（风险/机会信号）"""
    try:
        alerts = _service().check_alerts()
        return {'success': True, 'data': alerts}
    except Exception as e:
        logger.error(f"alerts.check failed: {e}", exc_info=True)
        return error_response({'success': False, 'error': str(e)}, 500)


@router.get('/api/alerts/statistics')
def get_alert_statistics():
    """获取预警统计（按类型/级别分组 + 最近预警）"""
    try:
        stats = _service().get_alert_statistics()
        return {'success': True, 'data': stats}
    except Exception as e:
        logger.error(f"alerts.statistics failed: {e}", exc_info=True)
        return error_response({'success': False, 'error': str(e)}, 500)
