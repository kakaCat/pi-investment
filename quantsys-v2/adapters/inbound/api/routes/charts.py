"""
charts routes.
"""
from typing import Optional
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
import re
import uuid

from flask import Blueprint, jsonify, request

import os
import base64 as _base64

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

charts_bp = Blueprint('charts', __name__)

_CHART_DIR = Path(os.getcwd()) / '.pi-invest' / 'quant' / 'charts'


def _import_visualizer():
    """Lazy import visualizer with sys.path adjustment for quant package."""
    _quant_path = Path(os.getcwd()).parent / 'quant'
    if str(_quant_path) not in __import__('sys').path:
        __import__('sys').path.insert(0, str(_quant_path))
    return visualizer


@charts_bp.route('/api/charts/accuracy', methods=['GET'])
@handle_api_error
def chart_accuracy():
    """模型准确率趋势图"""
    try:
        visualizer = _import_visualizer()
    except Exception:
        return jsonify({'success': False, 'error': 'Chart module not available'}), 503

    days = request.args.get('days', 90, type=int)
    _CHART_DIR.mkdir(parents=True, exist_ok=True)
    output_path = str(_CHART_DIR / 'accuracy_trend.png')

    result = visualizer.plot_model_accuracy_trend(days=days, output_path=output_path)

    image_b64 = None
    if Path(output_path).exists():
        image_b64 = _base64.b64encode(Path(output_path).read_bytes()).decode('utf-8')

    return api_response({
        'chart_data': sanitize_for_json(result),
        'image_base64': image_b64,
        'image_path': output_path,
    })


@charts_bp.route('/api/charts/equity', methods=['GET'])
@handle_api_error
def chart_equity():
    """回测权益曲线图"""
    try:
        visualizer = _import_visualizer()
    except Exception:
        return jsonify({'success': False, 'error': 'Chart module not available'}), 503

    backtest_json = request.args.get('backtest_result')
    if backtest_json:
        backtest_result = json.loads(backtest_json)
    else:
        latest = ds.backtest.get_all_backtests(limit=1)
        backtest_result = latest[0] if latest else {}

    _CHART_DIR.mkdir(parents=True, exist_ok=True)
    output_path = str(_CHART_DIR / 'equity_curve.png')

    result = visualizer.plot_equity_curve(backtest_result=backtest_result, output_path=output_path)

    image_b64 = None
    if Path(output_path).exists():
        image_b64 = _base64.b64encode(Path(output_path).read_bytes()).decode('utf-8')

    return api_response({
        'chart_data': sanitize_for_json(result),
        'image_base64': image_b64,
    })


@charts_bp.route('/api/charts/comparison', methods=['GET'])
@handle_api_error
def chart_comparison():
    """策略对比图"""
    try:
        visualizer = _import_visualizer()
    except Exception:
        return jsonify({'success': False, 'error': 'Chart module not available'}), 503

    strategies_json = request.args.get('strategies_performance')
    if strategies_json:
        strategies_performance = json.loads(strategies_json)
    else:
        all_strategies = strategy_service.list_strategies()
        strategies_performance = []
        for s in (all_strategies or [])[:10]:
            stats = ds.backtest.get_backtest_stats(strategy_name=str(s.get('id')))
            if stats:
                strategies_performance.append({
                    'name': s.get('name', 'Unknown'),
                    'total_return': stats.get('avg_return', 0),
                    'sharpe_ratio': stats.get('avg_sharpe', 0),
                    'max_drawdown': stats.get('avg_max_drawdown', 0),
                })

    _CHART_DIR.mkdir(parents=True, exist_ok=True)
    output_path = str(_CHART_DIR / 'strategy_comparison.png')

    result = visualizer.plot_strategy_comparison(strategies_performance=strategies_performance, output_path=output_path)

    image_b64 = None
    if Path(output_path).exists():
        image_b64 = _base64.b64encode(Path(output_path).read_bytes()).decode('utf-8')

    return api_response({
        'chart_data': sanitize_for_json(result),
        'image_base64': image_b64,
    })


@charts_bp.route('/api/charts/importance', methods=['GET'])
@handle_api_error
def chart_importance():
    """特征重要性图表"""
    try:
        visualizer = _import_visualizer()
    except Exception:
        return jsonify({'success': False, 'error': 'Chart module not available'}), 503

    _CHART_DIR.mkdir(parents=True, exist_ok=True)
    output_path = str(_CHART_DIR / 'feature_importance.png')

    model_path = request.args.get('model_path',
        str(Path(os.getcwd()) / 'ml' / 'models' / 'xgboost_latest.pkl'))
    top_n = request.args.get('top_n', 20, type=int)

    result = visualizer.plot_feature_importance(model_path=model_path, output_path=output_path)

    image_b64 = None
    if Path(output_path).exists():
        image_b64 = _base64.b64encode(Path(output_path).read_bytes()).decode('utf-8')

    return api_response({
        'chart_data': sanitize_for_json(result),
        'image_base64': image_b64,
    })


@charts_bp.route('/api/charts/image/<chart_type>', methods=['GET'])
@handle_api_error
def chart_image(chart_type):
    """Serve rendered chart image by type."""
    valid_types = {'accuracy_trend', 'equity_curve', 'strategy_comparison', 'feature_importance'}
    if chart_type not in valid_types:
        return jsonify({
            'success': False,
            'error': f'Invalid chart type. Must be one of: {", ".join(sorted(valid_types))}'
        }), 400

    image_path = _CHART_DIR / f'{chart_type}.png'
    if not image_path.exists():
        return jsonify({
            'success': False,
            'error': 'Chart image not found. Generate the chart first via the corresponding data endpoint.'
        }), 404

    from flask import send_file
    return send_file(str(image_path), mimetype='image/png')


def _parse_sina_a_quote(raw: str, symbol: str) -> Optional[dict]:
    """解析新浪A股实时行情数据"""
    try:
        match = re.search(r'"(.+)"', raw)
        if not match:
            return None
        parts = match.group(1).split(",")
        if len(parts) < 32:
            return None
        
        name = parts[0]
        open_p = parts[1]
        prev_close = parts[2]
        price = parts[3]
        high = parts[4]
        low = parts[5]
        volume = parts[8]  # 成交量（股）
        amount = parts[9]  # 成交额
        date = parts[30]
        time_str = parts[31]

        price_f = float(price) if price else 0
        prev_f = float(prev_close) if prev_close else 0
        
        if price_f <= 0:
            return None

        change_pct = round((price_f - prev_f) / prev_f * 100, 2) if prev_f else 0

        return {
            "symbol": symbol,
            "name": name,
            "price": price_f,
            "change_pct": change_pct,
            "change_amount": round(price_f - prev_f, 3),
            "high": float(high) if high else 0,
            "low": float(low) if low else 0,
            "open": float(open_p) if open_p else 0,
            "prev_close": prev_f,
            "volume": int(float(volume)) if volume else 0,
            "amount": float(amount) if amount else 0,
            "data_time": f"{date} {time_str}",
            "market": "A",
            "source": "sina",
        }
    except Exception:
        return None


def _parse_sina_hk_quote(raw: str, symbol: str) -> Optional[dict]:
    """解析新浪港股实时行情数据"""
    try:
        match = re.search(r'"(.+)"', raw)
        if not match:
            return None
        parts = match.group(1).split(",")
        if len(parts) < 20:
            return None

        name = parts[1]
        open_p = parts[2]
        prev_close = parts[3]
        high = parts[4]
        low = parts[5]
        price = parts[6]
        change_amount = parts[7] if len(parts) > 7 else "0"
        change_pct_val = parts[8] if len(parts) > 8 else "0"
        date = parts[17] if len(parts) > 17 else ""
        time_str = parts[18] if len(parts) > 18 else ""

        price_f = float(price) if price else 0
        if price_f <= 0:
            return None

        return {
            "symbol": symbol,
            "name": name,
            "price": price_f,
            "change_pct": float(change_pct_val) if change_pct_val else 0,
            "change_amount": float(change_amount) if change_amount else 0,
            "high": float(high) if high else 0,
            "low": float(low) if low else 0,
            "open": float(open_p) if open_p else 0,
            "prev_close": float(prev_close) if prev_close else 0,
            "data_time": f"{date} {time_str}".strip(),
            "market": "HK",
            "source": "sina",
        }
    except Exception:
        return None


def _safe_float(value, default=0.0, decimals=None):
    """安全转换为浮点数"""
    if value is None:
        return default
    try:
        result = float(value)
        return round(result, decimals) if decimals is not None else result
    except (ValueError, TypeError):
        return default


def _aggregate_weekly(daily_records):
    """将日K线聚合为周K线"""
    if not daily_records:
        return []
    from datetime import datetime as _dt
    weeks = {}
    for r in daily_records:
        try:
            d = _dt.strptime(r['date'], '%Y-%m-%d')
            week_key = d.strftime('%Y-W%W')
        except (ValueError, TypeError):
            continue
        if week_key not in weeks:
            weeks[week_key] = {
                'date': r['date'],
                'open': r['open'],
                'high': r['high'],
                'low': r['low'],
                'close': r['close'],
                'volume': r.get('volume', 0),
            }
        else:
            w = weeks[week_key]
            w['high'] = max(w['high'], r['high'])
            w['low'] = min(w['low'], r['low'])
            w['close'] = r['close']
            w['volume'] += r.get('volume', 0)
            w['date'] = r['date']  # Last day of week
    result = list(weeks.values())
    for i, r in enumerate(result):
        if i > 0:
            prev = result[i-1]['close']
            r['change_pct'] = round((r['close'] - prev) / prev * 100, 2) if prev else 0
        else:
            r['change_pct'] = 0.0
    return result


def _aggregate_monthly(daily_records):
    """将日K线聚合为月K线"""
    if not daily_records:
        return []
    months = {}
    for r in daily_records:
        try:
            month_key = r['date'][:7]  # YYYY-MM
        except (KeyError, IndexError):
            continue
        if month_key not in months:
            months[month_key] = {
                'date': r['date'],
                'open': r['open'],
                'high': r['high'],
                'low': r['low'],
                'close': r['close'],
                'volume': r.get('volume', 0),
            }
        else:
            m = months[month_key]
            m['high'] = max(m['high'], r['high'])
            m['low'] = min(m['low'], r['low'])
            m['close'] = r['close']
            m['volume'] += r.get('volume', 0)
            m['date'] = r['date']
    result = list(months.values())
    for i, r in enumerate(result):
        if i > 0:
            prev = result[i-1]['close']
            r['change_pct'] = round((r['close'] - prev) / prev * 100, 2) if prev else 0
        else:
            r['change_pct'] = 0.0
    return result


