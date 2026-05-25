"""Crypto market structure factors for trading analysis."""

from __future__ import annotations

import requests
from typing import Any
from datetime import datetime


def fetch_funding_rate(symbol: str) -> dict[str, Any]:
    """获取资金费率（Funding Rate）- 衡量多空情绪"""
    try:
        # 使用 Binance API 获取资金费率
        base_symbol = _normalize_symbol(symbol)
        pair = f"{base_symbol}USDT"

        url = "https://fapi.binance.com/fapi/v1/premiumIndex"
        params = {"symbol": pair}

        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        funding_rate = float(data.get("lastFundingRate", 0)) * 100  # 转换为百分比
        next_funding_time = int(data.get("nextFundingTime", 0))

        # 资金费率解读
        if funding_rate > 0.1:
            level = "extremely_bullish"
            interpretation = f"资金费率 {funding_rate:.4f}% 极高 - 多头过热，警惕回调风险"
        elif funding_rate > 0.05:
            level = "bullish"
            interpretation = f"资金费率 {funding_rate:.4f}% 偏高 - 多头占优，注意持仓成本"
        elif funding_rate > -0.05:
            level = "neutral"
            interpretation = f"资金费率 {funding_rate:.4f}% 中性 - 多空平衡"
        elif funding_rate > -0.1:
            level = "bearish"
            interpretation = f"资金费率 {funding_rate:.4f}% 偏低 - 空头占优，可能反弹"
        else:
            level = "extremely_bearish"
            interpretation = f"资金费率 {funding_rate:.4f}% 极低 - 空头过热，警惕空头挤压"

        return {
            "symbol": base_symbol,
            "funding_rate": round(funding_rate, 4),
            "next_funding_time": next_funding_time,
            "level": level,
            "interpretation": interpretation,
            "data_date": _today(),
        }
    except Exception as exc:
        return {"error": str(exc), "symbol": symbol, **_default_funding_rate()}


def fetch_open_interest(symbol: str) -> dict[str, Any]:
    """获取未平仓量（Open Interest）- 衡量市场参与度"""
    try:
        base_symbol = _normalize_symbol(symbol)
        pair = f"{base_symbol}USDT"

        url = "https://fapi.binance.com/fapi/v1/openInterest"
        params = {"symbol": pair}

        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        open_interest = float(data.get("openInterest", 0))

        # 获取历史数据计算变化
        url_stats = "https://fapi.binance.com/futures/data/openInterestHist"
        params_stats = {"symbol": pair, "period": "1d", "limit": 2}

        resp_stats = requests.get(url_stats, params=params_stats, timeout=10)
        resp_stats.raise_for_status()
        stats_data = resp_stats.json()

        change_24h = 0.0
        if len(stats_data) >= 2:
            current_oi = float(stats_data[-1].get("sumOpenInterest", 0))
            prev_oi = float(stats_data[-2].get("sumOpenInterest", 0))
            if prev_oi > 0:
                change_24h = ((current_oi - prev_oi) / prev_oi) * 100

        # 未平仓量解读
        if change_24h > 10:
            interpretation = f"未平仓量 {open_interest:.0f} 张，24h增长 {change_24h:.2f}% - 新资金大量涌入，趋势可能延续"
        elif change_24h > 5:
            interpretation = f"未平仓量 {open_interest:.0f} 张，24h增长 {change_24h:.2f}% - 市场参与度上升"
        elif change_24h > -5:
            interpretation = f"未平仓量 {open_interest:.0f} 张，24h变化 {change_24h:.2f}% - 市场平稳"
        elif change_24h > -10:
            interpretation = f"未平仓量 {open_interest:.0f} 张，24h下降 {change_24h:.2f}% - 资金流出，趋势可能反转"
        else:
            interpretation = f"未平仓量 {open_interest:.0f} 张，24h暴跌 {change_24h:.2f}% - 大量平仓，警惕剧烈波动"

        return {
            "symbol": base_symbol,
            "open_interest": round(open_interest, 2),
            "change_24h": round(change_24h, 2),
            "interpretation": interpretation,
            "data_date": _today(),
        }
    except Exception as exc:
        return {"error": str(exc), "symbol": symbol, **_default_open_interest()}


def fetch_long_short_ratio(symbol: str) -> dict[str, Any]:
    """获取多空比（Long/Short Ratio）- 衡量市场情绪"""
    try:
        base_symbol = _normalize_symbol(symbol)
        pair = f"{base_symbol}USDT"

        url = "https://fapi.binance.com/futures/data/globalLongShortAccountRatio"
        params = {"symbol": pair, "period": "1d", "limit": 1}

        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        if not data or len(data) == 0:
            return {"error": "No data available", "symbol": symbol, **_default_long_short_ratio()}

        latest = data[-1]
        long_ratio = float(latest.get("longAccount", 0.5))
        short_ratio = float(latest.get("shortAccount", 0.5))
        long_short_ratio = long_ratio / short_ratio if short_ratio > 0 else 1.0

        # 多空比解读
        if long_short_ratio > 2.0:
            level = "extremely_bullish"
            interpretation = f"多空比 {long_short_ratio:.2f} 极高 - 散户过度看多，警惕反向操作"
        elif long_short_ratio > 1.5:
            level = "bullish"
            interpretation = f"多空比 {long_short_ratio:.2f} 偏高 - 多头占优，但需警惕情绪过热"
        elif long_short_ratio > 0.67:
            level = "neutral"
            interpretation = f"多空比 {long_short_ratio:.2f} 中性 - 多空相对平衡"
        elif long_short_ratio > 0.5:
            level = "bearish"
            interpretation = f"多空比 {long_short_ratio:.2f} 偏低 - 空头占优，可能反弹"
        else:
            level = "extremely_bearish"
            interpretation = f"多空比 {long_short_ratio:.2f} 极低 - 散户过度看空，警惕反向操作"

        return {
            "symbol": base_symbol,
            "long_ratio": round(long_ratio * 100, 2),
            "short_ratio": round(short_ratio * 100, 2),
            "long_short_ratio": round(long_short_ratio, 2),
            "level": level,
            "interpretation": interpretation,
            "data_date": _today(),
        }
    except Exception as exc:
        return {"error": str(exc), "symbol": symbol, **_default_long_short_ratio()}


def get_crypto_factors(symbol: str) -> dict[str, Any]:
    """获取加密货币市场结构因子汇总"""
    funding = fetch_funding_rate(symbol)
    oi = fetch_open_interest(symbol)
    ls_ratio = fetch_long_short_ratio(symbol)

    # 综合信号评估
    signals = []
    risk_score = 0

    # 资金费率信号
    funding_level = funding.get("level", "neutral")
    if funding_level == "extremely_bullish":
        signals.append("资金费率极高-多头过热")
        risk_score += 2
    elif funding_level == "extremely_bearish":
        signals.append("资金费率极低-空头过热")
        risk_score -= 2

    # 未平仓量信号
    oi_change = oi.get("change_24h", 0)
    if oi_change > 10:
        signals.append("未平仓量暴增-趋势强化")
    elif oi_change < -10:
        signals.append("未平仓量暴跌-趋势反转")
        risk_score += 1

    # 多空比信号
    ls_level = ls_ratio.get("level", "neutral")
    if ls_level == "extremely_bullish":
        signals.append("多空比极高-散户过度看多")
        risk_score += 1
    elif ls_level == "extremely_bearish":
        signals.append("多空比极低-散户过度看空")
        risk_score -= 1

    # 综合评估
    if risk_score >= 3:
        overall_sentiment = "高风险"
        overall_interpretation = "多个指标显示市场过热，建议谨慎操作或考虑反向"
    elif risk_score >= 1:
        overall_sentiment = "偏谨慎"
        overall_interpretation = "市场存在一定风险，建议控制仓位"
    elif risk_score <= -2:
        overall_sentiment = "偏乐观"
        overall_interpretation = "市场情绪偏空，可能存在反弹机会"
    else:
        overall_sentiment = "中性"
        overall_interpretation = "市场结构相对平衡，关注价格走势"

    return {
        "symbol": _normalize_symbol(symbol),
        "funding_rate": funding,
        "open_interest": oi,
        "long_short_ratio": ls_ratio,
        "overall": {
            "risk_score": risk_score,
            "sentiment": overall_sentiment,
            "interpretation": overall_interpretation,
            "signals": signals,
        },
        "data_date": _today(),
    }


def _normalize_symbol(symbol: str) -> str:
    """标准化加密货币符号"""
    raw = str(symbol or "").strip().upper()
    if not raw:
        return ""
    if "/" in raw:
        raw = raw.split("/", 1)[0]
    if ":" in raw:
        raw = raw.split(":", 1)[0]
    raw = raw.replace("-USD", "").replace("-USDT", "").replace("USDT", "")
    return raw


def _default_funding_rate() -> dict[str, Any]:
    return {
        "funding_rate": 0.01,
        "next_funding_time": 0,
        "level": "neutral",
        "interpretation": "资金费率数据暂不可用（默认值0.01%）",
        "data_date": _today(),
    }


def _default_open_interest() -> dict[str, Any]:
    return {
        "open_interest": 0.0,
        "change_24h": 0.0,
        "interpretation": "未平仓量数据暂不可用",
        "data_date": _today(),
    }


def _default_long_short_ratio() -> dict[str, Any]:
    return {
        "long_ratio": 50.0,
        "short_ratio": 50.0,
        "long_short_ratio": 1.0,
        "level": "neutral",
        "interpretation": "多空比数据暂不可用（默认值1.0）",
        "data_date": _today(),
    }


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


# === Daemon handler registration ===

from .daemon import register_daemon_method
from .context import build_context


def register_daemon_handlers() -> None:
    build_context(db_path=None, output_dir=None, python="python3")

    def _fetch_funding_rate(params):
        return fetch_funding_rate(params.get("symbol"))

    def _fetch_open_interest(params):
        return fetch_open_interest(params.get("symbol"))

    def _fetch_long_short_ratio(params):
        return fetch_long_short_ratio(params.get("symbol"))

    def _get_crypto_factors(params):
        return get_crypto_factors(params.get("symbol"))

    register_daemon_method("fetch_funding_rate", _fetch_funding_rate)
    register_daemon_method("fetch_open_interest", _fetch_open_interest)
    register_daemon_method("fetch_long_short_ratio", _fetch_long_short_ratio)
    register_daemon_method("get_crypto_factors", _get_crypto_factors)
