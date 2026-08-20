"""
决策追踪 API（FastAPI 版，Flask /api/decisions/* parity）

走 DecisionService → agent_decisions / pool_change_log 表（PG），
替代早期内存桩 decision_tracking_async（不同前缀 /decision-tracking，已废弃）。
"""
import structlog
from typing import Optional, Dict, Any
from fastapi import APIRouter, Body, Query
from fastapi.responses import JSONResponse

from adapters.shared.services import decision_service

logger = structlog.get_logger(__name__)

router = APIRouter(
    prefix="/api/decisions",
    tags=["Decision Tracking - 决策追踪"]
)


def _ok(data: Any) -> Dict[str, Any]:
    return {'success': True, 'data': data}


def _err(status: int, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={'success': False, 'error': message})


@router.post("/record", summary="记录决策")
def record_decision(decision_data: Dict[str, Any] = Body(...)):
    """
    记录一个决策（agent decision_record 工具调用此端点）。

    Request Body:
        decision_type（必填）、reasoning（必填）、
        context/parameters（可选，缺省 {}）、
        related_entity_type/related_entity_id/session_key（可选）
    """
    try:
        if not decision_data.get('decision_type'):
            return _err(400, '缺少必需字段: decision_type')
        if not decision_data.get('reasoning'):
            return _err(400, '缺少必需字段: reasoning')

        # agent 工具契约中 context/parameters 为可选，缺省 {}
        decision_data.setdefault('context', {})
        decision_data.setdefault('parameters', {})

        service = decision_service
        decision = service.record_decision(decision_data)
        return _ok(decision)
    except ValueError as e:
        return _err(400, str(e))
    except Exception as e:
        logger.exception(f"❌ 记录决策失败: {e}")
        return _err(500, str(e))


@router.get("/history", summary="决策历史")
def get_decision_history(
    entity_type: Optional[str] = Query(None),
    entity_id: Optional[str] = Query(None),
    decision_type: Optional[str] = Query(None),
    limit: int = Query(50),
):
    try:
        service = decision_service
        decisions = service.get_decision_history(
            entity_type=entity_type,
            entity_id=entity_id,
            decision_type=decision_type,
            limit=limit,
        )
        return _ok(decisions)
    except Exception as e:
        logger.exception(f"❌ 查询决策历史失败: {e}")
        return _err(500, str(e))


@router.get("/report", summary="决策报告")
def get_decision_report(
    entity_type: Optional[str] = Query(None),
    entity_id: Optional[str] = Query(None),
):
    if not entity_type or not entity_id:
        return _err(400, '缺少必需参数: entity_type, entity_id')
    try:
        service = decision_service
        report = service.generate_decision_report(entity_type, entity_id)
        return _ok(report)
    except Exception as e:
        logger.exception(f"❌ 生成决策报告失败: {e}")
        return _err(500, str(e))


@router.get("/pool-changes/{pool_id}", summary="池子变更历史")
def get_pool_changes(pool_id: int):
    try:
        service = decision_service
        changes = service.get_pool_change_history(pool_id=pool_id)
        return _ok(changes)
    except Exception as e:
        logger.exception(f"❌ 查询池子变更失败: {e}")
        return _err(500, str(e))


@router.get("/{decision_id}", summary="获取单个决策")
def get_decision(decision_id: str):
    try:
        service = decision_service
        decision = service.get_decision(decision_id)
        if not decision:
            return _err(404, '决策不存在')
        return _ok(decision)
    except Exception as e:
        logger.exception(f"❌ 获取决策失败: {e}")
        return _err(500, str(e))
