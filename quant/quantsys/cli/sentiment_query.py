"""Sentiment and ownership helpers exposed through the QuantSys CLI."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from .stock_query import _clean_symbol, _disable_proxy_env, _safe_float, _sina_symbol

# 进程级别的数据源成功率统计（内存缓存）
_source_stats = {
    'sina': {'success': 0, 'failure': 0, 'last_success_time': None},
    'akshare': {'success': 0, 'failure': 0, 'last_success_time': None},
}


def get_stock_fund_flow(symbol: str, days: int = 10) -> dict[str, Any]:
    """
    多渠道获取个股资金流向数据

    降级策略：新浪 → akshare

    Args:
        symbol: 股票代码（支持多种格式：600094, sh600094, SH600094）
        days: 查询天数，默认 10 天

    Returns:
        成功时返回包含 data, source, estimated_fields 的字典
        失败时返回包含 error 的字典
    """
    clean = _clean_symbol(symbol)

    # 尝试新浪数据源
    result = _fetch_from_sina(clean, days)
    if result and 'error' not in result:
        _update_stats('sina', success=True)
        return result

    _update_stats('sina', success=False)

    # 降级到 akshare
    result = _fetch_from_akshare(clean, days)
    if result and 'error' not in result:
        _update_stats('akshare', success=True)
    else:
        _update_stats('akshare', success=False)

    return result


def _fetch_from_sina(symbol: str, days: int) -> dict[str, Any]:
    """
    从新浪获取资金流向数据并转换为 akshare 格式

    Args:
        symbol: 纯数字股票代码（如 "600094"）
        days: 查询天数

    Returns:
        转换后的数据字典，失败时返回包含 error 的字典
    """
    try:
        import requests

        # 确定市场前缀
        if symbol.startswith("6"):
            market_prefix = "sh"
        elif symbol.startswith(("8", "4")):
            market_prefix = "bj"
        else:
            market_prefix = "sz"

        # 调用新浪 API
        url = "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/MoneyFlow.ssl_qsfx_zjlrqs"
        params = {
            "daima": f"{market_prefix}{symbol}",
            "num": days,
        }

        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()

        data = response.json()
        if not data or len(data) == 0:
            return {"error": "新浪返回空数据", "symbol": symbol}

        # 转换为 akshare 格式
        records = []
        for item in data:
            # 解析数值
            main_net = float(item.get("netamount", 0))
            main_ratio = float(item.get("ratioamount", 0)) * 100  # 转换为百分比

            record = {
                "日期": item.get("opendate"),
                "收盘价": float(item.get("trade", 0)),
                "涨跌幅": float(item.get("changeratio", 0)) * 100,  # 转换为百分比
                "主力净流入-净额": main_net,
                "主力净流入-净占比": main_ratio,
                # 估算超大单（60%）
                "超大单净流入-净额": main_net * 0.6,
                "超大单净流入-净占比": main_ratio * 0.6,
                # 估算大单（40%）
                "大单净流入-净额": main_net * 0.4,
                "大单净流入-净占比": main_ratio * 0.4,
                # 估算中单（反向 50%）
                "中单净流入-净额": -main_net * 0.5,
                "中单净流入-净占比": -main_ratio * 0.5,
                # 估算小单（反向 50%）
                "小单净流入-净额": -main_net * 0.5,
                "小单净流入-净占比": -main_ratio * 0.5,
            }
            records.append(record)

        # 新浪 API 的 num 参数不可靠，手动截取最近 N 天
        records = records[:days]

        return {
            "symbol": symbol,
            "data": records,
            "source": "sina",
            "estimated_fields": [
                "超大单净流入-净额",
                "超大单净流入-净占比",
                "大单净流入-净额",
                "大单净流入-净占比",
                "中单净流入-净额",
                "中单净流入-净占比",
                "小单净流入-净额",
                "小单净流入-净占比",
            ]
        }

    except Exception as e:
        return {"error": f"新浪数据源失败: {str(e)}", "symbol": symbol}


def _fetch_from_akshare(symbol: str, days: int) -> dict[str, Any]:
    """
    使用 akshare 原始接口获取资金流向数据

    Args:
        symbol: 纯数字股票代码（如 "600094"）
        days: 查询天数

    Returns:
        转换后的数据字典，失败时返回包含 error 的字典
    """
    try:
        _disable_proxy_env()
        import akshare as ak

        # 确定市场
        if symbol.startswith("6"):
            market = "sh"
        elif symbol.startswith(("8", "4")):
            market = "bj"
        else:
            market = "sz"

        # 调用 akshare
        frame = ak.stock_individual_fund_flow(stock=symbol, market=market)
        if frame is None or frame.empty:
            return {"error": f"无资金流向数据: {symbol}", "symbol": symbol}

        # 限制返回天数
        limit = max(int(days or 10), 1)
        records = frame.tail(limit).to_dict(orient="records")

        return {
            "symbol": symbol,
            "data": records,
            "source": "akshare",
            "estimated_fields": []  # akshare 数据无估算字段
        }

    except Exception as e:
        return {"error": f"akshare 数据源失败: {str(e)}", "symbol": symbol}


def get_lhb(symbol: str | None = None, date: str | None = None) -> dict[str, Any]:
    """Return Dragon-Tiger List data by date or recent stock appearances."""
    try:
        _disable_proxy_env()
        import akshare as ak

        if symbol:
            clean = _clean_symbol(symbol)
            end = datetime.now()
            start = end - timedelta(days=30)
            frame = ak.stock_lhb_detail_em(
                start_date=start.strftime("%Y%m%d"),
                end_date=end.strftime("%Y%m%d"),
            )
            if frame is None or frame.empty:
                return {"error": f"无龙虎榜数据: {clean}", "symbol": clean}
            stock_frame = frame[frame["代码"].astype(str) == clean].copy()
            if stock_frame.empty:
                return {
                    "error": f"该股近期未上龙虎榜: {clean}",
                    "symbol": clean,
                    "hint": "可使用不带 symbol 的 sentiment.lhb 查看指定日期龙虎榜全榜",
                }
            records = stock_frame.head(10).to_dict(orient="records")
            return {
                "symbol": clean,
                "count": len(records),
                "data": records,
                "data_date": _today(),
                "note": "个股统计周期为近30日明细（akShare API 变更后替代方案）",
            }

        query_date = date or (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")
        frame = ak.stock_lhb_detail_em(start_date=query_date, end_date=query_date)
        if frame is None or frame.empty:
            return {"error": f"无龙虎榜数据: {query_date}", "date": query_date}
        col_map = {
            "代码": "symbol",
            "名称": "name",
            "收盘价": "close",
            "涨跌幅": "change_pct",
            "龙虎榜净买额": "net_buy",
            "龙虎榜买入额": "buy_amount",
            "龙虎榜卖出额": "sell_amount",
            "净买额占总成交比": "net_buy_ratio",
            "上榜原因": "reason",
            "解读": "analysis",
            "换手率": "turnover_rate",
        }
        frame = frame.rename(columns={key: value for key, value in col_map.items() if key in frame.columns})
        records = frame.head(30).to_dict(orient="records")
        return {"date": query_date, "count": len(records), "data": records, "data_date": _today()}
    except Exception as exc:
        return {"error": str(exc), "symbol": symbol, "date": date}


def get_insider_trades(symbol: str) -> dict[str, Any]:
    """Return recent insider trading records."""
    clean = _clean_symbol(symbol)
    xq_symbol = f"SH{clean}" if clean.startswith("6") else f"SZ{clean}"
    try:
        _disable_proxy_env()
        import akshare as ak

        frame = ak.stock_inner_trade_xq(symbol=xq_symbol)
        if frame is None or frame.empty:
            return {"error": f"未找到 {clean} 的高管交易记录", "symbol": clean}
        col_map = {
            "股票代码": "symbol",
            "股票名称": "name",
            "变动人": "person",
            "董监高职务": "title",
            "变动日期": "date",
            "变动股数": "shares_changed",
            "成交均价": "avg_price",
            "变动后持股数": "shares_after",
            "与董监高关系": "relationship",
        }
        frame = frame.rename(columns={key: value for key, value in col_map.items() if key in frame.columns})
        frame["symbol"] = clean
        records = frame.to_dict(orient="records")
        return {"symbol": clean, "count": len(records), "data": records, "data_date": _today()}
    except Exception as exc:
        return {"error": str(exc), "symbol": clean}


def get_fund_holdings(symbol: str) -> dict[str, Any]:
    """Return funds holding the stock."""
    clean = _clean_symbol(symbol)
    try:
        _disable_proxy_env()
        import akshare as ak

        frame = ak.stock_institute_hold_detail(stock=clean, quarter="")
        if frame is None or frame.empty:
            return {"error": f"无基金持仓数据: {clean}", "symbol": clean}
        records = frame.head(20).to_dict(orient="records")
        return {"symbol": clean, "count": len(records), "data": records, "data_date": _today()}
    except Exception as exc:
        return {"error": str(exc), "symbol": clean}


def get_top_fund_stocks() -> dict[str, Any]:
    """Return top fund-heavy stocks if the upstream interface is available."""
    return {"error": "akshare 已移除 fund_stock_rank_em 接口，该功能暂不可用"}


def get_top_holders(symbol: str, date: str | None = None) -> dict[str, Any]:
    """Return top 10 shareholders."""
    clean = _clean_symbol(symbol)
    date_str = date or _latest_quarter_end()
    try:
        _disable_proxy_env()
        import akshare as ak

        frame = ak.stock_gdfx_top_10_em(symbol=_sina_symbol(clean), date=date_str)
        if frame is None or frame.empty:
            return {"error": f"无股东数据: {clean}", "symbol": clean}
        records = frame.to_dict(orient="records")
        return {
            "symbol": clean,
            "report_date": date_str,
            "count": len(records),
            "data": records,
            "data_date": _today(),
        }
    except Exception as exc:
        return {"error": str(exc), "symbol": clean}


def get_holder_changes(symbol: str) -> dict[str, Any]:
    """Return recent shareholder count changes."""
    clean = _clean_symbol(symbol)
    try:
        _disable_proxy_env()
        import akshare as ak

        frame = ak.stock_zh_a_gdhs(symbol=clean)
        if frame is None or frame.empty:
            return {"error": f"无股东人数数据: {clean}", "symbol": clean}
        records = frame.tail(8).to_dict(orient="records")
        return {"symbol": clean, "count": len(records), "data": records, "data_date": _today()}
    except Exception as exc:
        return {"error": str(exc), "symbol": clean}


def get_margin_data(symbol: str) -> dict[str, Any]:
    """Return recent stock-level margin financing and securities lending data."""
    clean = _clean_symbol(symbol)
    if not clean.isdigit() or len(clean) != 6:
        return {"error": f"无效股票代码格式: {clean}，需要6位数字", "symbol": clean}

    try:
        _disable_proxy_env()
        import akshare as ak

        if clean.startswith("6"):
            exchange = "sse"
            api_func = ak.stock_margin_detail_sse
            symbol_col = "标的证券代码"
        elif clean.startswith(("0", "2", "3")):
            exchange = "szse"
            api_func = ak.stock_margin_detail_szse
            symbol_col = "证券代码"
        else:
            return {"error": f"不支持的股票代码: {clean}（仅支持沪深A股）", "symbol": clean}

        results = []
        errors = []
        today = datetime.now()
        for days_back in range(15):
            date_str = (today - timedelta(days=days_back)).strftime("%Y%m%d")
            try:
                frame = api_func(date=date_str)
                if frame is None or frame.empty:
                    continue
                if symbol_col not in frame.columns:
                    errors.append(f"{date_str}: 列名不匹配 (expected {symbol_col})")
                    continue
                filtered = frame[frame[symbol_col].astype(str) == clean]
                if not filtered.empty:
                    results.append(filtered.iloc[0].to_dict())
                    if len(results) >= 10:
                        break
            except Exception as exc:
                errors.append(f"{date_str}: {str(exc)[:50]}")
                if len(errors) >= 3 and not results:
                    break

        if not results:
            if errors:
                return {
                    "error": f"无法获取融资融券数据: {clean}",
                    "symbol": clean,
                    "exchange": exchange,
                    "details": f"尝试了 {len(errors)} 个日期，均失败。最近错误: {errors[-1]}",
                }
            return {"error": f"该股票不在融资融券标的范围内: {clean}", "symbol": clean, "exchange": exchange}

        return {"symbol": clean, "exchange": exchange, "count": len(results), "data": results, "data_date": _today()}
    except Exception as exc:
        return {"error": str(exc), "symbol": clean}


def _latest_quarter_end() -> str:
    now = datetime.now()
    for suffix in reversed(["0331", "0630", "0930", "1231"]):
        candidate = f"{now.year}{suffix}"
        if datetime.strptime(candidate, "%Y%m%d") < now:
            return candidate
    return f"{now.year - 1}1231"


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _update_stats(source: str, success: bool) -> None:
    """
    更新数据源成功率统计

    Args:
        source: 数据源名称（'sina' 或 'akshare'）
        success: 是否成功
    """
    from datetime import datetime

    if source in _source_stats:
        if success:
            _source_stats[source]['success'] += 1
            _source_stats[source]['last_success_time'] = datetime.now()
        else:
            _source_stats[source]['failure'] += 1


def get_fund_flow_stats() -> dict[str, Any]:
    """
    获取数据源统计信息（用于监控和调试）

    Returns:
        {
            'sina': {'success': 10, 'failure': 2, 'success_rate': 0.833, ...},
            'akshare': {'success': 0, 'failure': 5, 'success_rate': 0.0, ...}
        }
    """
    stats = {}
    for source, data in _source_stats.items():
        total = data['success'] + data['failure']
        success_rate = data['success'] / total if total > 0 else 0.0
        stats[source] = {
            **data,
            'total_requests': total,
            'success_rate': success_rate,
        }
    return stats


# === Daemon handler registration ===

from .daemon import register_daemon_method  # noqa: E402
from .context import build_context  # noqa: E402


def register_daemon_handlers() -> None:
    build_context(db_path=None, output_dir=None, python="python3")

    def _get_stock_fund_flow(params):
        return get_stock_fund_flow(
            symbol=params.get("symbol"),
            days=params.get("days", 10),
        )

    def _get_lhb(params):
        return get_lhb(
            symbol=params.get("symbol"),
            date=params.get("date"),
        )

    def _get_margin_data(params):
        return get_margin_data(symbol=params.get("symbol"))

    def _get_top_holders(params):
        return get_top_holders(
            symbol=params.get("symbol"),
            date=params.get("date"),
        )

    def _get_holder_changes(params):
        return get_holder_changes(symbol=params.get("symbol"))

    def _get_fund_holdings(params):
        return get_fund_holdings(symbol=params.get("symbol"))

    def _get_top_fund_stocks(params):
        return get_top_fund_stocks()

    def _get_insider_trades(params):
        return get_insider_trades(symbol=params.get("symbol"))

    register_daemon_method("get_stock_fund_flow", _get_stock_fund_flow)
    register_daemon_method("get_lhb", _get_lhb)
    register_daemon_method("get_margin_data", _get_margin_data)
    register_daemon_method("get_top_holders", _get_top_holders)
    register_daemon_method("get_holder_changes", _get_holder_changes)
    register_daemon_method("get_fund_holdings", _get_fund_holdings)
    register_daemon_method("get_top_fund_stocks", _get_top_fund_stocks)
    register_daemon_method("get_insider_trades", _get_insider_trades)

