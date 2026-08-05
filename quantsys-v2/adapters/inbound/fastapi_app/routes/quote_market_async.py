"""
quote_market routes (FastAPI 版本)

从 Flask adapters/inbound/api/routes/quote_market.py 迁移：
- /api/stock/{symbol}/history    OHLCV 历史K线（database→网络源 多源降级）

响应契约与 Flask 版保持一致（成功走 api_response camelCase；失败保留
provider_errors/suggestion snake_case 字段，agent 工具链依赖这些字段自我纠正）。
"""
import logging
from datetime import datetime, timedelta

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from adapters.inbound.fastapi_app.shared import api_response
from adapters.inbound.api.shared import _aggregate_weekly, _aggregate_monthly
from adapters.inbound.api.routes.quote_market import _kline_failure_suggestion

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Quote Market - 行情数据"])


@router.get('/api/stock/{symbol}/history')
def get_stock_history(
    symbol: str,
    period: str = Query('daily', description='daily|weekly|monthly|1m|5m|15m|30m'),
    start_date: str = Query(None, description='开始日期 YYYY-MM-DD'),
    end_date: str = Query(None, description='结束日期 YYYY-MM-DD'),
    limit: int = Query(60, description='返回数据点数(最大200)'),
    source: str = Query('auto', description='数据源选择 auto|db|akshare'),
):
    """
    OHLCV 历史数据 - 替代旧 quant_cli stock.history

    支持多数据源自动降级：database (主) → 网络源 (备)
    日/周/月线优先从数据库获取，分钟线使用实时查询（仅A股，最近30天）
    """
    from adapters.outbound.datasources import get_data_provider_manager

    limit = min(limit, 200)

    end_date = end_date or datetime.now().strftime('%Y-%m-%d')
    if not start_date:
        lookback_days = {"daily": limit + 20, "weekly": limit * 10 + 20, "monthly": limit * 35 + 20}
        # 分钟级数据默认查询最近2天
        if period in ['1m', '5m', '15m', '30m', '60m']:
            lookback_days[period] = 2
        start_dt = datetime.strptime(end_date, '%Y-%m-%d') - timedelta(days=lookback_days.get(period, limit + 20))
        start_date = start_dt.strftime('%Y-%m-%d')

    provider_manager = get_data_provider_manager()

    try:
        result = provider_manager.get_klines(symbol, period, start_date, end_date)

        if not result['success']:
            error_msg = result.get('error', 'No kline data available')
            attempted = result.get('attempted_sources', [])
            provider_errors = result.get('provider_errors', {})
            return JSONResponse(status_code=404, content={
                "success": False,
                "error": f"{error_msg} (尝试数据源: {', '.join(attempted)})",
                "provider_errors": provider_errors,
                "suggestion": _kline_failure_suggestion(symbol, period, provider_errors),
            })

        klines = result['data']
        data_source = result['source']

        records = []
        for kline in klines:
            records.append({
                "date": kline.date,
                "open": kline.open,
                "high": kline.high,
                "low": kline.low,
                "close": kline.close,
                "volume": kline.volume,
                "change_pct": kline.change_pct,
            })

        # 应用周期聚合（如果需要）
        if period == 'weekly':
            records = _aggregate_weekly(records)
        elif period == 'monthly':
            records = _aggregate_monthly(records)

        # 限制返回数量
        records = records[-limit:]

        payload = {
            "symbol": symbol,
            "period": period,
            "count": len(records),
            "data": records,
            "source": data_source,  # 标识实际使用的数据源
        }
        # 000xxx 存在歧义：既是深市个股（如 000001 平安银行），也常被用来
        # 指上证指数。当前一律按深市个股解析，显式告知调用方防止静默错查。
        if symbol.split('.')[0].startswith('000'):
            payload["note"] = (
                "注意: 000xxx 代码按深市个股解析"
                "（000001=平安银行，而非上证指数）；上证指数K线暂不支持"
            )
        return api_response(payload)

    except Exception as e:
        logger.error(f"Failed to get kline data for {symbol}: {e}")
        return JSONResponse(status_code=500, content={
            "success": False,
            "error": f"获取K线数据失败: {str(e)}"
        })
