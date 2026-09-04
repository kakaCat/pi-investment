"""流水线杂项 API - FastAPI 版（从 Flask pipeline.py 迁移，响应契约保持一致）

覆盖端点：
- POST /api/cli/calibrate         置信度校准（后台任务）
- GET  /api/stocks/data-full-status  数据完整状态
- GET  /api/stocks/data-status       单只股票数据完整性

后台执行函数 _execute_calibration 直接复用 Flask pipeline.py 的实现（同一实现，保证行为一致）。
"""
import json
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Query, Request
from fastapi.responses import StreamingResponse
import structlog

from adapters.inbound.fastapi_app.shared import (
    api_response, error_response, handle_api_error, sanitize_for_json,
    convert_keys_to_snake,
    _load_pipeline_runs, _save_pipeline_runs,
    acquire_task, get_running_tasks_snapshot,
)
from adapters.shared import _PROJECT_ROOT_PATH
# 复用 Flask pipeline.py 的后台执行函数（同一实现，保证行为一致）
from adapters.shared.pipeline_exec import (
    _execute_calibration, _execute_signal_generate_v2,
)

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["Pipeline Misc - CLI桥接/数据状态"])


# ═══════════════════════════════════════════════════════════════
# CLI 桥接端点
# ═══════════════════════════════════════════════════════════════


@router.post('/api/cli/calibrate')
@handle_api_error
def cli_calibrate(payload: Optional[Dict[str, Any]] = Body(None)):
    data = payload or {}
    params = convert_keys_to_snake(data)
    run_id = f"#C-{str(uuid.uuid4())[:8].upper()}"
    if not acquire_task('calibrate', run_id):
        existing = get_running_tasks_snapshot().get('calibrate', '?')
        return error_response({'success': False, 'error': f'校准已在运行中 (run_id={existing})'}, 409)
    now = datetime.now()
    run_record = {
        'runId': run_id, 'run_id': run_id, 'status': 'running', 'taskType': 'calibrate',
        'startTime': now.isoformat(), 'symbols': ['ALL'],
        'params': {
            'forward_days': params.get('forward_days', 5),
            'return_threshold': params.get('return_threshold', 0.02),
            'max_symbols': params.get('max_symbols', 500),
            'lookback_days': params.get('lookback_days', 180),
        },
        'logs': [f'[{now.isoformat()}] 置信度校准触发: {run_id}'],
    }
    runs = _load_pipeline_runs()
    runs.append(run_record)
    _save_pipeline_runs(runs)
    from infrastructure.concurrency.thread_manager import submit_background
    submit_background("api-bg", _execute_calibration, run_id,
        forward_days=params.get('forward_days', 5),
        return_threshold=params.get('return_threshold', 0.02),
        max_symbols=params.get('max_symbols', 500),
        lookback_days=params.get('lookback_days', 180))
    return error_response(
        api_response({'success': True, 'run_id': run_id, 'status': 'running',
                      'message': f'置信度校准已触发，run_id={run_id}'}), 202)


@router.get('/api/stocks/data-full-status')
@handle_api_error
def data_full_status():
    try:
        pipeline_runs = _load_pipeline_runs()
        latest_runs = sorted(pipeline_runs, key=lambda r: r.get('startTime', ''), reverse=True)[:5]

        # 截断过大的日志，防止响应体积过大
        MAX_LOG_LENGTH = 500  # 每条日志最大字符数
        MAX_LOGS = 20  # 最多返回的日志条数
        for run in latest_runs:
            if 'logs' in run and isinstance(run['logs'], list):
                # 截断每条日志
                run['logs'] = [
                    log[:MAX_LOG_LENGTH] + '...(truncated)' if len(log) > MAX_LOG_LENGTH else log
                    for log in run['logs'][:MAX_LOGS]
                ]
                if len(run.get('logs', [])) > MAX_LOGS:
                    run['logs'].append(f'... ({len(run["logs"]) - MAX_LOGS} more logs omitted)')

        return api_response({
            'success': True,
            'pipeline': {'total_runs': len(pipeline_runs), 'latest_runs': latest_runs},
            'cache': {},
            'db': {'provider': 'postgresql'},
        })
    except Exception as e:
        return error_response({'success': False, 'error': str(e)}, 500)


@router.get('/api/stocks/data-status')
@handle_api_error
def data_status(symbol: str = Query('000001.SZ')):
    try:
        from datetime import datetime
        from infrastructure.services.service_factory import ServiceFactory
        _stock_repo = ServiceFactory.get_stock_repository()
        _kline_repo = ServiceFactory.get_kline_repository()
        _signal_repo = ServiceFactory.get_signal_repository()
        _factor_repo = ServiceFactory.get_factor_repository()

        result = {
            'status': 'ok',
            'checked_at': datetime.now().isoformat(),
            'issues': [],
            'summary': {}
        }

        kline_count = _kline_repo.count_klines(symbol)
        result['summary']['kline_count'] = kline_count
        if kline_count == 0:
            result['issues'].append(f"No kline data for {symbol}")
            result['status'] = 'warning'

        stock_obj = _stock_repo.get_by_symbol(symbol)
        result['summary']['stock_exists'] = stock_obj is not None
        if not stock_obj:
            result['issues'].append(f"Stock {symbol} not found in database")
            result['status'] = 'error'

        today = datetime.now().strftime('%Y-%m-%d')
        signals = _signal_repo.get_signals_by_symbol(symbol, today, today)
        result['summary']['signal_count'] = len(signals)

        factors = _factor_repo.get_latest_factors(symbol)
        result['summary']['factor_count'] = len(factors)
        if len(factors) == 0:
            result['issues'].append(f"No factor data for {symbol}")

        return sanitize_for_json(result)
    except Exception as e:
        return error_response({'error': str(e)}, 500)
