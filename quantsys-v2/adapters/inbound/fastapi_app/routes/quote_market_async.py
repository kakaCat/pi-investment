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
from adapters.shared.quote_helpers import _kline_failure_suggestion

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Quote Market - 行情数据"])


def _aggregate_kline_records(records, freq):
    """将日K记录聚合为周/月K（records 含 date/open/high/low/close/volume）。

    Flask 旧版复用只认 trade_date 的 _aggregate_weekly/_aggregate_monthly，
    records 的 date 列对不上导致 resample 恒 500；这里直接在 date 索引上重采样。
    若数据源本身返回周/月K（如 baostock 原生 frequency=w/m），重采样幂等
    （每个周期仅一条记录，first/max/min/last/sum 后值不变），仅日期标签归一到周期末。
    """
    import pandas as pd
    if not records:
        return []
    df = pd.DataFrame(records)
    df['date'] = pd.to_datetime(df['date'])
    df.set_index('date', inplace=True)
    out = df.resample(freq).agg({
        'open': 'first', 'high': 'max', 'low': 'min',
        'close': 'last', 'volume': 'sum',
    }).dropna()
    out['change_pct'] = (out['close'].pct_change() * 100).round(2).fillna(0.0)
    out.reset_index(inplace=True)
    out['date'] = out['date'].dt.strftime('%Y-%m-%d')
    return out.to_dict('records')


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

    # 标记用户是否显式指定了 start_date（用于后续判断是否应用 limit 截断）
    user_specified_start_date = start_date is not None

    end_date = end_date or datetime.now().strftime('%Y-%m-%d')
    if not start_date:
        lookback_days = {"daily": limit + 20, "weekly": limit * 10 + 20, "monthly": limit * 35 + 20}
        # 分钟级数据默认查询最近2天
        if period in ['1m', '5m', '15m', '30m', '60m']:
            lookback_days[period] = 2
        start_dt = datetime.strptime(end_date, '%Y-%m-%d') - timedelta(days=lookback_days.get(period, limit + 20))
        start_date = start_dt.strftime('%Y-%m-%d')

    provider_manager = get_data_provider_manager()
    # 周/月线按日线取数后聚合：数据库只存日线，传 weekly/monthly 会绕过本地缓存
    # 直接打网络源（慢且易被封）；分钟线原样透传
    fetch_period = 'daily' if period in ('weekly', 'monthly') else period

    try:
        result = provider_manager.get_klines(symbol, fetch_period, start_date, end_date)

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
            records = _aggregate_kline_records(records, 'W')
        elif period == 'monthly':
            records = _aggregate_kline_records(records, 'ME')

        # 限制返回数量
        # 修复逻辑（2026-08-19）：当用户显式指定 start_date 时，应返回该日期范围的
        # 完整数据，而非被 limit 截断。limit 的原始设计是为"最近N条"语义（未指定
        # start_date），但用户指定了 start_date=2026-01-01 却只拿到最后60条的行为
        # 违反直觉且导致数据缺失（GitHub issue: data_fetch_kline 一直缺数据）。
        # 新逻辑：显式指定 start_date → 返回完整范围（最多500条保护上限）
        #         未指定 start_date → 返回最近 limit 条（保持原语义）
        if user_specified_start_date:
            # 用户显式指定了 start_date，返回完整数据（设置保护上限 500）
            effective_limit = min(len(records), 500)
            records = records[-effective_limit:] if len(records) > effective_limit else records
        else:
            # 未指定 start_date，保持"最近 limit 条"语义
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
