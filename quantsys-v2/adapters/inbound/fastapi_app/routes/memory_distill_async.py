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
    """获取 MemoryDistiller 实例

    2026-10-02（REQ-261001145152-3982 审查）：**原实现是坏的**——
    `MemoryDistiller.__init__` 要求必填 `memory_repo`，而这里空构造
    → 每次调用都抛 `TypeError: missing 1 required positional argument: 'memory_repo'`，
    本路由两个**线上已注册**端点（`/api/memory/distill/inputs`、`/candidates`）必然 500。

    根因：`IMemoryRepository`（domain/ports/repository_ports_extended.py:288）
    **只有端口、没有任何适配器实现**（全仓搜不到实现类），故此处无从注入。

    这里改为**响亮失败**：503 + 写明原因，而不是让裸 TypeError 冒充未知故障
    （「失败要响亮」；也让调用方一眼看出是"功能未接线"而非"查询出错"）。
    待补上 IMemoryRepository 的适配器实现后，把本函数改成
    `MemoryDistiller(memory_repo=<impl>)` 即可恢复。
    """
    raise HTTPException(
        status_code=503,
        detail="记忆蒸馏暂不可用：IMemoryRepository 端口尚无适配器实现（功能未接线）",
    )


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
