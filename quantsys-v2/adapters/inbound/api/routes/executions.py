"""
executions routes.
"""
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
import re
import uuid

from flask import Blueprint, jsonify, request

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

executions_bp = Blueprint('executions', __name__)

@executions_bp.route('/api/executions', methods=['GET'])
def list_executions():
    """查询执行记录列表"""
    status = request.args.get('status')
    limit = request.args.get('limit', 200, type=int)
    offset = request.args.get('offset', 0, type=int)
    results = ds.execution.get_all_executions(status=status, limit=limit, offset=offset)

    mapped_results = []
    for row in results:
        mapped_row = {
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
            'updatedAt': row.get('updated_at')
        }
        mapped_results.append(mapped_row)

    return jsonify(sanitize_for_json({'executions': mapped_results, 'count': len(mapped_results)}))


@executions_bp.route('/api/executions/stats', methods=['GET'])
def execution_stats():
    """执行统计"""
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    stats = ds.execution.get_execution_stats(start_date, end_date)
    return jsonify(sanitize_for_json(stats))


@executions_bp.route('/api/executions/daily', methods=['GET'])
def daily_execution_stats():
    """每日执行统计"""
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    if not start_date or not end_date:
        return jsonify({'error': 'start_date and end_date are required'}), 400
    stats = ds.execution.get_daily_execution_stats(start_date, end_date)
    return jsonify(sanitize_for_json({'daily_stats': stats, 'count': len(stats)}))


@executions_bp.route('/api/executions/<int:execution_id>', methods=['GET'])
def get_execution(execution_id):
    """获取单条执行记录"""
    ex = ds.execution.get_execution(execution_id)
    if not ex:
        return jsonify({'error': 'Execution not found'}), 404

    mapped_ex = {
        'executionId': ex.get('id'),
        'signalId': ex.get('signal_id'),
        'symbol': ex.get('symbol'),
        'name': ex.get('name'),
        'action': ex.get('action'),
        'price': ex.get('execution_price'),
        'quantity': ex.get('quantity'),
        'amount': (ex.get('execution_price') or 0) * (ex.get('quantity') or 0),
        'commission': ex.get('commission'),
        'status': ex.get('status'),
        'openDate': ex.get('execution_date'),
        'closeDate': ex.get('close_date'),
        'closePrice': ex.get('close_price'),
        'profit': ex.get('pnl'),
        'createdAt': ex.get('created_at'),
        'updatedAt': ex.get('updated_at')
    }

    return jsonify(sanitize_for_json(mapped_ex))


@executions_bp.route('/api/executions/signal/<int:signal_id>', methods=['GET'])
def get_executions_by_signal(signal_id):
    """获取指定信号的所有执行记录"""
    results = ds.execution.get_executions_by_signal(signal_id)

    def map_execution_fields(ex):
        return {
            'executionId': ex.get('id'),
            'signalId': ex.get('signal_id'),
            'symbol': ex.get('symbol'),
            'name': ex.get('name'),
            'action': ex.get('action'),
            'price': ex.get('execution_price'),
            'quantity': ex.get('quantity'),
            'amount': ex.get('execution_price', 0) * ex.get('quantity', 0),
            'commission': ex.get('commission'),
            'status': ex.get('status'),
            'openDate': ex.get('execution_date'),
            'closeDate': ex.get('close_date'),
            'closePrice': ex.get('close_price'),
            'profit': ex.get('pnl'),
            'createdAt': ex.get('created_at'),
            'updatedAt': ex.get('updated_at')
        }

    mapped_results = [map_execution_fields(ex) for ex in results]
    return jsonify(sanitize_for_json({'executions': mapped_results, 'count': len(mapped_results)}))


@executions_bp.route('/api/executions/pending', methods=['GET'])
def pending_executions():
    """获取待处理执行记录"""
    limit = request.args.get('limit', 100, type=int)
    results = ds.execution.get_pending_executions(limit=limit)

    def map_execution_fields(ex):
        return {
            'executionId': ex.get('id'),
            'signalId': ex.get('signal_id'),
            'symbol': ex.get('symbol'),
            'name': ex.get('name'),
            'action': ex.get('action'),
            'price': ex.get('execution_price'),
            'quantity': ex.get('quantity'),
            'amount': ex.get('execution_price', 0) * ex.get('quantity', 0),
            'commission': ex.get('commission'),
            'status': ex.get('status'),
            'openDate': ex.get('execution_date'),
            'closeDate': ex.get('close_date'),
            'closePrice': ex.get('close_price'),
            'profit': ex.get('pnl'),
            'createdAt': ex.get('created_at'),
            'updatedAt': ex.get('updated_at')
        }

    mapped_results = [map_execution_fields(ex) for ex in results]
    return jsonify(sanitize_for_json({'executions': mapped_results, 'count': len(mapped_results)}))


@executions_bp.route('/api/executions', methods=['POST'])
def create_execution():
    """创建执行记录"""
    data = request.get_json(silent=True) or {}
    try:
        exec_id = ds.execution.create_execution(data)
        return jsonify({'id': exec_id, 'message': 'Execution created'}), 201
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@executions_bp.route('/api/executions/<int:execution_id>/close', methods=['PUT'])
def close_execution(execution_id):
    """平仓执行记录"""
    data = request.get_json(silent=True) or {}
    close_date = data.get('close_date')
    close_price = data.get('close_price')

    if not close_date or close_price is None:
        return jsonify({'error': 'close_date and close_price are required'}), 400

    try:
        ok = ds.execution.close_execution(execution_id, close_date, float(close_price))
        if not ok:
            return jsonify({'error': 'Execution not found'}), 404
        updated = ds.execution.get_execution(execution_id)
        return jsonify(sanitize_for_json({'message': 'Execution closed', 'execution': updated}))
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@executions_bp.route('/api/executions/<int:execution_id>/cancel', methods=['PUT'])
def cancel_execution(execution_id):
    """取消执行记录"""
    try:
        ok = ds.execution.cancel_execution(execution_id)
        if not ok:
            return jsonify({'error': 'Execution not found'}), 404
        return jsonify({'message': 'Execution cancelled'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@executions_bp.route('/api/executions/<int:execution_id>/status', methods=['PUT'])
def update_execution_status(execution_id):
    """更新执行状态"""
    data = request.get_json(silent=True) or {}
    status = data.get('status')
    if not status:
        return jsonify({'error': 'status is required'}), 400
    try:
        ok = ds.execution.update_execution_status(execution_id, status)
        if not ok:
            return jsonify({'error': 'Execution not found'}), 404
        return jsonify({'message': f'Status updated to {status}'})
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@executions_bp.route('/api/executions/summary', methods=['GET'])
def execution_summary():
    """信号执行综合摘要"""
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    summary = ds.get_execution_summary(start_date, end_date)
    return jsonify(sanitize_for_json(summary))


