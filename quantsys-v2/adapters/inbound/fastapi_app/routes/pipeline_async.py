"""流水线 API - FastAPI 版（从 Flask pipeline.py 迁移，响应契约保持一致）

复用 Flask shared 的 pipeline 存储助手（_load_pipeline_runs/_save_pipeline_runs/
_get_pipeline_run）与 acquire_task 等。字面量路由必须先于 /{run_id} 注册。
后台执行函数 _execute_pipeline_stages 直接从 Flask pipeline.py 复用。
"""
import threading
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query, Body
import structlog

from adapters.inbound.fastapi_app.shared import (
    ds, api_response, error_response, handle_api_error, convert_keys_to_snake,
    _load_pipeline_runs, _save_pipeline_runs, _get_pipeline_run,
    acquire_task, get_running_tasks_snapshot,
)
# 复用 Flask pipeline.py 的后台执行函数（同一实现，保证行为一致）
from adapters.shared.pipeline_exec import _execute_pipeline_stages

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["Pipeline - 流水线"])


@router.get('/api/tasks/running')
def get_running_tasks():
    snapshot = get_running_tasks_snapshot()
    return api_response({'running_tasks': snapshot, 'count': len(snapshot)})


@router.get('/api/pipeline/statistics')
@handle_api_error
def get_pipeline_statistics():
    runs = _load_pipeline_runs()
    today = datetime.now().strftime('%Y-%m-%d')
    running = sum(1 for r in runs if r.get('status') == 'running')
    completed_today = sum(1 for r in runs if r.get('status') == 'completed' and (r.get('endTime', '')[:10] == today))
    failed = sum(1 for r in runs if r.get('status') == 'failed')
    durations = [r.get('duration', 0) for r in runs if r.get('duration')]
    return api_response({
        'running_tasks': running, 'completed_today': completed_today, 'failed_tasks': failed,
        'avg_duration': round(sum(durations) / len(durations), 1) if durations else 0,
    })


@router.get('/api/pipeline/tasks/list')
@handle_api_error
def get_pipeline_tasks():
    return api_response({
        'items': [
            {'type': 'data_update', 'name': '数据更新', 'description': 'Update market data'},
            {'type': 'factors', 'name': '因子计算', 'description': 'Compute factors'},
            {'type': 'signals', 'name': '信号扫描', 'description': 'Scan for signals'},
            {'type': 'risk', 'name': '风控检查', 'description': 'Risk assessment'},
            {'type': 'calibrate', 'name': '置信度校准', 'description': 'Confidence calibration'},
            {'type': 'ml_train', 'name': 'ML训练', 'description': 'ML model training'},
        ],
    })


def _get_pipeline_runs_impl(page: int, page_size: int, run_id: Optional[str], status: Optional[str]):
    page = max(1, page)
    page_size = min(page_size, 100)
    runs = _load_pipeline_runs()
    if run_id:
        runs = [r for r in runs if r.get('runId') == run_id or r.get('run_id') == run_id]
    if status:
        runs = [r for r in runs if r.get('status') == status]
    runs.sort(key=lambda x: x.get('startTime', ''), reverse=True)
    total = len(runs)
    start = (page - 1) * page_size
    return api_response({'runs': runs[start:start + page_size], 'total': total, 'page': page, 'page_size': page_size})


@router.get('/api/pipeline/runs/list')
@router.get('/api/pipeline/runs')
@handle_api_error
def get_pipeline_runs(page: int = Query(1), page_size: int = Query(20),
                      run_id: Optional[str] = Query(None), status: Optional[str] = Query(None)):
    return _get_pipeline_runs_impl(page, page_size, run_id, status)


@router.get('/api/pipeline/history')
@handle_api_error
def pipeline_history_alias(page: int = Query(1), page_size: int = Query(20),
                           run_id: Optional[str] = Query(None), status: Optional[str] = Query(None)):
    return _get_pipeline_runs_impl(page, page_size, run_id, status)


def _create_pipeline_run_impl(data: Dict[str, Any]):
    if not data:
        return error_response({'success': False, 'error': 'Request body is required'}, 400)
    pipeline_data = convert_keys_to_snake(data)
    symbols = pipeline_data.get('symbols', [])
    stages = pipeline_data.get('stages', ['data_update', 'factors', 'signals', 'risk'])
    if not symbols:
        symbols = [s['symbol'] for s in ds.stock.get_all(limit=100)]
    if not symbols:
        return error_response({'success': False, 'error': 'No symbols provided and no stocks in database'}, 400)
    run_id = f"#P-{str(uuid.uuid4())[:8].upper()}"
    if not acquire_task('pipeline', run_id):
        existing = get_running_tasks_snapshot().get('pipeline', '?')
        return error_response({'success': False, 'error': f'流水线已在运行中 (run_id={existing})'}, 409)
    start_time = datetime.now()
    run = {
        'runId': run_id, 'startTime': start_time.isoformat(), 'status': 'running',
        'stockCount': len(symbols), 'model': pipeline_data.get('model', 'xgboost'),
        'config': {
            'stockRange': ','.join(symbols[:5]) + ('...' if len(symbols) > 5 else ''),
            'days': pipeline_data.get('days', 365), 'model': pipeline_data.get('model', 'xgboost'),
            'threshold': pipeline_data.get('threshold', 0.65),
        },
        'stages': [{'name': s, 'status': 'pending', 'progress': 0, 'detail': ''} for s in stages],
        'logs': [
            f"[{start_time.isoformat()}] 开始运行流水线 {run_id}",
            f"[{start_time.isoformat()}] 配置: 股票数={len(symbols)}, 模型={pipeline_data.get('model', 'xgboost')}",
        ],
    }
    runs = _load_pipeline_runs()
    runs.insert(0, run)
    _save_pipeline_runs(runs)
    threading.Thread(target=_execute_pipeline_stages, args=(run_id, symbols, stages, 'pipeline'), daemon=True).start()
    return error_response({'success': True, 'data': run}, 202)


@router.post('/api/pipeline/run')
@handle_api_error
def create_pipeline_run(payload: Optional[Dict[str, Any]] = Body(None)):
    return _create_pipeline_run_impl(payload or {})


@router.post('/api/pipeline/trigger')
@handle_api_error
def trigger_pipeline(payload: Optional[Dict[str, Any]] = Body(None)):
    return _create_pipeline_run_impl(payload or {})


@router.get('/api/pipeline/{run_id}')
@handle_api_error
def get_pipeline_run_detail(run_id: str):
    run = _get_pipeline_run(run_id)
    if not run:
        return error_response({'success': False, 'error': 'Pipeline run not found'}, 404)
    return api_response(run)


@router.get('/api/pipeline/{run_id}/logs')
@handle_api_error
def get_pipeline_run_logs(run_id: str):
    run = _get_pipeline_run(run_id)
    if not run:
        return error_response({'success': False, 'error': 'Pipeline run not found'}, 404)
    return api_response({'logs': run.get('logs', [])})
