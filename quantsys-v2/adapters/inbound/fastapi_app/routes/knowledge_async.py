"""Knowledge API - FastAPI 版（知识库查询/应用/摘要/验证）

背景：knowledge 路由此前只有 Flask 版（adapters/inbound/api/routes/knowledge_management.py），
FastAPI 侧缺失导致 /api/knowledge/* 404（W1.1 服务层修复因此无法经 API 生效）。
本文件补齐 FastAPI 路由，复用同一个 KnowledgeService。
"""
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, HTTPException, Query
import structlog

from application.services.knowledge_service import KnowledgeService

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["Knowledge - 知识库"])


@router.get("/api/knowledge/active")
def get_active_knowledge(domain: Optional[str] = Query(None, description="知识领域过滤（可选）")):
    """获取活跃知识列表"""
    try:
        service = KnowledgeService()
        return service.get_active_knowledge(domain)
    except Exception as e:
        logger.error(f"get_active_knowledge failed: {e}")
        raise HTTPException(status_code=500, detail=f"查询知识失败: {str(e)}")


@router.post("/api/knowledge/apply")
def apply_knowledge(context: Dict[str, Any] = Body(...)):
    """应用知识到当前决策上下文"""
    try:
        service = KnowledgeService()
        return service.apply_knowledge(context)
    except Exception as e:
        logger.error(f"apply_knowledge failed: {e}")
        raise HTTPException(status_code=500, detail=f"应用知识失败: {str(e)}")


@router.get("/api/knowledge/summary")
def get_knowledge_summary():
    """知识库统计摘要"""
    try:
        service = KnowledgeService()
        return service.get_knowledge_summary()
    except Exception as e:
        logger.error(f"get_knowledge_summary failed: {e}")
        raise HTTPException(status_code=500, detail=f"获取知识摘要失败: {str(e)}")


@router.post("/api/knowledge/{knowledge_id}/validate")
def validate_knowledge(knowledge_id: str, payload: Dict[str, Any] = Body(...)):
    """验证知识（应用后反馈结果）

    Request Body: {"success": true/false}
    """
    try:
        service = KnowledgeService()
        success = bool(payload.get("success", False))
        return service.validate_knowledge(knowledge_id, success)
    except Exception as e:
        logger.error(f"validate_knowledge failed: {e}")
        raise HTTPException(status_code=500, detail=f"验证知识失败: {str(e)}")
