"""
risk routes.
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

risk_bp = Blueprint('risk', __name__)

@risk_bp.route('/api/stock/<symbol>/risk/trade-check', methods=['POST'])
@handle_api_error
def check_trade_risk_v2(symbol):
    """交易风控检查 - 替代旧 quant_cli risk.trade_check"""
    try:
        from application.services.risk_service import RiskService

        data = request.get_json(silent=True) or {}
        action = data.get('action', 'buy')
        price = data.get('price', 0)
        shares = data.get('shares', 0)
        if not price or not shares:
            return jsonify({'success': False, 'error': 'price and shares required'}), 400

        risk_service = RiskService()
        result = risk_service.check_trade_risk(symbol, action, float(price), int(shares))

        if not result.get('success'):
            return jsonify({'success': False, 'error': result.get('error')}), 400
        return api_response(result.get('data'))
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@risk_bp.route('/api/stock/<symbol>/risk/position-size', methods=['POST'])
@handle_api_error
def calculate_position_size_v2(symbol):
    """Kelly仓位计算 - 替代旧 quant_cli risk.position_size"""
    try:
        from application.services.risk_service import RiskService

        data = request.get_json(silent=True) or {}
        price = data.get('price', 0)
        account_value = data.get('account_value', 100000)  # 默认账户价值
        risk_percent = data.get('risk_percent', 2.0)  # 默认风险百分比

        if not price:
            return jsonify({'success': False, 'error': 'price required'}), 400

        risk_service = RiskService()
        result = risk_service.calculate_position_size(symbol, float(account_value), float(risk_percent))

        if not result.get('success'):
            return jsonify({'success': False, 'error': result.get('error')}), 400
        return api_response(result.get('data'))
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@risk_bp.route('/api/stock/<symbol>/risk/stop-loss', methods=['POST'])
@handle_api_error
def calculate_stop_loss_v2(symbol):
    """止损价计算 - 替代旧 quant_cli risk.stop_loss"""
    try:
        from application.services.risk_service import RiskService

        data = request.get_json(silent=True) or {}
        entry_price = data.get('entry_price', 0)
        method = data.get('method', 'percentage')  # 默认使用百分比方法

        if not entry_price:
            return jsonify({'success': False, 'error': 'entry_price required'}), 400

        risk_service = RiskService()
        result = risk_service.calculate_stop_loss(symbol, float(entry_price), method)

        if not result.get('success'):
            return jsonify({'success': False, 'error': result.get('error')}), 400
        return api_response(result.get('data'))
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@risk_bp.route('/api/risk/check', methods=['POST'])
def risk_check():
    """风险检查"""
    try:
        data = request.get_json() or {}
        symbols = data.get('symbols')

        holdings = ds.portfolio.get_all_holdings()
        if symbols:
            holdings = [h for h in holdings if h['symbol'] in symbols]

        account_value = float(data.get('account_value', 0)) if data.get('account_value') else None

        holdings_stats = ds.portfolio.get_holdings_stats()
        sector_concentration_map = {}  # sector -> ratio
        if holdings_stats and account_value and account_value > 0:
            sector_dist = holdings_stats.get('sector_distribution', [])
            for sector_info in sector_dist:
                sector_name = sector_info.get('sector', '未知')
                sector_invested = sector_info.get('invested', 0) or 0
                sector_ratio = sector_invested / account_value
                if sector_ratio > 0.5:  # 50% threshold
                    sector_concentration_map[sector_name] = sector_ratio

        checks = []
        for h in holdings:
            symbol = h['symbol']
            position_value = h.get('total_invested', 0) or (h.get('quantity', 0) * h.get('avg_cost', 0))
            item_checks = []

            current_price = 0
            try:
                latest_kline = ds.kline.get_latest_daily_kline(symbol)
                if latest_kline is not None and not latest_kline.is_empty():
                    kline_row = latest_kline.to_dicts()[0]
                    current_price = float(kline_row.get('close', 0))
            except Exception:
                pass  # 如果获取失败，使用默认值 0

            if account_value and account_value > 0:
                concentration = (position_value / account_value) * 100
                if concentration > 30:
                    item_checks.append({
                        'type': 'concentration',
                        'level': 'high',
                        'message': f'{symbol} 仓位集中度 {concentration:.1f}% > 30%',
                        'suggestion': '建议分散持仓'
                    })

            holding_sector = h.get('sector', '未知')
            if holding_sector in sector_concentration_map:
                sector_ratio = sector_concentration_map[holding_sector]
                item_checks.append({
                    'type': 'sector_concentration',
                    'level': 'high',
                    'message': f'{symbol} 所属行业 "{holding_sector}" 集中度 {sector_ratio*100:.1f}% > 50%',
                    'suggestion': '建议分散行业配置'
                })

            risk_metrics = ds.risk.get_latest_risk_metrics(symbol)
            var_95 = 0
            volatility = 0
            max_drawdown = 0

            if risk_metrics:
                var_95 = risk_metrics.get('var_95', 0) or 0
                volatility = risk_metrics.get('volatility', 0) or 0
                max_drawdown = risk_metrics.get('max_drawdown', 0) or 0

                if var_95 < -0.05:
                    item_checks.append({
                        'type': 'var',
                        'level': 'medium',
                        'message': f'{symbol} VaR 95% = {var_95:.3f}',
                        'suggestion': '建议设置止损'
                    })

            checks.append({
                'symbol': symbol,
                'position_value': position_value,
                'current_price': current_price,
                'var_95': var_95,
                'volatility': volatility,
                'max_drawdown': max_drawdown,
                'checks': item_checks
            })

        return jsonify(sanitize_for_json({
            'total_holdings': len(holdings),
            'checks': checks,
            'risk_level': 'high' if len(checks) > 3 else 'low'
        }))
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@risk_bp.route('/api/risk/stop-loss/rules', methods=['GET'])
def get_stop_loss_rules():
    """获取止损规则列表（可选按symbol过滤）"""
    try:
        from adapters.outbound.repositories import RiskORMRepository

        symbol = request.args.get('symbol')
        status = request.args.get('status')

        repo = RiskORMRepository()
        rules = repo.list_stop_loss_rules(symbol=symbol, status=status)

        rules_list = []
        for rule in rules:
            formatted_rule = {
                'id': rule.get('id'),
                'symbol': rule.get('symbol'),
                'name': rule.get('name'),
                'type': rule.get('type'),
                'stopLossPercent': rule.get('stop_loss_percent'),
                'triggerPercent': rule.get('stop_loss_percent'),  # Alias for compatibility
                'trailingPercent': rule.get('trailing_percent'),
                'atrMultiplier': rule.get('atr_multiplier'),
                'status': rule.get('status'),
                'createdAt': rule.get('created_at'),
                'updatedAt': rule.get('updated_at')
            }
            rules_list.append(formatted_rule)

        return jsonify({'success': True, 'rules': rules_list, 'count': len(rules_list)})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


def _normalize_stop_loss_type(stop_loss_type):
    """
    Normalize stop-loss type from frontend format to backend format.
    Supports both naming conventions for backward compatibility.
    """
    type_mapping = {
        'price': 'fixed_price',
        'percent': 'fixed_percent',
        'trailing': 'trailing_stop',
        'fixed_price': 'fixed_price',
        'fixed_percent': 'fixed_percent',
        'trailing_stop': 'trailing_stop'
    }
    return type_mapping.get(stop_loss_type, 'fixed_percent')


@risk_bp.route('/api/risk/stop-loss/rules', methods=['POST'])
def create_stop_loss_rule():
    """创建止损规则"""
    try:
        from adapters.outbound.repositories import RiskORMRepository

        body = request.get_json() or {}
        if not body.get('symbol'):
            return jsonify({'success': False, 'error': '缺少symbol参数'}), 400

        trigger_value = body.get('stopLossPercent') or body.get('triggerPercent')
        stop_loss_type = body.get('stopLossType') or body.get('type', 'fixed_percent')

        rule_id = str(int(datetime.now().timestamp() * 1000))

        repo = RiskORMRepository()
        rule_data = {
            'id': rule_id,
            'symbol': body['symbol'],
            'name': body.get('name', f"{body['symbol']}止损"),
            'type': _normalize_stop_loss_type(stop_loss_type),
            'stop_loss_percent': trigger_value,
            'trailing_percent': body.get('trailingPercent'),
            'atr_multiplier': body.get('atrMultiplier'),
            'status': 'active'
        }
        repo.create_stop_loss_rule(rule_data)

        rule = repo.get_stop_loss_rule(rule_id)
        if rule:
            formatted_rule = {
                'id': rule.get('id'),
                'symbol': rule.get('symbol'),
                'name': rule.get('name'),
                'type': rule.get('type'),
                'stopLossPercent': rule.get('stop_loss_percent'),
                'triggerPercent': rule.get('stop_loss_percent'),
                'trailingPercent': rule.get('trailing_percent'),
                'atrMultiplier': rule.get('atr_multiplier'),
                'status': rule.get('status'),
                'createdAt': rule.get('created_at'),
                'updatedAt': rule.get('updated_at')
            }
            return jsonify({'success': True, 'rule': formatted_rule})
        else:
            return jsonify({'success': False, 'error': '创建规则失败'}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@risk_bp.route('/api/risk/stop-loss/rules/batch', methods=['POST'])
def batch_create_stop_loss_rules():
    """批量创建止损规则"""
    try:
        from adapters.outbound.repositories import RiskORMRepository

        body = request.get_json() or {}
        rules_data = body.get('rules', [])
        if not rules_data:
            return jsonify({'success': False, 'error': '缺少rules参数'}), 400

        repo = RiskORMRepository()
        created = []

        for idx, item in enumerate(rules_data):
            trigger_value = item.get('stopLossPercent') or item.get('triggerPercent')
            stop_loss_type = item.get('stopLossType') or item.get('type', 'fixed_percent')

            rule_id = str(int(datetime.now().timestamp() * 1000) + idx)

            rule_data = {
                'id': rule_id,
                'symbol': item['symbol'],
                'name': item.get('name', f"{item['symbol']}止损"),
                'type': _normalize_stop_loss_type(stop_loss_type),
                'stop_loss_percent': trigger_value,
                'trailing_percent': item.get('trailingPercent'),
                'atr_multiplier': item.get('atrMultiplier'),
                'status': 'active'
            }
            repo.create_stop_loss_rule(rule_data)

            rule = repo.get_stop_loss_rule(rule_id)
            if rule:
                formatted_rule = {
                    'id': rule.get('id'),
                    'symbol': rule.get('symbol'),
                    'name': rule.get('name'),
                    'type': rule.get('type'),
                    'stopLossPercent': rule.get('stop_loss_percent'),
                    'triggerPercent': rule.get('stop_loss_percent'),
                    'trailingPercent': rule.get('trailing_percent'),
                    'atrMultiplier': rule.get('atr_multiplier'),
                    'status': rule_dict.get('status'),
                    'createdAt': rule_dict.get('created_at'),
                    'updatedAt': rule_dict.get('updated_at')
                }
                created.append(formatted_rule)

        return jsonify({'success': True, 'rules': created, 'count': len(created)})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@risk_bp.route('/api/risk/stop-loss/rules/<rule_id>', methods=['PUT'])
def update_stop_loss_rule(rule_id):
    """更新止损规则"""
    try:
        from adapters.outbound.repositories import RiskORMRepository

        body = request.get_json() or {}

        repo = RiskORMRepository()

        update_params = {}

        if 'name' in body:
            update_params['name'] = body['name']

        if 'stopLossType' in body:
            update_params['type'] = _normalize_stop_loss_type(body['stopLossType'])
        elif 'type' in body:
            update_params['type'] = _normalize_stop_loss_type(body['type'])

        if 'triggerPercent' in body:
            update_params['stop_loss_percent'] = body['triggerPercent']
        elif 'stopLossPercent' in body:
            update_params['stop_loss_percent'] = body['stopLossPercent']

        if 'trailingPercent' in body:
            update_params['trailing_percent'] = body['trailingPercent']

        if 'atrMultiplier' in body:
            update_params['atr_multiplier'] = body['atrMultiplier']

        if 'status' in body:
            update_params['status'] = body['status']

        success = repo.update_stop_loss_rule(rule_id, update_params)

        if not success:
            return jsonify({'success': False, 'error': '规则不存在'}), 404

        rule = repo.get_stop_loss_rule(rule_id)
        if rule:
            formatted_rule = {
                'id': rule.get('id'),
                'symbol': rule.get('symbol'),
                'name': rule.get('name'),
                'type': rule.get('type'),
                'stopLossPercent': rule_dict.get('stop_loss_percent'),
                'triggerPercent': rule_dict.get('stop_loss_percent'),
                'trailingPercent': rule_dict.get('trailing_percent'),
                'atrMultiplier': rule_dict.get('atr_multiplier'),
                'status': rule_dict.get('status'),
                'createdAt': rule_dict.get('created_at'),
                'updatedAt': rule_dict.get('updated_at')
            }
            return jsonify({'success': True, 'rule': formatted_rule})
        else:
            return jsonify({'success': False, 'error': '更新后无法获取规则'}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@risk_bp.route('/api/risk/stop-loss/rules/<rule_id>', methods=['DELETE'])
def delete_stop_loss_rule(rule_id):
    """删除止损规则"""
    try:
        from adapters.outbound.repositories import RiskORMRepository

        repo = RiskORMRepository()

        success = repo.delete_stop_loss_rule(rule_id)

        if not success:
            return jsonify({'success': False, 'error': '规则不存在'}), 404

        return jsonify({'success': True, 'message': '规则已删除'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ============== 风险指标计算端点（empyrical-based） ==============

@risk_bp.route('/api/risk/metrics', methods=['POST'])
def calculate_risk_metrics():
    """
    计算标准化风险指标（基于empyrical）

    POST /api/risk/metrics

    请求体:
    {
        "returns": [0.01, -0.02, 0.03, ...],  // 必需：收益率序列
        "benchmark_returns": [0.005, -0.01, 0.02, ...],  // 可选：基准收益率
        "risk_free": 0.03  // 可选：年化无风险利率（默认3%）
    }

    响应:
    {
        "success": true,
        "metrics": {
            "sharpe_ratio": 1.52,
            "sortino_ratio": 1.89,
            "calmar_ratio": 0.85,
            "max_drawdown": -0.18,
            "annual_return": 0.25,
            "annual_volatility": 0.16,
            "var_95": -0.032,
            "cvar_95": -0.045,
            "cumulative_return": 0.28,
            "alpha": 0.05,  // 如果提供了benchmark_returns
            "beta": 1.12,
            "information_ratio": 0.65
        }
    }
    """
    try:
        from application.services.risk_metrics_service import RiskMetricsService

        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': '请求体不能为空'
            }), 400

        returns = data.get('returns')
        if not returns:
            return jsonify({
                'success': False,
                'error': '缺少必需参数: returns'
            }), 400

        if not isinstance(returns, list) or len(returns) == 0:
            return jsonify({
                'success': False,
                'error': 'returns必须是非空列表'
            }), 400

        benchmark_returns = data.get('benchmark_returns')
        risk_free = data.get('risk_free', 0.03)

        if benchmark_returns is not None:
            if not isinstance(benchmark_returns, list):
                return jsonify({
                    'success': False,
                    'error': 'benchmark_returns必须是列表'
                }), 400

            if len(benchmark_returns) != len(returns):
                return jsonify({
                    'success': False,
                    'error': 'benchmark_returns长度必须与returns相同'
                }), 400

        # 计算指标
        service = RiskMetricsService(risk_free=risk_free)
        metrics = service.calculate_all_metrics(
            returns=returns,
            benchmark_returns=benchmark_returns
        )

        return jsonify({
            'success': True,
            'metrics': sanitize_for_json(metrics)
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': f'计算风险指标失败: {str(e)}'
        }), 500


@risk_bp.route('/api/risk/sharpe', methods=['POST'])
def calculate_sharpe_only():
    """
    单独计算夏普比率

    POST /api/risk/sharpe

    请求体:
    {
        "returns": [0.01, -0.02, 0.03, ...],
        "risk_free": 0.03  // 可选
    }
    """
    try:
        from application.services.risk_metrics_service import RiskMetricsService

        data = request.get_json()
        if not data or not data.get('returns'):
            return jsonify({
                'success': False,
                'error': '缺少必需参数: returns'
            }), 400

        returns = data.get('returns')
        risk_free = data.get('risk_free', 0.03)

        service = RiskMetricsService(risk_free=risk_free)
        sharpe = service.calculate_sharpe_ratio(returns)

        return jsonify({
            'success': True,
            'sharpe_ratio': float(sharpe)
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'计算夏普比率失败: {str(e)}'
        }), 500


@risk_bp.route('/api/risk/alpha-beta', methods=['POST'])
def calculate_alpha_beta_only():
    """
    计算Alpha和Beta

    POST /api/risk/alpha-beta

    请求体:
    {
        "returns": [0.01, -0.02, 0.03, ...],
        "benchmark_returns": [0.005, -0.01, 0.02, ...],
        "risk_free": 0.03  // 可选
    }
    """
    try:
        from application.services.risk_metrics_service import RiskMetricsService

        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': '请求体不能为空'
            }), 400

        returns = data.get('returns')
        benchmark_returns = data.get('benchmark_returns')

        if not returns or not benchmark_returns:
            return jsonify({
                'success': False,
                'error': '缺少必需参数: returns 和 benchmark_returns'
            }), 400

        if len(returns) != len(benchmark_returns):
            return jsonify({
                'success': False,
                'error': 'returns和benchmark_returns长度必须相同'
            }), 400

        risk_free = data.get('risk_free', 0.03)

        service = RiskMetricsService(risk_free=risk_free)
        alpha, beta = service.calculate_alpha_beta(returns, benchmark_returns)

        return jsonify({
            'success': True,
            'alpha': float(alpha),
            'beta': float(beta)
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'计算Alpha/Beta失败: {str(e)}'
        }), 500
