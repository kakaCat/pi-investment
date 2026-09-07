"""Financial Data V2 API — migrated to DataProviderManager."""
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
import structlog

from adapters.outbound.datasources import get_data_provider_manager
from adapters.shared.services import get_stock_repo

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
        # 2026-09-01：补充 PE/PB（stocks 表有估值字段，报表源无）——此前
        # data_fetch_financial 工具硬编码 pe_ttm=0/pb=0，估值维度失真。
        # 表字段是 pe/pb；PE-TTM 暂无单独字段，用 pe 作为静态市盈率近似。
        if isinstance(result, dict) and result.get('data') is not None:
            data = result['data']
            # data 可能是 FinancialData dataclass（非 dict），统一转 dict 再补字段
            if not isinstance(data, dict):
                try:
                    from dataclasses import asdict
                    data = asdict(data)
                except Exception:
                    data = None
            if isinstance(data, dict):
                try:
                    repo = get_stock_repo()
                    stock = repo.get_by_symbol(symbol)
                    if stock:
                        pe = getattr(stock, 'pe', None)
                        pb = getattr(stock, 'pb', None)
                        data['pe'] = float(pe) if pe is not None else None
                        data['pb'] = float(pb) if pb is not None else None
                        data['pe_ttm'] = float(pe) if pe is not None else None
                except Exception as e:
                    logger.warning(f"补充 PE/PB 失败 {symbol}: {e}")
                result['data'] = data
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
