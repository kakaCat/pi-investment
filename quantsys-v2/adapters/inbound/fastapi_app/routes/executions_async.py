"""执行记录 API - FastAPI 版（从 Flask executions.py 迁移，响应契约保持一致）

字面量路由（/stats、/daily、/pending、/summary）必须先于
/{execution_id} 注册。Flask 用 jsonify(sanitize_for_json(...)) 直接返回，故同样处理。
"""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query, Body
import structlog

from adapters.inbound.fastapi_app.shared import (
    execution_repo, error_response, sanitize_for_json,
)

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["Executions - 执行记录"])


def _map_execution(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        'executionId': row.get('id'),
        'signalId': row.get('signal_id'),
        'symbol': row.get('symbol'),
        'name': row.get('name'),
        'action': row.get('action'),
        'price': row.get('execution_price'),
        'quantity': row.get('quantity'),
        'amount': (row.get('execution_price') or 0) * (row.get('quantity') or 0),
        'commission': row.get('commission'),
        'status': row.get('status'),
        'openDate': row.get('execution_date'),
        'closeDate': row.get('close_date'),
        'closePrice': row.get('close_price'),
        'profit': row.get('pnl'),
        'createdAt': row.get('created_at'),
        'updatedAt': row.get('updated_at'),
    }


# ---- 字面量路由（先于 /{execution_id}）----

@router.get('/api/executions/stats')
def execution_stats(start_date: Optional[str] = Query(None), end_date: Optional[str] = Query(None)):
    stats = execution_repo.get_execution_stats(start_date, end_date)
    return sanitize_for_json(stats)


@router.get('/api/executions/daily')
def daily_execution_stats(start_date: Optional[str] = Query(None), end_date: Optional[str] = Query(None)):
    if not start_date or not end_date:
        return error_response({'error': 'start_date and end_date are required'}, 400)
    stats = execution_repo.get_daily_execution_stats(start_date, end_date)
    return sanitize_for_json({'daily_stats': stats, 'count': len(stats)})


@router.get('/api/executions/pending')
def pending_executions(limit: int = Query(100)):
    results = execution_repo.get_pending_executions()
    return sanitize_for_json({'executions': [_map_execution(e) for e in results[:limit]], 'count': len(results)})


@router.get('/api/executions/summary')
def execution_summary(start_date: Optional[str] = Query(None), end_date: Optional[str] = Query(None)):
    stats = execution_repo.get_execution_stats(start_date, end_date)
    return sanitize_for_json(stats)


@router.get('/api/executions/signal/{signal_id}')
def get_executions_by_signal(signal_id: int):
    results = execution_repo.get_executions_by_signal(signal_id)
    return sanitize_for_json({'executions': [_map_execution(e) for e in results], 'count': len(results)})


# ---- 列表 / 创建 ----

@router.get('/api/executions')
def list_executions(status: Optional[str] = Query(None), limit: int = Query(200), offset: int = Query(0)):
    # 2026-09-14（w-c8cae280）修**真实缺陷**：本路由声明了 status 参数却从未使用 ——
    # 原实现直接 get_all_executions(limit)，status 被静默忽略（API 承诺的过滤无声失效）。
    try:
        if status:
            results = execution_repo.get_executions_by_status(status, limit=limit)
        else:
            # offset 此前被静默忽略（路由声明了却没用 = 分页是假的）；现传下去。
            results = execution_repo.get_all_executions(limit=limit, offset=offset)
    except ValueError as e:
        return error_response({'error': str(e)}, 400)
    mapped = [_map_execution(r) for r in results]
    return sanitize_for_json({'executions': mapped, 'count': len(mapped)})


@router.post('/api/executions')
def create_execution(payload: Optional[Dict[str, Any]] = Body(None)):
    try:
        # 2026-09-14（w-c8cae280）修**线上 500**：本路由原样把 payload 这个 dict 传给
        # execution_repo.create_execution(...)，而该方法的签名是
        #   create_execution(signal_id, execution_date, execution_price, quantity, commission=0.0, status='pending')
        # → TypeError: missing 3 required positional arguments → 被 except Exception 包成 500。
        # 实测复现：create_execution({'signal_id': 1, 'execution_date': '2024-01-01'}) → TypeError。
        # 现按真实签名解包并显式校验，缺字段返回 400（而不是伪装成服务器错误）。
        data = payload or {}
        signal_id = data.get('signal_id')
        execution_date = data.get('execution_date') or data.get('date')
        execution_price = data.get('execution_price', data.get('price'))
        quantity = data.get('quantity', data.get('shares'))
        missing = [k for k, v in (('signal_id', signal_id), ('execution_date', execution_date),
                                  ('execution_price', execution_price), ('quantity', quantity)) if v is None]
        if missing:
            return error_response({'error': '缺少必需参数: ' + ', '.join(missing)}, 400)
        try:
            exec_id = execution_repo.create_execution(
                int(signal_id), str(execution_date), float(execution_price), int(quantity),
                float(data.get('commission') or 0.0), str(data.get('status') or 'pending'))
        except (TypeError, ValueError) as e:
            return error_response({'error': str(e)}, 400)
        return error_response({'id': exec_id, 'message': 'Execution created'}, 201)
    except ValueError as e:
        return error_response({'error': str(e)}, 400)
    except Exception as e:
        return error_response({'error': str(e)}, 500)


# ---- /{execution_id} 参数路由（最后注册）----

@router.get('/api/executions/{execution_id}')
def get_execution(execution_id: int):
    ex = execution_repo.get_execution(execution_id)
    if not ex:
        return error_response({'error': 'Execution not found'}, 404)
    return sanitize_for_json(_map_execution(ex))


@router.put('/api/executions/{execution_id}/close')
def close_execution(execution_id: int, payload: Optional[Dict[str, Any]] = Body(None)):
    data = payload or {}
    close_date = data.get('close_date')
    close_price = data.get('close_price')
    if not close_date or close_price is None:
        return error_response({'error': 'close_date and close_price are required'}, 400)
    try:
        # 2026-09-14（w-c8cae280）修**线上 500**：仓库签名是
        #   close_execution(execution_id, close_date, close_price, pnl)
        # 而本路由只传了前 3 个 → TypeError: missing 1 required positional argument: 'pnl' → 500。
        # pnl 优先取请求体；未提供则由**已存执行记录**推算（(平仓价-执行价)×数量），
        # 不在路由里凭空写 0 —— 那会让盈亏统计静默失真。
        _pnl = data.get('pnl')
        if _pnl is None:
            _ex = execution_repo.get_execution(execution_id)
            if _ex is None:
                return error_response({'error': 'Execution not found'}, 404)
            _entry = float(getattr(_ex, 'execution_price', 0) or 0)
            _qty = float(getattr(_ex, 'execution_amount', 0) or 0)
            _pnl = (float(close_price) - _entry) * _qty
        ok = execution_repo.close_execution(execution_id, close_date, float(close_price), float(_pnl))
        if not ok:
            return error_response({'error': 'Execution not found'}, 404)
        updated = execution_repo.get_execution(execution_id)
        return sanitize_for_json({'message': 'Execution closed', 'execution': updated})
    except ValueError as e:
        return error_response({'error': str(e)}, 400)
    except Exception as e:
        return error_response({'error': str(e)}, 500)


@router.put('/api/executions/{execution_id}/cancel')
def cancel_execution(execution_id: int):
    try:
        ok = execution_repo.cancel_execution(execution_id)
        if not ok:
            return error_response({'error': 'Execution not found'}, 404)
        return {'message': 'Execution cancelled'}
    except Exception as e:
        return error_response({'error': str(e)}, 500)


@router.put('/api/executions/{execution_id}/status')
def update_execution_status(execution_id: int, payload: Optional[Dict[str, Any]] = Body(None)):
    data = payload or {}
    status = data.get('status')
    if not status:
        return error_response({'error': 'status is required'}, 400)
    try:
        ok = execution_repo.update_execution_status(execution_id, status)
        if not ok:
            return error_response({'error': 'Execution not found'}, 404)
        return {'message': f'Status updated to {status}'}
    except ValueError as e:
        return error_response({'error': str(e)}, 400)
    except Exception as e:
        return error_response({'error': str(e)}, 500)
