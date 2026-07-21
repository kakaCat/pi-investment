"""
执行记录 API (FastAPI 异步版本)

信号执行记录管理
"""
from fastapi import APIRouter, Query
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import date
import structlog

from adapters.outbound.repositories.signal_execution_async_repository import SignalExecutionAsyncRepository
from infrastructure.persistence.orm.async_config import get_async_session_context

logger = structlog.get_logger(__name__)

router = APIRouter(
    prefix="/executions",
    tags=["Executions - 执行记录"]
)


class ApiResponse(BaseModel):
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None


@router.get("", response_model=ApiResponse, summary="查询执行记录")
async def get_executions(
    status: Optional[str] = Query(None, description="状态"),
    start_date: Optional[str] = Query(None, description="开始日期"),
    end_date: Optional[str] = Query(None, description="结束日期"),
    limit: int = Query(100, description="返回数量")
):
    """
    查询信号执行记录
    """
    try:
        async with get_async_session_context() as session:
            repo = SignalExecutionAsyncRepository(session)

            executions = await repo.get_executions(
                status=status,
                start_date=start_date,
                end_date=end_date,
                limit=limit
            )

            return {
                "success": True,
                "data": {
                    "items": executions,
                    "count": len(executions)
                }
            }
    except Exception as e:
        logger.exception(f"Get executions failed: {e}")
        return {"success": False, "error": str(e)}


@router.get("/pending", response_model=ApiResponse, summary="获取待执行记录")
async def get_pending_executions(
    limit: int = Query(100, description="返回数量")
):
    """
    获取待执行的记录
    """
    try:
        async with get_async_session_context() as session:
            repo = SignalExecutionAsyncRepository(session)
            executions = await repo.get_pending_executions(limit)

            return {
                "success": True,
                "data": {
                    "items": executions,
                    "count": len(executions)
                }
            }
    except Exception as e:
        logger.exception(f"Get pending executions failed: {e}")
        return {"success": False, "error": str(e)}


@router.get("/signal/{signal_id}", response_model=ApiResponse, summary="按信号查询执行")
async def get_executions_by_signal(signal_id: int):
    """
    查询某信号的所有执行记录
    """
    try:
        async with get_async_session_context() as session:
            repo = SignalExecutionAsyncRepository(session)
            executions = await repo.get_executions_by_signal(signal_id)

            return {
                "success": True,
                "data": {
                    "items": executions,
                    "count": len(executions)
                }
            }
    except Exception as e:
        logger.exception(f"Get executions by signal failed: {e}")
        return {"success": False, "error": str(e)}


@router.put("/{execution_id}/status", response_model=ApiResponse, summary="更新执行状态")
async def update_execution_status(
    execution_id: int,
    status: str = Query(..., description="新状态"),
    error_message: Optional[str] = Query(None, description="错误消息")
):
    """
    更新执行记录状态
    """
    try:
        async with get_async_session_context() as session:
            repo = SignalExecutionAsyncRepository(session)

            success = await repo.update_execution_status(
                execution_id,
                status,
                error_message
            )

            if not success:
                return {
                    "success": False,
                    "error": f"执行记录 {execution_id} 不存在或更新失败"
                }

            return {
                "success": True,
                "data": {"message": f"执行记录 {execution_id} 状态更新成功"}
            }
    except Exception as e:
        logger.exception(f"Update execution status failed: {e}")
        return {"success": False, "error": str(e)}
