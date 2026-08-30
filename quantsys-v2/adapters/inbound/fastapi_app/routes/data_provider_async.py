"""Unified DataProvider API — all DataProviderManager methods exposed as HTTP endpoints.

This is the SINGLE source of truth for data provider HTTP APIs.
All endpoints return {"success": bool, "data": ..., "source": str}.
"""
from typing import List, Optional
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from adapters.outbound.datasources import get_data_provider_manager

router = APIRouter(prefix="/api/provider", tags=["DataProvider"])


def _call(method_name: str, *args, **kwargs):
    mgr = get_data_provider_manager()
    fn = getattr(mgr, method_name, None)
    if fn is None:
        return JSONResponse(status_code=404, content={"success": False, "error": f"Method {method_name} not found"})
    return fn(*args, **kwargs)


# ==================== Quote ====================

@router.get("/quote/{symbol}")
def get_quote(symbol: str):
    return _call("get_quote", symbol)


@router.get("/quotes")
def get_batch_quotes(symbols: str = Query(..., description="Comma-separated symbols")):
    symbol_list = [s.strip() for s in symbols.split(",") if s.strip()]
    return _call("get_quotes", symbol_list)


# ==================== Kline ====================

@router.get("/kline/{symbol}")
def get_kline(
    symbol: str,
    start_date: str = Query(...),
    end_date: str = Query(...),
    period: str = Query("daily"),
):
    return _call("get_klines", symbol, period, start_date, end_date)


# ==================== Financial ====================

@router.get("/financial/{symbol}")
def get_financial(symbol: str, report_type: str = Query("latest")):
    return _call("get_financial", symbol, report_type=report_type)


@router.get("/financial/{symbol}/sina-statements")
def get_sina_financial_statements(symbol: str):
    return _call("get_sina_financial_statements", symbol)


@router.get("/financial/{symbol}/analysis-indicator")
def get_financial_analysis_indicator(symbol: str):
    return _call("get_financial_analysis_indicator", symbol)


@router.get("/financial/{symbol}/cash-flow")
def get_cash_flow_sheet(symbol: str):
    return _call("get_cash_flow_sheet", symbol)


@router.get("/financial/{symbol}/profit-sheet")
def get_profit_sheet(symbol: str):
    return _call("get_profit_sheet", symbol)


# ==================== Dividend ====================

@router.get("/dividend/{symbol}")
def get_dividends(symbol: str, years: int = Query(5)):
    return _call("get_dividends", symbol, years=years)


@router.get("/dividend-calendar")
def get_dividend_calendar(start_date: str = Query(""), end_date: str = Query("")):
    return _call("get_dividend_calendar", start_date, end_date)


@router.get("/screen-high-dividend")
def screen_high_dividend(min_yield: float = Query(3.0), min_years: int = Query(5)):
    return _call("screen_high_dividend", min_yield=min_yield, min_years=min_years)


# ==================== Market ====================

@router.get("/market/overview")
def get_market_overview():
    return _call("get_market_overview")


@router.get("/market/spot")
def get_market_spot():
    return _call("get_market_spot")


@router.get("/market/macro")
def get_macro_data():
    return _call("get_macro_data")


@router.get("/market/news")
def get_market_news():
    return _call("get_market_news")


@router.get("/market/margin")
def get_market_margin():
    return _call("get_market_margin")


@router.get("/market/sector-flow")
def get_sector_fund_flow(indicator: str = Query("今日")):
    return _call("get_sector_fund_flow", indicator)


# ==================== Sector ====================

@router.get("/sector/{sector}/stocks")
def get_sector_stocks(sector: str):
    return _call("get_sector_stocks", sector)


@router.get("/sectors")
def get_sector_list():
    return _call("get_sector_list")


# ==================== LHB (龙虎榜) ====================

@router.get("/lhb/{symbol}/{date}")
def get_lhb_stock(symbol: str, date: str):
    return _call("get_lhb_stock", symbol, date)


@router.get("/lhb/daily/{date}")
def get_lhb_daily(date: str):
    return _call("get_lhb_daily", date)


@router.get("/lhb/detail/{symbol}")
def get_lhb_detail(symbol: str, start_date: str = Query(""), end_date: str = Query("")):
    return _call("get_lhb_detail", symbol, start_date, end_date)


@router.get("/zt-pool/{date}")
def get_zt_pool(date: str):
    return _call("get_zt_pool", date)


# ==================== HK ====================

@router.get("/hk/overview")
def get_hk_market_overview():
    return _call("get_hk_market_overview")


@router.get("/hk/south-flow")
def get_south_flow():
    return _call("get_south_flow")


@router.get("/hk/hot-rank")
def get_hk_hot_rank():
    return _call("get_hk_hot_rank")


@router.get("/hk/{symbol}/daily")
def get_hk_daily(symbol: str):
    return _call("get_hk_daily", symbol)


@router.get("/hk/{symbol}/financials")
def get_hk_financials(symbol: str):
    return _call("get_hk_financials", symbol)


# ==================== Stock ====================

@router.get("/stock/{symbol}/announcements")
def get_announcements(symbol: str):
    return _call("get_announcements", symbol)


@router.get("/stock/{symbol}/news")
def get_news(symbol: str, num: int = Query(10)):
    return _call("get_news", symbol, num=num)


@router.get("/stock/{symbol}/insider-trades")
def get_insider_trades(symbol: str):
    return _call("get_insider_trades", symbol)


# ==================== Index ====================

@router.get("/index/{symbol}/daily")
def get_index_daily(symbol: str):
    return _call("get_index_daily", symbol)


@router.get("/index/{symbol}/constituents")
def get_index_constituents(symbol: str):
    return _call("get_index_constituents", symbol)


# ==================== Calendar ====================

@router.get("/trading-calendar")
def get_trading_calendar(start_date: str = Query(""), end_date: str = Query("")):
    return _call("get_trading_calendar", start_date, end_date)


# ==================== Health / Stats ====================

@router.get("/health")
def get_provider_health():
    return _call("get_provider_health")


@router.get("/stats")
def get_provider_stats():
    return _call("get_provider_stats")
