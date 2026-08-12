"""Memory API - FastAPI 版（统一记忆存储服务）
设计：docs/superpowers/plans/2026-08-12-framework-evolution-roadmap.md W1.2
"""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, HTTPException, Query
from fastapi.responses import JSONResponse
import structlog

from adapters.outbound.repositories.memory_repository import MemoryRepository
from domain.memory import MemoryEntry, MemoryService

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["Memory - 统一记忆"])


def _get_service() -> MemoryService:
    """获取 MemoryService 实例（BaseORMRepository 自动取线程级 scoped session）"""
    return MemoryService(MemoryRepository())


@router.post("/api/memory")
def create_memory(payload: Dict[str, Any] = Body(...)):
    """创建新记忆条目

    证据链门禁：evidence 为空时，status 只能是 testing（或被拒）

    Request Body:
    {
        "kind": "rule|episode|experience|stock_note",
        "scope": "global|stock:X|strategy:Y|sector:Z",
        "title": "记忆标题",
        "content": "记忆内容",
        "payload": {},  // 结构化数据（可选）
        "evidence": {},  // 证据链（testing/active 必需）
        "status": "testing|active|deprecated|archived",
        "confidence": 0.3,
        "provenance": {"session_kind": "...", "channel": "...", "session_id": "..."},
        "source": "distiller|agent|manual|recall"
    }
    """
    try:
        service = _get_service()
        entry = MemoryEntry.from_dict(payload)
        result = service.create(entry)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"create_memory failed: {e}")
        raise HTTPException(status_code=500, detail=f"创建记忆失败: {str(e)}")


@router.get("/api/memory/search")
def search_memory(
    q: Optional[str] = Query(None, description="查询文本（BM25+向量混合检索）"),
    scope: Optional[str] = Query(None, description="范围过滤"),
    kind: Optional[str] = Query(None, description="类型过滤"),
    status: Optional[str] = Query(None, description="状态过滤"),
    limit: int = Query(20, ge=1, le=100, description="返回数量上限"),
):
    """检索记忆（W1.3 混合检索：BM25(jieba) + 向量 + RRF）

    Query Parameters:
    - q: 查询文本（带 q 时走混合检索；不带 q 时为过滤列举）
    - scope: 范围过滤（global | stock:X | strategy:Y | sector:Z）
    - kind: 类型过滤（rule | episode | experience | stock_note）
    - status: 状态过滤（testing | active | deprecated | archived）
    - limit: 返回数量上限（1-100，默认 20）

    Response（带 q）:
    {
        "items": [...带 score 与 source(bm25|vector|both)],
        "total": N,
        "degraded": false,  // true = ollama 不可达，已降级纯 BM25
        "strategy": "hybrid|bm25|vector|none"
    }
    """
    try:
        service = _get_service()
        if q:
            return service.hybrid_search(
                q=q, scope=scope, kind=kind, status=status, limit=limit
            )
        results = service.search(q=None, scope=scope, kind=kind, status=status, limit=limit)
        return {"items": results, "total": len(results), "degraded": False, "strategy": "filter"}
    except Exception as e:
        logger.error(f"search_memory failed: {e}")
        raise HTTPException(status_code=500, detail=f"检索记忆失败: {str(e)}")


@router.get("/api/memory/export")
def export_memory():
    """全量导出记忆（JSON 格式，迁移保险用）"""
    try:
        service = _get_service()
        results = service.export_all()
        return {"items": results, "total": len(results)}
    except Exception as e:
        logger.error(f"export_memory failed: {e}")
        raise HTTPException(status_code=500, detail=f"导出记忆失败: {str(e)}")


@router.get("/api/memory/health")
def health_check():
    """健康检查"""
    return {"status": "ok", "service": "memory"}


@router.get("/api/memory/{entry_id}")
def get_memory(entry_id: int):
    """根据 ID 获取记忆"""
    try:
        service = _get_service()
        result = service.get_by_id(entry_id)
        if not result:
            raise HTTPException(status_code=404, detail=f"Memory entry not found: id={entry_id}")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"get_memory failed: {e}")
        raise HTTPException(status_code=500, detail=f"获取记忆失败: {str(e)}")


@router.post("/api/memory/{entry_id}/validate")
def validate_memory(
    entry_id: int,
    payload: Dict[str, Any] = Body(...),
):
    """验证记忆条目，更新置信度

    置信度爬坡规则：
    - < 10 样本：0.3
    - 10-30 样本：0.5
    - > 30 样本：0.7

    Request Body:
    {
        "success": true/false,  // 本次验证是否成功
        "promote": false  // 是否提升状态（testing → active）
    }
    """
    try:
        success = payload.get("success", False)
        promote = payload.get("promote", False)

        service = _get_service()
        result = service.validate(entry_id, success=success, promote=promote)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"validate_memory failed: {e}")
        raise HTTPException(status_code=500, detail=f"验证记忆失败: {str(e)}")


@router.post("/api/memory/{entry_id}/supersede")
def supersede_memory(
    entry_id: int,
    payload: Dict[str, Any] = Body(...),
):
    """标记记忆被替代

    Request Body:
    {
        "new_id": 123  // 替代的新记忆 ID
    }
    """
    try:
        new_id = payload.get("new_id")
        if not new_id:
            raise HTTPException(status_code=400, detail="Missing required field: new_id")

        service = _get_service()
        result = service.supersede(old_id=entry_id, new_id=new_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"supersede_memory failed: {e}")
        raise HTTPException(status_code=500, detail=f"标记替代失败: {str(e)}")


@router.post("/api/memory/import")
def import_memory(payload: Dict[str, Any] = Body(...)):
    """批量导入记忆条目（往返无损用）

    Request Body:
    {
        "entries": [
            {...},  // MemoryEntry dict
            {...}
        ]
    }

    Response:
    {
        "imported": 10,
        "skipped": 2,
        "errors": [...]
    }
    """
    try:
        entries = payload.get("entries", [])
        if not entries:
            raise HTTPException(status_code=400, detail="Missing required field: entries")

        service = _get_service()
        result = service.import_entries(entries)
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"import_memory failed: {e}")
        raise HTTPException(status_code=500, detail=f"导入记忆失败: {str(e)}")
