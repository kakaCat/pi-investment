"""
stock routes.
"""
import json
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path
import re
import uuid
from typing import Any, Dict, List, Optional

from flask import Blueprint, jsonify, request

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
from application.services.stock_data_service import stock_data_service

stock_bp = Blueprint('stock', __name__)

def enrich_stock_data(stock: Dict) -> Dict:
    """
    为股票添加额外信息（价格、涨跌幅、K线天数、因子数量等）

    Args:
        stock: 基础股票信息

    Returns:
        enriched_stock: 包含完整信息的股票数据
    """
    symbol = stock['symbol']
    stock_data = {
        'symbol': symbol,
        'name': stock['name'],
        'market': stock.get('market', ''),
        'industry': stock.get('industry', ''),
        'price': 0.0,
        'changePercent': 0.0,
        'klineDays': 0,
        'factorCount': 0,
        'dataStatus': 'incomplete'
    }

    try:
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')

        logger.debug(f"Fetching klines for {symbol} from {start_date} to {end_date}")
        klines = ds.kline.get_daily_klines(symbol, start_date, end_date)

        # 安全检查 klines（支持 list, DataFrame 等多种类型）
        klines_len = 0
        if klines is not None:
            if hasattr(klines, '__len__'):
                klines_len = len(klines)
            elif hasattr(klines, 'shape'):  # DataFrame
                klines_len = klines.shape[0]

        logger.debug(f"Got {klines_len} klines for {symbol}")

        if klines is not None and klines_len > 0:
            latest = klines[-1]
            stock_data['price'] = float(latest.get('close', 0))
            logger.debug(f"{symbol} latest price: {stock_data['price']}")

            if klines_len >= 2:
                prev_close = float(klines[-2].get('close', 0))
                if prev_close > 0:
                    stock_data['changePercent'] = ((stock_data['price'] - prev_close) / prev_close) * 100
                    logger.debug(f"{symbol} change: {stock_data['changePercent']:.2f}%")

        kline_stats = ds.kline.get_kline_stats(symbol, '2020-01-01', end_date)
        if kline_stats:
            stock_data['klineDays'] = kline_stats.get('count', 0)
            logger.debug(f"{symbol} kline days: {stock_data['klineDays']}")

        available_factors = ds.factor.get_available_factors(symbol)
        if available_factors:
            stock_data['factorCount'] = len(available_factors)
            logger.debug(f"{symbol} factor count: {stock_data['factorCount']}")

        if stock_data['klineDays'] > 0 and stock_data['factorCount'] > 0:
            stock_data['dataStatus'] = 'complete'

    except Exception as e:
        logger.warning(f"Failed to enrich stock {symbol}: {e}", exc_info=True)

    return stock_data


@stock_bp.route('/api/stocks/search', methods=['GET'])
def search_stocks():
    """搜索股票（代码和名称模糊匹配）"""
    q = request.args.get('q', '').strip()
    if not q:
        return jsonify({'error': '搜索关键词不能为空'}), 400

    page = max(1, request.args.get('page', 1, type=int))
    page_size = max(1, min(request.args.get('pageSize', 20, type=int), 100))
    offset = (page - 1) * page_size

    try:
        results = ds.stock.search(q, limit=page_size + offset)
        total = len(results)
        stocks = results[offset:offset + page_size]

        enriched_stocks = [enrich_stock_data(s) for s in stocks]

        return jsonify({
            'query': q,
            'total': total,
            'page': page,
            'pageSize': page_size,
            'stocks': enriched_stocks
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@stock_bp.route('/api/stocks/list', methods=['GET'])
def get_stock_list():
    """获取股票列表"""
    try:
        market = request.args.get('market')
        industry = request.args.get('industry')
        keyword = request.args.get('keyword', '').strip()
        page = max(1, request.args.get('page', 1, type=int))
        page_size = max(1, min(request.args.get('pageSize', 20, type=int), 100))

        if keyword:
            all_stocks = ds.stock.search(keyword, limit=500)
            if market:
                all_stocks = [stock for stock in all_stocks if stock.get('market') == market]
            if industry:
                all_stocks = [stock for stock in all_stocks if stock.get('industry') == industry]
        else:
            all_stocks = ds.stock.get_all(market=market, industry=industry, limit=500)
        if keyword:
            keyword_lower = keyword.lower()
            all_stocks = [
                stock for stock in all_stocks
                if keyword_lower in str(stock.get('symbol', '')).lower()
                or keyword_lower in str(stock.get('name', '')).lower()
            ]
        total = len(all_stocks)

        offset = (page - 1) * page_size
        stocks = all_stocks[offset:offset + page_size]

        enriched_stocks = [enrich_stock_data(s) for s in stocks]

        return jsonify({
            'count': total,
            'stocks': enriched_stocks,
            'page': page,
            'pageSize': page_size
        })
    except Exception as e:
        logger.error(f"Failed to get stock list: {e}")
        return jsonify({'error': str(e)}), 500


@stock_bp.route('/api/stocks/resolve', methods=['POST'])
def resolve_stock():
    """解析股票代码"""
    data = request.get_json() or {}
    code = data.get('code', '').strip()
    if not code:
        return jsonify({'error': '股票代码不能为空'}), 400

    try:
        stock = ds.stock.get_by_symbol(code)
        if not stock:
            return jsonify({'found': False, 'symbol': code}), 404

        return jsonify({
            'found': True,
            'symbol': stock['symbol'],
            'name': stock['name'],
            'market': stock.get('market', ''),
            'industry': stock.get('industry', '')
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@stock_bp.route('/api/stocks/add', methods=['POST'])
def add_stock():
    """添加股票"""
    data = request.get_json() or {}
    try:
        ds.stock.save(data)
        return jsonify({'success': True, 'symbol': data.get('symbol')})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ── 数据状态 / 更新端点已迁移到 api/routes/pipeline.py ──

@stock_bp.route('/api/stock/<symbol>/announcements', methods=['GET'])
@handle_api_error
def get_announcements_v2(symbol):
    """公告 - v2 原生实现"""
    result = stock_data_service.get_announcements(symbol)

    if not result.get('success'):
        return jsonify(result), 400

    return api_response(result.get('data', {}))


@stock_bp.route('/api/stock/<symbol>/news', methods=['GET'])
@handle_api_error
def get_stock_news_v2(symbol):
    """新闻 - v2 原生实现"""
    num = request.args.get('num', 10, type=int)
    result = stock_data_service.get_news(symbol, num)

    if not result.get('success'):
        return jsonify(result), 400

    return api_response(result.get('data', {}))


@stock_bp.route('/api/stocks/batch-quotes', methods=['POST'])
@handle_api_error
def get_batch_quotes_v2():
    """批量行情 - v2 原生实现"""
    data = request.get_json(silent=True) or {}
    symbols = data.get('symbols', [])

    if not symbols:
        return jsonify({'success': False, 'error': 'symbols required'}), 400

    result = stock_data_service.get_batch_quotes(symbols)

    if not result.get('success'):
        return jsonify(result), 400

    return api_response(result.get('data', {}))


@stock_bp.route('/api/stock/<symbol>/insider-trades', methods=['GET'])
@handle_api_error
def get_insider_trades_v2(symbol):
    """内部人交易 - v2 原生实现"""
    result = stock_data_service.get_insider_trades(symbol)

    if not result.get('success'):
        return jsonify(result), 400

    return api_response(result.get('data', {}))


@stock_bp.route('/api/stock/<symbol>/peers', methods=['GET'])
@handle_api_error
def get_peers(symbol):
    """同行对比 - v2 原生实现"""
    result = stock_data_service.compare_peers(symbol)

    if not result.get('success'):
        return jsonify(result), 400

    return api_response(result.get('data', {}))


@stock_bp.route('/api/stocks/my-stocks', methods=['GET'])
@handle_api_error
def get_my_stocks():
    """获取我的股票（持仓 + 自选股）"""
    positions = []
    watchlist = []

    # 获取持仓
    try:
        db = ds.portfolio.db
        if db:
            cursor = db.cursor()
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_schema = 'quant' AND table_name = 'positions'
                )
            """)
            has_new_schema = cursor.fetchone()['exists']

            if has_new_schema:
                cursor.execute("""
                    SELECT symbol, name FROM quant.positions
                    WHERE status = 'open'
                    ORDER BY entry_date DESC
                """)
                positions = [{'symbol': row['symbol'], 'name': row.get('name', '')} for row in cursor.fetchall()]
            else:
                holdings = ds.portfolio.get_all_holdings()
                positions = [{'symbol': h['symbol'], 'name': h.get('name', '')} for h in holdings]

            cursor.close()
    except Exception as e:
        pass

    # 获取自选股
    try:
        wl = _read_watchlist()
        items = wl.get('items', [])
        watchlist = [{'symbol': item['symbol'], 'name': item.get('name', '')} for item in items]
    except Exception as e:
        pass

    return api_response({
        'positions': positions,
        'watchlist': watchlist
    })
