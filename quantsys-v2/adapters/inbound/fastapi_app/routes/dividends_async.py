"""分红数据 API — migrated to DataProviderManager."""
from typing import Any, Dict, Optional

from fastapi import APIRouter, Query, Body
from fastapi.responses import JSONResponse
import structlog

from adapters.outbound.datasources import get_data_provider_manager

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["Dividends - 分红"])


@router.get('/api/stock/{symbol}/dividends')
def get_dividends(symbol: str, years: int = Query(10)):
    logger.info(f"GET /api/stock/{symbol}/dividends - years={years}")
    mgr = get_data_provider_manager()
    return mgr.get_dividends(symbol, years=years)


@router.post('/api/dividends/screen')
def screen_dividends(payload: Optional[Dict[str, Any]] = Body(None)):
    params = payload or {}
    min_yield = params.get('min_yield', 3.0)
    min_years = params.get('min_years', 5)
    logger.info(f"POST /api/dividends/screen - min_yield={min_yield}, min_years={min_years}")
    mgr = get_data_provider_manager()
    return mgr.screen_high_dividend(min_yield=min_yield, min_years=min_years)


@router.get('/api/dividends/calendar')
def dividend_calendar(start_date: Optional[str] = Query(None), end_date: Optional[str] = Query(None), event: str = Query('ex_dividend')):
    if not start_date or not end_date:
        return JSONResponse(status_code=400, content={"success": False, "error": "start_date and end_date are required"})
    logger.info(f"GET /api/dividends/calendar - {start_date} to {end_date}, event={event}")
    mgr = get_data_provider_manager()
    return mgr.get_dividend_calendar(start_date, end_date)
