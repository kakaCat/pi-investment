"""Memory API - FastAPI 版（统一记忆存储服务）
设计：docs/superpowers/plans/2026-08-12-framework-evolution-roadmap.md W1.2

⚠️ 2026-08-25 起：写入功能已停用，迁移到 Agent OS 记忆库（agent-dh 所有记忆插件调用走 @pi-investment/os-memory 适配器）。
   保留本模块仅供：① 历史数据回填（export 恢复后灌 OS）；② 过渡期只读查询（agent-dh 已不调用）。
   背景：ollama embedding 服务挂起导致写入超时 30s+，用户决策统一使用 Agent OS（/api/v1/memory，postgres 持久无 embedding 依赖）。
"""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, HTTPException, Query
from fastapi.responses import JSONResponse
import structlog

from adapters.outbound.repositories.memory_repository import MemoryRepository
from adapters.outbound.repositories.memory_recall_audit_repository import MemoryRecallAuditRepository
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


# ========== 召回审计 API（P1-T4）==========
# 注意：这些路由必须在 /api/memory/{entry_id} 之前，否则会被通配路由拦截

@router.post("/api/memory/recall-audit", status_code=201)
def create_recall_audit(payload: Dict[str, Any] = Body(...)):
    """记录一次召回的门禁结果与命中明细

    Request Body:
    {
        "ts": "2026-08-13T10:00:00+00:00",
        "session_id": "s-123",
        "flow": "chat|watch|skill",
        "query_text": "查询文本",
        "strategy": "hybrid|bm25|vector",
        "degraded": false,
        "gate_result": "injected|suppressed",
        "suppress_reason": "low_score|...",
        "hits": [{"memory_id": 101, "score": 0.85, "title": "..."}, ...]
    }
    """
    try:
        # 校验必需字段
        flow = payload.get("flow", "").strip()
        gate_result = payload.get("gate_result", "").strip()
        if not flow:
            raise HTTPException(status_code=422, detail="Missing required field: flow")
        if not gate_result:
            raise HTTPException(status_code=422, detail="Missing required field: gate_result")

        repo = MemoryRecallAuditRepository()
        result = repo.create(payload)
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"create_recall_audit failed: {e}")
        raise HTTPException(status_code=500, detail=f"创建召回审计失败: {str(e)}")


@router.get("/api/memory/recall-audit")
def list_recall_audit(
    flow: Optional[str] = Query(None),
    gate_result: Optional[str] = Query(None),
    suppressed_only: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    """分页列举召回审计记录（ts DESC）

    Query Parameters:
    - flow: 筛选流（chat|watch|skill）
    - gate_result: 筛选结果（injected|suppressed）
    - suppressed_only: "true" = 只返回被抑制的
    - date_from/date_to: ISO 8601 日期范围
    - page/page_size: 分页
    """
    try:
        suppressed_only_bool = suppressed_only and suppressed_only.lower() == "true"
        repo = MemoryRecallAuditRepository()
        items, total = repo.list_filtered(
            flow=flow,
            gate_result=gate_result,
            suppressed_only=suppressed_only_bool,
            date_from=date_from,
            date_to=date_to,
            page=page,
            page_size=page_size,
        )
        return {"items": items, "total": total}
    except Exception as e:
        logger.error(f"list_recall_audit failed: {e}")
        raise HTTPException(status_code=500, detail=f"列举召回审计失败: {str(e)}")


@router.get("/api/memory/recall-audit/stats")
def recall_audit_stats(
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
):
    """聚合统计：注入率、分流、抑制原因、分数直方图

    Response:
    {
        "total": N,
        "injected": N,
        "suppressed": N,
        "injection_rate": 0.xx,
        "by_flow": {flow: {"total": N, "injected": N, "suppressed": N}},
        "suppress_reasons": {reason: N},
        "score_histogram": [{"bucket": "0.0-0.1", "count": N}, ...]
    }
    """
    try:
        repo = MemoryRecallAuditRepository()
        stats = repo.get_stats(date_from=date_from, date_to=date_to)
        return stats
    except Exception as e:
        logger.error(f"recall_audit_stats failed: {e}")
        raise HTTPException(status_code=500, detail=f"召回审计统计失败: {str(e)}")


@router.post("/api/memory/recall-audit/{audit_id}/feedback")
def recall_audit_feedback(
    audit_id: int,
    payload: Dict[str, Any] = Body(...),
):
    """为 hits 数组中某条记忆标注 feedback

    Request Body:
    {
        "memory_id": 101,
        "feedback": "relevant|irrelevant",
        "feedback_by": "human|agent"
    }

    规则：
    - human 覆盖 agent → 允许
    - agent 覆盖 human → 409
    - audit_id 不存在 / memory_id 不在 hits 中 → 404
    - feedback 非法值 → 422
    """
    try:
        memory_id = payload.get("memory_id")
        feedback = payload.get("feedback")
        feedback_by = payload.get("feedback_by")

        if not memory_id:
            raise HTTPException(status_code=422, detail="Missing required field: memory_id")
        if feedback not in ("relevant", "irrelevant"):
            raise HTTPException(status_code=422, detail="feedback must be 'relevant' or 'irrelevant'")
        if feedback_by not in ("human", "agent"):
            raise HTTPException(status_code=422, detail="feedback_by must be 'human' or 'agent'")

        repo = MemoryRecallAuditRepository()
        result = repo.update_feedback(
            audit_id=audit_id,
            memory_id=memory_id,
            feedback=feedback,
            feedback_by=feedback_by,
        )
        return result
    except HTTPException:
        raise
    except ValueError as e:
        # audit 不存在 / memory_id 不在 hits
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        # agent 覆盖 human
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        logger.error(f"recall_audit_feedback failed: {e}")
        raise HTTPException(status_code=500, detail=f"召回审计标注失败: {str(e)}")


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


@router.post("/api/memory/{entry_id}/deprecate")
def deprecate_memory(entry_id: int):
    """废弃记忆条目（status → deprecated）

    T4.3 确认门禁的"废弃"路径：supersede 需要 new_id（替代场景），
    无替代品的单纯废弃走本端点。deprecated 条目不参与召回。
    """
    try:
        service = _get_service()
        result = service.update(entry_id, {"status": "deprecated"})
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"deprecate_memory failed: {e}")
        raise HTTPException(status_code=500, detail=f"废弃记忆失败: {str(e)}")


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
