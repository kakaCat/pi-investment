"""Financial Data V2 API — migrated to DataProviderManager."""
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
import structlog

from adapters.outbound.datasources import get_data_provider_manager

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["Financials V2 - 财务报表"])


@router.get('/api/v2/stock/{symbol}/financials')
def get_financial_data_v2(
    symbol: str,
    statement_type: str = Query('all'),
    periods: int = Query(4),
    source: str = Query('auto'),
):
    """获取财务报表数据（通过 DataProviderManager）"""
    try:
        mgr = get_data_provider_manager()
        result = mgr.get_financial(symbol, report_type='latest')
        return result
    except Exception as e:
        logger.error(f"获取财务报表失败 {symbol}: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={'success': False, 'error': str(e)},
        )


@router.get('/api/v2/financials/stats')
def get_stats():
    """获取 provider 健康统计"""
    mgr = get_data_provider_manager()
    return {'success': True, 'data': mgr.get_provider_stats()}
