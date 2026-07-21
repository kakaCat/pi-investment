"""
分析工具 API (FastAPI 异步版本)

股票分析和对比工具
"""
from fastapi import APIRouter, Query, Body, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Union
import structlog
import asyncio

from application.services.core_async_services import FactorAnalysisAsyncService, DataAsyncService
from ..models.analysis import SwingPointsRequest, SwingPointsResponse

logger = structlog.get_logger(__name__)

router = APIRouter(
    prefix="/analysis",
    tags=["Analysis - 分析工具"]
)


class ApiResponse(BaseModel):
    success: bool
    data: Optional[Union[Dict, List]] = None
    error: Optional[str] = None


class CompareRequest(BaseModel):
    symbols: List[str]
    factor_names: Optional[List[str]] = None


@router.get("/stock/{symbol}/factors", response_model=ApiResponse, summary="获取股票因子")
async def get_stock_factors(
    symbol: str,
    factor_names: Optional[List[str]] = Query(None, description="因子名称列表")
):
    """
    获取股票的因子数据
    """
    try:
        service = FactorAnalysisAsyncService()
        factors = await service.get_factors(symbol, factor_names)

        return {
            "success": True,
            "data": {
                "symbol": symbol,
                "factors": factors
            }
        }
    except Exception as e:
        logger.exception(f"Get stock factors failed: {e}")
        return {"success": False, "error": str(e)}


@router.post("/stocks/compare", response_model=ApiResponse, summary="股票对比")
async def compare_stocks(request: CompareRequest):
    """
    对比多只股票的因子数据
    """
    try:
        service = FactorAnalysisAsyncService()

        comparison = {}
        for symbol in request.symbols:
            factors = await service.get_factors(symbol, request.factor_names)
            comparison[symbol] = factors

        return {
            "success": True,
            "data": {
                "comparison": comparison,
                "symbols": request.symbols
            }
        }
    except Exception as e:
        logger.exception(f"Compare stocks failed: {e}")
        return {"success": False, "error": str(e)}


@router.get("/stock/{symbol}/klines", response_model=ApiResponse, summary="获取K线数据")
async def get_stock_klines(
    symbol: str,
    start_date: Optional[str] = Query(None, description="开始日期"),
    end_date: Optional[str] = Query(None, description="结束日期"),
    limit: int = Query(250, description="返回数量")
):
    """
    获取股票K线数据
    """
    try:
        service = DataAsyncService()
        klines = await service.get_klines(symbol, start_date, end_date, limit)

        return {
            "success": True,
            "data": {
                "symbol": symbol,
                "klines": klines,
                "count": len(klines)
            }
        }
    except Exception as e:
        logger.exception(f"Get stock klines failed: {e}")
        return {"success": False, "error": str(e)}


@router.post("/swing-points", response_model=SwingPointsResponse, summary="ZigZag 波段分析")
async def analyze_swing_points(request: SwingPointsRequest = Body(...)):
    """
    ZigZag 波段分析 - 识别历史价格拐点和买卖点
    
    **算法原理**:
    1. 从第一个数据点开始，追踪当前趋势方向（上涨/下跌）
    2. 当价格反转超过 min_change（百分比），确认一个拐点
    3. 局部低点 = 买点，局部高点 = 卖点
    4. 最终输出所有买卖点序列及收益统计
    
    **参数说明**:
    - **symbol**: 股票代码（如 600519 贵州茅台）
    - **min_change**: 最小波动幅度百分比（1-30%，默认 5%）
    - **start_date/end_date**: 分析时间范围（可选，默认最近 1 年）
    - **lookback_days**: 回溯天数（可选，与日期范围二选一）
    
    **返回数据**:
    - `swing_points`: 所有拐点列表（高低交替）
    - `trades`: 交易配对（买入→卖出）
    - `summary`: 统计摘要（胜率、收益率、持仓天数等）
    
    **示例**:
    ```json
    {
        "symbol": "600519",
        "min_change": 5.0,
        "start_date": "2025-01-01",
        "end_date": "2026-06-01"
    }
    ```
    """
    try:
        from application.services.swing_point_service import SwingPointService

        logger.info(f"开始 ZigZag 波段分析: {request.symbol}, 阈值: {request.min_change}%")

        # 将同步服务调用包装为异步（Python 3.8 兼容）
        service = SwingPointService()
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            service.analyze,
            request.dict(exclude_none=True)
        )
        
        # 检查是否有错误
        if isinstance(result, dict) and 'error' in result:
            logger.error(f"波段分析失败: {result['error']}")
            raise HTTPException(status_code=400, detail=result['error'])
        
        logger.info(f"波段分析完成: {request.symbol}, 拐点数: {len(result.get('swing_points', []))}")
        
        return SwingPointsResponse(
            success=True,
            data=result
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"ZigZag 波段分析异常: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"服务器内部错误: {str(e)}"
        )
