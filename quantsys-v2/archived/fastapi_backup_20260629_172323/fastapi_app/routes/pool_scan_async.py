"""
池子扫描 API (FastAPI 异步版本)

股票池扫描功能
"""
from fastapi import APIRouter, Query, Body
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import structlog

from application.services.stock_pool_async_service import StockPoolAsyncService

logger = structlog.get_logger(__name__)

router = APIRouter(
    prefix="/pool-scan",
    tags=["Pool Scan - 池子扫描"]
)


class ApiResponse(BaseModel):
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None


class ScanRequest(BaseModel):
    watchlist: List[str] = []


@router.post("/universe", response_model=ApiResponse, summary="获取扫描范围")
async def get_scan_universe(request: ScanRequest):
    """
    获取扫描范围（自选股 + 热门股）
    """
    try:
        service = StockPoolAsyncService()
        universe = await service.get_scan_universe(request.watchlist)

        return {
            "success": True,
            "data": {
                "symbols": universe,
                "count": len(universe)
            }
        }
    except Exception as e:
        logger.exception(f"Get scan universe failed: {e}")
        return {"success": False, "error": str(e)}


@router.get("/hot-stocks", response_model=ApiResponse, summary="获取热门股票")
async def get_hot_stocks():
    """
    获取热门股票池
    """
    try:
        service = StockPoolAsyncService()
        hot_stocks = await service.get_hot_stocks()

        return {
            "success": True,
            "data": {
                "symbols": hot_stocks,
                "count": len(hot_stocks)
            }
        }
    except Exception as e:
        logger.exception(f"Get hot stocks failed: {e}")
        return {"success": False, "error": str(e)}
