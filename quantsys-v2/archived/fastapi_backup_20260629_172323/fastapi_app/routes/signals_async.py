"""
交易信号 API (FastAPI 异步版本)

集成 SignalAsyncRepository
"""
from fastapi import APIRouter, HTTPException, Depends, Query, Body
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import date
import structlog

from application.services.core_async_services import DataAsyncService
from adapters.outbound.repositories.signal_async_repository import SignalAsyncRepository
from infrastructure.persistence.orm.async_config import get_async_session_context

logger = structlog.get_logger(__name__)

router = APIRouter(
    prefix="/signals",
    tags=["Signals - 交易信号"]
)


# ==================== Pydantic 模型 ====================

class CreateSignalRequest(BaseModel):
    """创建信号请求"""
    symbol: str = Field(..., description="股票代码")
    signal_date: str = Field(..., description="信号日期 YYYY-MM-DD")
    action: str = Field(..., description="操作类型: BUY/SELL/HOLD")
    action_type: int = Field(..., description="操作类型代码")
    strategy_id: str = Field(..., description="策略ID")
    name: str = Field(..., description="信号名称")
    price: Optional[float] = Field(None, description="信号价格")
    confidence: Optional[float] = Field(None, description="置信度 0-1")
    reason: Optional[str] = Field(None, description="信号原因")


class SignalResponse(BaseModel):
    """信号响应"""
    id: int
    symbol: str
    signal_date: str
    action: str
    strategy_id: str
    status: str
    confidence: Optional[float] = None


class ApiResponse(BaseModel):
    """通用API响应"""
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None


# ==================== 路由 ====================

@router.get("", response_model=ApiResponse, summary="查询交易信号")
async def list_signals(
    symbol: Optional[str] = Query(None, description="股票代码"),
    start_date: Optional[str] = Query(None, description="开始日期"),
    end_date: Optional[str] = Query(None, description="结束日期"),
    signal_type: Optional[str] = Query(None, description="信号类型"),
    status: Optional[str] = Query(None, description="信号状态"),
    limit: int = Query(100, description="返回数量")
):
    """
    查询交易信号列表

    - **symbol**: 股票代码（可选）
    - **start_date**: 开始日期（可选）
    - **end_date**: 结束日期（可选）
    - **signal_type**: 信号类型（可选）
    - **status**: 信号状态（可选）
    - **limit**: 返回数量，默认100
    """
    try:
        async with get_async_session_context() as session:
            signal_repo = SignalAsyncRepository(session)

            signals = await signal_repo.get_signals(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                signal_type=signal_type,
                status=status,
                limit=limit
            )

            return {
                "success": True,
                "data": signals
            }

    except Exception as e:
        logger.exception(f"List signals failed: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@router.get("/pending", response_model=ApiResponse, summary="获取待处理信号")
async def get_pending_signals(
    limit: int = Query(100, description="返回数量")
):
    """
    获取待处理的信号

    - **limit**: 返回数量，默认100
    """
    try:
        async with get_async_session_context() as session:
            signal_repo = SignalAsyncRepository(session)

            signals = await signal_repo.get_pending_signals(limit=limit)

            return {
                "success": True,
                "data": signals
            }

    except Exception as e:
        logger.exception(f"Get pending signals failed: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@router.get("/by-strategy/{strategy_id}", response_model=ApiResponse, summary="按策略查询信号")
async def get_signals_by_strategy(
    strategy_id: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
):
    """
    按策略ID查询信号

    - **strategy_id**: 策略ID
    - **start_date**: 开始日期（可选）
    - **end_date**: 结束日期（可选）
    """
    try:
        async with get_async_session_context() as session:
            signal_repo = SignalAsyncRepository(session)

            signals = await signal_repo.get_signals_by_strategy(
                strategy_id=strategy_id,
                start_date=start_date,
                end_date=end_date
            )

            return {
                "success": True,
                "data": signals
            }

    except Exception as e:
        logger.exception(f"Get signals by strategy failed: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@router.post("/scan", response_model=ApiResponse, summary="扫描交易机会")
async def scan_opportunities(
    symbols: Optional[List[str]] = Body(None, description="股票代码列表"),
    technical: Optional[List[str]] = Body(None, description="技术面条件"),
    fundamental: Optional[List[str]] = Body(None, description="基本面条件"),
    limit: int = Body(20, description="返回数量"),
    weights: Optional[Dict[str, float]] = Body(None, description="权重配置")
):
    """
    扫描交易机会（支持多维评分）

    - **symbols**: 股票代码列表（可选，留空扫描全市场）
    - **technical**: 技术面条件列表
    - **fundamental**: 基本面条件列表
    - **limit**: 返回数量
    - **weights**: 权重配置 {technical, fundamental, capital}
    """
    try:
        # TODO: 接入实际的机会扫描服务
        # from application.services.opportunity_scanner import OpportunityScannerService
        # service = OpportunityScannerService()
        # result = await service.scan(symbols, technical, fundamental, limit, weights)

        # 临时返回示例数据
        opportunities = [
            {
                "symbol": "600519.SH",
                "name": "贵州茅台",
                "score": 85.5,
                "technical_score": 80.0,
                "fundamental_score": 90.0,
                "capital_score": 85.0,
                "price": 1680.0,
                "change_pct": 2.5,
                "signals": ["RSI超卖", "MACD金叉"],
                "risk_level": "low"
            }
        ]

        return {
            "success": True,
            "opportunities": opportunities[:limit]
        }
    except Exception as e:
        logger.exception(f"Scan opportunities failed: {e}")
        return {"success": False, "error": str(e)}


@router.post("", response_model=ApiResponse, status_code=201, summary="创建交易信号")
async def create_signal(request: CreateSignalRequest):
    """
    创建交易信号
    """
    try:
        from datetime import datetime

        signal_data = {
            'symbol': request.symbol,
            'signal_date': request.signal_date,
            'action': request.action,
            'action_type': request.action_type,
            'strategy_id': request.strategy_id,
            'name': request.name,
            'price': request.price,
            'confidence': request.confidence,
            'reason': request.reason,
            'status': 'pending',
            'created_at': datetime.now()
        }

        async with get_async_session_context() as session:
            signal_repo = SignalAsyncRepository(session)

            signal_id = await signal_repo.create_signal(signal_data)

            if not signal_id:
                raise HTTPException(status_code=500, detail="创建信号失败")

            return {
                "success": True,
                "data": {"id": signal_id, "message": "信号创建成功"}
            }

    except Exception as e:
        logger.exception(f"Create signal failed: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@router.put("/{signal_id}/status", response_model=ApiResponse, summary="更新信号状态")
async def update_signal_status(
    signal_id: int,
    status: str = Query(..., description="新状态"),
    error_description: Optional[str] = Query(None, description="错误描述")
):
    """
    更新信号状态

    - **signal_id**: 信号ID
    - **status**: 新状态
    - **error_description**: 错误描述（可选）
    """
    try:
        async with get_async_session_context() as session:
            signal_repo = SignalAsyncRepository(session)

            success = await signal_repo.update_signal_status(
                signal_id=signal_id,
                status=status,
                error_description=error_description
            )

            if not success:
                raise HTTPException(status_code=404, detail=f"信号 {signal_id} 不存在或更新失败")

            return {
                "success": True,
                "data": {"message": f"信号 {signal_id} 状态更新成功"}
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Update signal status failed: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@router.get("/stats/by-status", response_model=ApiResponse, summary="按状态统计信号")
async def count_signals_by_status(
    status: str = Query(..., description="信号状态")
):
    """
    统计某状态的信号数量

    - **status**: 信号状态
    """
    try:
        async with get_async_session_context() as session:
            signal_repo = SignalAsyncRepository(session)

            count = await signal_repo.count_by_status(status)

            return {
                "success": True,
                "data": {"status": status, "count": count}
            }

    except Exception as e:
        logger.exception(f"Count signals by status failed: {e}")
        return {
            "success": False,
            "error": str(e)
        }
