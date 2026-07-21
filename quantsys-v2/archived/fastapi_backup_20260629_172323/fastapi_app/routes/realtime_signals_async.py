"""
实时信号 API (FastAPI 异步版本)

实时信号推送和查询
"""
from fastapi import APIRouter, Query, WebSocket
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import structlog

from adapters.outbound.repositories.signal_async_repository import SignalAsyncRepository
from infrastructure.persistence.orm.async_config import get_async_session_context

logger = structlog.get_logger(__name__)

router = APIRouter(
    prefix="/realtime-signals",
    tags=["Realtime Signals - 实时信号"]
)


class ApiResponse(BaseModel):
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None


@router.get("/latest", response_model=ApiResponse, summary="获取最新信号")
async def get_latest_signals(
    limit: int = Query(20, description="返回数量"),
    status: Optional[str] = Query(None, description="状态过滤")
):
    """
    获取最新生成的信号
    """
    try:
        async with get_async_session_context() as session:
            signal_repo = SignalAsyncRepository(session)

            signals = await signal_repo.get_signals(
                status=status,
                limit=limit
            )

            return {
                "success": True,
                "data": {
                    "signals": signals,
                    "count": len(signals),
                    "timestamp": "2026-06-27T20:00:00"
                }
            }
    except Exception as e:
        logger.exception(f"Get latest signals failed: {e}")
        return {"success": False, "error": str(e)}


@router.get("/today", response_model=ApiResponse, summary="获取今日信号")
async def get_today_signals():
    """
    获取今日生成的所有信号
    """
    try:
        from datetime import date

        today = date.today().isoformat()

        async with get_async_session_context() as session:
            signal_repo = SignalAsyncRepository(session)

            signals = await signal_repo.get_signals(
                start_date=today,
                end_date=today,
                limit=1000
            )

            return {
                "success": True,
                "data": {
                    "date": today,
                    "signals": signals,
                    "count": len(signals)
                }
            }
    except Exception as e:
        logger.exception(f"Get today signals failed: {e}")
        return {"success": False, "error": str(e)}


@router.get("/stream", response_model=ApiResponse, summary="信号流")
async def get_signal_stream(
    start_time: Optional[str] = Query(None, description="开始时间"),
    limit: int = Query(50, description="返回数量")
):
    """
    获取信号流（按时间倒序）
    """
    try:
        async with get_async_session_context() as session:
            signal_repo = SignalAsyncRepository(session)

            signals = await signal_repo.get_signals(limit=limit)

            return {
                "success": True,
                "data": {
                    "stream": signals,
                    "count": len(signals)
                }
            }
    except Exception as e:
        logger.exception(f"Get signal stream failed: {e}")
        return {"success": False, "error": str(e)}
