"""
scheduler routes.
"""
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
import re
import uuid
from typing import Any, Dict, List, Optional, Tuple

from flask import Blueprint, jsonify, request

from adapters.inbound.api.decorators import paginate
from adapters.inbound.api.response_builder import sanitize_for_json as response_sanitize_for_json

from adapters.inbound.api.shared import (
    ds,
    api_response,
    handle_api_error,
    sanitize_for_json,
    convert_keys_to_snake,
    convert_keys_to_camel,
    _safe_float,
    _V2_ROOT,
    _PROJECT_ROOT_PATH,
    _LEGACY_QUANT_ROOT,
    _load_pipeline_runs,
    _save_pipeline_runs,
    _get_pipeline_run,
    _update_pipeline_run,
    acquire_task,
    release_task,
    get_running_tasks_snapshot,
    strategy_service,
    stock_pool_service,
    factor_adapter,
    scoring_service,
    _read_watchlist,
    _write_watchlist,
    _read_groups,
    _write_groups,
    _parse_sina_a_quote,
    _parse_sina_hk_quote,
    to_camel_case,
    to_snake_case,
    get_query_params_snake_case,
    enrich_stock_data,
    signal_to_opportunity,
)

scheduler_bp = Blueprint('scheduler', __name__)

from infrastructure.scheduler import SchedulerService as _SchedulerService

_scheduler = _SchedulerService(ds=ds)


def _pagination_payload(total: int, page: int, page_size: int) -> Dict[str, int]:
    """Build the common pagination metadata used by API responses."""
    total_pages = (total + page_size - 1) // page_size if page_size > 0 else 0
    return {
        'total': total,
        'page': page,
        'page_size': page_size,
        'pageSize': page_size,
        'total_pages': total_pages,
        'totalPages': total_pages,
    }


def _is_deleted_task(task: Dict[str, Any]) -> bool:
    """Return True for legacy soft-deleted scheduler tasks."""
    if task.get('deleted_at'):
        return True
    params = _extract_params_dict(task.get('params'))
    return bool(params.get('_deleted_at'))


def _list_visible_tasks(limit: int, offset: int) -> Tuple[List[Dict[str, Any]], int]:
    """List non-deleted scheduler tasks with DB-backed pagination.

    Legacy deletes are stored inside params._deleted_at, so we over-fetch only
    when those rows appear to keep the public list and total consistent.
    """
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
    """Map Express schedule kinds to cron expressions."""
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


def _extract_params_dict(params: Any) -> Dict[str, Any]:
    """Normalize task params to a plain dict (handles JSON strings and empty values)."""
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


def _normalize_run(run: Dict[str, Any], task_name: str = None) -> Dict[str, Any]:
    """Convert a DB scheduler run row to the format the frontend expects."""
    task_name_val = task_name or str(run.get('task_id', ''))
    return {
        'id': run.get('id'),
        'taskId': run.get('task_id'),
        'taskName': task_name_val,
        'status': run.get('status'),
        'triggeredAt': str(run.get('started_at', '')),
        'startedAt': str(run.get('started_at', '')),
        'finishedAt': str(run.get('completed_at', '')),
        'durationMs': run.get('duration_ms'),
        'payload': run.get('result'),
        'error': run.get('error'),
    }


def _task_to_summary(task: Dict[str, Any]) -> Dict[str, Any]:
    """Convert a scheduler task dict to a summary with computed fields."""
    runs = _scheduler.list_runs(task_id=task.get('id'), limit=100)
    today = datetime.now().strftime('%Y-%m-%d')
    today_runs = [r for r in runs if str(r.get('started_at') or '')[:10] == today]
    today_triggered = len(today_runs)
    today_success = sum(1 for r in today_runs if r.get('status') == 'success')

    last_run = runs[0] if runs else None

    return {
        'id': str(task.get('id', '')),
        'name': task.get('name', ''),
        'enabled': task.get('is_enabled', True),
        'scheduleKind': 'cron',
        'scheduleExpr': task.get('cron_expression', ''),
        'payload': {
            'command': task.get('command', ''),
            'description': task.get('description', ''),
            **(_extract_params_dict(task.get('params'))),
        },
        'nextRunAt': str(task.get('next_run_at', '')),
        'lastRun': _normalize_run(last_run, task.get('name')) if last_run else None,
        'todayTriggered': today_triggered,
        'todaySuccess': today_success,
        'createdAt': str(task.get('created_at', '')),
        'updatedAt': str(task.get('updated_at', '')),
    }


@scheduler_bp.route('/api/scheduler/tasks', methods=['GET'])
@handle_api_error
@paginate(default_page_size=12, max_page_size=100)
def list_scheduler_tasks(*, page: int, page_size: int, offset: int):
    """List all scheduler tasks with summaries."""
    tasks, total = _list_visible_tasks(page_size, offset)
    summaries = [_task_to_summary(t) for t in tasks]
    pagination = _pagination_payload(total, page, page_size)
    return jsonify(response_sanitize_for_json({
        'success': True,
        'tasks': summaries,
        'count': total,
        'total': total,
        'page': page,
        'pageSize': page_size,
        'pagination': pagination,
    }))


@scheduler_bp.route('/api/scheduler/tasks', methods=['POST'])
@handle_api_error
def create_scheduler_task():
    """Create a new scheduler task."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'success': False, 'error': 'Request body is required'}), 400

    task_data = convert_keys_to_snake(data)

    name = task_data.get('name', 'Unnamed Task')
    schedule_kind = task_data.get('schedule_kind', 'cron')
    schedule_expr = task_data.get('schedule_expr')
    every_seconds = task_data.get('every_seconds')
    schedule_at = task_data.get('schedule_at')
    delay_seconds = task_data.get('delay_seconds')
    cron_expr = _schedule_kind_to_cron(schedule_kind, schedule_expr, every_seconds, schedule_at, delay_seconds)

    payload = task_data.get('payload', {})
    command = task_data.get('command') or payload.get('command') or 'data_update'
    description = task_data.get('description') or payload.get('description', '')
    params = payload if isinstance(payload, dict) else {}

    if schedule_kind != 'cron':
        params['_schedule_kind'] = schedule_kind
    if task_data.get('compensation_enabled'):
        params['_compensation_enabled'] = True
        params['_compensation_check_after'] = task_data.get('compensation_check_after')
        params['_compensation_max_attempts'] = task_data.get('compensation_max_attempts', 1)
    if task_data.get('delete_after_run'):
        params['_delete_after_run'] = True

    try:
        task_id = _scheduler.add_task(
            name=name,
            cron_expression=cron_expr,
            command=command,
            params=params,
            description=description,
        )
        task = _scheduler.get_task(task_id)
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 409

    return jsonify({'success': True, 'data': task}), 201


@scheduler_bp.route('/api/scheduler/tasks/<task_id>', methods=['PUT'])
@handle_api_error
def update_scheduler_task(task_id):
    """Update a scheduler task."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'success': False, 'error': 'Request body is required'}), 400

    task_data = convert_keys_to_snake(data)
    payload = task_data.get('payload', {})
    tid = int(task_id)

    updates = {}
    if 'name' in task_data:
        updates['name'] = task_data['name']
    if 'cron_expression' in task_data:
        updates['cron_expression'] = task_data['cron_expression']
    if 'command' in task_data:
        updates['command'] = task_data['command']
    elif isinstance(payload, dict) and 'command' in payload:
        updates['command'] = payload['command']
    if isinstance(payload, dict) and payload:
        existing = _scheduler.get_task(tid)
        existing_params = _extract_params_dict(existing.get('params')) if existing else {}
        merged = {**existing_params, **payload}
        updates['params'] = merged
    if 'params' in task_data:
        updates['params'] = task_data['params']
    if 'is_enabled' in task_data:
        updates['is_enabled'] = task_data['is_enabled']

    if 'schedule_kind' in task_data or 'schedule_expr' in task_data:
        task = _scheduler.get_task(tid)
        if task:
            schedule_kind = task_data.get('schedule_kind', 'cron')
            schedule_expr = task_data.get('schedule_expr')
            cron_expr = _schedule_kind_to_cron(
                schedule_kind, schedule_expr,
                task_data.get('every_seconds'),
                task_data.get('schedule_at'),
                task_data.get('delay_seconds'),
            )
            updates['cron_expression'] = cron_expr

    if updates:
        _scheduler.update_task(tid, **updates)

    updated = _scheduler.get_task(tid)
    return jsonify({'success': True, 'data': updated})


@scheduler_bp.route('/api/scheduler/tasks/<task_id>/enable', methods=['POST'])
@handle_api_error
def enable_scheduler_task(task_id):
    """Enable a scheduler task."""
    try:
        _scheduler.enable_task(int(task_id))
        task = _scheduler.get_task(int(task_id))
        return jsonify({'success': True, 'data': task})
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 404


@scheduler_bp.route('/api/scheduler/tasks/<task_id>/disable', methods=['POST'])
@handle_api_error
def disable_scheduler_task(task_id):
    """Disable a scheduler task."""
    try:
        _scheduler.disable_task(int(task_id))
        task = _scheduler.get_task(int(task_id))
        return jsonify({'success': True, 'data': task})
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 404


@scheduler_bp.route('/api/scheduler/tasks/<task_id>', methods=['DELETE'])
@handle_api_error
def delete_scheduler_task(task_id):
    """Soft-delete a scheduler task."""
    try:
        tid = int(task_id)
        task = _scheduler.get_task(tid)
        if task is None:
            return jsonify({'success': False, 'error': 'Task not found'}), 404

        params = task.get('params') or {}
        if isinstance(params, str):
            try:
                params = json.loads(params)
            except json.JSONDecodeError:
                params = {}
        params['_deleted_at'] = datetime.now().isoformat()

        _scheduler.update_task(tid, params=params, is_enabled=False)
        return jsonify({'success': True})
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 404


@scheduler_bp.route('/api/scheduler/tasks/<task_id>/runs', methods=['GET'])
@handle_api_error
@paginate(default_page_size=20, max_page_size=100)
def get_scheduler_task_runs(task_id, *, page: int, page_size: int, offset: int):
    """Get run history for a specific task."""
    tid = int(task_id)
    task = _scheduler.get_task(tid)
    task_name = task.get('name') if task else str(tid)
    runs = _scheduler.list_runs(task_id=tid, limit=page_size, offset=offset)
    total = _scheduler.count_runs(task_id=tid)
    normalized = [_normalize_run(r, task_name) for r in runs]
    pagination = _pagination_payload(total, page, page_size)
    return jsonify(response_sanitize_for_json({
        'success': True,
        'runs': normalized,
        'count': total,
        'total': total,
        'page': page,
        'pageSize': page_size,
        'pagination': pagination,
    }))


@scheduler_bp.route('/api/scheduler/runs', methods=['GET'])
@handle_api_error
@paginate(default_page_size=20, max_page_size=100)
def list_scheduler_runs(*, page: int, page_size: int, offset: int):
    """List all scheduler runs."""
    date = request.args.get('date')
    runs = _scheduler.list_runs(limit=page_size, offset=offset, date_filter=date)
    total = _scheduler.count_runs(date_filter=date)

    task_name_cache = {}
    normalized = []
    for r in runs:
        tid = r.get('task_id')
        if tid and tid not in task_name_cache:
            task = _scheduler.get_task(tid)
            task_name_cache[tid] = task.get('name') if task else str(tid)
        normalized.append(_normalize_run(r, task_name_cache.get(tid, str(tid))))
    pagination = _pagination_payload(total, page, page_size)
    return jsonify(response_sanitize_for_json({
        'success': True,
        'runs': normalized,
        'count': total,
        'total': total,
        'page': page,
        'pageSize': page_size,
        'pagination': pagination,
    }))


@scheduler_bp.route('/api/scheduler/runs/failed', methods=['GET'])
@handle_api_error
@paginate(default_page_size=20, max_page_size=100)
def list_scheduler_failed_runs(*, page: int, page_size: int, offset: int):
    """List failed scheduler runs."""
    date = request.args.get('date')
    statuses = ['failed', 'missed', 'skipped']
    failed = _scheduler.list_runs(
        limit=page_size,
        offset=offset,
        statuses=statuses,
        date_filter=date,
    )
    total = _scheduler.count_runs(statuses=statuses, date_filter=date)

    task_name_cache = {}
    normalized = []
    for r in failed:
        tid = r.get('task_id')
        if tid and tid not in task_name_cache:
            task = _scheduler.get_task(tid)
            task_name_cache[tid] = task.get('name') if task else str(tid)
        normalized.append(_normalize_run(r, task_name_cache.get(tid, str(tid))))
    pagination = _pagination_payload(total, page, page_size)
    return jsonify(response_sanitize_for_json({
        'success': True,
        'count': total,
        'total': total,
        'page': page,
        'pageSize': page_size,
        'pagination': pagination,
        'runs': normalized,
    }))


@scheduler_bp.route('/api/scheduler/tasks/<task_id>/trigger', methods=['POST'])
@handle_api_error
def trigger_scheduler_task(task_id):
    """Manually trigger a scheduler task."""
    try:
        result = _scheduler.run_task(int(task_id))
        return jsonify({'success': True, 'data': result})
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 404


@scheduler_bp.route('/api/scheduler/tasks/<task_id>/compensate', methods=['POST'])
@handle_api_error
def compensate_scheduler_task(task_id):
    """Trigger compensation for a scheduler task."""
    try:
        result = _scheduler.run_task(int(task_id))
        result['triggerType'] = 'compensation'
        return jsonify({'success': True, 'data': result})
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 404
