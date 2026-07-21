"""
图表数据 API (FastAPI 异步版本)

图表数据查询
"""
from fastapi import APIRouter, Query
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import structlog

from application.services.core_async_services import DataAsyncService

logger = structlog.get_logger(__name__)

router = APIRouter(
    prefix="/charts",
    tags=["Charts - 图表数据"]
)


class ApiResponse(BaseModel):
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None


@router.get("/kline/{symbol}", response_model=ApiResponse, summary="K线图数据")
async def get_kline_chart(
    symbol: str,
    period: str = Query("daily", description="周期: daily/weekly/monthly"),
    limit: int = Query(250, description="返回数量")
):
    """
    获取K线图数据
    """
    try:
        service = DataAsyncService()
        klines = await service.get_klines(symbol, limit=limit)

        return {
            "success": True,
            "data": {
                "symbol": symbol,
                "period": period,
                "data": klines
            }
        }
    except Exception as e:
        logger.exception(f"Get kline chart failed: {e}")
        return {"success": False, "error": str(e)}


@router.get("/price/{symbol}", response_model=ApiResponse, summary="价格走势图")
async def get_price_chart(
    symbol: str,
    start_date: Optional[str] = Query(None, description="开始日期"),
    end_date: Optional[str] = Query(None, description="结束日期")
):
    """
    获取价格走势图数据
    """
    try:
        service = DataAsyncService()
        klines = await service.get_klines(symbol, start_date, end_date)

        # 提取价格数据
        prices = [{"date": k["trade_date"], "price": k["close"]} for k in klines]

        return {
            "success": True,
            "data": {
                "symbol": symbol,
                "prices": prices
            }
        }
    except Exception as e:
        logger.exception(f"Get price chart failed: {e}")
        return {"success": False, "error": str(e)}
