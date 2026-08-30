"""市场/港股数据 API — migrated to DataProviderManager.

Endpoints not covered by DataProviderManager (concepts, technical, analysis,
heatmap) fall back to original services.
"""
from typing import Optional

from fastapi import APIRouter, Query
import structlog

from adapters.outbound.datasources import get_data_provider_manager

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["Market Data - 市场/港股数据"])


@router.get('/api/market/sectors')
def get_sectors_v2():
    mgr = get_data_provider_manager()
    return mgr.get_sector_list()


@router.get('/api/market/heatmap')
def get_market_heatmap(date: Optional[str] = Query(None), window: int = Query(5)):
    from application.services.heatmap_service import heatmap_service
    result = heatmap_service.get_heatmap(date=date, window=window)
    if not result.get('success', False):
        return {"success": False, "error": result.get("error", "heatmap failed")}
    return result


@router.get('/api/market/macro')
def get_macro():
    mgr = get_data_provider_manager()
    return mgr.get_macro_data()


@router.get('/api/market/news')
def get_news(limit: int = Query(20)):
    mgr = get_data_provider_manager()
    return mgr.get_market_news()


@router.get('/api/market/margin')
def get_market_margin_v2():
    mgr = get_data_provider_manager()
    return mgr.get_market_margin()


@router.get('/api/market/sector-flow')
def get_sector_flow_v2(period: str = Query('即时')):
    mgr = get_data_provider_manager()
    return mgr.get_sector_fund_flow(indicator=period)


@router.get('/api/market/concepts')
def get_concepts(keyword: Optional[str] = Query(None)):
    try:
        from adapters.shared.services import market_data_service
        result = market_data_service.get_concepts(keyword=keyword)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get('/api/market/concept/{concept:path}/stocks')
def get_concept_stocks_v2(concept: str):
    try:
        from adapters.shared.services import market_data_service
        result = market_data_service.get_concept_stocks(concept)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get('/api/market/north-flow')
def get_north_flow_v2(start_date: Optional[str] = Query(None), end_date: Optional[str] = Query(None)):
    mgr = get_data_provider_manager()
    return mgr.get_south_flow()


@router.get('/api/market/index-history')
def get_index_history_v2(symbol: str = Query('sh000300'), start_date: str = Query(''), end_date: str = Query('')):
    if not start_date or not end_date:
        return {"success": False, "error": "require start_date and end_date params"}
    mgr = get_data_provider_manager()
    return mgr.get_index_daily(symbol)


@router.get('/api/hk/overview')
def get_hk_overview():
    mgr = get_data_provider_manager()
    return mgr.get_hk_market_overview()


@router.get('/api/hk/south-flow')
def get_hk_south_flow_v2():
    mgr = get_data_provider_manager()
    return mgr.get_south_flow()


@router.get('/api/hk/hot-rank')
def get_hk_hot_rank_v2():
    mgr = get_data_provider_manager()
    return mgr.get_hk_hot_rank()


@router.get('/api/hk/{symbol}/technical')
def get_hk_technical(symbol: str):
    try:
        from adapters.shared.services import hk_market_data_service
        result = hk_market_data_service.get_technical(symbol)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get('/api/hk/{symbol}/financials')
def get_hk_financials(symbol: str):
    mgr = get_data_provider_manager()
    return mgr.get_hk_financials(symbol)


@router.get('/api/hk/{symbol}/analysis')
def get_hk_analysis(symbol: str):
    try:
        from adapters.shared.services import hk_market_data_service
        result = hk_market_data_service.get_analysis(symbol)
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get('/api/market/sector/{sector:path}')
def get_sector_stocks(sector: str, max_pe: Optional[float] = Query(None), limit: int = Query(30)):
    limit = min(limit, 50)
    mgr = get_data_provider_manager()
    result = mgr.get_sector_stocks(sector)
    if not result.get('success'):
        return {"success": False, "error": result.get('error', 'No sector data available')}
    payload = result['data'].data
    if not payload.get('found'):
        return {"success": False, "error": f"Sector not found: {sector}"}
    stocks = payload.get('stocks', [])
    if not stocks:
        return {"success": False, "error": f"No stocks found in {sector}"}
    for s in stocks:
        s['market_cap_billion'] = round((s.pop('market_cap', 0) or 0) / 1e8, 2)
    if max_pe:
        stocks = [s for s in stocks if not (s['pe'] > max_pe and s['pe'] > 0)]
    stocks = stocks[:limit]
    return {
        'success': True,
        'data': {
            'sector': sector,
            'sector_code': payload.get('sector_code'),
            'stocks': sorted(stocks, key=lambda x: x['market_cap_billion'], reverse=True),
            'count': len(stocks),
            'source': result.get('source'),
        }
    }


@router.get('/api/stocks/market/overview')
def get_stocks_market_overview(market: Optional[str] = Query(None)):
    mgr = get_data_provider_manager()
    return mgr.get_market_overview()
