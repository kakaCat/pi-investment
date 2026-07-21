"""L1 Data Layer handlers."""
import json
from typing import Any, Dict
from infrastructure.daemon.registry import register_method
from infrastructure.daemon.handlers.api_client import call_api


@register_method("get_stock_info")
async def get_stock_info(params: dict) -> str:
    """
    Get basic stock information.

    Params:
        symbol: Stock symbol (required)

    Returns:
        JSON string with stock info
    """
    symbol = params.get("symbol")
    if not symbol:
        raise ValueError("Parameter 'symbol' is required")

    # Call API
    data = await call_api("GET", f"/api/stocks/{symbol}")

    return json.dumps(data, ensure_ascii=False)


@register_method("get_stock_price")
async def get_stock_price(params: dict) -> str:
    """
    Get stock price data.

    Params:
        symbol: Stock symbol (required)
        start_date: Start date (optional, format: YYYY-MM-DD)
        end_date: End date (optional, format: YYYY-MM-DD)

    Returns:
        JSON string with price data
    """
    symbol = params.get("symbol")
    if not symbol:
        raise ValueError("Parameter 'symbol' is required")

    # Build query params
    query_params = []
    if params.get("start_date"):
        query_params.append(f"start_date={params['start_date']}")
    if params.get("end_date"):
        query_params.append(f"end_date={params['end_date']}")

    query_string = "?" + "&".join(query_params) if query_params else ""

    # Call API
    data = await call_api("GET", f"/api/stocks/{symbol}/prices{query_string}")

    return json.dumps(data, ensure_ascii=False)


@register_method("get_stock_fundamentals")
async def get_stock_fundamentals(params: dict) -> str:
    """
    Get stock fundamental data.

    Params:
        symbol: Stock symbol (required)

    Returns:
        JSON string with fundamental data
    """
    symbol = params.get("symbol")
    if not symbol:
        raise ValueError("Parameter 'symbol' is required")

    data = await call_api("GET", f"/api/stocks/{symbol}/fundamentals")

    return json.dumps(data, ensure_ascii=False)


@register_method("get_stock_realtime_price")
async def get_stock_realtime_price(params: dict) -> str:
    """
    Get real-time stock price (quote).

    Params:
        symbol: Stock symbol (required)

    Returns:
        JSON string with real-time price data
    """
    symbol = params.get("symbol")
    if not symbol:
        raise ValueError("Parameter 'symbol' is required")

    data = await call_api("GET", f"/api/stock/{symbol}/quote")

    return json.dumps(data, ensure_ascii=False)


@register_method("get_stock_news")
async def get_stock_news(params: dict) -> str:
    """
    Get stock news.

    Params:
        symbol: Stock symbol (required)
        num: Number of news items (optional, default: 10)

    Returns:
        JSON string with news data
    """
    symbol = params.get("symbol")
    if not symbol:
        raise ValueError("Parameter 'symbol' is required")

    num = params.get("num", 10)
    data = await call_api("GET", f"/api/stock/{symbol}/news?limit={num}")

    return json.dumps(data, ensure_ascii=False)


@register_method("get_announcements")
async def get_announcements(params: dict) -> str:
    """
    Get stock announcements.

    Params:
        symbol: Stock symbol (required)

    Returns:
        JSON string with announcements data
    """
    symbol = params.get("symbol")
    if not symbol:
        raise ValueError("Parameter 'symbol' is required")

    data = await call_api("GET", f"/api/stock/{symbol}/announcements")

    return json.dumps(data, ensure_ascii=False)


@register_method("get_stock_history")
async def get_stock_history(params: dict) -> str:
    """
    Get historical K-line data (OHLCV).

    Params:
        symbol: Stock symbol (required)
        period: Period type - daily/weekly/monthly (optional, default: daily)
        start_date: Start date in YYYYMMDD or YYYY-MM-DD format (optional)
        end_date: End date in YYYYMMDD or YYYY-MM-DD format (optional)

    Returns:
        JSON string with K-line data
    """
    symbol = params.get("symbol")
    if not symbol:
        raise ValueError("Parameter 'symbol' is required")

    # Convert date format: YYYYMMDD → YYYY-MM-DD
    def format_date(date_str):
        if not date_str:
            return None
        date_str = str(date_str)
        # If YYYYMMDD format (8 digits), convert to YYYY-MM-DD
        if len(date_str) == 8 and date_str.isdigit():
            return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
        return date_str

    # Build query parameters
    query_params = []
    if params.get("period"):
        query_params.append(f"period={params['period']}")

    start_date = format_date(params.get("start_date"))
    if start_date:
        query_params.append(f"start_date={start_date}")

    end_date = format_date(params.get("end_date"))
    if end_date:
        query_params.append(f"end_date={end_date}")

    query_string = "?" + "&".join(query_params) if query_params else ""

    data = await call_api("GET", f"/api/stock/{symbol}/klines{query_string}")

    return json.dumps(data, ensure_ascii=False)


@register_method("search_stocks")
async def search_stocks(params: dict) -> str:
    """
    Search for stocks by query string.

    Params:
        query: Search query (required)
        limit: Maximum number of results (optional, default: 20)

    Returns:
        JSON string with search results
    """
    query = params.get("query")
    if not query:
        raise ValueError("Parameter 'query' is required")

    limit = params.get("limit", 20)
    data = await call_api("GET", f"/api/stocks/search?q={query}&limit={limit}")

    return json.dumps(data, ensure_ascii=False)


@register_method("get_market_data")
async def get_market_data(params: dict) -> str:
    """
    Get market overview data.

    Params:
        None required

    Returns:
        JSON string with market overview data
    """
    data = await call_api("GET", "/api/market/overview")

    return json.dumps(data, ensure_ascii=False)


@register_method("update_stock_data")
async def update_stock_data(params: dict) -> str:
    """
    Trigger stock data update.

    Params:
        symbol: Stock symbol (required)

    Returns:
        JSON string with update status
    """
    symbol = params.get("symbol")
    if not symbol:
        raise ValueError("Parameter 'symbol' is required")

    data = await call_api("POST", f"/api/stocks/{symbol}/update", data={})

    return json.dumps(data, ensure_ascii=False)
