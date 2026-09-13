"""分红数据 API — migrated to DataProviderManager."""
import re
from typing import Any, Dict, Optional

from fastapi import APIRouter, Query, Body
from fastapi.responses import JSONResponse
import structlog

from adapters.outbound.datasources import get_data_provider_manager

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["Dividends - 分红"])

# A 股代码：6 位数字，允许 .SH/.SZ/.BJ 后缀或 sh/sz/bj 前缀
_A_SHARE_RE = re.compile(r'^(?:\d{6})(?:\.(?:SH|SZ|BJ))?$', re.IGNORECASE)


def _normalize_a_symbol(symbol: str) -> Optional[str]:
    """把 600519 / 600519.SH / 600519.sh 归一为 6 位代码；非 A 股代码返回 None。

    2026-09-13（w-32314d00，看板事件 a80adf91 / f089ee31 / 5f0ac25a）：
    本端点原先对 symbol 不做任何格式校验，任意字符串（实测 `GET /api/stock/INVALID/dividends`）
    都会被扇出到全部数据源，每个源各报一次错 —— 一条客户端低级错误因此变成一串
    ERROR 级日志并被采集为错误事件（实测 9 次/日、连续 3 天）。而且响应还是 **HTTP 200**
    （body 里写 All data providers failed），调用方无法从状态码看出请求本身有问题。
    故在入口校验格式：不合格直接 400，不下发、不产生 ERROR。
    """
    raw = str(symbol or '').strip()
    return raw.split('.')[0] if _A_SHARE_RE.match(raw) else None


@router.get('/api/stock/{symbol}/dividends')
def get_dividends(symbol: str, years: int = Query(10)):
    code = _normalize_a_symbol(symbol)
    if code is None:
        # 客户端错误：用 WARNING 而不是 ERROR（等级不匹配会让错误台账被无效请求淹没）
        logger.warning(f"GET /api/stock/{symbol}/dividends - 拒绝：symbol 不是 A 股 6 位代码")
        return JSONResponse(status_code=400, content={
            'success': False,
            'error': f'无效的股票代码: {symbol!r}（需要 A 股 6 位数字，如 600519）',
        })
    logger.info(f"GET /api/stock/{symbol}/dividends - years={years}")
    mgr = get_data_provider_manager()
    return mgr.get_dividends(code, years=years)


@router.post('/api/dividends/screen')
def screen_dividends(payload: Optional[Dict[str, Any]] = Body(None)):
    params = payload or {}
    min_yield = params.get('min_yield', 3.0)
    min_years = params.get('min_years', 5)
    logger.info(f"POST /api/dividends/screen - min_yield={min_yield}, min_years={min_years}")
    mgr = get_data_provider_manager()
    return mgr.screen_high_dividend(min_yield=min_yield, min_years=min_years)


@router.get('/api/dividends/calendar')
def dividend_calendar(start_date: Optional[str] = Query(None), end_date: Optional[str] = Query(None), event: str = Query('ex_dividend')):
    if not start_date or not end_date:
        return JSONResponse(status_code=400, content={"success": False, "error": "start_date and end_date are required"})
    logger.info(f"GET /api/dividends/calendar - {start_date} to {end_date}, event={event}")
    mgr = get_data_provider_manager()
    return mgr.get_dividend_calendar(start_date, end_date)
