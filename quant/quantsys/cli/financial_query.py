"""Financial statement helpers exposed through the QuantSys CLI."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from .stock_query import (
    _clean_symbol,
    _disable_proxy_env,
    _hk_code,
    _safe_float,
    _sina_symbol,
    get_stock_history,
    get_stock_quote,
)


def get_financial_indicators(symbol: str) -> dict[str, Any]:
    """Return recent A-share financial ratios."""
    clean = _clean_symbol(symbol)
    try:
        _disable_proxy_env()
        import akshare as ak

        frame = ak.stock_financial_abstract_ths(symbol=clean, indicator="按报告期")
        if frame is None or frame.empty:
            return {"error": f"无财务数据: {clean}", "symbol": clean}
        frame = frame.tail(4).iloc[::-1]
        quarters = []

        def parse_pct(value: Any) -> float:
            if isinstance(value, str) and "%" in value:
                return _safe_float(value.replace("%", ""))
            return _safe_float(value)

        for _, row in frame.iterrows():
            quarters.append({
                "report_date": str(row.get("报告期", "")),
                "roe": parse_pct(row.get("净资产收益率", 0)),
                "gross_margin": parse_pct(row.get("销售毛利率", 0)),
                "net_margin": parse_pct(row.get("销售净利率", 0)),
                "debt_ratio": parse_pct(row.get("资产负债率", 0)),
                "current_ratio": _safe_float(row.get("流动比率", 0)),
            })

        return {"symbol": clean, "quarters": quarters, "data": quarters, "data_date": _today()}
    except Exception as exc:
        return {"error": str(exc), "symbol": clean}


def get_financial_statements(symbol: str, statement: str = "all", recent_n: int = 8) -> dict[str, Any]:
    """Return A-share income, balance sheet, cashflow, or all statements."""
    result: dict[str, Any] = {}
    if statement in ("income", "all"):
        result["income_statement"] = _financial_report(symbol, "利润表", recent_n)
    if statement in ("balance", "all"):
        result["balance_sheet"] = _financial_report(symbol, "资产负债表", recent_n)
    if statement in ("cashflow", "all"):
        cashflow = _financial_report(symbol, "现金流量表", recent_n)
        result["cash_flow"] = cashflow
        result["cashflow_statement"] = cashflow
    if not result:
        return {"error": f"不支持的报表类型: {statement}", "symbol": _clean_symbol(symbol)}
    return result


def get_hk_financials(symbol: str) -> dict[str, Any]:
    """Return HK stock annual income and balance-sheet summary."""
    code = _hk_code(symbol)
    results: dict[str, Any] = {}

    def pivot(frame: Any) -> dict[str, dict[str, float]]:
        output: dict[str, dict[str, float]] = {}
        for _, row in frame.iterrows():
            date = str(row["REPORT_DATE"])[:10]
            item = str(row["STD_ITEM_NAME"])
            value = _safe_float(row["AMOUNT"], decimals=0)
            output.setdefault(date, {})[item] = value
        return output

    try:
        _disable_proxy_env()
        import akshare as ak

        frame = ak.stock_financial_hk_report_em(stock=code, symbol="利润表", indicator="年度")
        if frame is not None and not frame.empty:
            by_date = pivot(frame)
            income = []
            for date in sorted(by_date.keys(), reverse=True)[:4]:
                row = by_date[date]
                revenue = row.get("营业额", row.get("营运收入", 0.0))
                net_profit = row.get("股东应占溢利", row.get("除税后溢利", 0.0))
                income.append({
                    "period": date,
                    "revenue": revenue,
                    "net_profit": net_profit,
                    "net_margin": round(net_profit / revenue * 100, 2) if revenue else 0.0,
                })
            results["income"] = income
    except Exception as exc:
        results["income_error"] = str(exc)

    try:
        _disable_proxy_env()
        import akshare as ak

        frame = ak.stock_financial_hk_report_em(stock=code, symbol="资产负债表", indicator="年度")
        if frame is not None and not frame.empty:
            by_date = pivot(frame)
            latest_date = sorted(by_date.keys(), reverse=True)[0]
            row = by_date[latest_date]
            total_assets = row.get("总资产", 0.0)
            total_liabilities = row.get("总负债", 0.0)
            equity = row.get("股东权益", row.get("总权益", 0.0))
            roe = 0.0
            if results.get("income") and equity:
                roe = round(results["income"][0]["net_profit"] / equity * 100, 2)
            results["balance"] = {
                "period": latest_date,
                "total_assets": total_assets,
                "total_liabilities": total_liabilities,
                "equity": equity,
                "debt_ratio": round(total_liabilities / total_assets * 100, 2) if total_assets else 0.0,
                "roe": roe,
            }
    except Exception as exc:
        results["balance_error"] = str(exc)

    if not results or (results.get("income_error") and results.get("balance_error")):
        return {
            "error": f"无法获取港股财务数据: {symbol}（akshare港股财报接口可能不支持该股票）",
            "symbol": symbol,
        }

    results["symbol"] = code
    results["market"] = "HK"
    results["data_date"] = _today()
    return results


def get_hk_analysis(symbol: str) -> dict[str, Any]:
    """Return HK stock price, technical summary, and available financial data."""
    code = _hk_code(symbol)
    result: dict[str, Any] = {"symbol": code, "market": "HK", "data_date": _today()}
    unavailable = []

    price_data = get_stock_quote(symbol)
    if "error" in price_data:
        return {"error": f"无法获取港股实时价格: {price_data['error']}", "symbol": symbol}
    result["price"] = price_data

    try:
        history = get_stock_history(symbol, period="daily", limit=60)
        if "error" not in history and history.get("data"):
            data = history["data"]
            closes = [float(item["close"]) for item in data]
            result["history_count"] = len(data)
            result["recent_high_20d"] = _safe_float(max(closes[-20:]))
            result["recent_low_20d"] = _safe_float(min(closes[-20:]))
            if len(closes) >= 20:
                result["ma20"] = _safe_float(sum(closes[-20:]) / 20)
            if len(closes) >= 60:
                result["ma60"] = _safe_float(sum(closes[-60:]) / 60)
            current = _safe_float(price_data.get("price", 0))
            ma20 = result.get("ma20", 0)
            ma60 = result.get("ma60", 0)
            if ma20 and ma60:
                if current > ma20 > ma60:
                    result["trend"] = "多头排列（短期强势）"
                elif current < ma20 < ma60:
                    result["trend"] = "空头排列（短期弱势）"
                else:
                    result["trend"] = "震荡整理"
        else:
            unavailable.append("历史K线（港股历史数据获取失败）")
    except Exception as exc:
        unavailable.append(f"历史K线（{exc}）")

    financials = get_hk_financials(symbol)
    if "error" not in financials:
        result["financials"] = financials
    else:
        unavailable.append(f"财务报表（{financials['error']}）")

    result["not_supported"] = [
        "PE历史分位数（需A股数据源）",
        "龙虎榜（仅A股）",
        "北向资金（仅A股）",
        "融资融券（仅A股）",
        "公告（需港交所接口）",
    ]
    if unavailable:
        result["data_unavailable"] = unavailable
    return result


def _financial_report(symbol: str, report_type: str, recent_n: int = 8) -> dict[str, Any]:
    clean = _clean_symbol(symbol)
    try:
        _disable_proxy_env()
        import akshare as ak

        frame = ak.stock_financial_report_sina(stock=_sina_symbol(clean), symbol=report_type)
        if frame is None or frame.empty:
            return {"error": f"无{report_type}数据: {clean}", "symbol": clean}
        frame = frame.head(max(int(recent_n or 8), 1))
        for col in ["报告日", "更新日期"]:
            if col in frame.columns:
                frame[col] = frame[col].astype(str)
        frame = frame.where(frame.notna(), None)
        records = frame.to_dict(orient="records")
        return {"symbol": clean, "report_type": report_type, "count": len(records), "data": records, "data_date": _today()}
    except Exception as exc:
        return {"error": str(exc), "symbol": clean}


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")
