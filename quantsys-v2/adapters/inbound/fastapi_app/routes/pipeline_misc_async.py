"""流水线杂项 API - FastAPI 版（从 Flask pipeline.py 迁移，响应契约保持一致）

覆盖端点：
- POST /api/cli/calibrate         置信度校准（后台任务）
- POST /api/cli/signal-generate   信号生成（同步 NDJSON/JSON 或异步后台任务）
- GET  /api/stocks/data-full-status  数据完整状态
- GET  /api/stocks/data-status       单只股票数据完整性

后台执行函数 _execute_calibration / _execute_signal_generate_v2 直接复用 Flask
pipeline.py 的实现（同一实现，保证行为一致）。
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


@router.post('/api/cli/signal-generate')
@handle_api_error
def cli_signal_generate(request: Request, payload: Optional[Dict[str, Any]] = Body(None)):
    """
    使用指定策略对指定股票生成最新信号（支持同步/异步模式）。

    同步模式（< 50 stocks）：流式返回 NDJSON（或按 Accept: application/json 返回标准 JSON）
    异步模式（>= 50 stocks）：后台任务，返回 run_id
    """
    data = convert_keys_to_snake(payload or {})

    strategy_id = data.get('strategy_id')
    if not strategy_id:
        return error_response({'success': False, 'error': '缺少参数: strategy_id'}, 400)

    symbols_raw = data.get('symbols', [])
    if isinstance(symbols_raw, str) and symbols_raw.strip():
        symbols = [s.strip() for s in symbols_raw.split(',') if s.strip()]
    elif isinstance(symbols_raw, list):
        symbols = [str(s).strip() for s in symbols_raw if s]
    else:
        # 默认：从 portfolio 读取持仓股
        symbols = []
        try:
            portfolio_path = _PROJECT_ROOT_PATH / '.pi-invest' / 'portfolio.json'
            if portfolio_path.exists():
                with open(portfolio_path) as f:
                    pf = json.load(f)
                symbols = [pos['symbol'] for pos in pf.get('positions', [])]
        except Exception as e:
            logger.warning(f"读取 portfolio 失败: {e}")

    if not symbols:
        return error_response({'success': False, 'error': '未指定 symbols 且 portfolio 为空'}, 400)

    try:
        strategy_id_int = int(strategy_id)
    except (ValueError, TypeError):
        # 内置策略请使用 /api/strategies/execute 接口
        from adapters.outbound.repositories import StrategyORMRepository
        repo = StrategyORMRepository()
        builtin = repo.get_builtin_by_type(str(strategy_id).lower())
        if builtin:
            return error_response({
                'success': False,
                'error': f"'{strategy_id}' 是内置策略（类型: {builtin['category']}），请使用 /api/strategies/execute 接口",
                'hint': f"POST /api/strategies/execute with {{'symbol':'...', 'strategyName':'{builtin['strategy_type']}'}}"
            }, 400)
        return error_response({'success': False, 'error': f'无效的 strategy_id: {strategy_id}'}, 400)

    # 模式选择：< 50 stocks = sync, >= 50 = async
    SYNC_THRESHOLD = 50
    if len(symbols) < SYNC_THRESHOLD:
        # 同步模式：检测 Accept header 决定返回格式
        from adapters.shared.services import strategy_service

        # 获取策略名
        try:
            strategy_row = strategy_service.strategy_repo.get_by_id(strategy_id_int)
            strategy_name = strategy_row.get('strategy_name') if strategy_row else f'Strategy#{strategy_id_int}'
        except Exception:
            strategy_name = f'Strategy#{strategy_id_int}'

        # 检测客户端期望的响应格式
        accept_header = request.headers.get('Accept', '')
        prefer_json = 'application/json' in accept_header and 'application/x-ndjson' not in accept_header

        if prefer_json:
            # 返回标准 JSON（用于 TS 工具调用）
            signals = []
            buy = sell = hold = 0

            for symbol in symbols:
                try:
                    signal = service.generate_signal(
                        strategy_id=strategy_id_int,
                        symbol=symbol
                    )

                    if signal:
                        signal_type = signal.get('signal_type', 'hold')
                        if signal_type.upper() == 'BUY':
                            buy += 1
                        elif signal_type.upper() == 'SELL':
                            sell += 1
                        else:
                            hold += 1
                        signals.append({'type': 'signal', 'data': signal})
                    else:
                        hold += 1

                except Exception as e:
                    logger.warning(f"信号生成失败: {symbol} — {e}")
                    hold += 1
                    signals.append({
                        'type': 'error',
                        'data': {'symbol': symbol, 'error': str(e)}
                    })

            # 返回标准 JSON（Flask 为 jsonify，不做 camelCase/sanitize 转换）
            return {
                'success': True,
                'signals': signals,
                'summary': {
                    'strategy_id': strategy_id_int,
                    'strategy_name': strategy_name,
                    'total': len(symbols),
                    'buy': buy,
                    'sell': sell,
                    'hold': hold,
                    'generated_at': datetime.now().isoformat()
                }
            }

        else:
            # 返回 NDJSON stream（默认行为，用于 CLI）
            def generate():
                """生成器：逐个生成信号"""
                buy = sell = hold = 0

                for symbol in symbols:
                    try:
                        signal = service.generate_signal(
                            strategy_id=strategy_id_int,
                            symbol=symbol
                        )

                        if signal:
                            signal_type = signal.get('signal_type', 'hold')
                            if signal_type.upper() == 'BUY':
                                buy += 1
                            elif signal_type.upper() == 'SELL':
                                sell += 1
                            else:
                                hold += 1

                            # 输出信号行
                            yield json.dumps({'type': 'signal', 'data': signal}, ensure_ascii=False) + '\n'
                        else:
                            # 无信号视为 hold
                            hold += 1

                    except Exception as e:
                        logger.warning(f"信号生成失败: {symbol} — {e}")
                        hold += 1
                        # 输出错误行
                        yield json.dumps({
                            'type': 'error',
                            'data': {'symbol': symbol, 'error': str(e)}
                        }, ensure_ascii=False) + '\n'

                # 输出汇总行
                yield json.dumps({
                    'type': 'summary',
                    'data': {
                        'strategy_id': strategy_id_int,
                        'strategy_name': strategy_name,
                        'total': len(symbols),
                        'buy': buy,
                        'sell': sell,
                        'hold': hold,
                        'generated_at': datetime.now().isoformat()
                    }
                }, ensure_ascii=False) + '\n'

            return StreamingResponse(generate(), media_type='application/x-ndjson')

    else:
        # 异步模式：后台任务
        run_id = f"signal_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        now = datetime.now()

        run_record = {
            'runId': run_id,
            'run_id': run_id,
            'status': 'running',
            'taskType': 'signal_generate',
            'startTime': now.isoformat(),
            'params': {
                'strategy_id': strategy_id_int,
                'symbols': symbols,
                'count': len(symbols)
            },
            'logs': [f'[{now.isoformat()}] 信号生成触发: {run_id}, {len(symbols)} stocks'],
        }

        runs = _load_pipeline_runs()
        runs.append(run_record)
        _save_pipeline_runs(runs)

        # 启动后台任务（统一线程池，Phase 4）
        from infrastructure.concurrency.thread_manager import submit_background
        submit_background("api-bg", _execute_signal_generate_v2, run_id, strategy_id_int, symbols)

        return error_response({
            'success': True,
            'run_id': run_id,
            'status': 'running',
            'message': f'后台任务已启动，run_id={run_id}'
        }, 202)


# ═══════════════════════════════════════════════════════════════
# 数据状态端点
# ═══════════════════════════════════════════════════════════════


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
