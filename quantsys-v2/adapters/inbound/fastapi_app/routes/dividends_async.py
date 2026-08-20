"""分红数据 API - FastAPI 版（从 Flask dividends.py 迁移，响应契约保持一致）

复用同一 DividendService（含本会话早些时候的股息率百分比/连续年数修复）。
Flask 直接 jsonify(service result)，故同样处理。
"""
from typing import Any, Dict, Optional

from fastapi import APIRouter, Query, Body
from fastapi.responses import JSONResponse
import structlog

from adapters.shared.services import dividend_service as service

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["Dividends - 分红"])

# 与 Flask 一致：模块级服务单例（通过 ServiceFactory 统一获取）
# service = DividendService()  # 已迁移到 adapters.shared.services


@router.get('/api/stock/{symbol}/dividends')
def get_dividends(symbol: str, years: int = Query(10)):
    """获取单股分红数据"""
    logger.info(f"GET /api/stock/{symbol}/dividends - years={years}")
    result = service.get_stock_dividends(symbol, years)
    return result


@router.post('/api/dividends/screen')
def screen_dividends(payload: Optional[Dict[str, Any]] = Body(None)):
    """筛选高股息股票"""
    params = payload or {}
    logger.info(f"POST /api/dividends/screen - params={params}")
    result = service.screen_dividend_stocks(params)
    return result


@router.get('/api/dividends/calendar')
def dividend_calendar(start_date: Optional[str] = Query(None),
                      end_date: Optional[str] = Query(None),
                      event: str = Query('ex_dividend')):
    """分红日历"""
    if not start_date or not end_date:
        return JSONResponse(status_code=400, content={
            "success": False, "error": "start_date and end_date are required"})
    logger.info(f"GET /api/dividends/calendar - {start_date} to {end_date}, event={event}")
    result = service.get_dividend_calendar(start_date, end_date, event)
    return result
