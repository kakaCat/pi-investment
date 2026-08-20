"""市场/港股数据 API - FastAPI 版（从 Flask market.py / quote_market.py 迁移，响应契约保持一致）

覆盖端点：
- market.py: /api/market/sectors, /api/market/macro, /api/market/news, /api/market/margin,
  /api/market/sector-flow, /api/market/concepts,
  /api/market/concept/{concept}/stocks, /api/market/north-flow, /api/market/index-history,
  /api/hk/overview, /api/hk/south-flow, /api/hk/hot-rank,
  /api/hk/{symbol}/technical, /api/hk/{symbol}/financials, /api/hk/{symbol}/analysis
- quote_market.py: /api/market/sector/{sector}, /api/stocks/market/overview

复用同一 market_data_service / hk_market_data_service / ds 单例，保证 parity。
（/api/market/overview、/api/market/sentiment 分别由 market_async.py / analysis_async.py 提供，不在此迁移。）
"""
from typing import Optional

from fastapi import APIRouter, Query
import structlog

from adapters.inbound.fastapi_app.shared import (
    ds, api_response, error_response, handle_api_error,
)
from adapters.shared.services import market_data_service, hk_market_data_service

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["Market Data - 市场/港股数据"])


# ============ A 股市场数据（market.py） ============

@router.get('/api/market/sectors')
@handle_api_error
def get_sectors_v2():
    """A 股行业板块列表 - v2 原生实现"""
    result = market_data_service.get_sectors()
    if not result.get('success', False):
        return error_response(result, 503)
    return api_response(result.get('data', {}))


@router.get('/api/market/heatmap')
@handle_api_error
def get_market_heatmap(date: Optional[str] = Query(None), window: int = Query(5)):
    """市场热力图 - 行业×个股验证窗涨跌 + agent 判断痕迹叠加（本地 DB 聚合）"""
    from application.services.heatmap_service import heatmap_service
    result = heatmap_service.get_heatmap(date=date, window=window)
    if not result.get('success', False):
        return error_response(result, 400)
    return api_response(result.get('data', {}))


@router.get('/api/market/macro')
@handle_api_error
def get_macro():
    """宏观数据 - v2 原生实现"""
    result = market_data_service.get_macro_data()

    if not result.get('success'):
        return error_response(result, 400)

    return api_response(result.get('data', {}))


@router.get('/api/market/news')
@handle_api_error
def get_news(limit: int = Query(20)):
    """市场新闻 - v2 原生实现"""
    result = market_data_service.get_market_news(limit=limit)

    if not result.get('success'):
        return error_response(result, 400)

    return api_response(result.get('data', {}))


@router.get('/api/market/margin')
@handle_api_error
def get_market_margin_v2():
    """全市场融资融券 - v2 原生实现"""
    result = market_data_service.get_market_margin()
    if not result.get('success', False):
        return error_response(result, 503)
    return api_response(result.get('data', {}))


@router.get('/api/market/sector-flow')
@handle_api_error
def get_sector_flow_v2(period: str = Query('即时')):
    """行业资金流向 - v2 原生实现"""
    result = market_data_service.get_sector_fund_flow(period=period)
    if not result.get('success', False):
        return error_response(result, 503)
    return api_response(result.get('data', {}))


@router.get('/api/market/concepts')
@handle_api_error
def get_concepts(keyword: Optional[str] = Query(None)):
    """概念板块列表 - v2 原生实现"""
    result = market_data_service.get_concepts(keyword=keyword)

    if not result.get('success'):
        return error_response(result, 400)

    return api_response(result.get('data', {}))


@router.get('/api/market/concept/{concept:path}/stocks')
@handle_api_error
def get_concept_stocks_v2(concept: str):
    """概念板块成分股 - v2 原生实现"""
    result = market_data_service.get_concept_stocks(concept)

    if not result.get('success'):
        return error_response(result, 400)

    return api_response(result.get('data', {}))


@router.get('/api/market/north-flow')
@handle_api_error
def get_north_flow_v2(start_date: Optional[str] = Query(None), end_date: Optional[str] = Query(None)):
    """北向资金流向 - v2 原生实现"""
    result = market_data_service.get_north_flow(start_date=start_date, end_date=end_date)
    if not result.get('success', False):
        return error_response(result, 503)
    return api_response(result.get('data', {}))


@router.get('/api/market/index-history')
@handle_api_error
def get_index_history_v2(symbol: str = Query('sh000300'), start_date: str = Query(''),
                         end_date: str = Query('')):
    """指数历史K线 - v2 原生实现"""
    if not start_date or not end_date:
        return error_response({'success': False, 'error': 'require start_date and end_date params'}, 400)

    result = market_data_service.get_index_history(symbol, start_date, end_date)

    if not result.get('success'):
        return error_response(result, 400)

    return api_response(result.get('data', {}))


# ============ 港股市场数据（market.py） ============

@router.get('/api/hk/overview')
@handle_api_error
def get_hk_overview():
    """港股市场概览 - v2 原生实现"""
    result = hk_market_data_service.get_market_overview()

    if not result.get('success'):
        return error_response(result, 400)

    return api_response(result.get('data', {}))


@router.get('/api/hk/south-flow')
@handle_api_error
def get_hk_south_flow_v2():
    """南向资金 - v2 原生实现"""
    result = hk_market_data_service.get_south_flow()

    if not result.get('success'):
        return error_response(result, 400)

    return api_response(result.get('data', {}))


@router.get('/api/hk/hot-rank')
@handle_api_error
def get_hk_hot_rank_v2():
    """港股人气排行 - v2 原生实现"""
    result = hk_market_data_service.get_hot_rank()

    if not result.get('success'):
        return error_response(result, 400)

    return api_response(result.get('data', {}))


@router.get('/api/hk/{symbol}/technical')
@handle_api_error
def get_hk_technical(symbol: str):
    """港股技术指标 - v2 原生实现"""
    result = hk_market_data_service.get_technical(symbol)

    if not result.get('success'):
        return error_response(result, 400)

    return api_response(result.get('data', {}))


@router.get('/api/hk/{symbol}/financials')
@handle_api_error
def get_hk_financials(symbol: str):
    """港股财务数据 - v2 原生实现"""
    result = hk_market_data_service.get_financials(symbol)

    if not result.get('success'):
        return error_response(result, 400)

    return api_response(result.get('data', {}))


@router.get('/api/hk/{symbol}/analysis')
@handle_api_error
def get_hk_analysis(symbol: str):
    """港股分析数据 - v2 原生实现"""
    result = hk_market_data_service.get_analysis(symbol)

    if not result.get('success'):
        return error_response(result, 400)

    return api_response(result.get('data', {}))


# ============ 板块成分 / 市场概览（quote_market.py） ============

@router.get('/api/market/sector/{sector:path}')
@handle_api_error
def get_sector_stocks(sector: str, max_pe: Optional[float] = Query(None),
                      limit: int = Query(30)):
    """
    行业/概念板块成分筛选 - 替代旧 quant_cli screening.sector

    参数: sector (板块名称), max_pe, limit
    数据来源: DataProviderManager -> EastmoneySectorProvider（多数据源统一层）
    """
    from adapters.outbound.datasources import get_data_provider_manager

    limit = min(limit, 50)

    try:
        result = get_data_provider_manager().get_sector_stocks(sector)

        if not result.get('success'):
            # 所有数据源网络失败
            error_msg = result.get('error', 'No sector data available')
            attempted = result.get('attempted_sources', [])
            return error_response({
                "success": False,
                "error": f"{error_msg} (尝试数据源: {', '.join(attempted)})"
            }, 502)

        payload = result['data'].data  # MarketData.data dict
        if not payload.get('found'):
            return error_response({"success": False, "error": f"Sector not found: {sector}"}, 404)

        stocks = payload.get('stocks', [])
        if not stocks:
            return error_response({"success": False, "error": f"No stocks found in {sector}"}, 404)

        # 统一字段：market_cap(元) -> market_cap_billion(亿元)
        for s in stocks:
            s['market_cap_billion'] = round((s.pop('market_cap', 0) or 0) / 1e8, 2)

        if max_pe:
            stocks = [s for s in stocks if not (s['pe'] > max_pe and s['pe'] > 0)]
        stocks = stocks[:limit]

        return api_response({
            'sector': sector,
            'sector_code': payload.get('sector_code'),
            'stocks': sorted(stocks, key=lambda x: x['market_cap_billion'], reverse=True),
            'count': len(stocks),
            'source': result.get('source'),
        })
    except Exception as e:
        return error_response({"success": False, "error": str(e)}, 502)


@router.get('/api/stocks/market/overview')
@handle_api_error
def get_stocks_market_overview(market: Optional[str] = Query(None)):
    """市场概览（兼容 Express 前端）"""
    overview = ds.get_market_overview(market=market)
    return api_response(overview)
