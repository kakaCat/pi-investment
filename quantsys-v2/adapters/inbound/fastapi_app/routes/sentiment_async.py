"""情绪/资金 API - FastAPI 版（从 Flask sentiment.py 迁移，响应契约保持一致）

覆盖端点：
- /api/stock/{symbol}/fund-flow     个股资金流向
- /api/stock/{symbol}/margin        个股融资融券
- /api/stock/{symbol}/lhb           龙虎榜（个股）
- /api/stock/{symbol}/fund-holdings 基金持仓
- /api/stock/{symbol}/top-holders   十大股东
- /api/stock/{symbol}/holder-changes 股东变化趋势
- /api/sentiment/top-fund-stocks    基金重仓股

复用同一 LhbService / SentimentService / 数据源实现，保证 parity。
（/api/stock/{symbol}/insider-trades 不在本批迁移范围。）
"""
from typing import Optional

from fastapi import APIRouter, Query
import structlog

from adapters.inbound.fastapi_app.shared import (
    api_response, error_response, handle_api_error,
)
from adapters.shared.services import lhb_service

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["Sentiment - 情绪/资金"])

# 与 Flask 一致：模块级服务单例（通过 ServiceFactory 统一获取）
# lhb_service = LhbService()  # 已迁移到 adapters.shared.services


@router.get('/api/stock/{symbol}/fund-flow')
@handle_api_error
def get_stock_fund_flow_v2(symbol: str, days: int = Query(5)):
    """个股资金流向 - v2 原生实现"""
    from adapters.outbound.datasources.fund_flow_source import FundFlowDataSource
    from application.services.sentiment_service import SentimentService

    # 初始化服务
    fund_flow_source = FundFlowDataSource()
    sentiment_service = SentimentService(fund_flow_source)

    # 获取资金流向数据
    result = sentiment_service.get_stock_fund_flow(symbol, days)

    if 'error' in result:
        return error_response({'success': False, 'error': result['error']}, 400)

    return api_response(result)


@router.get('/api/stock/{symbol}/margin')
@handle_api_error
def get_stock_margin(symbol: str, days: int = Query(5)):
    """个股融资融券 - v2 原生实现"""
    from adapters.outbound.datasources.margin_data_source import MarginDataSource

    # 初始化数据源
    margin_source = MarginDataSource()

    # 获取融资融券数据
    result = margin_source.get_margin_data(symbol, days)

    return api_response(result)


@router.get('/api/stock/{symbol}/lhb')
@handle_api_error
def get_stock_lhb(symbol: str, days: int = Query(30)):
    """
    龙虎榜 - 个股查询

    Query Params:
        days: 查询最近N天（默认 30）

    Example:
        GET /api/stock/600737/lhb?days=30
    """
    result = lhb_service.get_stock_lhb(symbol, days)
    return api_response(result)


@router.get('/api/stock/{symbol}/fund-holdings')
@handle_api_error
def get_fund_holdings(symbol: str, quarter: Optional[str] = Query(None)):
    """基金持仓数据 - v2 原生实现"""
    from adapters.outbound.datasources.sentiment_data_source import SentimentDataSource

    source = SentimentDataSource()
    result = source.get_fund_holdings(symbol, quarter)

    return api_response(result)


@router.get('/api/stock/{symbol}/top-holders')
@handle_api_error
def get_top_holders(symbol: str, holder_type: str = Query('all')):
    """十大股东数据 - v2 原生实现"""
    from adapters.outbound.datasources.sentiment_data_source import SentimentDataSource

    source = SentimentDataSource()
    result = source.get_top_holders(symbol, holder_type)

    return api_response(result)


@router.get('/api/stock/{symbol}/holder-changes')
@handle_api_error
def get_holder_changes(symbol: str, periods: int = Query(4)):
    """股东变化趋势 - v2 原生实现"""
    from adapters.outbound.datasources.sentiment_data_source import SentimentDataSource

    source = SentimentDataSource()
    result = source.get_holder_changes(symbol, periods)

    return api_response(result)


@router.get('/api/sentiment/top-fund-stocks')
@handle_api_error
def get_top_fund_stocks(fund_type: str = Query('all'), limit: int = Query(50)):
    """基金重仓股 - v2 原生实现"""
    from adapters.outbound.datasources.sentiment_data_source import SentimentDataSource

    source = SentimentDataSource()
    result = source.get_top_fund_stocks(fund_type, limit)

    return api_response(result)
