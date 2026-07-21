"""指标管理 API - FastAPI 版（从 Flask indicators.py 迁移，响应契约保持一致）

复用 strategy_service（StrategyCodeService）与 normalize_indicator_fields，
calculate_backtest_summary 原样复制。
"""
import math
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd
from fastapi import APIRouter, Query, Body
import structlog

from adapters.inbound.fastapi_app.shared import (
    api_response, error_response, handle_api_error, convert_keys_to_snake, strategy_service,
)
from adapters.inbound.api.utils.response import normalize_indicator_fields

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["Indicators - 指标管理"])


def is_active_indicator(indicator):
    return indicator.get('is_active', True) is not False


def calculate_backtest_summary(equity_curve, trades, start_date, end_date):
    """计算回测摘要指标（与 Flask indicators.py 一致）。"""
    if not equity_curve:
        return {}
    initial_equity = equity_curve[0]['equity']
    if initial_equity <= 0:
        return {}
    final_equity = equity_curve[-1]['equity']
    total_return = (final_equity - initial_equity) / initial_equity

    days = (end_date - start_date).days
    years = days / 365.0
    annual_return = (1 + total_return) ** (1 / years) - 1 if years > 0 else 0

    max_drawdown = 0
    peak = equity_curve[0]['equity']
    for point in equity_curve:
        equity = point['equity']
        if equity > peak:
            peak = equity
        drawdown = (equity - peak) / peak
        if drawdown < max_drawdown:
            max_drawdown = drawdown

    returns = []
    for i in range(1, len(equity_curve)):
        prev_equity = equity_curve[i - 1]['equity']
        curr_equity = equity_curve[i]['equity']
        if prev_equity > 0:
            returns.append((curr_equity - prev_equity) / prev_equity)
    if len(returns) > 1:
        avg_return = sum(returns) / len(returns)
        variance = sum((r - avg_return) ** 2 for r in returns) / (len(returns) - 1)
        std_return = math.sqrt(variance)
        if std_return > 0:
            daily_risk_free = 0.03 / 252
            sharpe_ratio = (avg_return - daily_risk_free) / std_return * math.sqrt(252)
        else:
            sharpe_ratio = 0
    else:
        sharpe_ratio = 0

    if trades:
        total_trades = len(trades)
        winning_trades = sum(1 for t in trades if t.get('pnl', 0) > 0)
        losing_trades = sum(1 for t in trades if t.get('pnl', 0) < 0)
        win_rate = winning_trades / total_trades if total_trades > 0 else 0
        wins = [t['pnl'] for t in trades if t.get('pnl', 0) > 0]
        losses = [t['pnl'] for t in trades if t.get('pnl', 0) < 0]
        avg_win = sum(wins) / len(wins) if wins else 0
        avg_loss = sum(losses) / len(losses) if losses else 0
        total_win = sum(wins) if wins else 0
        total_loss = abs(sum(losses)) if losses else 0
        if total_loss > 0:
            profit_factor = total_win / total_loss
        elif total_win > 0:
            profit_factor = float('inf')
        else:
            profit_factor = 0
    else:
        total_trades = winning_trades = losing_trades = 0
        win_rate = avg_win = avg_loss = 0
        profit_factor = 0

    return {
        'total_return': round(total_return, 4),
        'annual_return': round(annual_return, 4),
        'max_drawdown': round(max_drawdown, 4),
        'sharpe_ratio': round(sharpe_ratio, 2) if sharpe_ratio else 0,
        'total_trades': total_trades,
        'winning_trades': winning_trades,
        'losing_trades': losing_trades,
        'win_rate': round(win_rate, 4),
        'avg_win': round(avg_win, 2),
        'avg_loss': round(avg_loss, 2),
        'profit_factor': round(profit_factor, 2) if profit_factor != float('inf') else 'inf',
    }


@router.get('/api/indicators/list')
@handle_api_error
def get_indicators_list(page: int = Query(1), pageSize: int = Query(20),
                        type: Optional[str] = Query(None), author: Optional[str] = Query(None),
                        category: Optional[str] = Query(None)):
    indicators = strategy_service.list_strategies(code_type='indicator', active_only=True)
    indicators = [i for i in indicators if is_active_indicator(i)]
    if type == 'my':
        indicators = [i for i in indicators if i.get('strategy_type') == 'custom']
    elif type == 'system':
        indicators = [i for i in indicators if i.get('strategy_type') != 'custom']
    if author:
        indicators = [i for i in indicators if i.get('author', '') == author]
    if category:
        indicators = [i for i in indicators if i.get('category', '') == category]
    total = len(indicators)
    offset = (page - 1) * pageSize
    indicators_page = normalize_indicator_fields(indicators[offset:offset + pageSize])
    return api_response({'total': total, 'page': page, 'page_size': pageSize, 'items': indicators_page})


@router.get('/api/indicators/detail/{indicator_id}')
@handle_api_error
def get_indicator_detail(indicator_id: int):
    indicator = strategy_service.get_strategy(indicator_id)
    if not indicator:
        return error_response({'success': False, 'error': '指标不存在'}, 404)
    if indicator.get('code_type') != 'indicator':
        return error_response({'success': False, 'error': '该策略不是指标类型'}, 400)
    indicator = normalize_indicator_fields([indicator])[0]
    return api_response(indicator)


@router.post('/api/indicators/create')
@handle_api_error
def create_indicator(payload: Optional[Dict[str, Any]] = Body(None)):
    indicator_data = convert_keys_to_snake(payload or {})
    if 'name' not in indicator_data:
        return error_response({'success': False, 'error': '缺少name参数'}, 400)
    if 'code' not in indicator_data:
        return error_response({'success': False, 'error': '缺少code参数'}, 400)
    desired_name = indicator_data['name']
    final_name = desired_name
    suffix = 2
    while strategy_service.strategy_repo.get_by_name(final_name):
        final_name = f"{desired_name} ({suffix})"
        suffix += 1
    result = strategy_service.create_strategy(
        name=final_name, code=indicator_data['code'], code_type='indicator',
        params=indicator_data.get('params'), description=indicator_data.get('description', ''),
        category=indicator_data.get('category', 'custom'), is_public=indicator_data.get('is_public', False))
    return api_response(result, message='指标创建成功')


@router.post('/api/indicators/update/{indicator_id}')
@handle_api_error
def update_indicator(indicator_id: int, payload: Optional[Dict[str, Any]] = Body(None)):
    indicator_data = convert_keys_to_snake(payload or {})
    indicator = strategy_service.get_strategy(indicator_id)
    if not indicator:
        return error_response({'success': False, 'error': '指标不存在'}, 404)
    if indicator.get('code_type') != 'indicator':
        return error_response({'success': False, 'error': '该策略不是指标类型'}, 400)
    updated = strategy_service.update_strategy(
        strategy_id=indicator_id, code=indicator_data.get('code'), params=indicator_data.get('params'),
        name=indicator_data.get('name'), description=indicator_data.get('description'),
        is_public=indicator_data.get('is_public'), category=indicator_data.get('category'),
        is_active=indicator_data.get('is_active'), notebook=indicator_data.get('notebook'),
        strategy_profile=indicator_data.get('strategy_profile'))
    return api_response(updated, message='指标更新成功')


@router.post('/api/indicators/delete/{indicator_id}')
@handle_api_error
def delete_indicator(indicator_id: int):
    indicator = strategy_service.get_strategy(indicator_id)
    if not indicator:
        return error_response({'success': False, 'error': '指标不存在'}, 404)
    if indicator.get('code_type') != 'indicator':
        return error_response({'success': False, 'error': '该策略不是指标类型'}, 400)
    success = strategy_service.delete_strategy(indicator_id)
    if not success:
        return error_response({'success': False, 'error': '指标删除失败'}, 500)
    return api_response({'indicator_id': indicator_id}, message='指标删除成功')


@router.post('/api/indicators/run/{indicator_id}')
@handle_api_error
def run_indicator(indicator_id: int, payload: Optional[Dict[str, Any]] = Body(None)):
    indicator_data = convert_keys_to_snake(payload or {})
    symbol = indicator_data.get('symbol')
    if not symbol:
        return error_response({'success': False, 'error': '缺少symbol参数'}, 400)
    indicator = strategy_service.get_strategy(indicator_id)
    if not indicator:
        return error_response({'success': False, 'error': '指标不存在'}, 404)
    if indicator.get('code_type') != 'indicator':
        return error_response({'success': False, 'error': '该策略不是指标类型'}, 400)
    limit = int(indicator_data.get('limit', 100))
    chart_limit = indicator_data.get('chart_limit')
    chart_limit = int(chart_limit) if chart_limit is not None else None
    result = strategy_service.run_strategy(
        strategy_id=indicator_id, symbol=symbol, limit=limit,
        chart_limit=chart_limit, period=indicator_data.get('period'))
    return api_response(result, message='指标运行成功')


@router.post('/api/indicators/backtest')
@handle_api_error
def backtest_indicator(payload: Optional[Dict[str, Any]] = Body(None)):
    indicator_data = convert_keys_to_snake(payload or {})
    required_fields = ['indicator_id', 'symbol', 'start_date', 'end_date']
    for field in required_fields:
        if field not in indicator_data:
            return error_response({'success': False, 'error': f'缺少必需参数: {field}'}, 400)
    indicator_id = indicator_data['indicator_id']
    try:
        indicator_id = int(indicator_id)
    except (ValueError, TypeError):
        return error_response({'success': False, 'error': f'indicator_id 必须为整数, 当前值: {indicator_id}'}, 400)
    indicator = strategy_service.get_strategy(indicator_id)
    if not indicator:
        return error_response({'success': False, 'error': '指标不存在'}, 404)
    if indicator.get('code_type') != 'indicator':
        return error_response({'success': False, 'error': '该策略不是指标类型'}, 400)
    result = strategy_service.backtest_strategy(
        strategy_id=indicator_id, symbol=indicator_data['symbol'],
        start_date=indicator_data['start_date'], end_date=indicator_data['end_date'],
        initial_cash=indicator_data.get('initial_cash', 1000000), period=indicator_data.get('period'))

    equity_curve = result.get('equity_curve', [])
    trades = result.get('trades', [])
    try:
        start_date = datetime.strptime(indicator_data['start_date'], '%Y-%m-%d')
        end_date = datetime.strptime(indicator_data['end_date'], '%Y-%m-%d')
    except ValueError as e:
        return error_response({'success': False, 'error': f'日期格式无效，必须为 YYYY-MM-DD: {str(e)}'}, 400)
    result['summary'] = calculate_backtest_summary(equity_curve, trades, start_date, end_date)
    return api_response(result, message='指标回测完成')


@router.post('/api/indicators/publish/{indicator_id}')
@handle_api_error
def publish_indicator(indicator_id: int):
    indicator = strategy_service.get_strategy(indicator_id)
    if not indicator:
        return error_response({'success': False, 'error': '指标不存在'}, 404)
    if indicator.get('code_type') != 'indicator':
        return error_response({'success': False, 'error': '该策略不是指标类型'}, 400)
    updated = strategy_service.update_strategy(strategy_id=indicator_id, is_public=True)
    return api_response({'id': indicator_id, 'published': True}, message='指标发布成功')


@router.post('/api/indicators/favorite/{indicator_id}')
@handle_api_error
def favorite_indicator(indicator_id: int):
    indicator = strategy_service.get_strategy(indicator_id)
    if not indicator:
        return error_response({'success': False, 'error': '指标不存在'}, 404)
    if indicator.get('code_type') != 'indicator':
        return error_response({'success': False, 'error': '该策略不是指标类型'}, 400)
    current_count = indicator.get('favorite_count', 0) or 0
    updated = strategy_service.update_strategy(strategy_id=indicator_id, favorite_count=current_count + 1)
    return api_response({'id': indicator_id, 'favorite': True, 'favoriteCount': current_count + 1}, message='收藏成功')


@router.post('/api/indicators/unfavorite/{indicator_id}')
@handle_api_error
def unfavorite_indicator(indicator_id: int):
    indicator = strategy_service.get_strategy(indicator_id)
    if not indicator:
        return error_response({'success': False, 'error': '指标不存在'}, 404)
    if indicator.get('code_type') != 'indicator':
        return error_response({'success': False, 'error': '该策略不是指标类型'}, 400)
    current_count = indicator.get('favorite_count', 0) or 0
    new_count = max(0, current_count - 1)
    updated = strategy_service.update_strategy(strategy_id=indicator_id, favorite_count=new_count)
    return api_response({'id': indicator_id, 'favorite': False, 'favoriteCount': new_count}, message='已取消收藏')


# ============ 策略对比 / 沙箱列（indicators.py 追加） ============

def safe_calculate_return(equity_curve):
    """安全计算收益率（与 Flask indicators.py 一致）。"""
    if not equity_curve or len(equity_curve) < 2:
        return 0.0
    initial = equity_curve[0].get('equity', 0)
    if initial <= 0:
        return 0.0
    final = equity_curve[-1].get('equity', 0)
    return (final - initial) / initial


@router.post('/api/indicators/compare')
@handle_api_error
def compare_indicators(payload: Optional[Dict[str, Any]] = Body(None)):
    indicator_data = convert_keys_to_snake(payload or {})
    required_fields = ['indicator_id_a', 'indicator_id_b', 'symbol', 'start_date', 'end_date']
    for field in required_fields:
        if field not in indicator_data:
            return error_response({'success': False, 'error': f'缺少必需参数: {field}'}, 400)
    try:
        indicator_id_a = int(indicator_data['indicator_id_a'])
        indicator_id_b = int(indicator_data['indicator_id_b'])
    except (ValueError, TypeError):
        return error_response({'success': False, 'error': '指标ID必须为整数'}, 400)
    symbol = indicator_data['symbol']
    start_date = indicator_data['start_date']
    end_date = indicator_data['end_date']
    initial_cash = indicator_data.get('initial_cash', 1000000)

    indicator_a = strategy_service.get_strategy(indicator_id_a)
    indicator_b = strategy_service.get_strategy(indicator_id_b)
    if not indicator_a:
        return error_response({'success': False, 'error': f'指标A (ID={indicator_id_a}) 不存在'}, 404)
    if not indicator_b:
        return error_response({'success': False, 'error': f'指标B (ID={indicator_id_b}) 不存在'}, 404)
    if indicator_a.get('code_type') != 'indicator':
        return error_response({'success': False, 'error': '策略A不是指标类型'}, 400)
    if indicator_b.get('code_type') != 'indicator':
        return error_response({'success': False, 'error': '策略B不是指标类型'}, 400)

    result_a = strategy_service.backtest_strategy(
        strategy_id=indicator_id_a, symbol=symbol, start_date=start_date,
        end_date=end_date, initial_cash=initial_cash)
    result_b = strategy_service.backtest_strategy(
        strategy_id=indicator_id_b, symbol=symbol, start_date=start_date,
        end_date=end_date, initial_cash=initial_cash)

    trades_a = result_a.get('trades', [])
    trades_b = result_b.get('trades', [])
    buy_dates_a = set(t['date'] for t in trades_a if t.get('action') == 'buy')
    buy_dates_b = set(t['date'] for t in trades_b if t.get('action') == 'buy')
    filtered_dates = buy_dates_a - buy_dates_b
    filtered_trades = []
    for trade in trades_a:
        if trade['date'] in filtered_dates and trade.get('action') == 'buy':
            filtered_trades.append({
                'date': trade['date'], 'would_buy_price': trade.get('price'),
                'signal_a': 'buy', 'signal_b': 'hold', 'reason': 'filtered by strategy B'})

    equity_a = result_a.get('equity_curve', [])
    equity_b = result_b.get('equity_curve', [])
    total_return_a = safe_calculate_return(equity_a)
    total_return_b = safe_calculate_return(equity_b)

    comparison = {
        'return_diff': round(total_return_b - total_return_a, 4),
        'trades_diff': len(trades_b) - len(trades_a),
        'filtered_by_b_only': len(filtered_trades),
        'filtered_trades': filtered_trades,
    }
    return api_response({
        'strategy_a': {'indicator_id': indicator_id_a, 'name': indicator_a.get('name'),
                       'total_return': round(total_return_a, 4), 'total_trades': len(trades_a),
                       'equity_curve': equity_a, 'trades': trades_a},
        'strategy_b': {'indicator_id': indicator_id_b, 'name': indicator_b.get('name'),
                       'total_return': round(total_return_b, 4), 'total_trades': len(trades_b),
                       'equity_curve': equity_b, 'trades': trades_b},
        'comparison': comparison,
    }, message='策略对比完成')


@router.get('/api/indicators/sandbox-columns')
@handle_api_error
def get_sandbox_columns(symbol: Optional[str] = Query(None)):
    if not symbol:
        return error_response({'success': False, 'error': '缺少symbol参数'}, 400)
    from adapters.outbound.repositories import KlineORMRepository
    kline_repo = KlineORMRepository()
    klines = kline_repo.get_latest(symbol, limit=1000)
    if not klines:
        return error_response({'success': False, 'error': f'股票 {symbol} 无数据'}, 404)
    df = pd.DataFrame(klines)
    columns_to_check = [
        'roe_q', 'gross_margin_q', 'net_profit_margin_q', 'debt_ratio_q',
        'revenue_growth_q', 'ocf_to_profit_q', 'current_ratio_q', 'roa_q', 'operating_margin_q',
        'roe_y', 'gross_margin_y', 'net_profit_margin_y', 'debt_ratio_y',
        'revenue_growth_y', 'ocf_to_profit_y', 'current_ratio_y', 'roa_y', 'operating_margin_y',
        'rsi', 'macd', 'macd_signal', 'macd_hist',
        'atr', 'bollinger_upper', 'bollinger_middle', 'bollinger_lower',
        'ma5', 'ma10', 'ma20', 'ma60']
    columns_info = {}
    for col in columns_to_check:
        if col in df.columns:
            non_null_count = df[col].notna().sum()
            coverage = non_null_count / len(df) if len(df) > 0 else 0
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
                'latest_date': str(latest_date) if latest_date else None}
    date_range = {
        'start': str(df['trade_date'].min()) if 'trade_date' in df.columns else None,
        'end': str(df['trade_date'].max()) if 'trade_date' in df.columns else None}
    return api_response({'symbol': symbol, 'columns': columns_info, 'total_rows': len(df), 'date_range': date_range})
