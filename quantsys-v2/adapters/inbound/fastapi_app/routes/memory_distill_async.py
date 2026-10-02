"""Memory Distill API - FastAPI 版（记忆蒸馏服务）
设计：docs/superpowers/plans/2026-08-12-execution-tickets.md T1（W1.5a）
"""
from typing import Any, Dict, List

from fastapi import APIRouter, Body, HTTPException, Query
import structlog

from domain.memory.distiller import MemoryDistiller

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["Memory - 蒸馏"])


def _get_distiller() -> MemoryDistiller:
    """获取 MemoryDistiller 实例（**按端口注入**其仓储依赖）。

    2026-10-02（REQ-261001145152-3982 审查）：
    原实现是 `return MemoryDistiller()` —— 而 `__init__` 要求必填 `memory_repo`，
    于是本路由两个**线上已注册**端点（`/api/memory/distill/inputs`、`/candidates`）
    每次调用都抛 `TypeError: missing 1 required positional argument: 'memory_repo'`，
    即必然 500。

    现在按仓内 DI 口径**解析端口再注入**：
      · 有 `IMemoryRepository` 实现（或测试里打了桩）→ 正常构造，功能可用；
      · 端口**无实现**（实测全仓只有端口定义、无适配器）→ 抛**明确的 503**
        （"功能未接线"），而不是让裸 TypeError 冒充未知服务器故障。
    """
    from domain.ports import IMemoryRepository
    from infrastructure.services.service_factory import ServiceFactory

    try:
        memory_repo = ServiceFactory.resolve(IMemoryRepository)
    except Exception as exc:  # noqa: BLE001 - 无实现属"能力缺失"，回 503
        logger.warning("memory_distill_unavailable", error=str(exc))
        raise HTTPException(
            status_code=503,
            detail="记忆蒸馏暂不可用：IMemoryRepository 端口尚无适配器实现（功能未接线）",
        ) from exc
    return MemoryDistiller(memory_repo=memory_repo)


@router.get("/api/memory/distill/inputs")
def get_distill_inputs(days: int = Query(7, ge=1, le=90, description="回溯天数")):
    """获取蒸馏输入数据（memory_entries + agent_decisions）

    Query Parameters:
    - days: 回溯天数（1-90，默认 7）

    Response:
    {
        "episodes": [
            {"id": 1, "title": "...", "content": "...", ...},
            ...
        ],
        "decisions": [
            {"id": 1, "decision_type": "...", "reasoning": "...", "success": true/false},
            ...
        ]
    }
    """
    try:
        distiller = _get_distiller()
        result = distiller.collect_inputs(days=days)
        return result
    except Exception as e:
        logger.error(f"get_distill_inputs failed: {e}")
        raise HTTPException(status_code=500, detail=f"获取蒸馏输入失败: {str(e)}")


@router.post("/api/memory/distill/candidates")
def save_distill_candidates(payload: Dict[str, Any] = Body(...)):
    """保存蒸馏出的候选规则

    Request Body:
    {
        "candidates": [
            {
                "title": "规则标题",
                "content": "规则内容",
                "evidence_ids": [1, 5, 12]  // 必须引用输入中的 ID
            },
            ...
        ]
    }

    Response:
    {
        "saved": 5,
        "skipped": 2
    }
    """
    try:
        candidates = payload.get("candidates", [])
        if not candidates:
            raise HTTPException(status_code=400, detail="Missing required field: candidates")

        distiller = _get_distiller()
        result = distiller.save_candidates(candidates)
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"save_distill_candidates failed: {e}")
        raise HTTPException(status_code=500, detail=f"保存蒸馏候选失败: {str(e)}")
