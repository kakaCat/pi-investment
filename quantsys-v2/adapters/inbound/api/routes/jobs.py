"""
jobs routes.
"""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path
import re
import uuid

from flask import Blueprint, jsonify, request
from typing import Dict, List, Optional, Any, Tuple, Union

import threading

logger = logging.getLogger(__name__)

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

# 从 health.py 导入共享的 Job 基础设施
from adapters.inbound.api.routes.health import (
    _jobs,
    _jobs_lock,
    _audit_job,
    _execute_job_by_type,
    _JOB_TYPES,
)

jobs_bp = Blueprint('jobs', __name__)

@jobs_bp.route('/api/jobs', methods=['GET'])
def list_jobs():
    """List all jobs (generic, all types) with pagination."""
    page = request.args.get('page', 1, type=int)
    page_size = request.args.get('pageSize', 20, type=int)

    with _jobs_lock:
        jobs = list(_jobs.values())
        jobs.sort(key=lambda x: x.get('createdAt', ''), reverse=True)
        total = len(jobs)

        start = (page - 1) * page_size
        end = start + page_size
        jobs = jobs[start:end]

    return jsonify(sanitize_for_json({
        'success': True,
        'jobs': jobs,
        'count': total
    }))


@jobs_bp.route('/api/jobs/<job_id>', methods=['GET'])
def get_job(job_id):
    """Get a single job by id."""
    with _jobs_lock:
        job = _jobs.get(job_id)
    if not job:
        return jsonify({'success': False, 'error': f'Job not found: {job_id}'}), 404
    return jsonify({'success': True, 'data': sanitize_for_json(job)})


@jobs_bp.route('/api/jobs/<job_type>/run', methods=['POST'])
def run_job_by_type(job_type):
    """Create and run a job of the given type."""
    if job_type not in _JOB_TYPES:
        return jsonify({
            'success': False,
            'error': f'Unsupported job type: {job_type}. Must be one of: {", ".join(sorted(_JOB_TYPES))}'
        }), 400

    data = request.get_json(silent=True) or {}
    params = convert_keys_to_snake(data)

    with _jobs_lock:
        for j in _jobs.values():
            if j.get('type') == job_type and j.get('status') in ('pending', 'running', 'queued'):
                return jsonify({
                    'success': False,
                    'error': f'Active job already exists for type: {job_type}'
                }), 409

    job_id = str(uuid.uuid4())
    job = {
        'id': job_id,
        'type': job_type,
        'params': params,
        'status': 'queued',
        'createdAt': datetime.now().isoformat(),
    }

    with _jobs_lock:
        _jobs[job_id] = job

    _audit_job('run', job)

    def _run_job():
        try:
            with _jobs_lock:
                if job_id in _jobs:
                    _jobs[job_id]['status'] = 'running'
            result = _execute_job_by_type(job_type, params)
            with _jobs_lock:
                if job_id in _jobs:
                    _jobs[job_id]['status'] = 'completed'
                    _jobs[job_id]['result'] = result
                    _jobs[job_id]['completedAt'] = datetime.now().isoformat()
        except Exception as e:
            with _jobs_lock:
                if job_id in _jobs:
                    _jobs[job_id]['status'] = 'failed'
                    _jobs[job_id]['error'] = str(e)
                    _jobs[job_id]['completedAt'] = datetime.now().isoformat()

    thread = threading.Thread(target=_run_job, daemon=True)
    thread.start()

    _audit_job('run', job)
    return jsonify({'success': True, 'data': sanitize_for_json(job)}), 202


@jobs_bp.route('/api/jobs/<job_id>/retry', methods=['POST'])
def retry_job(job_id):
    """Retry a failed job."""
    with _jobs_lock:
        job = _jobs.get(job_id)

    if not job:
        return jsonify({'success': False, 'error': f'Job not found: {job_id}'}), 404

    if job['status'] not in ('failed', 'cancelled'):
        return jsonify({
            'success': False,
            'error': f'Only failed or cancelled jobs can be retried. Current status: {job["status"]}'
        }), 400

    job_type = job.get('type', 'data_update')
    params = job.get('params', None)

    if not params:
        params = {
            'source': job.get('source', 'watchlist'),
            'days': job.get('days', 730),
            'force': job.get('force', False),
        }

    new_job_id = str(uuid.uuid4())
    new_job = {
        'id': new_job_id,
        'type': job_type,
        'params': params,
        'status': 'queued',
        'createdAt': datetime.now().isoformat(),
        'retryOf': job_id,
    }

    with _jobs_lock:
        _jobs[new_job_id] = new_job

    _audit_job('retry', new_job)

    def _retry():
        try:
            with _jobs_lock:
                if new_job_id in _jobs:
                    _jobs[new_job_id]['status'] = 'running'
            result = _execute_job_by_type(job_type, params)
            with _jobs_lock:
                if new_job_id in _jobs:
                    _jobs[new_job_id]['status'] = 'completed'
                    _jobs[new_job_id]['result'] = result
                    _jobs[new_job_id]['completedAt'] = datetime.now().isoformat()
        except Exception as e:
            with _jobs_lock:
                if new_job_id in _jobs:
                    _jobs[new_job_id]['status'] = 'failed'
                    _jobs[new_job_id]['error'] = str(e)
                    _jobs[new_job_id]['completedAt'] = datetime.now().isoformat()

    thread = threading.Thread(target=_retry, daemon=True)
    thread.start()

    return jsonify({
        'success': True,
        'job_id': new_job_id,
        'message': f'Job retried: {new_job_id}'
    })


@jobs_bp.route('/api/jobs/<job_id>/cancel', methods=['POST'])
def cancel_job(job_id):
    """Cancel a pending or running job."""
    with _jobs_lock:
        job = _jobs.get(job_id)

    if not job:
        return jsonify({'success': False, 'error': f'Job not found: {job_id}'}), 404

    if job['status'] not in ('pending', 'running', 'queued'):
        return jsonify({
            'success': False,
            'error': f'Only pending or running jobs can be cancelled. Current status: {job["status"]}'
        }), 400

    with _jobs_lock:
        _jobs[job_id]['status'] = 'cancelled'
        _jobs[job_id]['cancelledAt'] = datetime.now().isoformat()

    _audit_job('cancel', job)

    return jsonify({'success': True, 'message': f'Job cancelled: {job_id}'})

from adapters.shared.fund_flow_helpers import (
    _FUND_FLOW_COLUMN_MAP, _inject_fund_flow_to_klines, _extract_fund_flow_factors,
    _fetch_financial_data, _parse_financial_periods, _report_date, _pick_num,
)
@jobs_bp.route('/api/compute/factors', methods=['POST'])
def compute_factors():
    """计算因子（支持单个symbol或批量symbols）"""
    data = request.get_json() or {}
    symbol = data.get('symbol')
    symbols = data.get('symbols', [])
    requested_factors = data.get('factors', [])
    include_fundamental = data.get('include_fundamental', False)

    # Auto-detect: if fscore or earnings_quality is in the requested factors,
    # enable fundamental factor computation automatically
    if not include_fundamental and requested_factors:
        fundamental_names = {'fscore', 'earnings_quality'}
        if fundamental_names & set(requested_factors):
            include_fundamental = True

    all_symbols = list(symbols) if symbols else []
    if symbol and symbol not in all_symbols:
        all_symbols.append(symbol)

    if not all_symbols:
        return jsonify({'error': '缺少symbol或symbols参数'}), 400

    try:
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=120)).strftime('%Y-%m-%d')

        from domain.quantlib.stages.factor_stage import FactorStage

        results = []
        for sym in all_symbols:
            klines_df = ds.kline.get_daily_klines(sym, start_date, end_date)
            if klines_df is None or klines_df.is_empty():
                results.append({'symbol': sym, 'error': 'No kline data'})
                continue

            # Convert DataFrame to list of dicts for compatibility with existing code
            klines = klines_df.to_dicts()

            # -- 注入主力资金流数据到 klines --
            klines = _inject_fund_flow_to_klines(klines, sym)

            # -- 准备财务数据（如果需要基本面因子） --
            financial_data = None
            if include_fundamental:
                financial_data = _fetch_financial_data(sym)

            stage = FactorStage(
                name="factors",
                factor_names=requested_factors if requested_factors else None
            )
            stage_input = {
                'symbol': sym,
                'klines': klines
            }
            if financial_data:
                stage_input['financial_data'] = financial_data
            if requested_factors:
                stage_input['requested_factors'] = requested_factors

            result = stage.process(stage_input)
            factors = result.get('factors', {})

            # -- 附加主力资金流因子（从最后一条 kline 提取） --
            fund_factors = _extract_fund_flow_factors(klines)
            factors.update(fund_factors)

            last_row = klines[-1]
            latest_date = last_row.get('trade_date') or last_row.get('date') or ''
            ds.factor.save_factors(sym, str(latest_date), factors)

            results.append({
                'symbol': sym,
                'date': str(latest_date),
                'factor_count': len(factors),
                'factors': factors
            })

        return jsonify(sanitize_for_json({
            'success': True,
            'results': results,
            'count': len(results)
        }))
    except Exception as e:
        logger.exception(f"compute_factors failed: {e}")
        return jsonify({'error': str(e)}), 500

