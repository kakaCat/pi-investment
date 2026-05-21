"""Sector screening helpers exposed through the QuantSys CLI."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from .analysis_query import get_quality_score
from .stock_query import _disable_proxy_env, _safe_float


def screen_stocks_by_sector(
    sector: str,
    min_roe: float | None = None,
    max_pe: float | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    """Screen stocks in one industry sector using Eastmoney/AkShare data."""
    try:
        _disable_proxy_env()
        import akshare as ak

        frame = ak.stock_board_industry_cons_em(symbol=sector)
        if frame is None or frame.empty:
            return {
                "error": f"未找到板块: {sector}",
                "sector": sector,
                "suggestion": "使用 get_sector_list 或 market.sectors 查询可用行业名称",
            }

        rows = []
        for _, row in frame.head(max(int(limit or 20), 1)).iterrows():
            stock = {
                "code": str(row.get("代码", "")),
                "name": str(row.get("名称", "")),
                "price": _safe_float(row.get("最新价", 0)),
                "change_pct": _safe_float(row.get("涨跌幅", 0)),
            }
            if "市盈率-动态" in row:
                stock["pe"] = _safe_float(row.get("市盈率-动态", 0))
            if "净资产收益率" in row:
                stock["roe"] = _safe_float(row.get("净资产收益率", 0))
            rows.append(stock)

        if max_pe is not None:
            rows = [item for item in rows if item.get("pe", 0) > 0 and item["pe"] <= float(max_pe)]
        if min_roe is not None:
            rows = [item for item in rows if item.get("roe", 0) >= float(min_roe)]

        bounded_limit = max(int(limit or 20), 1)
        return {
            "sector": sector,
            "count": len(rows),
            "data": rows[:bounded_limit],
            "data_date": _today(),
        }
    except Exception as exc:
        message = str(exc)
        if "Connection" in message or "Proxy" in message or "Remote" in message:
            return {
                "error": f"网络连接失败，无法获取板块数据: {sector}",
                "sector": sector,
                "suggestion": "请检查网络连接或稍后重试。建议使用 get_stock_info 查询个股信息",
                "technical_error": message[:200],
            }
        return {
            "error": f"板块筛选失败: {message[:200]}",
            "sector": sector,
            "suggestion": "使用 get_stock_info 查询个股信息",
        }


def screen_stocks_quality(
    sector: str,
    min_score: int = 50,
    max_pe: float | None = None,
    limit: int = 10,
) -> dict[str, Any]:
    """Screen sector stocks and rank them by quality score."""
    try:
        raw = screen_stocks_by_sector(sector, max_pe=max_pe, limit=30)
        if "error" in raw:
            suggestions = _sector_suggestions(sector)
            if suggestions:
                return {
                    "error": f"未找到板块: {sector}",
                    "sector": sector,
                    "suggestions": suggestions,
                    "hint": "请使用建议的板块名重试",
                }
            return raw

        candidates = raw.get("data", [])
        if not candidates:
            return {"error": f"板块无候选股票: {sector}", "sector": sector}

        scored = []
        for stock in candidates[:30]:
            symbol = str(stock.get("code") or stock.get("symbol") or "")
            if not symbol:
                continue
            quality = get_quality_score(symbol)
            if "error" in quality:
                continue
            details = quality.get("details", {})
            scored.append({
                "symbol": symbol,
                "name": stock.get("name", quality.get("symbol", symbol)),
                "pe": stock.get("pe", 0),
                "price": stock.get("price", 0),
                "score": quality["score"],
                "grade": quality["grade"],
                "roe": details.get("roe", 0),
                "debt_ratio": details.get("debt_ratio", 0),
                "gross_margin": details.get("gross_margin", 0),
            })

        threshold = int(min_score if min_score is not None else 50)
        filtered = [item for item in scored if item["score"] >= threshold]
        filtered.sort(key=lambda item: item["score"], reverse=True)
        bounded_limit = max(int(limit or 10), 1)
        return {
            "sector": sector,
            "total_screened": len(candidates),
            "qualified": len(filtered),
            "min_score": threshold,
            "data": filtered[:bounded_limit],
            "data_date": _today(),
        }
    except Exception as exc:
        return {"error": str(exc), "sector": sector}


def _sector_suggestions(sector: str) -> list[str]:
    try:
        _disable_proxy_env()
        import akshare as ak

        frame = ak.stock_board_industry_name_em()
        if frame is None or frame.empty:
            return []
        names = [str(name) for name in frame["板块名称"].tolist()]
        return [name for name in names if sector in name or name in sector][:5]
    except Exception:
        return []


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")
