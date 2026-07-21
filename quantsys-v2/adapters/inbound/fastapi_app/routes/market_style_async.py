"""市场风格检测 API - FastAPI 版（从 Flask market_style.py 迁移，响应契约保持一致）"""
from fastapi import APIRouter, Request
import structlog

from adapters.inbound.fastapi_app.shared import (
    api_response, error_response, handle_api_error, get_query_params_snake_case,
)

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["Market Style - 市场风格"])


@router.get('/api/market/style')
@handle_api_error
def detect_market_style(request: Request):
    """检测市场风格"""
    params = get_query_params_snake_case(request)
    lookback_days = int(params.get('lookback_days', 60))
    try:
        from application.services.market_style_detector import MarketStyleDetector
        detector = MarketStyleDetector()
        result = detector.detect_market_style(lookback_days)
        return api_response(result)
    except Exception as e:
        logger.error(f"市场风格检测失败: {e}", exc_info=True)
        return error_response({'success': False, 'error': str(e)}, 500)
