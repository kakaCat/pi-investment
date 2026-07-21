"""
market routes.
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
from application.services.market_data_service import market_data_service
from application.services.hk_market_data_service import hk_market_data_service

market_bp = Blueprint('market', __name__)

@market_bp.route('/api/market/overview', methods=['GET'])
@handle_api_error
def get_market_overview():
    """
    获取市场概览

    返回：
    - 市场统计（股票数量、活跃股票）
    - 因子覆盖率（MA、MACD、RSI 等技术指标）
    - 数据更新时间
    """
    import logging
    logger = logging.getLogger(__name__)

    from adapters.outbound.repositories import StockORMRepository
    from adapters.outbound.repositories import KlineORMRepository

    stock_repo = StockORMRepository()
    kline_repo = KlineORMRepository()

    # 获取股票总数
    logger.info("Calling stock_repo.count_all()...")
    total_stocks = stock_repo.count_all()
    logger.info(f"Total stocks: {total_stocks}")

    # 获取活跃股票数（有K线数据的）
    logger.info("Calling kline_repo.count_stocks_with_data()...")
    active_stocks = kline_repo.count_stocks_with_data()
    logger.info(f"Active stocks: {active_stocks}")

    # 获取因子覆盖率
    # 检查最近一天有技术指标数据的股票数量
    logger.info("Calling kline_repo.get_factor_coverage()...")
    factor_coverage = kline_repo.get_factor_coverage()
    logger.info(f"Factor coverage: {factor_coverage}")

    # 获取最新数据时间
    logger.info("Calling kline_repo.get_latest_update_time()...")
    latest_update = kline_repo.get_latest_update_time()
    logger.info(f"Latest update: {latest_update}")

    return api_response({
        'market_stats': {
            'total_stocks': total_stocks,
            'active_stocks': active_stocks,
            'coverage_rate': round(active_stocks / total_stocks * 100, 2) if total_stocks > 0 else 0
        },
        'factor_coverage': {
            'ma': factor_coverage.get('ma', 0),
            'macd': factor_coverage.get('macd', 0),
            'rsi': factor_coverage.get('rsi', 0),
            'bollinger': factor_coverage.get('bollinger', 0),
            'atr': factor_coverage.get('atr', 0)
        },
        'last_update': latest_update.isoformat() if latest_update else None
    })

@market_bp.route('/api/market/sectors', methods=['GET'])
@handle_api_error
def get_sectors_v2():
    """A 股行业板块列表 - v2 原生实现"""
    from application.services.market_data_service import market_data_service
    result = market_data_service.get_sectors()
    if not result.get('success', False):
        return jsonify(result), 503
    return api_response(result.get('data', {}))

@market_bp.route('/api/market/macro', methods=['GET'])
@handle_api_error
def get_macro():
    """宏观数据 - v2 原生实现"""
    result = market_data_service.get_macro_data()

    if not result.get('success'):
        return jsonify(result), 400

    return api_response(result.get('data', {}))


@market_bp.route('/api/market/news', methods=['GET'])
@handle_api_error
def get_news():
    """市场新闻 - v2 原生实现"""
    limit = request.args.get('limit', 20, type=int)
    result = market_data_service.get_market_news(limit=limit)

    if not result.get('success'):
        return jsonify(result), 400

    return api_response(result.get('data', {}))


@market_bp.route('/api/market/margin', methods=['GET'])
@handle_api_error
def get_market_margin_v2():
    """全市场融资融券 - v2 原生实现"""
    from application.services.market_data_service import market_data_service
    result = market_data_service.get_market_margin()
    if not result.get('success', False):
        return jsonify(result), 503
    return api_response(result.get('data', {}))


@market_bp.route('/api/market/hot-stocks', methods=['GET'])
@handle_api_error
def get_hot_stocks_v2():
    """热搜股票 - v2 多数据源实现

    查询参数:
    - market: 市场类型（A股/港股/美股），默认 A股
    - mode: 返回模式（first/all），默认 all
      - first: 返回第一个成功的数据源
      - all: 返回所有成功的数据源
    """
    from application.services.market_data_service import market_data_service
    market = request.args.get('market', 'A股')
    mode = request.args.get('mode', 'all')
    result = market_data_service.get_hot_stocks(market=market, mode=mode)
    if not result.get('success', False):
        return jsonify(result), 503
    return api_response(result.get('data', {}))


@market_bp.route('/api/market/sector-flow', methods=['GET'])
@handle_api_error
def get_sector_flow_v2():
    """行业资金流向 - v2 原生实现"""
    from application.services.market_data_service import market_data_service
    period = request.args.get('period', '即时')
    result = market_data_service.get_sector_fund_flow(period=period)
    if not result.get('success', False):
        return jsonify(result), 503
    return api_response(result.get('data', {}))


@market_bp.route('/api/market/concepts', methods=['GET'])
@handle_api_error
def get_concepts():
    """概念板块列表 - v2 原生实现"""
    keyword = request.args.get('keyword', None)
    result = market_data_service.get_concepts(keyword=keyword)

    if not result.get('success'):
        return jsonify(result), 400

    return api_response(result.get('data', {}))


@market_bp.route('/api/market/concept/<path:concept>/stocks', methods=['GET'])
@handle_api_error
def get_concept_stocks_v2(concept):
    """概念板块成分股 - v2 原生实现"""
    result = market_data_service.get_concept_stocks(concept)

    if not result.get('success'):
        return jsonify(result), 400

    return api_response(result.get('data', {}))


@market_bp.route('/api/market/north-flow', methods=['GET'])
@handle_api_error
def get_north_flow_v2():
    """北向资金流向 - v2 原生实现"""
    from application.services.market_data_service import market_data_service
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    result = market_data_service.get_north_flow(start_date=start_date, end_date=end_date)
    if not result.get('success', False):
        return jsonify(result), 503
    return api_response(result.get('data', {}))


@market_bp.route('/api/market/index-history', methods=['GET'])
@handle_api_error
def get_index_history_v2():
    """指数历史K线 - v2 原生实现"""
    symbol = request.args.get('symbol', 'sh000300')
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')

    if not start_date or not end_date:
        return jsonify({'success': False, 'error': 'require start_date and end_date params'}), 400

    result = market_data_service.get_index_history(symbol, start_date, end_date)

    if not result.get('success'):
        return jsonify(result), 400

    return api_response(result.get('data', {}))


@market_bp.route('/api/hk/overview', methods=['GET'])
@handle_api_error
def get_hk_overview():
    """港股市场概览 - v2 原生实现"""
    result = hk_market_data_service.get_market_overview()

    if not result.get('success'):
        return jsonify(result), 400

    return api_response(result.get('data', {}))


@market_bp.route('/api/hk/south-flow', methods=['GET'])
@handle_api_error
def get_hk_south_flow_v2():
    """南向资金 - v2 原生实现"""
    result = hk_market_data_service.get_south_flow()

    if not result.get('success'):
        return jsonify(result), 400

    return api_response(result.get('data', {}))


@market_bp.route('/api/hk/hot-rank', methods=['GET'])
@handle_api_error
def get_hk_hot_rank_v2():
    """港股人气排行 - v2 原生实现"""
    result = hk_market_data_service.get_hot_rank()

    if not result.get('success'):
        return jsonify(result), 400

    return api_response(result.get('data', {}))


@market_bp.route('/api/hk/<symbol>/technical', methods=['GET'])
@handle_api_error
def get_hk_technical(symbol):
    """港股技术指标 - v2 原生实现"""
    result = hk_market_data_service.get_technical(symbol)

    if not result.get('success'):
        return jsonify(result), 400

    return api_response(result.get('data', {}))


@market_bp.route('/api/hk/<symbol>/financials', methods=['GET'])
@handle_api_error
def get_hk_financials(symbol):
    """港股财务数据 - v2 原生实现"""
    result = hk_market_data_service.get_financials(symbol)

    if not result.get('success'):
        return jsonify(result), 400

    return api_response(result.get('data', {}))


@market_bp.route('/api/hk/<symbol>/analysis', methods=['GET'])
@handle_api_error
def get_hk_analysis(symbol):
    """港股分析数据 - v2 原生实现"""
    result = hk_market_data_service.get_analysis(symbol)

    if not result.get('success'):
        return jsonify(result), 400

    return api_response(result.get('data', {}))


@market_bp.route('/api/market/sentiment', methods=['GET'])
@handle_api_error
def get_market_sentiment():
    """市场情绪分析 - v2 原生实现"""
    from application.services.market_sentiment_service import MarketSentimentService

    # 初始化服务
    sentiment_service = MarketSentimentService(ds)

    # 分析市场情绪
    result = sentiment_service.analyze_market_sentiment()

    if 'error' in result:
        return jsonify({'success': False, 'error': result['error']}), 400

    return api_response(result)
