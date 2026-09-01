"""调度器 API - FastAPI 版（从 Flask scheduler.py 迁移，响应契约保持一致）

复用同一 SchedulerService(ds) 单例与全部辅助函数，paginate 用 FastAPI Query 参数实现。
"""
import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Query, Body
import structlog

from adapters.inbound.fastapi_app.shared import (
    ds, api_response, error_response, handle_api_error,
    sanitize_for_json, convert_keys_to_snake,
)

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["Scheduler - 定时任务"])

from infrastructure.scheduler import SchedulerService as _SchedulerService

_scheduler = _SchedulerService()


# ============ 辅助函数（与 Flask scheduler.py 一致）============

def _pagination_payload(total: int, page: int, page_size: int) -> Dict[str, int]:
    total_pages = (total + page_size - 1) // page_size if page_size > 0 else 0
    return {'total': total, 'page': page, 'page_size': page_size, 'pageSize': page_size,
            'total_pages': total_pages, 'totalPages': total_pages}


def _extract_params_dict(params: Any) -> Dict[str, Any]:
    if not params:
        return {}
    if isinstance(params, dict):
        return params
    if isinstance(params, str):
        try:
            return json.loads(params)
        except (json.JSONDecodeError, TypeError):
            return {}
    return {}


def _is_deleted_task(task: Dict[str, Any]) -> bool:
    if task.get('deleted_at'):
        return True
    params = _extract_params_dict(task.get('params'))
    return bool(params.get('_deleted_at'))


def _list_visible_tasks(limit: int, offset: int) -> Tuple[List[Dict[str, Any]], int]:
    raw_total = _scheduler.count_tasks()
    visible_total = raw_total
    cursor_offset = 0
    visible_seen = 0
    page_items: List[Dict[str, Any]] = []
    batch_size = max(limit + offset, 100)
    while cursor_offset < raw_total and len(page_items) < limit:
        batch = _scheduler.list_tasks(limit=batch_size, offset=cursor_offset)
        if not batch:
            break
        for task in batch:
            if _is_deleted_task(task):
                visible_total -= 1
                continue
            if visible_seen >= offset and len(page_items) < limit:
                page_items.append(task)
            visible_seen += 1
        cursor_offset += len(batch)
    if cursor_offset < raw_total:
        remaining_offset = cursor_offset
        while remaining_offset < raw_total:
            batch = _scheduler.list_tasks(limit=batch_size, offset=remaining_offset)
            if not batch:
                break
            visible_total -= sum(1 for task in batch if _is_deleted_task(task))
            remaining_offset += len(batch)
    return page_items, max(visible_total, 0)


def _schedule_kind_to_cron(schedule_kind: str, schedule_expr: str, every_seconds: Optional[int],
                            schedule_at: Optional[str], delay_seconds: Optional[int]) -> str:
    if schedule_kind == 'cron' and schedule_expr:
        return schedule_expr
    if schedule_kind == 'every' and every_seconds:
        if every_seconds <= 60:
            return f'*/{every_seconds // 60 or 1} * * * *'
        elif every_seconds <= 3600:
            return f'*/{every_seconds // 60} * * * *'
        else:
            hours = every_seconds // 3600
            return f'0 */{hours} * * *'
    if schedule_kind == 'at' and schedule_at:
        try:
            dt = datetime.fromisoformat(schedule_at)
            return f'{dt.minute} {dt.hour} {dt.day} {dt.month} *'
        except (ValueError, TypeError):
            pass
    if schedule_kind == 'delay' and delay_seconds:
        run_at = datetime.now() + timedelta(seconds=delay_seconds)
        return f'{run_at.minute} {run_at.hour} {run_at.day} {run_at.month} *'
    return '0 9 * * 1-5'


def _normalize_run(run: Dict[str, Any], task_name: str = None) -> Dict[str, Any]:
    task_name_val = task_name or str(run.get('task_id', ''))
    return {
        'id': run.get('id'), 'taskId': run.get('task_id'), 'taskName': task_name_val,
        'status': run.get('status'), 'triggeredAt': str(run.get('started_at', '')),
        'startedAt': str(run.get('started_at', '')), 'finishedAt': str(run.get('completed_at', '')),
        'durationMs': run.get('duration_ms'), 'payload': run.get('result'), 'error': run.get('error'),
    }


def _task_to_summary(task: Dict[str, Any]) -> Dict[str, Any]:
    runs = _scheduler.list_runs(task_id=task.get('id'), limit=100)
    today = datetime.now().strftime('%Y-%m-%d')
    today_runs = [r for r in runs if str(r.get('started_at') or '')[:10] == today]
    today_triggered = len(today_runs)
    today_success = sum(1 for r in today_runs if r.get('status') == 'success')
    last_run = runs[0] if runs else None
    return {
        'id': str(task.get('id', '')), 'name': task.get('name', ''),
        'enabled': task.get('is_enabled', True), 'scheduleKind': 'cron',
        'scheduleExpr': task.get('cron_expression', ''),
        'payload': {'command': task.get('command', ''), 'description': task.get('description', ''),
                    **(_extract_params_dict(task.get('params')))},
        'nextRunAt': str(task.get('next_run_at', '')),
        'lastRun': _normalize_run(last_run, task.get('name')) if last_run else None,
        'todayTriggered': today_triggered, 'todaySuccess': today_success,
        'createdAt': str(task.get('created_at', '')), 'updatedAt': str(task.get('updated_at', '')),
    }


def _runs_with_task_names(runs: List[Dict]) -> List[Dict]:
    cache: Dict[Any, str] = {}
    normalized = []
    for r in runs:
        tid = r.get('task_id')
        if tid and tid not in cache:
            task = _scheduler.get_task(tid)
            cache[tid] = task.get('name') if task else str(tid)
        normalized.append(_normalize_run(r, cache.get(tid, str(tid))))
    return normalized


# ============ 任务 CRUD ============

@router.get('/api/scheduler/tasks')
@handle_api_error
def list_scheduler_tasks(page: int = Query(1), pageSize: int = Query(12)):
    page = max(1, page)
    page_size = max(1, min(pageSize, 100))
    offset = (page - 1) * page_size
    tasks, total = _list_visible_tasks(page_size, offset)
    summaries = [_task_to_summary(t) for t in tasks]
    pagination = _pagination_payload(total, page, page_size)
    return sanitize_for_json({'success': True, 'tasks': summaries, 'count': total, 'total': total,
                              'page': page, 'pageSize': page_size, 'pagination': pagination})


@router.post('/api/scheduler/tasks')
@handle_api_error
def create_scheduler_task(payload: Optional[Dict[str, Any]] = Body(None)):
    if not payload:
        return error_response({'success': False, 'error': 'Request body is required'}, 400)
    task_data = convert_keys_to_snake(payload)
    name = task_data.get('name', 'Unnamed Task')
    schedule_kind = task_data.get('schedule_kind', 'cron')

    # 确定任务类型
    task_type = task_data.get('task_type')
    if not task_type:
        # 根据 schedule_kind 推断 task_type
        task_type_mapping = {
            'cron': 'cron',
            'delay': 'delay',
            'every': 'interval',
            'at': 'once'
        }
        task_type = task_type_mapping.get(schedule_kind, 'cron')

    # 构建 cron_expression 或延迟参数
    cron_expr = _schedule_kind_to_cron(
        schedule_kind, task_data.get('schedule_expr'), task_data.get('every_seconds'),
        task_data.get('schedule_at'), task_data.get('delay_seconds'))

    pl = task_data.get('payload', {})
    command = task_data.get('command') or pl.get('command') or 'data_update'
    description = task_data.get('description') or pl.get('description', '')
    params = pl if isinstance(pl, dict) else {}

    # 保存额外参数到 params
    if schedule_kind != 'cron':
        params['_schedule_kind'] = schedule_kind
    if task_data.get('delay_seconds'):
        params['delay_seconds'] = task_data['delay_seconds']
    if task_data.get('interval_seconds'):
        params['interval_seconds'] = task_data['interval_seconds']
    if task_data.get('run_at'):
        params['run_at'] = task_data['run_at']
    if task_data.get('compensation_enabled'):
        params['_compensation_enabled'] = True
        params['_compensation_check_after'] = task_data.get('compensation_check_after')
        params['_compensation_max_attempts'] = task_data.get('compensation_max_attempts', 1)
    if task_data.get('delete_after_run') or task_type in ['delay', 'once']:
        # 延迟任务和一次性任务默认执行后删除
        params['_delete_after_run'] = True

    try:
        task_id = _scheduler.add_task(
            name=name,
            cron_expression=cron_expr,
            command=command,
            params=params,
            description=description,
            task_type=task_type
        )
        task = _scheduler.get_task(task_id)
    except ValueError as e:
        return error_response({'success': False, 'error': str(e)}, 409)
    return error_response({'success': True, 'data': task}, 201)


@router.put('/api/scheduler/tasks/{task_id}')
@handle_api_error
def update_scheduler_task(task_id: str, payload: Optional[Dict[str, Any]] = Body(None)):
    if not payload:
        return error_response({'success': False, 'error': 'Request body is required'}, 400)
    task_data = convert_keys_to_snake(payload)
    pl = task_data.get('payload', {})
    tid = int(task_id)
    updates: Dict[str, Any] = {}
    if 'name' in task_data:
        updates['name'] = task_data['name']
    if 'cron_expression' in task_data:
        updates['cron_expression'] = task_data['cron_expression']
    if 'command' in task_data:
        updates['command'] = task_data['command']
    elif isinstance(pl, dict) and 'command' in pl:
        updates['command'] = pl['command']
    if 'task_type' in task_data:
        updates['task_type'] = task_data['task_type']
    if isinstance(pl, dict) and pl:
        existing = _scheduler.get_task(tid)
        existing_params = _extract_params_dict(existing.get('params')) if existing else {}
        updates['params'] = {**existing_params, **pl}
    if 'params' in task_data:
        updates['params'] = task_data['params']
    if 'is_enabled' in task_data:
        updates['is_enabled'] = task_data['is_enabled']
    if 'schedule_kind' in task_data or 'schedule_expr' in task_data:
        task = _scheduler.get_task(tid)
        if task:
            cron_expr = _schedule_kind_to_cron(
                task_data.get('schedule_kind', 'cron'), task_data.get('schedule_expr'),
                task_data.get('every_seconds'), task_data.get('schedule_at'), task_data.get('delay_seconds'))
            updates['cron_expression'] = cron_expr
    if updates:
        _scheduler.update_task(tid, **updates)
    updated = _scheduler.get_task(tid)
    return {'success': True, 'data': updated}


@router.post('/api/scheduler/tasks/{task_id}/enable')
@handle_api_error
def enable_scheduler_task(task_id: str):
    try:
        _scheduler.enable_task(int(task_id))
        task = _scheduler.get_task(int(task_id))
        return {'success': True, 'data': task}
    except ValueError as e:
        return error_response({'success': False, 'error': str(e)}, 404)


@router.post('/api/scheduler/tasks/{task_id}/disable')
@handle_api_error
def disable_scheduler_task(task_id: str):
    try:
        _scheduler.disable_task(int(task_id))
        task = _scheduler.get_task(int(task_id))
        return {'success': True, 'data': task}
    except ValueError as e:
        return error_response({'success': False, 'error': str(e)}, 404)


@router.delete('/api/scheduler/tasks/{task_id}')
@handle_api_error
def delete_scheduler_task(task_id: str):
    try:
        tid = int(task_id)
        task = _scheduler.get_task(tid)
        if task is None:
            return error_response({'success': False, 'error': 'Task not found'}, 404)
        params = task.get('params') or {}
        if isinstance(params, str):
            try:
                params = json.loads(params)
            except json.JSONDecodeError:
                params = {}
        params['_deleted_at'] = datetime.now().isoformat()
        _scheduler.update_task(tid, params=params, is_enabled=False)
        return {'success': True}
    except ValueError as e:
        return error_response({'success': False, 'error': str(e)}, 404)


@router.get('/api/scheduler/tasks/{task_id}/runs')
@handle_api_error
def get_scheduler_task_runs(task_id: str, page: int = Query(1), pageSize: int = Query(20)):
    page = max(1, page)
    page_size = max(1, min(pageSize, 100))
    offset = (page - 1) * page_size
    tid = int(task_id)
    task = _scheduler.get_task(tid)
    task_name = task.get('name') if task else str(tid)
    runs = _scheduler.list_runs(task_id=tid, limit=page_size, offset=offset)
    total = _scheduler.count_runs(task_id=tid)
    normalized = [_normalize_run(r, task_name) for r in runs]
    pagination = _pagination_payload(total, page, page_size)
    return sanitize_for_json({'success': True, 'runs': normalized, 'count': total, 'total': total,
                              'page': page, 'pageSize': page_size, 'pagination': pagination})


@router.post('/api/scheduler/tasks/{task_id}/trigger')
@handle_api_error
def trigger_scheduler_task(task_id: str):
    """手动触发任务执行（异步派发，立即返回）。

    2026-09-01 修复：原实现在同步路由里直接执行重任务（如 data_quality_check
    含全市场数据检查+自动回填），曾卡死 HTTP 工作线程 46 分钟致全服务无响应。
    改为后台线程派发：立即返回 accepted，执行结果看任务执行日志/记录。
    """
    import threading

    def _run_async():
        try:
            from adapters.inbound.fastapi_app.main import app
            scheduler_service = getattr(app.state, 'scheduler_service', None)
            if scheduler_service is not None:
                scheduler_service.trigger_task_now(int(task_id))
                logger.info(f"Task {task_id} triggered via APScheduler")
                return
        except Exception as e:
            logger.warning(f"APScheduler trigger unavailable, legacy path: {e}")
        try:
            _scheduler.run_task(int(task_id))
            logger.info(f"Task {task_id} completed via legacy scheduler")
        except Exception as e:
            logger.exception(f"Task {task_id} execution failed: {e}")

    threading.Thread(target=_run_async, name=f"trigger-{task_id}", daemon=True).start()
    return {'success': True, 'message': f'Task {task_id} dispatched asynchronously',
            'note': '异步派发：执行结果见日志/任务执行记录'}


@router.post('/api/scheduler/compensate')
@handle_api_error
def compensate_scheduler_task(task_id: str):
    """补偿执行（异步派发，同 trigger 修复：避免重任务阻塞工作线程）"""
    import threading

    def _run_async():
        try:
            _scheduler.run_task(int(task_id))
            logger.info(f"Task {task_id} compensation completed")
        except Exception as e:
            logger.exception(f"Task {task_id} compensation failed: {e}")

    threading.Thread(target=_run_async, name=f"compensate-{task_id}", daemon=True).start()
    return {'success': True, 'message': f'Task {task_id} compensation dispatched',
            'triggerType': 'compensation'}


@router.post('/api/scheduler/reload')
@handle_api_error
def reload_scheduler_tasks():
    """重新加载所有任务（用于动态更新 APScheduler）

    2026-09-01: 当用户修改 scheduler_tasks 表后，调用此接口同步到 APScheduler
    """
    try:
        from adapters.inbound.fastapi_app.main import app
        scheduler_service = getattr(app.state, 'scheduler_service', None)

        if scheduler_service is not None:
            scheduler_service.reload_tasks()
            return {'success': True, 'message': 'Tasks reloaded in APScheduler'}
        else:
            return {'success': False, 'error': 'APScheduler not available (Agent OS mode or not started)'}
    except Exception as e:
        logger.exception(f"Failed to reload tasks: {e}")
        return error_response({'success': False, 'error': str(e)}, 500)


# ============ 运行记录 ============

@router.get('/api/scheduler/runs')
@handle_api_error
def list_scheduler_runs(date: Optional[str] = Query(None),
                        page: int = Query(1), pageSize: int = Query(20)):
    page = max(1, page)
    page_size = max(1, min(pageSize, 100))
    offset = (page - 1) * page_size
    runs = _scheduler.list_runs(limit=page_size, offset=offset, date_filter=date)
    total = _scheduler.count_runs(date_filter=date)
    normalized = _runs_with_task_names(runs)
    pagination = _pagination_payload(total, page, page_size)
    return sanitize_for_json({'success': True, 'runs': normalized, 'count': total, 'total': total,
                              'page': page, 'pageSize': page_size, 'pagination': pagination})


@router.get('/api/scheduler/runs/failed')
@handle_api_error
def list_scheduler_failed_runs(date: Optional[str] = Query(None),
                               page: int = Query(1), pageSize: int = Query(20)):
    page = max(1, page)
    page_size = max(1, min(pageSize, 100))
    offset = (page - 1) * page_size
    statuses = ['failed', 'missed', 'skipped']
    failed = _scheduler.list_runs(limit=page_size, offset=offset, statuses=statuses, date_filter=date)
    total = _scheduler.count_runs(statuses=statuses, date_filter=date)
    normalized = _runs_with_task_names(failed)
    pagination = _pagination_payload(total, page, page_size)
    return sanitize_for_json({'success': True, 'count': total, 'total': total, 'page': page,
                              'pageSize': page_size, 'pagination': pagination, 'runs': normalized})
