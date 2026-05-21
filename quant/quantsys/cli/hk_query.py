"""HK market helpers exposed through the QuantSys CLI."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from .stock_query import _disable_proxy_env, _hk_code, _safe_float, get_stock_history


def get_hk_market_overview() -> dict[str, Any]:
    """Return real-time snapshots for major HK indices."""
    try:
        import requests

        _disable_proxy_env()
        response = requests.get(
            "https://hq.sinajs.cn/list=rt_hkHSI,rt_hkHSCEI,rt_hkHSTECH",
            headers={"Referer": "https://finance.sina.com.cn", "User-Agent": "Mozilla/5.0"},
            timeout=10,
        )
        response.encoding = "gbk"

        indices = []
        for line in response.text.strip().split("\n"):
            line = line.strip()
            if not line.startswith("var "):
                continue
            eq_idx = line.find("=")
            if eq_idx == -1:
                continue
            raw = line[eq_idx + 1:].strip().strip('"').strip("'").strip(";")
            parts = raw.split(",")
            if len(parts) < 9:
                continue

            indices.append({
                "code": parts[0],
                "name": _decode_gbk_field(parts[1]),
                "current": _safe_float(parts[4]),
                "change": _safe_float(parts[7]),
                "change_pct": _safe_float(parts[8]),
                "open": _safe_float(parts[2]),
                "high": _safe_float(parts[5]),
                "low": _safe_float(parts[6]),
                "prev_close": _safe_float(parts[3]),
                "data_date": parts[16] if len(parts) > 16 else "",
                "data_time": parts[17] if len(parts) > 17 else "",
            })

        if not indices:
            return {"error": "无法获取港股指数数据", "indices": []}

        return {
            "indices": indices,
            "data_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
    except Exception as exc:
        return {"error": f"港股指数数据获取失败: {exc}", "indices": []}


def get_hk_south_flow() -> dict[str, Any]:
    """Return recent southbound capital flow data."""
    try:
        _disable_proxy_env()
        import akshare as ak

        frame = ak.stock_hsgt_hist_em(symbol="南向资金")
        if frame is None or frame.empty:
            return {"error": "无南向资金数据", "data": []}

        records = []
        for _, row in frame.tail(10).iterrows():
            records.append({
                "date": str(row.get("日期", "")),
                "net_amount_billion": _safe_float(row.get("当日成交净买额", 0)),
                "buy_amount_billion": _safe_float(row.get("买入成交额", 0)),
                "sell_amount_billion": _safe_float(row.get("卖出成交额", 0)),
            })

        return {
            "data": records,
            "direction": "南向（内地→港股）",
            "data_date": datetime.now().strftime("%Y-%m-%d"),
        }
    except Exception as exc:
        return {"error": str(exc), "data": []}


def get_hk_technical(symbol: str) -> dict[str, Any]:
    """Calculate HK stock technical indicators from recent daily history."""
    try:
        import pandas as pd
    except ImportError:
        return {"error": "pandas 未安装，无法计算港股技术指标", "symbol": _hk_code(symbol)}

    code = _hk_code(symbol)
    history = get_stock_history(symbol, period="daily", limit=60)
    if "error" in history or not history.get("data"):
        return {"error": f"无法获取{code}的历史数据", "symbol": code}

    data = history["data"]
    if len(data) < 30:
        return {"error": f"历史数据不足（{len(data)}条），需要至少30个交易日", "symbol": code}

    closes = pd.Series([row["close"] for row in data])
    result: dict[str, Any] = {
        "symbol": code,
        "market": "HK",
        "data_date": datetime.now().strftime("%Y-%m-%d"),
    }

    ma_values = {}
    for period, name in {5: "MA5", 10: "MA10", 20: "MA20", 60: "MA60"}.items():
        if len(closes) >= period:
            ma_values[name] = _safe_float(closes.tail(period).mean())
    result["ma"] = ma_values

    dif = dea = None
    if len(closes) >= 26:
        ema12 = closes.ewm(span=12, adjust=False).mean()
        ema26 = closes.ewm(span=26, adjust=False).mean()
        dif = ema12 - ema26
        dea = dif.ewm(span=9, adjust=False).mean()
        macd_hist = 2 * (dif - dea)
        result["macd"] = {
            "dif": _safe_float(dif.iloc[-1]),
            "dea": _safe_float(dea.iloc[-1]),
            "histogram": _safe_float(macd_hist.iloc[-1]),
        }
    else:
        result["macd"] = None

    if len(closes) >= 15:
        delta = closes.diff()
        gain = delta.where(delta > 0, 0.0)
        loss = (-delta).where(delta < 0, 0.0)
        avg_gain = gain.rolling(14).mean()
        avg_loss = loss.rolling(14).mean()
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        result["rsi_14"] = _safe_float(rsi.iloc[-1])
    else:
        result["rsi_14"] = None

    if len(closes) >= 20:
        ma20 = closes.tail(20).mean()
        std20 = closes.tail(20).std()
        result["bollinger"] = {
            "upper": _safe_float(ma20 + 2 * std20),
            "middle": _safe_float(ma20),
            "lower": _safe_float(ma20 - 2 * std20),
        }
    else:
        result["bollinger"] = None

    result["signals"] = _hk_technical_signals(closes, ma_values, result, dif, dea)
    result["current_price"] = _safe_float(closes.iloc[-1])
    return result


def get_hk_hot_rank() -> dict[str, Any]:
    """Return Eastmoney HK popularity ranking."""
    try:
        _disable_proxy_env()
        import akshare as ak

        frame = ak.stock_hk_hot_rank_em()
        if frame is None or frame.empty:
            return {"error": "无法获取港股人气排行", "stocks": []}

        stocks = []
        for _, row in frame.iterrows():
            stocks.append({
                "rank": int(row.get("当前排名", 0)),
                "symbol": str(row.get("代码", "")),
                "name": str(row.get("股票名称", "")),
                "price": _safe_float(row.get("最新价", 0)),
                "change_pct": _safe_float(row.get("涨跌幅", 0)),
            })

        return {
            "stocks": stocks,
            "total": len(stocks),
            "data_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
    except Exception as exc:
        return {"error": str(exc), "stocks": []}


def _decode_gbk_field(value: str) -> str:
    try:
        return value.encode("latin1").decode("gbk")
    except Exception:
        return value


def _hk_technical_signals(
    closes: Any,
    ma_values: dict[str, float],
    result: dict[str, Any],
    dif: Any,
    dea: Any,
) -> list[str]:
    signals = []
    current = closes.iloc[-1]
    ma5 = ma_values.get("MA5")
    ma10 = ma_values.get("MA10")
    ma20 = ma_values.get("MA20")
    ma60 = ma_values.get("MA60")

    if ma5 and ma10 and ma20 and ma60:
        if current > ma5 > ma10 > ma20 > ma60:
            signals.append("多头排列（短期强势）")
        elif current < ma5 < ma10 < ma20 < ma60:
            signals.append("空头排列（短期弱势）")
        elif ma5 > ma10 and current > ma20:
            signals.append("短期偏多")
        elif ma5 < ma10 and current < ma20:
            signals.append("短期偏空")
        else:
            signals.append("震荡整理")

    macd = result.get("macd")
    if macd and macd.get("dif") and macd.get("dea"):
        if macd["dif"] > macd["dea"]:
            signals.append("MACD多头（DIF在DEA上方）")
        else:
            signals.append("MACD空头（DIF在DEA下方）")
        if dif is not None and dea is not None and len(closes) >= 26:
            dif_prev = _safe_float(dif.iloc[-2])
            dea_prev = _safe_float(dea.iloc[-2])
            if dif_prev < dea_prev and macd["dif"] > macd["dea"]:
                signals.append("MACD金叉（买入信号）")
            elif dif_prev > dea_prev and macd["dif"] < macd["dea"]:
                signals.append("MACD死叉（卖出信号）")

    rsi_val = result.get("rsi_14")
    if rsi_val is not None:
        if rsi_val > 70:
            signals.append("RSI超买（>70）")
        elif rsi_val < 30:
            signals.append("RSI超卖（<30）")

    bollinger = result.get("bollinger")
    if bollinger:
        if current >= bollinger["upper"]:
            signals.append("价格触及布林上轨")
        elif current <= bollinger["lower"]:
            signals.append("价格触及布林下轨")

    return signals
