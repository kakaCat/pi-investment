"""
indicators routes.
"""
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
import re
import uuid
import logging
import math
import pandas as pd

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
from adapters.shared.response_helpers import normalize_indicator_fields
from adapters.outbound.repositories import KlineORMRepository

logger = logging.getLogger(__name__)

indicators_bp = Blueprint('indicators', __name__)


def is_active_indicator(indicator):
    """Treat missing is_active as active for legacy records."""
    return indicator.get('is_active', True) is not False

@indicators_bp.route('/api/indicators/list', methods=['GET'])
@handle_api_error
def get_indicators_list():
    """获取指标列表

    Query params:
        page: 页码 (默认1)
        pageSize: 每页数量 (默认20)
        type: 过滤类型 'my' (用户自定义) | 'system' (系统内置), 不传返回全部
        author: 按作者过滤
        category: 按分类过滤
    """
    page = request.args.get('page', 1, type=int)
    page_size = request.args.get('pageSize', 20, type=int)
    filter_type = request.args.get('type')
    author = request.args.get('author')
    category = request.args.get('category')

    indicators = strategy_service.list_strategies(code_type='indicator', active_only=True)
    indicators = [i for i in indicators if is_active_indicator(i)]

    if filter_type == 'my':
        indicators = [i for i in indicators if i.get('strategy_type') == 'custom']
    elif filter_type == 'system':
        indicators = [i for i in indicators if i.get('strategy_type') != 'custom']
    if author:
        indicators = [i for i in indicators if i.get('author', '') == author]
    if category:
        indicators = [i for i in indicators if i.get('category', '') == category]

    total = len(indicators)
    offset = (page - 1) * page_size
    indicators_page = indicators[offset:offset + page_size]

    indicators_page = normalize_indicator_fields(indicators_page)

    return api_response({
        'total': total,
        'page': page,
        'page_size': page_size,
        'items': indicators_page
    })


@indicators_bp.route('/api/indicators/detail/<int:indicator_id>', methods=['GET'])
@handle_api_error
def get_indicator_detail(indicator_id):
    """获取指标详情"""
    indicator = strategy_service.get_strategy(indicator_id)

    if not indicator:
        return jsonify({'success': False, 'error': '指标不存在'}), 404

    if indicator.get('code_type') != 'indicator':
        return jsonify({'success': False, 'error': '该策略不是指标类型'}), 400

    indicator = normalize_indicator_fields([indicator])[0]

    return api_response(indicator)


@indicators_bp.route('/api/indicators/create', methods=['POST'])
@handle_api_error
def create_indicator():
    """创建指标"""
    data = request.get_json() or {}
    indicator_data = convert_keys_to_snake(data)

    if 'name' not in indicator_data:
        return jsonify({'success': False, 'error': '缺少name参数'}), 400
    if 'code' not in indicator_data:
        return jsonify({'success': False, 'error': '缺少code参数'}), 400

    desired_name = indicator_data['name']
    final_name = desired_name
    suffix = 2
    while strategy_service.strategy_repo.get_by_name(final_name):
        final_name = f"{desired_name} ({suffix})"
        suffix += 1

    result = strategy_service.create_strategy(
        name=final_name,
        code=indicator_data['code'],
        code_type='indicator',
        params=indicator_data.get('params'),
        description=indicator_data.get('description', ''),
        category=indicator_data.get('category', 'custom'),
        is_public=indicator_data.get('is_public', False)
    )

    return api_response(result, message='指标创建成功')


@indicators_bp.route('/api/indicators/update/<int:indicator_id>', methods=['POST'])
@handle_api_error
def update_indicator(indicator_id):
    """更新指标"""
    data = request.get_json() or {}
    indicator_data = convert_keys_to_snake(data)

    indicator = strategy_service.get_strategy(indicator_id)
    if not indicator:
        return jsonify({'success': False, 'error': '指标不存在'}), 404

    if indicator.get('code_type') != 'indicator':
        return jsonify({'success': False, 'error': '该策略不是指标类型'}), 400

    updated = strategy_service.update_strategy(
        strategy_id=indicator_id,
        code=indicator_data.get('code'),
        params=indicator_data.get('params'),
        name=indicator_data.get('name'),
        description=indicator_data.get('description'),
        is_public=indicator_data.get('is_public'),
        category=indicator_data.get('category'),
        is_active=indicator_data.get('is_active'),
        notebook=indicator_data.get('notebook'),
        strategy_profile=indicator_data.get('strategy_profile')
    )

    return api_response(updated, message='指标更新成功')


@indicators_bp.route('/api/indicators/delete/<int:indicator_id>', methods=['POST'])
@handle_api_error
def delete_indicator(indicator_id):
    """删除指标"""
    indicator = strategy_service.get_strategy(indicator_id)
    if not indicator:
        return jsonify({'success': False, 'error': '指标不存在'}), 404

    if indicator.get('code_type') != 'indicator':
        return jsonify({'success': False, 'error': '该策略不是指标类型'}), 400

    success = strategy_service.delete_strategy(indicator_id)

    if not success:
        return jsonify({'success': False, 'error': '指标删除失败'}), 500

    return api_response({'indicator_id': indicator_id}, message='指标删除成功')


@indicators_bp.route('/api/indicators/run/<int:indicator_id>', methods=['POST'])
@handle_api_error
def run_indicator(indicator_id):
    """运行指标"""
    data = request.get_json() or {}
    indicator_data = convert_keys_to_snake(data)

    symbol = indicator_data.get('symbol')
    if not symbol:
        return jsonify({'success': False, 'error': '缺少symbol参数'}), 400

    indicator = strategy_service.get_strategy(indicator_id)
    if not indicator:
        return jsonify({'success': False, 'error': '指标不存在'}), 404

    if indicator.get('code_type') != 'indicator':
        return jsonify({'success': False, 'error': '该策略不是指标类型'}), 400

    limit = int(indicator_data.get('limit', 100))
    chart_limit = indicator_data.get('chart_limit')
    chart_limit = int(chart_limit) if chart_limit is not None else None
    result = strategy_service.run_strategy(
        strategy_id=indicator_id,
        symbol=symbol,
        limit=limit,
        chart_limit=chart_limit,
        period=indicator_data.get('period')
    )

    return api_response(result, message='指标运行成功')


@indicators_bp.route('/api/indicators/backtest', methods=['POST'])
@handle_api_error
def backtest_indicator():
    """回测指标"""
    data = request.get_json() or {}
    indicator_data = convert_keys_to_snake(data)

    required_fields = ['indicator_id', 'symbol', 'start_date', 'end_date']
    for field in required_fields:
        if field not in indicator_data:
            return jsonify({'success': False, 'error': f'缺少必需参数: {field}'}), 400

    indicator_id = indicator_data['indicator_id']
    try:
        indicator_id = int(indicator_id)
    except (ValueError, TypeError):
        return jsonify({'success': False, 'error': f'indicator_id 必须为整数, 当前值: {indicator_id}'}), 400

    indicator = strategy_service.get_strategy(indicator_id)
    if not indicator:
        return jsonify({'success': False, 'error': '指标不存在'}), 404

    if indicator.get('code_type') != 'indicator':
        return jsonify({'success': False, 'error': '该策略不是指标类型'}), 400

    result = strategy_service.backtest_strategy(
        strategy_id=indicator_id,
        symbol=indicator_data['symbol'],
        start_date=indicator_data['start_date'],
        end_date=indicator_data['end_date'],
        initial_cash=indicator_data.get('initial_cash', 1000000),
        period=indicator_data.get('period')  # 支持分钟级回测：None=日线, '5min'/'15min'/'30min'/'60min'
    )

    # 新增：计算摘要指标
    from datetime import datetime
    equity_curve = result.get('equity_curve', [])
    trades = result.get('trades', [])

    # 验证日期格式
    try:
        start_date = datetime.strptime(indicator_data['start_date'], '%Y-%m-%d')
        end_date = datetime.strptime(indicator_data['end_date'], '%Y-%m-%d')
    except ValueError as e:
        return jsonify({'success': False, 'error': f'日期格式无效，必须为 YYYY-MM-DD: {str(e)}'}), 400

    summary = calculate_backtest_summary(equity_curve, trades, start_date, end_date)
    result['summary'] = summary

    return api_response(result, message='指标回测完成')


@indicators_bp.route('/api/indicators/publish/<int:indicator_id>', methods=['POST'])
@handle_api_error
def publish_indicator(indicator_id):
    """发布指标到社区"""
    indicator = strategy_service.get_strategy(indicator_id)
    if not indicator:
        return jsonify({'success': False, 'error': '指标不存在'}), 404

    if indicator.get('code_type') != 'indicator':
        return jsonify({'success': False, 'error': '该策略不是指标类型'}), 400

    updated = strategy_service.update_strategy(
        strategy_id=indicator_id,
        is_public=True
    )

    return api_response({'id': indicator_id, 'published': True}, message='指标发布成功')


@indicators_bp.route('/api/indicators/favorite/<int:indicator_id>', methods=['POST'])
@handle_api_error
def favorite_indicator(indicator_id):
    """收藏指标"""
    indicator = strategy_service.get_strategy(indicator_id)
    if not indicator:
        return jsonify({'success': False, 'error': '指标不存在'}), 404

    if indicator.get('code_type') != 'indicator':
        return jsonify({'success': False, 'error': '该策略不是指标类型'}), 400

    current_count = indicator.get('favorite_count', 0) or 0
    updated = strategy_service.update_strategy(
        strategy_id=indicator_id,
        favorite_count=current_count + 1
    )

    return api_response({'id': indicator_id, 'favorite': True, 'favoriteCount': current_count + 1}, message='收藏成功')


@indicators_bp.route('/api/indicators/unfavorite/<int:indicator_id>', methods=['POST'])
@handle_api_error
def unfavorite_indicator(indicator_id):
    """取消收藏指标"""
    indicator = strategy_service.get_strategy(indicator_id)
    if not indicator:
        return jsonify({'success': False, 'error': '指标不存在'}), 404

    if indicator.get('code_type') != 'indicator':
        return jsonify({'success': False, 'error': '该策略不是指标类型'}), 400

    current_count = indicator.get('favorite_count', 0) or 0
    new_count = max(0, current_count - 1)
    updated = strategy_service.update_strategy(
        strategy_id=indicator_id,
        favorite_count=new_count
    )

    return api_response({'id': indicator_id, 'favorite': False, 'favoriteCount': new_count}, message='取消收藏成功')


def calculate_backtest_summary(equity_curve, trades, start_date, end_date):
    """计算回测摘要指标

    Args:
        equity_curve: list of dict, 每个元素包含 {'date': str, 'equity': float}
        trades: list of dict, 每个元素包含 {'date': str, 'action': str, 'pnl': float}
        start_date: datetime 对象
        end_date: datetime 对象

    Returns:
        dict 包含所有摘要指标，如果数据不足返回 {}
    """
    # 修复问题3：只检查权益曲线，允许无交易但有权益曲线的情况
    if not equity_curve:
        return {}

    # 修复问题2：添加 initial_equity 除零检查
    initial_equity = equity_curve[0]['equity']
    if initial_equity <= 0:
        return {}

    final_equity = equity_curve[-1]['equity']
    total_return = (final_equity - initial_equity) / initial_equity

    # 计算年化收益率
    days = (end_date - start_date).days
    years = days / 365.0
    if years > 0:
        annual_return = (1 + total_return) ** (1 / years) - 1
    else:
        annual_return = 0

    # 计算最大回撤
    max_drawdown = 0
    peak = equity_curve[0]['equity']
    for point in equity_curve:
        equity = point['equity']
        if equity > peak:
            peak = equity
        drawdown = (equity - peak) / peak
        if drawdown < max_drawdown:
            max_drawdown = drawdown

    # 计算日收益率序列
    returns = []
    for i in range(1, len(equity_curve)):
        prev_equity = equity_curve[i - 1]['equity']
        curr_equity = equity_curve[i]['equity']
        if prev_equity > 0:
            ret = (curr_equity - prev_equity) / prev_equity
            returns.append(ret)

    # 修复问题1：从日收益率序列一致计算夏普比率
    if len(returns) > 1:
        avg_return = sum(returns) / len(returns)
        variance = sum((r - avg_return) ** 2 for r in returns) / (len(returns) - 1)
        std_return = math.sqrt(variance)
        if std_return > 0:
            # 假设无风险利率 3%，转换为日收益率
            risk_free_rate = 0.03
            daily_risk_free = risk_free_rate / 252
            # 夏普比率 = (平均日收益率 - 无风险日收益率) / 日收益率标准差 * sqrt(252)
            sharpe_ratio = (avg_return - daily_risk_free) / std_return * math.sqrt(252)
        else:
            sharpe_ratio = 0
    else:
        sharpe_ratio = 0

    # 计算交易统计（如果没有交易，这些指标为0或空）
    if trades:
        total_trades = len(trades)
        winning_trades = sum(1 for t in trades if t.get('pnl', 0) > 0)
        losing_trades = sum(1 for t in trades if t.get('pnl', 0) < 0)

        win_rate = winning_trades / total_trades if total_trades > 0 else 0

        # 计算平均盈利和亏损
        wins = [t['pnl'] for t in trades if t.get('pnl', 0) > 0]
        losses = [t['pnl'] for t in trades if t.get('pnl', 0) < 0]

        avg_win = sum(wins) / len(wins) if wins else 0
        avg_loss = sum(losses) / len(losses) if losses else 0

        # 计算盈亏比
        total_win = sum(wins) if wins else 0
        total_loss = abs(sum(losses)) if losses else 0

        if total_loss > 0:
            profit_factor = total_win / total_loss
        elif total_win > 0:
            profit_factor = float('inf')
        else:
            profit_factor = 0
    else:
        # 没有交易时，交易相关指标为0
        total_trades = 0
        winning_trades = 0
        losing_trades = 0
        win_rate = 0
        avg_win = 0
        avg_loss = 0
        profit_factor = 0

    return {
        'total_return': round(total_return, 4),
        'annual_return': round(annual_return, 4),
        'max_drawdown': round(max_drawdown, 4),
        'sharpe_ratio': round(sharpe_ratio, 4),
        'win_rate': round(win_rate, 4),
        'total_trades': total_trades,
        'winning_trades': winning_trades,
        'losing_trades': losing_trades,
        'avg_win': round(avg_win, 2),
        'avg_loss': round(avg_loss, 2),
        'profit_factor': round(profit_factor, 4) if profit_factor != float('inf') else float('inf')
    }


def safe_calculate_return(equity_curve):
    """安全计算收益率

    Args:
        equity_curve: list of dict, 每个元素包含 {'date': str, 'equity': float}

    Returns:
        float: 收益率，如果数据不足或初始权益为0则返回0.0
    """
    if not equity_curve or len(equity_curve) < 2:
        return 0.0

    initial = equity_curve[0]['equity']
    if initial == 0:
        return 0.0

    final = equity_curve[-1]['equity']
    return (final - initial) / initial


@indicators_bp.route('/api/indicators/compare', methods=['POST'])
@handle_api_error
def compare_indicators():
    """对比两个指标策略"""
    data = request.get_json() or {}
    indicator_data = convert_keys_to_snake(data)

    # 验证参数
    required_fields = ['indicator_id_a', 'indicator_id_b', 'symbol', 'start_date', 'end_date']
    for field in required_fields:
        if field not in indicator_data:
            return jsonify({'success': False, 'error': f'缺少必需参数: {field}'}), 400

    # 安全的类型转换
    try:
        indicator_id_a = int(indicator_data['indicator_id_a'])
        indicator_id_b = int(indicator_data['indicator_id_b'])
    except (ValueError, TypeError):
        return jsonify({'success': False, 'error': '指标ID必须为整数'}), 400

    symbol = indicator_data['symbol']
    start_date = indicator_data['start_date']
    end_date = indicator_data['end_date']
    initial_cash = indicator_data.get('initial_cash', 1000000)

    # 验证指标存在
    indicator_a = strategy_service.get_strategy(indicator_id_a)
    indicator_b = strategy_service.get_strategy(indicator_id_b)

    if not indicator_a:
        return jsonify({'success': False, 'error': f'指标A (ID={indicator_id_a}) 不存在'}), 404
    if not indicator_b:
        return jsonify({'success': False, 'error': f'指标B (ID={indicator_id_b}) 不存在'}), 404

    if indicator_a.get('code_type') != 'indicator':
        return jsonify({'success': False, 'error': '策略A不是指标类型'}), 400
    if indicator_b.get('code_type') != 'indicator':
        return jsonify({'success': False, 'error': '策略B不是指标类型'}), 400

    # 回测两个策略
    result_a = strategy_service.backtest_strategy(
        strategy_id=indicator_id_a,
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        initial_cash=initial_cash
    )

    result_b = strategy_service.backtest_strategy(
        strategy_id=indicator_id_b,
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        initial_cash=initial_cash
    )

    # 对比交易
    trades_a = result_a.get('trades', [])
    trades_b = result_b.get('trades', [])

    # 找出A有买入但B没有的交易（B过滤掉的）
    buy_dates_a = set(t['date'] for t in trades_a if t.get('action') == 'buy')
    buy_dates_b = set(t['date'] for t in trades_b if t.get('action') == 'buy')
    filtered_dates = buy_dates_a - buy_dates_b

    filtered_trades = []
    for trade in trades_a:
        if trade['date'] in filtered_dates and trade.get('action') == 'buy':
            filtered_trades.append({
                'date': trade['date'],
                'would_buy_price': trade.get('price'),
                'signal_a': 'buy',
                'signal_b': 'hold',
                'reason': 'filtered by strategy B'
            })

    # 计算差异指标
    equity_a = result_a.get('equity_curve', [])
    equity_b = result_b.get('equity_curve', [])

    total_return_a = safe_calculate_return(equity_a)
    total_return_b = safe_calculate_return(equity_b)

    comparison = {
        'return_diff': round(total_return_b - total_return_a, 4),
        'trades_diff': len(trades_b) - len(trades_a),
        'filtered_by_b_only': len(filtered_trades),
        'filtered_trades': filtered_trades
    }

    return api_response({
        'strategy_a': {
            'indicator_id': indicator_id_a,
            'name': indicator_a.get('name'),
            'total_return': round(total_return_a, 4),
            'total_trades': len(trades_a),
            'equity_curve': equity_a,
            'trades': trades_a
        },
        'strategy_b': {
            'indicator_id': indicator_id_b,
            'name': indicator_b.get('name'),
            'total_return': round(total_return_b, 4),
            'total_trades': len(trades_b),
            'equity_curve': equity_b,
            'trades': trades_b
        },
        'comparison': comparison
    }, message='策略对比完成')


@indicators_bp.route('/api/indicators/sandbox-columns', methods=['GET'])
@handle_api_error
def get_sandbox_columns():
    """获取沙箱列可用性"""
    symbol = request.args.get('symbol')

    if not symbol:
        return jsonify({'success': False, 'error': '缺少symbol参数'}), 400

    kline_repo = KlineORMRepository()

    # 获取K线数据（带财务和技术指标）
    klines = kline_repo.get_latest(symbol, limit=1000)

    if not klines:
        return jsonify({'success': False, 'error': f'股票 {symbol} 无数据'}), 404

    # 转为DataFrame
    df = pd.DataFrame(klines)

    # 定义需要检查的列
    columns_to_check = [
        # 财务指标（季度）
        'roe_q', 'gross_margin_q', 'net_profit_margin_q', 'debt_ratio_q',
        'revenue_growth_q', 'ocf_to_profit_q', 'current_ratio_q', 'roa_q', 'operating_margin_q',
        # 财务指标（年度）
        'roe_y', 'gross_margin_y', 'net_profit_margin_y', 'debt_ratio_y',
        'revenue_growth_y', 'ocf_to_profit_y', 'current_ratio_y', 'roa_y', 'operating_margin_y',
        # 技术指标
        'rsi', 'macd', 'macd_signal', 'macd_hist',
        'atr', 'bollinger_upper', 'bollinger_middle', 'bollinger_lower',
        'ma5', 'ma10', 'ma20', 'ma60'
    ]

    # 统计每列的可用性
    columns_info = {}
    for col in columns_to_check:
        if col in df.columns:
            non_null_count = df[col].notna().sum()
            coverage = non_null_count / len(df) if len(df) > 0 else 0

            # 获取最新非空值
            latest_row = df[df[col].notna()].tail(1)
            if not latest_row.empty:
                latest_value = float(latest_row[col].iloc[0])
                latest_date = latest_row['trade_date'].iloc[0] if 'trade_date' in latest_row.columns else None
            else:
                latest_value = None
                latest_date = None

            columns_info[col] = {
                'coverage': round(coverage, 4),
                'latest_value': round(latest_value, 4) if latest_value is not None else None,
                'latest_date': str(latest_date) if latest_date else None
            }

    # 日期范围
    date_range = {
        'start': str(df['trade_date'].min()) if 'trade_date' in df.columns else None,
        'end': str(df['trade_date'].max()) if 'trade_date' in df.columns else None
    }

    return api_response({
        'symbol': symbol,
        'columns': columns_info,
        'total_rows': len(df),
        'date_range': date_range
    })
