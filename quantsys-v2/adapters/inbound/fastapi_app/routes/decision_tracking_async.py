"""
决策跟踪 API (FastAPI 异步版本)

决策记录和历史追踪
"""
from fastapi import APIRouter, Query, Body
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
import structlog

logger = structlog.get_logger(__name__)

router = APIRouter(
    prefix="/decision-tracking",
    tags=["Decision Tracking - 决策跟踪"]
)


class ApiResponse(BaseModel):
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None


class DecisionRecord(BaseModel):
    """决策记录"""
    decision_type: str = Field(..., description="决策类型")
    symbol: Optional[str] = Field(None, description="股票代码")
    action: str = Field(..., description="操作")
    reason: str = Field(..., description="原因")
    confidence: Optional[float] = Field(None, description="置信度")
    metadata: Optional[Dict] = Field(None, description="元数据")


# 内存存储（简化版）
_decision_store = []


@router.post("/record", response_model=ApiResponse, summary="记录决策")
async def record_decision(decision: DecisionRecord):
    """
    记录一个决策
    """
    try:
        decision_data = {
            "id": len(_decision_store) + 1,
            "decision_type": decision.decision_type,
            "symbol": decision.symbol,
            "action": decision.action,
            "reason": decision.reason,
            "confidence": decision.confidence,
            "metadata": decision.metadata,
            "created_at": datetime.now().isoformat()
        }

        _decision_store.append(decision_data)

        return {
            "success": True,
            "data": decision_data
        }
    except Exception as e:
        logger.exception(f"Record decision failed: {e}")
        return {"success": False, "error": str(e)}


@router.get("/{decision_id}", response_model=ApiResponse, summary="获取决策详情")
async def get_decision(decision_id: int):
    """
    获取决策详情
    """
    try:
        for decision in _decision_store:
            if decision["id"] == decision_id:
                return {
                    "success": True,
                    "data": decision
                }

        return {
            "success": False,
            "error": f"决策 {decision_id} 不存在"
        }
    except Exception as e:
        logger.exception(f"Get decision failed: {e}")
        return {"success": False, "error": str(e)}


@router.get("/history", response_model=ApiResponse, summary="决策历史")
async def get_decision_history(
    decision_type: Optional[str] = Query(None, description="决策类型"),
    symbol: Optional[str] = Query(None, description="股票代码"),
    limit: int = Query(50, description="返回数量")
):
    """
    查询决策历史
    """
    try:
        filtered = _decision_store

        if decision_type:
            filtered = [d for d in filtered if d.get("decision_type") == decision_type]

        if symbol:
            filtered = [d for d in filtered if d.get("symbol") == symbol]

        # 返回最新的N条
        result = list(reversed(filtered))[:limit]

        return {
            "success": True,
            "data": {
                "decisions": result,
                "count": len(result)
            }
        }
    except Exception as e:
        logger.exception(f"Get decision history failed: {e}")
        return {"success": False, "error": str(e)}


@router.get("/stats", response_model=ApiResponse, summary="决策统计")
async def get_decision_stats():
    """
    获取决策统计信息
    """
    try:
        stats = {
            "total": len(_decision_store),
            "by_type": {},
            "by_action": {}
        }

        for decision in _decision_store:
            # 按类型统计
            dtype = decision.get("decision_type", "unknown")
            stats["by_type"][dtype] = stats["by_type"].get(dtype, 0) + 1

            # 按操作统计
            action = decision.get("action", "unknown")
            stats["by_action"][action] = stats["by_action"].get(action, 0) + 1

        return {
            "success": True,
            "data": stats
        }
    except Exception as e:
        logger.exception(f"Get decision stats failed: {e}")
        return {"success": False, "error": str(e)}
