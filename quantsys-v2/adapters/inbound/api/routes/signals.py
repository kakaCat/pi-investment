"""
signals routes.
"""
import json
import sys
import logging
from datetime import datetime, timedelta
from pathlib import Path
import re
import uuid

from flask import Blueprint, jsonify, request

logger = logging.getLogger(__name__)

import math

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
    sector_rotation_service,
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

signals_bp = Blueprint('signals', __name__)

@signals_bp.route('/api/signals', methods=['GET'])
@handle_api_error
def get_signals():
    """获取信号/机会列表，支持筛选和排序"""
    try:
        params = get_query_params_snake_case()

        days = int(params['days']) if 'days' in params else None
        date_filter = params.get('date')
        limit = min(int(params.get('limit', 200)), 500)
        page = max(1, int(params.get('page', 1)))
        page_size = min(int(params.get('page_size', 20)), 100)
        signal_type = params.get('signal_type')
        min_confidence = float(params.get('min_confidence', 0.0))

        min_score = float(params.get('min_score', 0.0))
        max_risk_level = params.get('max_risk_level')
        industries = params.get('industries')  # 逗号分隔或 JSON 数组
        sort_by = params.get('sort_by', 'created_at')
        sort_order = params.get('sort_order', 'desc')

        if isinstance(industries, str) and industries:
            industries = [i.strip() for i in industries.split(',') if i.strip()]
        else:
            industries = None

        if date_filter == 'today':
            from datetime import datetime
            today = datetime.now().date()
            signals = ds.signal.get_signals_by_date_range(
                start_date=today.strftime('%Y-%m-%d'),
                end_date=today.strftime('%Y-%m-%d')
            )
        elif date_filter:
            signals = ds.signal.get_signals_by_date(date_filter, signal_type=signal_type)
        elif days:
            signals = ds.signal.get_latest_signals(days=days)
        else:
            signals = ds.signal.get_latest_signals(limit=limit)

        if min_confidence > 0:
            signals = [s for s in signals if (s.get('confidence') or 0) >= min_confidence]

        opportunities = [signal_to_opportunity(s) for s in signals]

        if min_score > 0:
            opportunities = [o for o in opportunities if o['score'] >= min_score]

        if max_risk_level:
            opportunities = [o for o in opportunities if o['riskLevel'] == max_risk_level]

        if industries:
            filtered = []
            for o in opportunities:
                stock = ds.stock.get_by_symbol(o['symbol'])
                if stock and stock.get('industry', '') in industries:
                    filtered.append(o)
            opportunities = filtered

        allowed_sort_fields = {
            'score', 'confidence', 'technicalScore', 'fundamentalScore',
            'sentimentScore', 'expectedReturn', 'createdAt', 'symbol',
            'riskLevel',
        }
        if sort_by in allowed_sort_fields:
            reverse = sort_order == 'desc'
            opportunities.sort(key=lambda o: o.get(sort_by, 0) or 0, reverse=reverse)
        else:
            opportunities.sort(key=lambda o: o.get('score', 0), reverse=True)

        total = len(opportunities)
        offset = (page - 1) * page_size
        paginated = opportunities[offset:offset + page_size]
        total_pages = math.ceil(total / page_size) if page_size > 0 else 0

        return api_response({
            'items': sanitize_for_json(paginated),
            'total': total,
            'page': page,
            'pageSize': page_size,
            'totalPages': total_pages
        })

    except Exception as e:
        logger.error(f"Failed to get signals: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@signals_bp.route('/api/signals/history', methods=['GET'])
def get_signals_history():
    """获取信号历史"""
    try:
        from datetime import datetime, timedelta
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')

        signals = ds.signal.get_latest_signals(limit=50)
        stats = ds.signal.get_signal_stats(start_date, end_date)

        return jsonify({
            'success': True,
            'data': sanitize_for_json(signals),
            'stats': sanitize_for_json(stats)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@signals_bp.route('/api/signals/scan', methods=['POST'])
def scan_signals():
    """机会雷达扫描 - 实时计算模式

    接收前端 OpportunityFilters:
      { minScore, maxRiskLevel, industries, technical, fundamental, stocks?, sectorFilter?, strategyId? }
    """
    data = request.get_json() or {}
    snake_data = convert_keys_to_snake(data)

    strategy_id = snake_data.get('strategy_id')
    stocks_param = snake_data.get('stocks', snake_data.get('symbols', []))
    min_score = float(snake_data.get('min_score', 0.0))
    max_risk_level = snake_data.get('max_risk_level', 'high')
    industries = snake_data.get('industries', [])
    technical = snake_data.get('technical', [])
    fundamental = snake_data.get('fundamental', [])
    sector_filter = snake_data.get('sector_filter', {})
    weights = snake_data.get('weights')  # 动态权重参数
    no_cache = bool(snake_data.get('no_cache', False))  # 跳过评分缓存强制重算

    # 分页参数（agent 工具传 limit，兼容映射到 page_size）
    page = max(1, int(snake_data.get('page', 1)))
    page_size = min(int(snake_data.get('page_size', snake_data.get('limit', 20))), 100)

    try:
        if strategy_id not in (None, ''):
            try:
                strategy_id = int(strategy_id)
            except (TypeError, ValueError):
                return jsonify({'success': False, 'error': f'无效的 strategy_id: {strategy_id}'}), 400

        # 处理行业筛选
        selected_sectors_info = None
        if sector_filter.get('enabled', False):
            top_n = sector_filter.get('top_n', 3)
            min_sector_score = sector_filter.get('min_sector_score', 0.0)
            exclude_sectors = sector_filter.get('exclude_sectors', [])
            market = sector_filter.get('market', 'A')

            logger.info(f"行业筛选启用: topN={top_n}, minScore={min_sector_score}, market={market}")

            # 获取强势行业
            top_sector_names, sector_ranking = sector_rotation_service.filter_top_sectors(
                top_n=top_n,
                min_score=min_sector_score,
                exclude_sectors=exclude_sectors,
                market=market
            )

            if top_sector_names:
                logger.info(f"选中强势行业: {top_sector_names}")
                # 覆盖 industries 参数
                industries = top_sector_names
                selected_sectors_info = {
                    'enabled': True,
                    'selected_sectors': sector_ranking,
                    'total_sectors': len(sector_ranking)
                }
            else:
                logger.warning("未找到符合条件的强势行业")
                selected_sectors_info = {
                    'enabled': True,
                    'selected_sectors': [],
                    'total_sectors': 0
                }

        # 确定扫描范围
        if stocks_param:
            symbols = list(stocks_param) if isinstance(stocks_param, list) else [stocks_param]
        elif industries:
            # 从行业获取股票
            symbols = ds.stock.get_stocks_by_industries(industries)
            logger.info(f"从行业 {industries} 获取 {len(symbols)} 只股票")
        else:
            try:
                watchlist = _read_watchlist()
                watchlist_symbols = [item['symbol'] for item in watchlist.get('items', [])]
            except Exception:
                watchlist_symbols = []

            hot_stocks = stock_pool_service.get_hot_stocks()
            symbols = list(set(watchlist_symbols + hot_stocks))

        logger.info(f"扫描开始: 股票数={len(symbols)}, 技术条件={technical}, 基本面条件={fundamental}")

        if strategy_id is not None:
            opportunities = _scan_strategy_opportunities(strategy_id, symbols)
        else:
            opportunities = scoring_service.score_stocks(
                symbols=symbols,
                filters={
                    'technical': technical,
                    'fundamental': fundamental
                },
                weights=weights,
                no_cache=no_cache
            )

        # 附加行业信息
        if selected_sectors_info:
            sector_score_map = {s['name']: s for s in selected_sectors_info['selected_sectors']}
            for opp in opportunities:
                stock = ds.stock.get_by_symbol(opp['symbol'], ['industry'])
                if stock:
                    industry = stock.get('industry', '')
                    opp['industry'] = industry
                    if industry in sector_score_map:
                        opp['sector_score'] = sector_score_map[industry]['composite_score']
                        opp['sector_rank'] = sector_score_map[industry]['rank']

        risk_level_map = {'low': 1, 'medium': 2, 'high': 3}
        max_risk = risk_level_map.get(max_risk_level, 3)
        filtered = [
            opp for opp in opportunities
            if risk_level_map.get(opp['risk_level'], 3) <= max_risk
        ]

        if min_score > 0:
            filtered = [o for o in filtered if o['score'] >= min_score]

        sorted_opps = sorted(filtered, key=lambda x: x['score'], reverse=True)

        # 分页处理
        total = len(sorted_opps)
        offset = (page - 1) * page_size
        paginated = sorted_opps[offset:offset + page_size]
        total_pages = math.ceil(total / page_size) if page_size > 0 else 0

        logger.info(f"扫描完成: 扫描{len(symbols)}只, 筛选后{total}只, 返回第{page}页({len(paginated)}只)")

        # 诊断信息：让调用方能区分「没有机会」和「没有数据」
        # （2026-07-28 前：池为空/K线不足时静默返回 total=0，agent 无法察觉数据断供）
        scoring_diag = getattr(scoring_service, 'last_diagnostics', None) or {}
        diagnostics = {
            'universe_size': len(symbols),
            'pool_source': (
                'explicit' if stocks_param else
                'industries' if industries else
                f"watchlist+hot_pool({getattr(stock_pool_service, '_hot_pool_source', 'unknown')})"
            ),
            'scored': scoring_diag.get('scored', len(opportunities)),
            'skipped_insufficient_klines': scoring_diag.get('skipped_insufficient_klines', 0),
            'skipped_condition_filter': scoring_diag.get('skipped_condition_filter', 0),
            # 动态评分诊断（2026-07-30）：降级计数 + 数据自愈报告 + 耗时
            'scoring_degraded': scoring_diag.get('degraded', {}),
            'repair_report': scoring_diag.get('repair_report', {}),
            'elapsed_ms': scoring_diag.get('elapsed_ms'),
        }
        degraded = len(symbols) == 0 or (
            diagnostics['universe_size'] > 0
            and diagnostics['skipped_insufficient_klines'] >= diagnostics['universe_size'] * 0.9
        )
        if degraded:
            diagnostics['degraded_reason'] = (
                '扫描池为空（index_constituents 无数据且 watchlist 为空）'
                if len(symbols) == 0 else
                '绝大多数股票 K 线不足 30 条（K线更新任务异常，检查 daily_klines 新鲜度）'
            )

        result = {
            'success': True,
            'scan_mode': 'strategy' if strategy_id is not None else 'score',
            'opportunities': paginated,
            'total': total,
            'page': page,
            'page_size': page_size,
            'total_pages': total_pages,
            'scanned': len(symbols),
            'degraded': degraded,
            'diagnostics': diagnostics,
        }

        if strategy_id is not None:
            result['strategy_id'] = strategy_id

        if selected_sectors_info:
            result['sector_info'] = selected_sectors_info

        return jsonify(result)

    except Exception as e:
        logger.error(f"扫描失败: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


def _scan_strategy_opportunities(strategy_id: int, symbols: list) -> list:
    """Run a user strategy across symbols and adapt buy signals to opportunity rows."""
    opportunities = []

    for symbol in symbols:
        try:
            signal = strategy_service.generate_signal(strategy_id, symbol)
        except ValueError:
            raise
        except Exception as e:
            logger.warning(f"策略扫描失败: strategy_id={strategy_id}, symbol={symbol}, error={e}")
            continue

        if not signal or signal.get('signal_type') != 'buy':
            continue

        confidence = _safe_float(signal.get('confidence'), 0.0)
        score = round(confidence * 100)
        opportunities.append({
            'symbol': signal.get('symbol') or symbol,
            'name': signal.get('name') or _get_stock_name(symbol),
            'score': score,
            'technical_score': score,
            'fundamental_score': 0,
            'capital_score': 0,
            'confidence': round(confidence, 4),
            'risk_level': _risk_level_from_score(score),
            'signal_type': 'buy',
            'strategy_id': strategy_id,
            'strategy_name': signal.get('strategy_name', f'strategy_{strategy_id}'),
            'price': _safe_float(signal.get('price'), 0.0),
            'signal_date': signal.get('signal_date', ''),
            'timestamp': signal.get('created_at') or datetime.now().isoformat()
        })

    return opportunities


def _get_stock_name(symbol: str) -> str:
    stock = ds.stock.get_by_symbol(symbol, ['name'])
    return stock.get('name', symbol) if stock else symbol


def _risk_level_from_score(score: float) -> str:
    if score >= 70:
        return 'low'
    if score >= 50:
        return 'medium'
    return 'high'


@signals_bp.route('/api/signals/detail/<signal_id>', methods=['GET'])
@handle_api_error
def get_signal_detail(signal_id):
    """获取信号/机会详情（返回 Opportunity 格式，兼容 int 和 string id）"""
    try:
        signal_id = int(signal_id)
    except (ValueError, TypeError):
        return jsonify({'success': False, 'error': f'无效的信号ID: {signal_id}'}), 400

    signal = ds.signal.get_signal(signal_id)

    if not signal:
        return jsonify({'success': False, 'error': '信号不存在'}), 404

    return api_response(signal_to_opportunity(signal))


@signals_bp.route('/api/signals/<int:signal_id>', methods=['GET'])
@handle_api_error
def get_signal_by_id(signal_id):
    """获取信号详情（别名，兼容前端 /api/signals/{id}）"""
    return get_signal_detail(str(signal_id))


@signals_bp.route('/api/signals/approve/<int:signal_id>', methods=['POST'])
@handle_api_error
def approve_signal(signal_id):
    """批准信号"""
    signal = ds.signal.get_signal(signal_id)
    if not signal:
        return jsonify({'success': False, 'error': '信号不存在'}), 404

    ds.signal.update_signal(signal_id, {
        'status': 'approved',
        'updated_at': datetime.now()
    })

    updated_signal = ds.signal.get_signal(signal_id)
    return api_response(updated_signal, message='信号已批准')


@signals_bp.route('/api/signals/reject/<int:signal_id>', methods=['POST'])
@handle_api_error
def reject_signal(signal_id):
    """拒绝信号"""
    signal = ds.signal.get_signal(signal_id)
    if not signal:
        return jsonify({'success': False, 'error': '信号不存在'}), 404

    data = request.get_json() or {}
    reason = data.get('reason', '')

    update_data = {
        'status': 'rejected',
        'updated_at': datetime.now()
    }

    if reason:
        update_data['reject_reason'] = reason

    ds.signal.update_signal(signal_id, update_data)

    updated_signal = ds.signal.get_signal(signal_id)
    return api_response(updated_signal, message='信号已拒绝')


@signals_bp.route('/api/signals/mark-error/<int:signal_id>', methods=['POST'])
@handle_api_error
def mark_error_signal(signal_id):
    """标记错误信号"""
    signal = ds.signal.get_signal(signal_id)
    if not signal:
        return jsonify({'success': False, 'error': '信号不存在'}), 404

    data = convert_keys_to_snake(request.get_json() or {})
    error_desc = data.get('error_type') or data.get('error_description', '')

    update_data = {
        'status': 'error',
        'updated_at': datetime.now()
    }

    if error_desc:
        update_data['error_description'] = error_desc

    ds.signal.update_signal(signal_id, update_data)

    updated_signal = ds.signal.get_signal(signal_id)
    return api_response(updated_signal, message='信号已标记为错误')


@signals_bp.route('/api/signals/statistics', methods=['GET'])
@handle_api_error
def get_signals_statistics():
    """获取信号统计"""
    params = get_query_params_snake_case()

    start_date = params.get('start_date', '2024-01-01')
    end_date = params.get('end_date', '2026-12-31')

    from adapters.outbound.repositories import SignalORMRepository
    signal_repo = SignalORMRepository()

    cursor = signal_repo._get_cursor()

    status_query = """
        SELECT
            COUNT(*) as total,
            COUNT(CASE WHEN status = 'pending' THEN 1 END) as pending,
            COUNT(CASE WHEN status = 'approved' THEN 1 END) as approved,
            COUNT(CASE WHEN status = 'rejected' THEN 1 END) as rejected,
            COUNT(CASE WHEN status = 'error' THEN 1 END) as error,
            COUNT(CASE WHEN status = 'executed' THEN 1 END) as executed
        FROM quant.signals
        WHERE signal_date >= %s AND signal_date <= %s
    """
    cursor.execute(status_query, (start_date, end_date))
    status_result = cursor.fetchone()

    confidence_query = """
        SELECT AVG(confidence) as avg_confidence
        FROM quant.signals
        WHERE signal_date >= %s AND signal_date <= %s
        AND confidence IS NOT NULL
    """
    cursor.execute(confidence_query, (start_date, end_date))
    confidence_result = cursor.fetchone()
    avg_confidence = float(confidence_result['avg_confidence'] or 0.0) if isinstance(confidence_result, dict) else float(confidence_result[0] or 0.0)

    accuracy_query = """
        SELECT
            action,
            COUNT(*) as total,
            COUNT(CASE WHEN status = 'approved' THEN 1 END) as approved_count
        FROM quant.signals
        WHERE signal_date >= %s AND signal_date <= %s
        GROUP BY action
    """
    cursor.execute(accuracy_query, (start_date, end_date))
    accuracy_results = cursor.fetchall()

    buy_accuracy = 0.0
    sell_accuracy = 0.0
    for row in accuracy_results:
        if isinstance(row, dict):
            if row['total'] > 0 and row.get('approved_count', 0) > 0:
                accuracy = (row['approved_count'] / row['total']) * 100
        else:
            # Tuple format: (action, total, approved_count)
            if row[1] > 0 and row[2] > 0:
                accuracy = (row[2] / row[1]) * 100
            if row['action'] == 'buy':
                buy_accuracy = accuracy
            elif row['action'] == 'sell':
                sell_accuracy = accuracy

    cursor.close()

    if status_result:
        stats = {
            'total': status_result['total'],
            'pending': status_result['pending'],
            'approved': status_result['approved'],
            'rejected': status_result['rejected'],
            'error': status_result['error'],
            'executed': status_result['executed'],
            'avg_confidence': round(avg_confidence, 2),
            'buy_approved_rate': round(buy_accuracy, 2),
            'sell_approved_rate': round(sell_accuracy, 2)
        }
    else:
        stats = {
            'total': 0,
            'pending': 0,
            'approved': 0,
            'rejected': 0,
            'error': 0,
            'executed': 0,
            'avg_confidence': 0.0,
            'buy_approved_rate': 0.0,
            'sell_approved_rate': 0.0
        }

    return api_response(stats)

@signals_bp.route('/api/signals/execute', methods=['POST'])
@handle_api_error
def execute_signal():
    """
    执行策略信号，创建订单

    POST /api/signals/execute
    {
        "symbol": "600000.SH",
        "signal": {
            "action": "buy",
            "confidence": 0.85,
            "reason": "...",
            "risk_management": { ... }
        },
        "order_type": "limit"
    }
    """
    data = request.get_json()
    symbol = data.get('symbol')
    signal = data.get('signal')
    order_type = data.get('order_type', 'limit')

    if not symbol or not signal:
        return jsonify({'success': False, 'error': 'Missing symbol or signal'}), 400

    try:
        from application.services.order_service import create_order_from_signal

        result = create_order_from_signal(ds, signal, symbol, order_type)

        return jsonify({
            'success': True,
            **result
        })

    except Exception as e:
        logger.error(f"Failed to execute signal: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@signals_bp.route('/api/signals/backtest-signal', methods=['POST'])
@handle_api_error
def backtest_signal():
    """
    回测单个信号（不创建真实订单）

    POST /api/signals/backtest-signal
    {
        "symbol": "600000.SH",
        "signal": { ... },
        "account_balance": {
            "total_assets": 1000000,
            "cash": 500000
        }
    }
    """
    data = request.get_json()
    symbol = data.get('symbol')
    signal = data.get('signal')
    account_balance = data.get('account_balance', {
        'total_assets': 1000000,
        'cash': 500000
    })

    try:
        from application.services.signal_processor import SignalProcessor

        latest = ds.kline.get_latest_daily_kline(symbol)
        current_price = latest['close'] if latest else 0

        processor = SignalProcessor(ds)
        trade_params = processor.process_signal(
            signal, symbol, current_price, account_balance
        )

        # 计算风险指标
        position_value = trade_params['quantity'] * trade_params['price']
        risk_amount = abs(
            trade_params['quantity'] *
            (trade_params['price'] - trade_params['stop_loss_price'])
        ) if trade_params['stop_loss_price'] else 0

        trade_params['position_value'] = round(position_value, 2)
        trade_params['position_percent'] = round(
            position_value / account_balance['total_assets'], 4
        )
        trade_params['risk_amount'] = round(risk_amount, 2)
        trade_params['risk_percent'] = round(
            risk_amount / account_balance['total_assets'], 4
        )

        return jsonify({
            'success': True,
            'trade_params': trade_params
        })

    except Exception as e:
        logger.error(f"Failed to backtest signal: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@signals_bp.route('/api/agent/logs', methods=['GET'])
@handle_api_error
def get_agent_logs():
    """获取Agent操作日志列表"""
    from infrastructure.persistence.database.base_repository import BaseRepository

    params = get_query_params_snake_case()
    start_date = params.get('start_date')
    end_date = params.get('end_date')
    action = params.get('action')
    status = params.get('status')
    limit = min(int(params.get('limit', 20)), 100)
    page = max(1, int(params.get('page', 1)))
    page_size = min(int(params.get('page_size', 20)), 100)

    repo = BaseRepository()
    cursor = repo._get_cursor()

    try:
        conditions = []
        query_params = []

        if start_date:
            conditions.append('timestamp >= %s::date')
            query_params.append(start_date)
        if end_date:
            conditions.append('timestamp < (%s::date + interval \'1 day\')')
            query_params.append(end_date)
        if action:
            conditions.append('action_type = %s')
            query_params.append(action)
        if status:
            conditions.append('status = %s')
            query_params.append(status)

        where_clause = ' AND '.join(conditions) if conditions else 'TRUE'

        count_query = f'SELECT COUNT(*) FROM quant.agent_logs WHERE {where_clause}'
        cursor.execute(count_query, query_params)
        count_result = cursor.fetchone()
        total = count_result['count'] if isinstance(count_result, dict) else count_result[0]

        offset = (page - 1) * page_size
        data_query = f'''
            SELECT id, timestamp, action_type, symbol, details, result, status, duration_ms, created_at
            FROM quant.agent_logs
            WHERE {where_clause}
            ORDER BY timestamp DESC
            LIMIT %s OFFSET %s
        '''
        cursor.execute(data_query, query_params + [limit if not page else page_size, offset])
        rows = cursor.fetchall()

        items = []
        for row in rows:
            r = dict(row)
            details = r.get('details') or {}
            res = r.get('result') or {}
            items.append({
                'id': str(r['id']),
                'timestamp': r['timestamp'].isoformat() if hasattr(r['timestamp'], 'isoformat') else str(r['timestamp']),
                'action': f"{r['action_type']} {r['symbol']}",
                'description': str(details.get('reason', details.get('summary', res.get('summary', '')))),
                'status': 'success' if r['status'] == 'success' else ('failed' if r['status'] == 'failed' else 'pending'),
                'details': sanitize_for_json(details),
                'signal_id': str(res.get('signal_id', '')) if res.get('signal_id') else None,
            })

        total_pages = math.ceil(total / page_size) if page_size > 0 else 0

        return api_response({
            'items': items,
            'total': total,
            'page': page,
            'page_size': page_size,
            'total_pages': total_pages,
        })
    finally:
        cursor.close()
        repo.db.close()
