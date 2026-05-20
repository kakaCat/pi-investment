"""Market query helpers exposed through the QuantSys CLI."""

from __future__ import annotations

import os
import re
from datetime import datetime
from typing import Any


def _disable_proxy_env() -> None:
    for key in list(os.environ):
        if key.lower().endswith("_proxy") or key.lower() == "no_proxy":
            os.environ.pop(key, None)
    os.environ["no_proxy"] = "*"


def get_market_overview() -> dict[str, Any]:
    """Return a snapshot of major A-share indices."""
    try:
        import requests

        _disable_proxy_env()
        codes = {
            "上证指数": "sh000001",
            "深证成指": "sz399001",
            "创业板指": "sz399006",
            "沪深300": "sh000300",
            "中证500": "sz399905",
        }
        response = requests.get(
            f"https://hq.sinajs.cn/list={','.join(codes.values())}",
            headers={"Referer": "https://finance.sina.com.cn", "User-Agent": "Mozilla/5.0"},
            timeout=10,
        )
        response.encoding = "gbk"
        lines = [line.strip() for line in response.text.strip().split("\n") if line.strip()]
        indices: dict[str, dict[str, float]] = {}
        for (name, _code), line in zip(codes.items(), lines):
            match = re.search(r'"([^"]*)"', line)
            if not match:
                continue
            fields = match.group(1).split(",")
            if len(fields) < 4:
                continue
            prev_close = _safe_float(fields[2])
            price = _safe_float(fields[3])
            indices[name] = {
                "price": price,
                "change_pct": round((price - prev_close) / prev_close * 100, 2) if prev_close else 0.0,
            }
        return {"indices": indices, "data_date": datetime.now().strftime("%Y-%m-%d")}
    except Exception as exc:
        return {"error": str(exc)}


def get_sector_list() -> dict[str, Any]:
    """Return A-share industry sector list."""
    try:
        _disable_proxy_env()
        import akshare as ak

        frame = ak.stock_fund_flow_industry(symbol="即时")
        if frame is None or frame.empty:
            return {"error": "板块数据暂时不可用", "count": 0, "data": []}
        records = [
            {
                "name": str(row.get("行业", "")),
                "code": "",
                "count": int(row.get("公司家数", 0)) if row.get("公司家数") else 0,
                "change_pct": float(row.get("行业-涨跌幅", 0)) if row.get("行业-涨跌幅") else 0,
            }
            for _, row in frame.iterrows()
        ]
        return {"count": len(records), "data": records, "data_date": datetime.now().strftime("%Y-%m-%d")}
    except Exception as exc:
        return {"error": str(exc), "count": 0, "data": []}


def get_concept_stocks(concept: str) -> dict[str, Any]:
    """Return concept/theme constituents."""
    try:
        _disable_proxy_env()
        import akshare as ak

        names = ak.stock_board_concept_name_ths()
        if names is None or names.empty:
            return {"error": "无法获取概念板块列表", "concept": concept}
        matched = names[names["name"] == concept]
        if matched.empty:
            matched = names[names["name"].str.contains(concept, na=False, regex=False)]
        if matched.empty:
            return {
                "error": f"未找到概念: {concept}",
                "concept": concept,
                "suggestion": "可使用 market.concepts 查看所有可用概念名称",
            }

        concept_name = str(matched.iloc[0]["name"])
        concept_code = str(matched.iloc[0]["code"])
        records = _fetch_ths_concept_page(concept_code)
        return {
            "concept": concept_name,
            "count": len(records),
            "data": records[:50],
            "data_date": datetime.now().strftime("%Y-%m-%d"),
        }
    except Exception as exc:
        return {"error": f"获取概念股数据失败: {str(exc)}", "concept": concept}


def get_concept_list() -> dict[str, Any]:
    """Return concept/theme list."""
    try:
        _disable_proxy_env()
        import akshare as ak

        frame = ak.stock_board_concept_name_ths()
        if frame is None or frame.empty:
            return _concept_list_from_fund_flow()
        records = [
            {"name": str(row.get("name", "")), "code": str(row.get("code", ""))}
            for _, row in frame.iterrows()
        ]
        return {
            "count": len(records),
            "data": records,
            "data_date": datetime.now().strftime("%Y-%m-%d"),
            "source": "ths",
        }
    except Exception as exc:
        fallback = _concept_list_from_fund_flow()
        if "error" not in fallback:
            return fallback
        return {"error": f"获取概念列表失败: {str(exc)}", "count": 0, "data": []}


def get_macro_data(indicators: list[str] | None = None) -> dict[str, Any]:
    """Return selected China macro indicators."""
    selected = indicators or ["pmi", "cpi", "gdp"]
    result: dict[str, Any] = {}
    try:
        _disable_proxy_env()
        import akshare as ak
    except Exception as exc:
        return {"error": str(exc)}

    if "pmi" in selected:
        try:
            frame = ak.macro_china_pmi()
            if frame is not None and not frame.empty:
                result["pmi"] = [
                    {"date": str(row["月份"]), "value": _safe_float(row["制造业-指数"])}
                    for _, row in frame.head(6).iterrows()
                ]
        except Exception as exc:
            result["pmi_error"] = str(exc)

    if "cpi" in selected:
        try:
            frame = ak.macro_china_cpi_monthly()
            if frame is not None and not frame.empty:
                result["cpi"] = [
                    {"date": str(row["日期"]), "yoy": _safe_float(row["今值"])}
                    for _, row in frame.tail(6).sort_values("日期", ascending=False).iterrows()
                ]
        except Exception as exc:
            result["cpi_error"] = str(exc)

    if "gdp" in selected:
        try:
            frame = ak.macro_china_gdp()
            if frame is not None and not frame.empty:
                result["gdp"] = [
                    {"date": str(row["季度"]), "value": _safe_float(row["国内生产总值-绝对值"])}
                    for _, row in frame.head(8).iterrows()
                ]
        except Exception as exc:
            result["gdp_error"] = str(exc)

    result["data_date"] = datetime.now().strftime("%Y-%m-%d")
    if all(key.endswith("_error") for key in result if key != "data_date"):
        return {"error": "所有宏观数据API均失败", **result}
    return result


def get_north_flow() -> dict[str, Any]:
    """Return northbound capital flow if the data source is fresh."""
    try:
        _disable_proxy_env()
        import akshare as ak

        frame = ak.stock_hsgt_hist_em(symbol="北向资金")
        valid = frame.dropna(subset=["当日成交净买额"])
        if valid.empty:
            return {"error": "北向资金数据源失效", "detail": "东方财富网北向资金接口无有效数据", "data": []}
        latest_date = valid["日期"].max()
        records = [
            {
                "date": str(row.get("日期", "")),
                "amount_billion": _safe_float(row.get("当日成交净买额", 0)),
                "buy": _safe_float(row.get("买入成交额", 0)),
                "sell": _safe_float(row.get("卖出成交额", 0)),
            }
            for _, row in valid.tail(10).iterrows()
        ]
        return {"data": records, "data_date": str(latest_date)}
    except Exception as exc:
        return {"error": f"获取北向资金数据失败: {str(exc)}"}


def get_sector_fund_flow() -> dict[str, Any]:
    """Return sector fund flow ranking."""
    try:
        _disable_proxy_env()
        import akshare as ak

        frame = ak.stock_fund_flow_industry(symbol="即时")
        if frame is None or frame.empty:
            return {"error": "无行业资金流向数据"}
        records = frame.head(20).to_dict(orient="records")
        return {"count": len(records), "data": records, "data_date": datetime.now().strftime("%Y-%m-%d")}
    except Exception as exc:
        return {"error": str(exc)}


def get_market_margin() -> dict[str, Any]:
    """Return market margin balance trend."""
    try:
        _disable_proxy_env()
        import akshare as ak

        sh_frame = ak.macro_china_market_margin_sh()
        sz_frame = ak.macro_china_market_margin_sz()
        if (sh_frame is None or sh_frame.empty) and (sz_frame is None or sz_frame.empty):
            return {"error": "无市场融资融券数据"}
        records = []
        if sh_frame is not None and sz_frame is not None and not sh_frame.empty and not sz_frame.empty:
            for _, sh_row in sh_frame.tail(30).iterrows():
                date = sh_row["日期"]
                sz_row = sz_frame.tail(30)[sz_frame.tail(30)["日期"] == date]
                if sz_row.empty:
                    continue
                sz = sz_row.iloc[0]
                sh_margin = _safe_float(sh_row.get("融资融券余额", 0)) / 100000000
                sz_margin = _safe_float(sz.get("融资融券余额", 0)) / 100000000
                records.append({
                    "date": str(date),
                    "total_margin": sh_margin + sz_margin,
                    "sh_margin": sh_margin,
                    "sz_margin": sz_margin,
                })
        return {"count": len(records), "data": records[-10:], "data_date": datetime.now().strftime("%Y-%m-%d")}
    except Exception as exc:
        return {"error": str(exc)}


def get_market_news(num: int = 20) -> dict[str, Any]:
    """Return broad market news."""
    result: dict[str, Any] = {"sources": [], "data_date": datetime.now().strftime("%Y-%m-%d")}
    try:
        _disable_proxy_env()
        import akshare as ak
    except Exception as exc:
        return {"error": str(exc), **result}

    try:
        frame = ak.stock_news_main_cx()
        if frame is not None and not frame.empty:
            items = [
                {"title": str(row.get("summary", "")), "tag": str(row.get("tag", "")), "url": str(row.get("url", ""))}
                for _, row in frame.head(max(1, num // 3)).iterrows()
            ]
            result["caixin"] = {"count": len(items), "data": items}
            result["sources"].append("caixin")
    except Exception as exc:
        result["caixin_error"] = str(exc)

    try:
        frame = ak.stock_news_em(symbol="全部")
        if frame is not None and not frame.empty:
            items = [
                {
                    "title": str(row.get("新闻标题", "")),
                    "source": str(row.get("文章来源", "")),
                    "time": str(row.get("发布时间", "")),
                }
                for _, row in frame.head(max(1, num // 3)).iterrows()
            ]
            result["eastmoney"] = {"count": len(items), "data": items}
            result["sources"].append("eastmoney")
    except Exception as exc:
        result["eastmoney_error"] = str(exc)

    if not result["sources"]:
        result["error"] = "所有新闻源均不可用"
    return result


def get_hot_stocks(market: str = "A股") -> dict[str, Any]:
    """Return hot-search stock ranking."""
    valid_markets = ["全部", "A股", "港股", "美股"]
    if market not in valid_markets:
        return {
            "error": f"无效的市场参数: {market}",
            "valid_values": valid_markets,
            "suggestion": "使用 market.sector_flow 查看市场热点",
        }
    try:
        _disable_proxy_env()
        import akshare as ak

        today = datetime.now().strftime("%Y%m%d")
        frame = ak.stock_hot_search_baidu(symbol=market, date=today, time="今日")
        if frame is None or frame.empty:
            return {"error": f"暂无热搜数据: {market}", "market": market}
        records = frame.head(20).to_dict(orient="records")
        return {"market": market, "count": len(records), "data": records, "data_date": today}
    except Exception as exc:
        return {"error": str(exc), "market": market}


def _fetch_ths_concept_page(concept_code: str) -> list[dict[str, Any]]:
    import requests

    session = requests.Session()
    session.trust_env = False
    headers = {"User-Agent": "Mozilla/5.0"}
    stocks: list[dict[str, Any]] = []
    for page in range(1, 11):
        response = session.get(
            f"http://q.10jqka.com.cn/gn/detail/code/{concept_code}/page/{page}/",
            headers=headers,
            timeout=10,
        )
        if response.status_code != 200:
            break
        page_stocks = []
        for row_html in re.findall(r"<tr[^>]*>(.*?)</tr>", response.text, re.DOTALL):
            cells = re.findall(r"<td[^>]*>(.*?)</td>", row_html, re.DOTALL)
            if len(cells) < 4:
                continue
            code_match = re.search(r"(\d{6})", cells[1])
            name = re.sub(r"<[^>]+>", "", cells[2]).strip()
            price = re.sub(r"<[^>]+>", "", cells[3]).strip()
            if not code_match or not name or "序号" in name:
                continue
            page_stocks.append({
                "code": code_match.group(1),
                "name": name,
                "price": _safe_float(price, 0),
                "change_pct": _extract_change_pct(cells),
            })
        if not page_stocks:
            break
        stocks.extend(page_stocks)
    return stocks


def _concept_list_from_fund_flow() -> dict[str, Any]:
    try:
        import akshare as ak

        frame = ak.stock_fund_flow_concept()
        if frame is None or frame.empty:
            return {"error": "无法获取概念板块列表", "count": 0, "data": []}
        records = [
            {
                "name": str(row.get("行业", "")),
                "code": "",
                "change_pct": float(row.get("行业-涨跌幅", 0)),
            }
            for _, row in frame.iterrows()
        ]
        return {
            "count": len(records),
            "data": records,
            "data_date": datetime.now().strftime("%Y-%m-%d"),
            "source": "fund_flow",
        }
    except Exception as exc:
        return {"error": str(exc), "count": 0, "data": []}


def _extract_change_pct(cells: list[str]) -> float:
    if len(cells) < 5:
        return 0.0
    text = re.sub(r"<[^>]+>", "", cells[4]).strip().replace("%", "")
    return _safe_float(text, 0.0)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
        if number != number or number in {float("inf"), float("-inf")}:
            return default
        return round(number, 2)
    except (TypeError, ValueError):
        return default
