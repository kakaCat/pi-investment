"""Stock query helpers exposed through the QuantSys CLI."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timedelta
from typing import Any


def _disable_proxy_env() -> None:
    """Domestic market data APIs often fail through local proxy settings."""
    for key in list(os.environ):
        if key.lower().endswith("_proxy") or key.lower() == "no_proxy":
            os.environ.pop(key, None)
    os.environ["no_proxy"] = "*"


def get_stock_quote(symbol: str) -> dict[str, Any]:
    """Return an A-share or HK real-time quote."""
    if _is_hk_symbol(symbol):
        return _get_hk_stock_quote(symbol)
    return _get_a_share_quote(symbol)


def get_batch_stock_quotes(symbols: list[str]) -> dict[str, Any]:
    """Return real-time prices for multiple A-share or HK symbols."""
    prices: dict[str, float] = {}
    errors: list[dict[str, str]] = []

    for raw_symbol in symbols:
        symbol = _hk_code(raw_symbol) if _is_hk_symbol(raw_symbol) else _clean_symbol(raw_symbol)
        quote = get_stock_quote(raw_symbol)
        price = quote.get("price")
        if isinstance(price, (int, float)) and price > 0:
            prices[symbol] = float(price)
        else:
            errors.append({
                "symbol": symbol,
                "error": str(quote.get("error") or "价格不可用"),
            })

    return {
        "prices": prices,
        "errors": errors,
        "count": len(prices),
        "timestamp": datetime.now().isoformat(),
    }


def get_stock_list(market: str = "A") -> dict[str, Any]:
    """Return live stock universe data in the legacy bridge shape."""
    normalized_market = (market or "A").upper()
    if normalized_market not in {"A", "HK"}:
        return {"error": f"暂不支持市场: {market}", "stocks": []}

    try:
        _disable_proxy_env()
        import akshare as ak

        if normalized_market == "HK":
            frame = ak.stock_hk_spot_em()
            code_key = "代码"
            name_key = "名称"
            records = [
                {
                    "code": str(row.get(code_key, "")).zfill(5),
                    "symbol": str(row.get(code_key, "")).zfill(5),
                    "name": str(row.get(name_key, "")),
                    "market": "HK",
                    "market_cap": _safe_float(row.get("总市值", 0), decimals=0) / 100000000,
                    "pe": _safe_float(row.get("市盈率", 0)),
                    "pb": _safe_float(row.get("市净率", 0)),
                }
                for _, row in frame.iterrows()
            ]
        else:
            frame = ak.stock_zh_a_spot_em()
            records = [
                {
                    "code": str(row.get("代码", "")),
                    "symbol": str(row.get("代码", "")),
                    "name": str(row.get("名称", "")),
                    "market": "A",
                    "market_cap": _safe_float(row.get("总市值", 0), decimals=0) / 100000000,
                    "pe": _safe_float(row.get("市盈率-动态", 0)),
                    "pb": _safe_float(row.get("市净率", 0)),
                }
                for _, row in frame.iterrows()
            ]

        return {
            "stocks": records,
            "count": len(records),
            "data_date": datetime.now().strftime("%Y-%m-%d"),
        }
    except Exception as exc:
        return {"error": str(exc), "stocks": []}


def get_stock_info(symbol: str) -> dict[str, Any]:
    """Return basic A-share or HK stock profile data."""
    if _is_hk_symbol(symbol):
        quote = _get_hk_stock_quote(symbol)
        if "error" in quote:
            return quote
        return {
            "symbol": quote["symbol"],
            "name": quote.get("name") or quote["symbol"],
            "market": "HK",
            "price": quote.get("price"),
            "change_pct": quote.get("change_pct"),
            "pe_ttm": 0.0,
            "pb": 0.0,
            "market_cap_billion": 0.0,
            "data_date": datetime.now().strftime("%Y-%m-%d"),
        }

    clean = _clean_symbol(symbol)
    try:
        import requests

        _disable_proxy_env()
        market = _market_prefix(clean)
        response = requests.get(
            f"https://emweb.securities.eastmoney.com/PC_HSF10/CompanySurvey/PageAjax?code={market}{clean}",
            timeout=10,
        )
        payload = response.json()
        basic = (payload.get("jbzl") or [{}])[0]
        quote = _get_a_share_quote(clean)
        return {
            "symbol": clean,
            "name": basic.get("SECURITY_NAME_ABBR") or quote.get("name") or clean,
            "sector": basic.get("EM2016") or "",
            "market": "A",
            "pe_ttm": quote.get("pe_dynamic", 0.0),
            "pb": quote.get("pb", 0.0),
            "market_cap_billion": quote.get("market_cap_billion", 0.0),
            "total_shares": str(basic.get("REG_CAPITAL", "")),
            "circulating_shares": "",
            "listed_date": str(basic.get("LISTING_DATE", ""))[:10] if basic.get("LISTING_DATE") else "",
            "data_date": datetime.now().strftime("%Y-%m-%d"),
        }
    except Exception as exc:
        return {"error": str(exc), "symbol": clean}


def get_stock_history(
    symbol: str,
    period: str = "daily",
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int = 60,
) -> dict[str, Any]:
    """Return recent OHLCV history for A-shares or HK stocks."""
    if _is_hk_symbol(symbol):
        return _get_hk_stock_history(symbol, period, start_date, end_date, limit)
    return _get_a_share_history(symbol, period, limit)


def get_stock_news(symbol: str, num: int = 10) -> dict[str, Any]:
    """Return recent stock news/announcements from Eastmoney."""
    raw = _clean_symbol(symbol)
    market_symbol = _eastmoney_symbol(raw)
    result: dict[str, Any] = {
        "symbol": raw,
        "sources": [],
        "data": [],
        "data_date": datetime.now().strftime("%Y-%m-%d"),
    }

    # Source 1: Eastmoney announcements API (primary, verified working)
    try:
        _disable_proxy_env()
        import requests as _requests

        ann_url = "http://np-anotice-stock.eastmoney.com/api/security/ann"
        ann_params = {
            "sr": -1,
            "page_size": min(num, 50),
            "page_index": 1,
            "ann_type": "A",
            "client_source": "web",
            "stock_list": raw,
        }
        ann_resp = _requests.get(
            ann_url,
            params=ann_params,
            headers={
                "Referer": "https://data.eastmoney.com",
                "User-Agent": "Mozilla/5.0",
            },
            timeout=10,
        )
        if ann_resp.status_code == 200:
            ann_data = ann_resp.json()
            ann_items = ann_data.get("data", {}).get("list") or []
            if ann_items:
                result["data"].extend([
                    {
                        "title": str(item.get("title", "")),
                        "date": str(item.get("notice_date", "")),
                        "source": "公司公告",
                        "content": str(item.get("summary", ""))[:200],
                        "type": "announcement",
                    }
                    for item in ann_items[:num]
                ])
                result["sources"].append("eastmoney_announcements")
    except Exception as exc:
        result["eastmoney_ann_error"] = str(exc)

    # Source 2: AkShare fallback (may be unavailable due to upstream changes)
    if len(result["data"]) < num:
        try:
            import akshare as ak

            frame = ak.stock_news_em(symbol=market_symbol)
            if frame is not None and not frame.empty:
                for _, row in frame.head(num - len(result["data"])).iterrows():
                    result["data"].append({
                        "title": str(row.get("新闻标题", "")),
                        "date": str(row.get("发布时间", "")),
                        "source": str(row.get("文章来源", "")),
                        "content": str(row.get("新闻内容", ""))[:200],
                        "type": "news",
                    })
                result["sources"].append("eastmoney_news")
        except Exception as exc:
            result["eastmoney_news_error"] = str(exc)

    if not result["data"]:
        result["warning"] = "所有新闻源均无数据"
    result["count"] = len(result["data"])
    return result


def get_stock_announcements(symbol: str) -> dict[str, Any]:
    """Return recent A-share announcements from CNINFO via AkShare."""
    raw = _clean_symbol(symbol)
    end_date = datetime.now().strftime("%Y%m%d")
    start_date = (datetime.now() - timedelta(days=180)).strftime("%Y%m%d")
    try:
        _disable_proxy_env()
        import akshare as ak

        frame = ak.stock_zh_a_disclosure_report_cninfo(
            symbol=raw,
            market="沪深京",
            start_date=start_date,
            end_date=end_date,
        )
        if frame is None or frame.empty:
            return {"error": f"无公告数据: {raw}", "symbol": raw}
        records = json.loads(frame.head(20).to_json(orient="records", force_ascii=False))
        return {
            "symbol": raw,
            "count": len(records),
            "data": records,
            "data_date": datetime.now().strftime("%Y-%m-%d"),
        }
    except Exception as exc:
        return {"error": str(exc), "symbol": raw}


def _get_a_share_quote(symbol: str) -> dict[str, Any]:
    clean = _clean_symbol(symbol)
    try:
        import requests

        _disable_proxy_env()
        response = requests.get(
            f"https://hq.sinajs.cn/list={_sina_symbol(clean)}",
            headers={"Referer": "https://finance.sina.com.cn", "User-Agent": "Mozilla/5.0"},
            timeout=10,
        )
        response.encoding = "gbk"
        fields = _parse_sina_realtime(response.text)
        if not fields or not fields.get("price"):
            return {"error": f"未找到: {clean}", "symbol": clean}

        price = _safe_float(fields["price"])
        prev_close = _safe_float(fields["prev_close"])
        quote = _fetch_eastmoney_quote(clean)
        return {
            "symbol": clean,
            "name": fields["name"],
            "price": price,
            "change_pct": round((price - prev_close) / prev_close * 100, 2) if prev_close else 0.0,
            "change_amount": round(price - prev_close, 3),
            "volume": _safe_float(fields["volume"], decimals=0),
            "amount": _safe_float(fields["amount"], decimals=0),
            "high": _safe_float(fields["high"]),
            "low": _safe_float(fields["low"]),
            "open": _safe_float(fields["open"]),
            "prev_close": prev_close,
            "turnover_rate": 0.0,
            "pe_dynamic": quote["pe_dynamic"],
            "pb": quote["pb"],
            "market_cap_billion": quote["market_cap_billion"],
            "data_date": f"{fields['date']} {fields['time']}",
        }
    except Exception as exc:
        return {"error": str(exc), "symbol": clean}


def _get_hk_stock_quote(symbol: str) -> dict[str, Any]:
    code = _hk_code(symbol)
    try:
        import requests

        _disable_proxy_env()
        response = requests.get(
            f"https://hq.sinajs.cn/list=hk{code}",
            headers={"Referer": "https://finance.sina.com.cn", "User-Agent": "Mozilla/5.0"},
            timeout=10,
        )
        response.encoding = "gbk"
        fields = _parse_sina_hk_realtime(response.text)
        if not fields or not fields.get("price"):
            return {"error": f"未找到港股: {symbol} (code={code})", "symbol": code}
        return {
            "symbol": code,
            "name": fields["name"],
            "price": _safe_float(fields["price"]),
            "change_pct": _safe_float(fields["change_pct"]),
            "change_amount": _safe_float(fields["change_amount"]),
            "volume": _safe_float(fields["volume"], decimals=0),
            "amount": _safe_float(fields["amount"], decimals=0),
            "high": _safe_float(fields["high"]),
            "low": _safe_float(fields["low"]),
            "open": _safe_float(fields["open"]),
            "prev_close": _safe_float(fields["prev_close"]),
            "market": "HK",
            "data_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
    except Exception as exc:
        return {"error": str(exc), "symbol": code}


def _get_a_share_history(symbol: str, period: str, limit: int) -> dict[str, Any]:
    clean = _clean_symbol(symbol)
    scale_map = {"daily": 240, "weekly": 1200, "monthly": 4800}
    scale = scale_map.get(period, 240)
    try:
        import requests

        _disable_proxy_env()
        response = requests.get(
            "https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData",
            params={"symbol": _sina_symbol(clean), "scale": scale, "ma": "no", "datalen": limit},
            headers={"Referer": "https://finance.sina.com.cn", "User-Agent": "Mozilla/5.0"},
            timeout=10,
        )
        rows = response.json() or []
        records = []
        prev_close = None
        for item in rows[-limit:]:
            close = _safe_float(item.get("close", 0))
            records.append({
                "date": item.get("day", ""),
                "open": _safe_float(item.get("open", 0)),
                "high": _safe_float(item.get("high", 0)),
                "low": _safe_float(item.get("low", 0)),
                "close": close,
                "volume": _safe_float(item.get("volume", 0), decimals=0),
                "change_pct": round((close - prev_close) / prev_close * 100, 2) if prev_close else 0.0,
            })
            prev_close = close
        if not records:
            return {"error": f"无历史数据: {clean}", "symbol": clean}
        return {
            "symbol": clean,
            "period": period,
            "count": len(records),
            "data": records,
            "data_date": datetime.now().strftime("%Y-%m-%d"),
        }
    except Exception as exc:
        return {"error": str(exc), "symbol": clean}


def _get_hk_stock_history(
    symbol: str,
    period: str,
    start_date: str | None,
    end_date: str | None,
    limit: int,
) -> dict[str, Any]:
    code = _hk_code(symbol)
    end = end_date or datetime.now().strftime("%Y%m%d")
    start = start_date or (datetime.now() - timedelta(days=180)).strftime("%Y%m%d")
    try:
        _disable_proxy_env()
        import akshare as ak

        frame = ak.stock_hk_hist(
            symbol=code,
            period=period,
            start_date=start,
            end_date=end,
            adjust="qfq",
        )
        if frame is None or frame.empty:
            return {"error": f"无历史数据: {symbol}", "symbol": code}
        records = []
        prev_close = None
        for _, row in frame.tail(limit).iterrows():
            close = float(row["收盘"])
            records.append({
                "date": str(row["日期"]),
                "open": float(row["开盘"]),
                "high": float(row["最高"]),
                "low": float(row["最低"]),
                "close": close,
                "volume": float(row["成交量"]),
                "change_pct": round((close - prev_close) / prev_close * 100, 2) if prev_close else 0.0,
            })
            prev_close = close
        return {
            "symbol": code,
            "period": period,
            "market": "HK",
            "count": len(records),
            "data": records,
            "data_date": datetime.now().strftime("%Y-%m-%d"),
        }
    except Exception as exc:
        return {"error": str(exc), "symbol": code}


def _fetch_eastmoney_quote(symbol: str) -> dict[str, float | str]:
    try:
        import requests

        response = requests.get(
            "https://datacenter-web.eastmoney.com/api/data/v1/get",
            params={
                "reportName": "RPT_VALUEANALYSIS_DET",
                "columns": "SECUCODE,PE_TTM,PB_MRQ,TOTAL_MARKET_CAP",
                "filter": f'(SECUCODE="{symbol}.{_market_prefix(symbol)}")',
                "pageSize": 1,
            },
            headers={"Referer": "https://finance.eastmoney.com", "User-Agent": "Mozilla/5.0"},
            timeout=8,
        )
        payload = response.json()
        rows = payload.get("result", {}).get("data") or []
        if rows:
            row = rows[0]
            market_cap = _safe_float(row.get("TOTAL_MARKET_CAP", 0), decimals=0)
            return {
                "pe_dynamic": _safe_float(row.get("PE_TTM", 0)),
                "pb": _safe_float(row.get("PB_MRQ", 0)),
                "market_cap_billion": round(market_cap / 1e8, 2) if market_cap > 0 else 0.0,
                "pe_source": "datacenter",
            }
    except Exception:
        pass
    return {
        "pe_dynamic": 0.0,
        "pb": 0.0,
        "market_cap_billion": 0.0,
        "pe_source": "unavailable",
    }


def _clean_symbol(symbol: str) -> str:
    return symbol.replace("sh", "").replace("sz", "").replace("bj", "").strip()


def _market_prefix(symbol: str) -> str:
    clean = _clean_symbol(symbol)
    if clean.startswith("6"):
        return "SH"
    if clean.startswith(("8", "4")):
        return "BJ"
    return "SZ"


def _sina_symbol(symbol: str) -> str:
    clean = _clean_symbol(symbol)
    if clean.startswith("6"):
        return f"sh{clean}"
    if clean.startswith(("0", "3")):
        return f"sz{clean}"
    if clean.startswith(("8", "4")):
        return f"bj{clean}"
    return f"sh{clean}"


def _eastmoney_symbol(symbol: str) -> str:
    clean = _clean_symbol(symbol)
    return f"{_market_prefix(clean)}{clean}"


def _is_hk_symbol(symbol: str) -> bool:
    value = symbol.upper().strip()
    if value.endswith(".HK"):
        value = value[:-3]
    return value.isdigit() and 1 <= len(value) <= 5


def _hk_code(symbol: str) -> str:
    value = symbol.upper().strip()
    if value.endswith(".HK"):
        value = value[:-3]
    return value.zfill(5)


def _safe_float(value: Any, default: float = 0.0, decimals: int = 2) -> float:
    try:
        number = float(value)
        if number != number or number in {float("inf"), float("-inf")}:
            return default
        return round(number, decimals)
    except (TypeError, ValueError):
        return default


def _parse_sina_realtime(raw: str) -> dict[str, str]:
    match = re.search(r'"([^"]*)"', raw)
    if not match:
        return {}
    fields = match.group(1).strip().split(",")
    if len(fields) < 32:
        return {}
    return {
        "name": fields[0],
        "open": fields[1],
        "prev_close": fields[2],
        "price": fields[3],
        "high": fields[4],
        "low": fields[5],
        "volume": fields[8],
        "amount": fields[9],
        "date": fields[30],
        "time": fields[31],
    }


def _parse_sina_hk_realtime(raw: str) -> dict[str, str]:
    match = re.search(r'"([^"]*)"', raw)
    if not match:
        return {}
    fields = match.group(1).strip().split(",")
    if len(fields) < 8:
        return {}
    return {
        "name": fields[0],
        "prev_close": fields[2],
        "open": fields[3],
        "high": fields[4],
        "low": fields[5],
        "price": fields[6],
        "change_amount": fields[7],
        "change_pct": fields[8] if len(fields) > 8 else "0",
        "volume": fields[9] if len(fields) > 9 else "0",
        "amount": fields[10] if len(fields) > 10 else "0",
    }


# === Daemon handler registration ===

from .daemon import register_daemon_method
from .context import build_context


def register_daemon_handlers() -> None:
    build_context(db_path=None, output_dir=None, python="python3")

    def _get_stock_info(params):
        return get_stock_info(params.get("symbol"))

    def _get_stock_quote(params):
        return get_stock_quote(params.get("symbol"))

    def _get_stock_history(params):
        return get_stock_history(
            symbol=params.get("symbol"),
            period=params.get("period", "daily"),
            start_date=params.get("start_date"),
            end_date=params.get("end_date"),
            limit=params.get("limit", 60),
        )

    def _get_stock_news(params):
        return get_stock_news(
            symbol=params.get("symbol"),
            num=params.get("limit", 10),
        )

    def _get_stock_announcements(params):
        return get_stock_announcements(params.get("symbol"))

    register_daemon_method("get_stock_info", _get_stock_info)
    register_daemon_method("get_stock_price", _get_stock_quote)
    register_daemon_method("get_stock_realtime_price", _get_stock_quote)
    register_daemon_method("get_stock_history", _get_stock_history)
    register_daemon_method("get_stock_news", _get_stock_news)
    register_daemon_method("get_announcements", _get_stock_announcements)
