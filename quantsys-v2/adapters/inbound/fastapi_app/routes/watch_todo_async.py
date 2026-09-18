"""盯盘待办闭环 API - FastAPI 版（REQ-c9f899 t5，2026-09-18）

端点（interfaces.md §1.1）：

  GET  /api/watch/todos                 待办列表（level/flow_state/account/terminal/limit）
  POST /api/watch/todos/{id}/claim      认领（body: {owner_ref}）
  POST /api/watch/todos/{id}/close      收敛（body: {terminal, close_reason, next_condition?,
                                                  action_kind, decision_audit_id?}）

响应风格照 routes/watch_async.py：成功 {'success': True, 'data': {...}}；
错误 {'success': False, 'error': <稳定错误码>, 'message': <人读原因>} —— error 取
interfaces.md §4 的错误码（路由层负责 code → HTTP 状态的映射，domain 只给 code）。

错误码 → HTTP（interfaces §4）：
  watch_todo_not_found             404
  watch_todo_already_closed        409
  watch_todo_invalid_terminal      400
  watch_todo_missing_audit         400
  watch_todo_missing_next_condition 400
（另含 t5 新增的 out_of_scope / invalid_autonomy → 400；它们不经本路由的 create 暴露，
 但映射表齐备以便复用。）

⚠️ 本文件**不**注册到 main.py——路由注册统一由 t12 处理（任务边界）。
"""
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Query
from fastapi.responses import JSONResponse

from adapters.outbound.repositories.watch_todo_repository import (
    WatchTodoRepository, todo_to_dict,
)
from application.services.watch_engine.todo_service import TodoService
from domain.watch.ports import WatchTodoError

router = APIRouter(tags=['Watch - 待办闭环'])

#: 稳定错误码 → HTTP 状态（interfaces.md §4）
_STATUS_BY_CODE = {
    'watch_todo_not_found': 404,
    'watch_todo_already_closed': 409,
    'watch_todo_invalid_terminal': 400,
    'watch_todo_missing_audit': 400,
    'watch_todo_missing_next_condition': 400,
    'watch_todo_out_of_scope': 400,
    'watch_todo_invalid_autonomy': 400,
}

#: 列表分页：默认 100、上限 500（interfaces.md §1.1）
DEFAULT_LIMIT = 100
MAX_LIMIT = 500


def _err(code: str, message: str = '') -> JSONResponse:
    """错误响应：稳定错误码 + 人读原因（HTTP 状态由错误码映射）"""
    status = _STATUS_BY_CODE.get(code, 500)
    return JSONResponse({'success': False, 'error': code, 'message': message or code},
                        status_code=status)


def _bad_request(message: str) -> JSONResponse:
    """请求本身的缺参/类型错误（不属于 §4 的闭环错误码）"""
    return JSONResponse({'success': False, 'error': 'invalid_request', 'message': message},
                        status_code=400)


def _service() -> TodoService:
    """服务工厂（单测/route 测试可替换；无状态，故每次请求新建亦安全）"""
    return TodoService(WatchTodoRepository())


def _limit_of(limit) -> int:
    try:
        value = int(limit) if limit is not None else DEFAULT_LIMIT
    except (TypeError, ValueError):
        value = DEFAULT_LIMIT
    return max(1, min(value, MAX_LIMIT))


@router.get('/api/watch/todos')
def list_todos(level: Optional[str] = Query(None),
               flow_state: Optional[str] = Query(None),
               account: Optional[str] = Query(None),
               terminal: Optional[str] = Query(None),
               limit: Optional[str] = Query(None)):
    """待办列表。

    terminal 不传 = 只返回未收敛（闭环工作队列的默认视图）；terminal=* = 全部；
    其余按终态精确过滤。
    """
    try:
        todos = _service().list(level=level, account=account, limit=_limit_of(limit),
                                flow_state=flow_state, terminal=terminal)
    except WatchTodoError as e:
        return _err(e.code, e.message)
    except Exception as e:  # noqa: BLE001
        return JSONResponse({'success': False, 'error': 'internal_error',
                             'message': f'查询待办失败: {e}'}, status_code=500)
    items = [todo_to_dict(t) for t in todos]
    return {'success': True, 'data': {'items': items, 'total': len(items)}}


@router.post('/api/watch/todos/{todo_id}/claim')
def claim_todo(todo_id: int, payload: Dict[str, Any] = Body(default_factory=dict)):
    """认领待办：未终态 → 404/409 之外返回 {todo}（L1→L2）"""
    data = payload or {}
    owner_ref = str(data.get('owner_ref') or '').strip()
    if not owner_ref:
        return _bad_request('缺少必填参数: owner_ref')
    try:
        todo = _service().claim(todo_id, owner_ref)
    except WatchTodoError as e:
        return _err(e.code, e.message)
    except Exception as e:  # noqa: BLE001
        return JSONResponse({'success': False, 'error': 'internal_error',
                             'message': f'认领失败: {e}'}, status_code=500)
    return {'success': True, 'data': {'todo': todo_to_dict(todo)}}


@router.post('/api/watch/todos/{todo_id}/close')
def close_todo(todo_id: int, payload: Dict[str, Any] = Body(default_factory=dict)):
    """收敛待办：终态校验见 TodoService.close（400/404/409）"""
    data = payload or {}
    try:
        todo = _service().close(
            todo_id,
            data.get('terminal'),
            close_reason=data.get('close_reason'),
            next_condition=data.get('next_condition'),
            action_kind=data.get('action_kind'),
            decision_audit_id=data.get('decision_audit_id'),
            closed_by=data.get('closed_by'),
        )
    except WatchTodoError as e:
        return _err(e.code, e.message)
    except Exception as e:  # noqa: BLE001
        return JSONResponse({'success': False, 'error': 'internal_error',
                             'message': f'关闭失败: {e}'}, status_code=500)
    # interfaces §1.1 的响应为 { todo, receipt }：回执由 t6 的 ReceiptService 产生，
    # t5 阶段先给 todo，receipt 留待接入后填充（不伪造空回执）。
    return {'success': True, 'data': {'todo': todo_to_dict(todo), 'receipt': None}}
