"""
信号执行相关API

提供信号执行管道的手动触发、日志查询、统计分析和配置管理功能。
"""

import logging
from flask import Blueprint, jsonify, request
from datetime import datetime, date, timedelta
from typing import Dict, List

from adapters.inbound.api.shared import (
    ds,
    api_response,
    handle_api_error,
    get_query_params_snake_case
)
from application.services.signal_execution_scheduler import SignalExecutionScheduler
from adapters.outbound.repositories import SignalExecutionLogORMRepository
from adapters.outbound.repositories import RiskConfigORMRepository

logger = logging.getLogger(__name__)

signal_execution_bp = Blueprint('signal_execution', __name__)


@signal_execution_bp.route('/api/signal-execution/trigger', methods=['POST'])
@handle_api_error
def trigger_execution():
    """
    手动触发信号执行

    Request Body (optional):
        {
            "execution_date": "2026-05-28"  // Optional, defaults to today
        }

    Response:
        {
            "success": true,
            "data": {
                "execution_date": "2026-05-28",
                "strategies_run": 5,
                "signals_generated": 150,
                "signals_approved": 120,
                "signals_rejected": 30,
                "orders_created": 120,
                "duration_ms": 1200
            },
            "message": "信号执行完成"
        }
    """
    data = request.get_json() or {}
    execution_date_str = data.get('execution_date')

    if execution_date_str:
        try:
            execution_date = datetime.strptime(execution_date_str, '%Y-%m-%d').date()
        except ValueError:
            return jsonify({
                'success': False,
                'error': '日期格式错误，应为 YYYY-MM-DD'
            }), 400
    else:
        execution_date = date.today()

    logger.info(f"手动触发信号执行: {execution_date}")

    try:
        scheduler = SignalExecutionScheduler()
        result = scheduler.execute_daily_signals()

        return api_response(result, message='信号执行完成')

    except Exception as e:
        logger.error(f"信号执行失败: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@signal_execution_bp.route('/api/signal-execution/logs', methods=['GET'])
@handle_api_error
def get_execution_logs():
    """
    查询执行日志

    Query Parameters:
        - start_date: Start date (YYYY-MM-DD), defaults to 30 days ago
        - end_date: End date (YYYY-MM-DD), defaults to today
        - page: Page number (default: 1)
        - page_size: Items per page (default: 20, max: 100)

    Response:
        {
            "success": true,
            "data": {
                "items": [
                    {
                        "id": 1,
                        "execution_date": "2026-05-28",
                        "start_time": "2026-05-28 15:30:00",
                        "end_time": "2026-05-28 15:31:12",
                        "duration_ms": 1200,
                        "strategies_run": 5,
                        "signals_generated": 150,
                        "signals_approved": 120,
                        "signals_rejected": 30,
                        "orders_created": 120,
                        "errors_count": 0,
                        "status": "completed"
                    }
                ],
                "total": 30,
                "page": 1,
                "page_size": 20
            }
        }
    """
    params = get_query_params_snake_case()

    start_date = params.get('start_date')
    end_date = params.get('end_date')
    page = max(1, int(params.get('page', 1)))
    page_size = min(int(params.get('page_size', 20)), 100)

    if not end_date:
        end_date = date.today().isoformat()
    if not start_date:
        start_date = (date.today() - timedelta(days=30)).isoformat()

    log_repo = SignalExecutionLogORMRepository()
    logs = log_repo.get_logs_by_date_range(start_date, end_date)

    total = len(logs)
    offset = (page - 1) * page_size
    logs_page = logs[offset:offset + page_size]

    return api_response({
        'items': logs_page,
        'total': total,
        'page': page,
        'page_size': page_size
    })


@signal_execution_bp.route('/api/signal-execution/statistics', methods=['GET'])
@handle_api_error
def get_execution_statistics():
    """
    获取执行统计信息

    Query Parameters:
        - days: Number of days to analyze (default: 30)

    Response:
        {
            "success": true,
            "data": {
                "period": {
                    "start_date": "2026-04-28",
                    "end_date": "2026-05-28",
                    "days": 30
                },
                "executions": {
                    "total": 22,
                    "successful": 21,
                    "failed": 1,
                    "success_rate": 95.45
                },
                "signals": {
                    "total_generated": 3300,
                    "total_approved": 2640,
                    "total_rejected": 660,
                    "approval_rate": 80.00
                },
                "orders": {
                    "total_created": 2640,
                    "execution_rate": 100.00
                },
                "performance": {
                    "avg_duration_ms": 1200,
                    "avg_signals_per_day": 150,
                    "avg_orders_per_day": 120
                }
            }
        }
    """
    params = get_query_params_snake_case()
    days = int(params.get('days', 30))

    end_date = date.today()
    start_date = end_date - timedelta(days=days)

    log_repo = SignalExecutionLogORMRepository()
    logs = log_repo.get_logs_by_date_range(start_date.isoformat(), end_date.isoformat())

    # Calculate statistics
    stats = _calculate_statistics(logs, start_date, end_date, days)

    return api_response(stats)


@signal_execution_bp.route('/api/signal-execution/config', methods=['GET', 'POST'])
@handle_api_error
def manage_risk_config():
    """
    查询或更新风控配置

    GET - Query current configuration:
        Response:
            {
                "success": true,
                "data": {
                    "config_name": "default",
                    "max_single_order_percent": 20.00,
                    "max_position_percent": 30.00,
                    "max_sector_percent": 40.00,
                    "max_daily_trades": 50,
                    "require_stop_loss": true,
                    "min_stop_loss_percent": 3.00,
                    "max_stop_loss_percent": 15.00,
                    ...
                }
            }

    POST - Update configuration:
        Request Body:
            {
                "max_single_order_percent": 25.00,
                "max_position_percent": 35.00
            }

        Response:
            {
                "success": true,
                "data": { /* updated config */ },
                "message": "配置更新成功"
            }
    """
    config_repo = RiskConfigORMRepository()
    config_name = 'default'

    if request.method == 'GET':
        # Query configuration
        config = config_repo.get_config(config_name)

        if not config:
            return jsonify({
                'success': False,
                'error': f'配置 {config_name} 不存在'
            }), 404

        return api_response(config)

    elif request.method == 'POST':
        # Update configuration
        data = request.get_json() or {}

        if not data:
            return jsonify({
                'success': False,
                'error': '请提供要更新的配置项'
            }), 400

        # Update config
        success = config_repo.update_config(config_name, data)

        if not success:
            return jsonify({
                'success': False,
                'error': '配置更新失败'
            }), 500

        # Return updated config
        updated_config = config_repo.get_config(config_name)

        return api_response(updated_config, message='配置更新成功')


def _calculate_statistics(logs: List[Dict], start_date: date, end_date: date, days: int) -> Dict:
    """
    计算执行统计信息

    Args:
        logs: 执行日志列表
        start_date: 统计开始日期
        end_date: 统计结束日期
        days: 统计天数

    Returns:
        统计结果字典
    """
    if not logs:
        return {
            'period': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'days': days
            },
            'executions': {
                'total': 0,
                'successful': 0,
                'failed': 0,
                'success_rate': 0.0
            },
            'signals': {
                'total_generated': 0,
                'total_approved': 0,
                'total_rejected': 0,
                'approval_rate': 0.0
            },
            'orders': {
                'total_created': 0,
                'execution_rate': 0.0
            },
            'performance': {
                'avg_duration_ms': 0,
                'avg_signals_per_day': 0,
                'avg_orders_per_day': 0
            }
        }

    # Execution statistics
    total_executions = len(logs)
    successful_executions = sum(1 for log in logs if log.get('status') == 'completed')
    failed_executions = total_executions - successful_executions
    success_rate = (successful_executions / total_executions * 100) if total_executions > 0 else 0.0

    # Signal statistics
    total_generated = sum(log.get('signals_generated', 0) or 0 for log in logs)
    total_approved = sum(log.get('signals_approved', 0) or 0 for log in logs)
    total_rejected = sum(log.get('signals_rejected', 0) or 0 for log in logs)
    approval_rate = (total_approved / total_generated * 100) if total_generated > 0 else 0.0

    # Order statistics
    total_orders = sum(log.get('orders_created', 0) or 0 for log in logs)
    execution_rate = (total_orders / total_approved * 100) if total_approved > 0 else 0.0

    # Performance statistics
    durations = [log.get('duration_ms', 0) or 0 for log in logs if log.get('duration_ms')]
    avg_duration = sum(durations) / len(durations) if durations else 0
    avg_signals_per_day = total_generated / total_executions if total_executions > 0 else 0
    avg_orders_per_day = total_orders / total_executions if total_executions > 0 else 0

    return {
        'period': {
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'days': days
        },
        'executions': {
            'total': total_executions,
            'successful': successful_executions,
            'failed': failed_executions,
            'success_rate': round(success_rate, 2)
        },
        'signals': {
            'total_generated': total_generated,
            'total_approved': total_approved,
            'total_rejected': total_rejected,
            'approval_rate': round(approval_rate, 2)
        },
        'orders': {
            'total_created': total_orders,
            'execution_rate': round(execution_rate, 2)
        },
        'performance': {
            'avg_duration_ms': round(avg_duration),
            'avg_signals_per_day': round(avg_signals_per_day),
            'avg_orders_per_day': round(avg_orders_per_day)
        }
    }
