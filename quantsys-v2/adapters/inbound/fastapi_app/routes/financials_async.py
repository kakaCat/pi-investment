"""Financial Data V2 API - FastAPI 版（从 Flask financials_v2.py 迁移，响应契约保持一致）

注意：本路由不走 api_response 的 camelCase 转换——Flask 版直接 jsonify
{success, data: <service.to_dict() 原样>}，agent-ts data_fetch_financial 工具
依赖 snake_case 字段（report_type/periods/source 等）。
"""
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
import structlog

from adapters.shared.services import enhanced_financial_service

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["Financials V2 - 财务报表"])


@router.get('/api/v2/stock/{symbol}/financials')
def get_financial_data_v2(
    symbol: str,
    statement_type: str = Query('all'),
    periods: int = Query(4),
    source: str = Query('auto'),
):
    """获取财务报表数据（带缓存与熔断）。

    statement_type: income/balance/cash_flow/all
    source: auto/fresh/cache_only
    """
    if source not in ('auto', 'fresh', 'cache_only'):
        return JSONResponse(
            status_code=400,
            content={
                'success': False,
                'error': f"Invalid source parameter: {source}. Must be auto/fresh/cache_only",
            },
        )

    try:
        service = enhanced_financial_service
        data = service.get_financial_data(symbol, statement_type, periods, source)

        # 直接展开 to_dict() 内容，添加 cached 字段（与 Flask 版一致）
        result = data.to_dict() if hasattr(data, 'to_dict') else data.__dict__
        result['cached'] = service.was_cache_hit()

        return {'success': True, 'data': result}
    except Exception as e:
        logger.error(f"获取财务报表失败 {symbol}: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={'success': False, 'error': str(e)},
        )


@router.get('/api/v2/financials/stats')
def get_stats():
    """获取服务统计（缓存命中率等）"""
    service = get_enhanced_financial_service()
    return {'success': True, 'data': {'stats': service.get_stats()}}


@router.post('/api/v2/financials/cache/clear')
def clear_cache():
    """清空缓存"""
    service = get_enhanced_financial_service()
    service.clear_cache()
    return {'success': True, 'data': {'message': '缓存已清空'}}


@router.post('/api/v2/financials/stats/reset')
def reset_stats():
    """重置统计信息（保留缓存和熔断器状态）"""
    service = get_enhanced_financial_service()
    service.reset_stats()
    return {'success': True, 'data': {'message': '统计信息已重置'}}
