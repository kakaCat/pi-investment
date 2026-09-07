"""
市场数据 API (FastAPI 异步版本)

提供市场数据查询服务
"""
from fastapi import APIRouter, Query
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import structlog

from adapters.shared.services import market_data_async_service, data_async_service

logger = structlog.get_logger(__name__)

router = APIRouter(
    prefix="/market",
    tags=["Market - 市场数据"]
)


class ApiResponse(BaseModel):
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None


@router.get("/stocks", response_model=ApiResponse, summary="获取股票列表")
async def get_stocks(
    market: str = Query("A", description="市场类型 A/HK"),
    limit: int = Query(1000, description="返回数量")
):
    """
    获取活跃股票列表
    """
    try:
        service = market_data_async_service
        stocks = await service.get_active_stocks(market)

        return {
            "success": True,
            "data": {
                "stocks": stocks[:limit],
                "count": len(stocks)
            }
        }
    except Exception as e:
        logger.exception(f"Get stocks failed: {e}")
        return {"success": False, "error": str(e)}


@router.get("/search", response_model=ApiResponse, summary="搜索股票")
async def search_stocks(
    keyword: str = Query(..., description="搜索关键词"),
    limit: int = Query(50, description="返回数量")
):
    """
    按名称或代码搜索股票
    """
    try:
        service = market_data_async_service
        stocks = await service.search_stocks(keyword)

        return {
            "success": True,
            "data": {
                "stocks": stocks[:limit],
                "count": len(stocks)
            }
        }
    except Exception as e:
        logger.exception(f"Search stocks failed: {e}")
        return {"success": False, "error": str(e)}


@router.get("/overview", response_model=ApiResponse, summary="市场概览")
async def get_market_overview():
    """
    获取市场概览数据
    """
    try:
        service = market_data_async_service
        overview = await service.get_market_overview()

        return {
            "success": True,
            "data": overview
        }
    except Exception as e:
        logger.exception(f"Get market overview failed: {e}")
        return {"success": False, "error": str(e)}


@router.get("/stock/{symbol}", response_model=ApiResponse, summary="获取股票详情")
async def get_stock_detail(symbol: str):
    """
    获取股票详细信息
    """
    try:
        service = data_async_service
        stock = await service.get_stock_info(symbol)

        if not stock:
            return {
                "success": False,
                "error": f"股票 {symbol} 不存在"
            }

        return {
            "success": True,
            "data": stock
        }
    except Exception as e:
        logger.exception(f"Get stock detail failed: {e}")
        return {"success": False, "error": str(e)}


@router.get("/stock/{symbol}/price", response_model=ApiResponse, summary="获取最新价格")
async def get_stock_price(symbol: str):
    """
    获取股票最新价格
    """
    try:
        service = data_async_service
        price = await service.get_latest_price(symbol)

        return {
            "success": True,
            "data": {
                "symbol": symbol,
                "price": price
            }
        }
    except Exception as e:
        logger.exception(f"Get stock price failed: {e}")
        return {"success": False, "error": str(e)}


@router.post("/prices/batch", response_model=ApiResponse, summary="批量获取价格")
async def get_batch_prices(symbols: List[str]):
    """
    批量获取多个股票的价格
    """
    try:
        service = data_async_service
        prices = await service.batch_get_prices(symbols)

        return {
            "success": True,
            "data": prices
        }
    except Exception as e:
        logger.exception(f"Get batch prices failed: {e}")
        return {"success": False, "error": str(e)}


@router.get("/quote", response_model=ApiResponse, summary="获取实时行情")
async def get_quote(
    symbol: str = Query(..., description="股票代码，如 000001.SZ")
):
    """
    获取股票实时行情（agent-ts 使用的主要接口）

    返回包含最新价格、涨跌幅等信息
    """
    try:
        service = data_async_service

        # 获取股票基本信息
        stock = await service.get_stock_info(symbol)
        if not stock:
            return {
                "success": False,
                "error": f"股票 {symbol} 不存在"
            }

        # 获取最新价格
        price = await service.get_latest_price(symbol)

        # 组合返回
        quote_data = {
            "symbol": symbol,
            "name": stock.get("name", ""),
            "price": price,
            "timestamp": None  # TODO: 添加时间戳
        }

        return {
            "success": True,
            "data": quote_data
        }
    except Exception as e:
        logger.exception(f"Get quote failed for {symbol}: {e}")
        return {"success": False, "error": str(e)}
