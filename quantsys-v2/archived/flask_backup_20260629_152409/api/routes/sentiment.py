"""
sentiment routes.
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
from application.services.lhb_service import LhbService

sentiment_bp = Blueprint('sentiment', __name__)
lhb_service = LhbService()

@sentiment_bp.route('/api/stock/<symbol>/fund-flow', methods=['GET'])
@handle_api_error
def get_stock_fund_flow_v2(symbol):
    """个股资金流向 - v2 原生实现"""
    from adapters.outbound.datasources.fund_flow_source import FundFlowDataSource
    from application.services.sentiment_service import SentimentService

    # 获取查询参数
    days = request.args.get('days', 5, type=int)

    # 初始化服务
    fund_flow_source = FundFlowDataSource()
    sentiment_service = SentimentService(fund_flow_source)

    # 获取资金流向数据
    result = sentiment_service.get_stock_fund_flow(symbol, days)

    if 'error' in result:
        return jsonify({'success': False, 'error': result['error']}), 400

    return api_response(result)


@sentiment_bp.route('/api/stock/<symbol>/margin', methods=['GET'])
@handle_api_error
def get_stock_margin(symbol):
    """个股融资融券 - v2 原生实现"""
    from adapters.outbound.datasources.margin_data_source import MarginDataSource

    # 获取查询参数
    days = request.args.get('days', 5, type=int)

    # 初始化数据源
    margin_source = MarginDataSource()

    # 获取融资融券数据
    result = margin_source.get_margin_data(symbol, days)

    return api_response(result)


@sentiment_bp.route('/api/stock/<symbol>/lhb', methods=['GET'])
@handle_api_error
def get_stock_lhb(symbol):
    """
    龙虎榜 - 个股查询

    Query Params:
        days: 查询最近N天（默认 30）

    Example:
        GET /api/stock/600737/lhb?days=30
    """
    days = request.args.get('days', 30, type=int)
    result = lhb_service.get_stock_lhb(symbol, days)
    return api_response(result)


@sentiment_bp.route('/api/stock/<symbol>/fund-holdings', methods=['GET'])
@handle_api_error
def get_fund_holdings(symbol):
    """基金持仓数据 - v2 原生实现"""
    from adapters.outbound.datasources.sentiment_data_source import SentimentDataSource

    quarter = request.args.get('quarter')
    
    source = SentimentDataSource()
    result = source.get_fund_holdings(symbol, quarter)
    
    return api_response(result)


@sentiment_bp.route('/api/stock/<symbol>/top-holders', methods=['GET'])
@handle_api_error
def get_top_holders(symbol):
    """十大股东数据 - v2 原生实现"""
    from adapters.outbound.datasources.sentiment_data_source import SentimentDataSource

    holder_type = request.args.get('holder_type', 'all')
    
    source = SentimentDataSource()
    result = source.get_top_holders(symbol, holder_type)
    
    return api_response(result)


@sentiment_bp.route('/api/stock/<symbol>/holder-changes', methods=['GET'])
@handle_api_error
def get_holder_changes(symbol):
    """股东变化趋势 - v2 原生实现"""
    from adapters.outbound.datasources.sentiment_data_source import SentimentDataSource

    periods = request.args.get('periods', 4, type=int)
    
    source = SentimentDataSource()
    result = source.get_holder_changes(symbol, periods)
    
    return api_response(result)


@sentiment_bp.route('/api/sentiment/top-fund-stocks', methods=['GET'])
@handle_api_error
def get_top_fund_stocks():
    """基金重仓股 - v2 原生实现"""
    from adapters.outbound.datasources.sentiment_data_source import SentimentDataSource

    fund_type = request.args.get('fund_type', 'all')
    limit = request.args.get('limit', 50, type=int)
    
    source = SentimentDataSource()
    result = source.get_top_fund_stocks(fund_type, limit)
    
    return api_response(result)


@sentiment_bp.route('/api/stock/<symbol>/insider-trades', methods=['GET'])
@handle_api_error
def get_insider_trades(symbol):
    """内部交易数据 - v2 原生实现"""
    from adapters.outbound.datasources.sentiment_data_source import SentimentDataSource

    days = request.args.get('days', 30, type=int)
    
    source = SentimentDataSource()
    result = source.get_insider_trades(symbol, days)
    
    return api_response(result)
