"""Market Sentiment Analysis Module.

Analyzes market sentiment indicators to provide a composite fear/greed score.
"""

from __future__ import annotations

from typing import Any


def calculate_sentiment_score(
    north_flow_data: dict[str, Any] | None,
    margin_data: dict[str, Any] | None,
    hot_stocks_data: dict[str, Any] | None,
    market_overview_data: dict[str, Any] | None,
    macro_data: dict[str, Any] | None,
) -> dict[str, Any]:
    """Calculate composite sentiment score from individual indicators.

    Args:
        north_flow_data: Northbound capital flow data
        margin_data: Margin trading balance data
        hot_stocks_data: Hot stocks ranking data
        market_overview_data: Market indices overview
        macro_data: Macro indicators (PMI, CPI, GDP)

    Returns:
        Dictionary with sentiment_score, sentiment_label, advice, and indicators breakdown
    """
    indicators: dict[str, Any] = {}
    details: dict[str, Any] = {}

    # 1. Northbound flow analysis (weight: 30%)
    if north_flow_data and not north_flow_data.get("error"):
        north_result = _analyze_north_flow(north_flow_data)
        if north_result["score"] is not None:
            indicators["north_flow"] = north_result
            details["north_flow"] = north_result["details"]

    # 2. Margin trading analysis (weight: 20%)
    if margin_data and not margin_data.get("error"):
        margin_result = _analyze_margin(margin_data)
        if margin_result["score"] is not None:
            indicators["margin"] = margin_result
            details["margin"] = margin_result["details"]

    # 3. Market breadth / hot stocks (weight: 20%)
    if hot_stocks_data and not hot_stocks_data.get("error"):
        breadth_result = _analyze_market_breadth(hot_stocks_data)
        if breadth_result["score"] is not None:
            indicators["market_breadth"] = breadth_result
            details["market_breadth"] = breadth_result["details"]

    # 4. Market trend (weight: 15%)
    if market_overview_data and not market_overview_data.get("error"):
        trend_result = _analyze_market_trend(market_overview_data)
        if trend_result["score"] is not None:
            indicators["market_trend"] = trend_result
            details["market_trend"] = trend_result["details"]

    # 5. Macro sentiment (weight: 15%)
    if macro_data and not macro_data.get("error"):
        macro_result = _analyze_macro(macro_data)
        if macro_result["score"] is not None:
            indicators["macro"] = macro_result
            details["macro"] = macro_result["details"]

    # Calculate weighted average
    total_weight = 0.0
    weighted_score = 0.0

    for key, indicator in indicators.items():
        score = indicator.get("score")
        weight = indicator.get("weight", 0.0)
        if score is not None:
            weighted_score += score * weight
            total_weight += weight

    if total_weight == 0:
        sentiment_score = 50  # neutral fallback
    else:
        sentiment_score = round(min(100, max(0, weighted_score / total_weight)))

    sentiment_label = _get_sentiment_label(sentiment_score)
    advice = _get_sentiment_advice(sentiment_label)

    return {
        "sentiment_score": sentiment_score,
        "sentiment_label": sentiment_label,
        "advice": advice,
        "indicators": indicators,
        "details": details,
    }


def _analyze_north_flow(data: dict[str, Any]) -> dict[str, Any]:
    """Analyze northbound capital flow sentiment."""
    flows = data.get("data", [])
    if not flows or len(flows) < 2:
        return {"score": None, "weight": 0.30, "details": {"error": "无有效北向资金数据"}}

    # Calculate recent trend: sum last 10 days
    recent_flows = flows[-10:] if len(flows) >= 10 else flows
    total_inflow = sum(float(f.get("amount_billion", 0)) for f in recent_flows)
    avg_inflow = total_inflow / len(recent_flows)

    # Normalize: -50亿/day = 0, +50亿/day = 100
    raw_score = ((avg_inflow + 50) / 100) * 100
    score = round(min(100, max(0, raw_score)))

    # Count consecutive inflow/outflow days
    consecutive_inflow = 0
    consecutive_outflow = 0
    for f in reversed(recent_flows):
        inflow = float(f.get("amount_billion", 0))
        if inflow > 0:
            consecutive_inflow += 1
            consecutive_outflow = 0
        else:
            consecutive_outflow += 1
            consecutive_inflow = 0

    trend = "外资净流入" if total_inflow > 0 else "外资净流出"

    return {
        "score": score,
        "weight": 0.30,
        "details": {
            "total_inflow_10d": round(total_inflow, 2),
            "avg_daily_inflow": round(avg_inflow, 2),
            "consecutive_inflow_days": consecutive_inflow,
            "consecutive_outflow_days": consecutive_outflow,
            "trend": trend,
        },
    }


def _analyze_margin(data: dict[str, Any]) -> dict[str, Any]:
    """Analyze margin trading sentiment."""
    margins = data.get("data", [])
    if not margins or len(margins) < 2:
        return {"score": None, "weight": 0.20, "details": {"error": "无有效融资融券数据"}}

    latest = margins[-1]
    prev = margins[-2]

    latest_balance = float(latest.get("total_margin", 0))
    prev_balance = float(prev.get("total_margin", 0))

    if prev_balance == 0:
        return {"score": None, "weight": 0.20, "details": {"error": "融资融券数据异常"}}

    change_pct = ((latest_balance - prev_balance) / prev_balance) * 100

    # Normalize: -2% = 0, +2% = 100
    raw_score = ((change_pct + 2) / 4) * 100
    score = round(min(100, max(0, raw_score)))

    trend = "融资余额上升" if change_pct > 0 else "融资余额下降"

    return {
        "score": score,
        "weight": 0.20,
        "details": {
            "latest_balance": round(latest_balance, 2),
            "change_pct": round(change_pct, 2),
            "trend": trend,
        },
    }


def _analyze_market_breadth(data: dict[str, Any]) -> dict[str, Any]:
    """Analyze market breadth via hot stocks."""
    stocks = data.get("data", [])
    if not stocks:
        return {"score": None, "weight": 0.20, "details": {"error": "无热门股票数据"}}

    # Extract change percentages
    changes = []
    for stock in stocks:
        # Try different field names
        change = stock.get("涨跌幅") or stock.get("change_pct") or stock.get("pct_chg")
        if change is not None:
            try:
                changes.append(float(change))
            except (ValueError, TypeError):
                continue

    if not changes:
        return {"score": None, "weight": 0.20, "details": {"error": "无有效涨跌幅数据"}}

    avg_change = sum(changes) / len(changes)
    extreme_count = sum(1 for c in changes if abs(c) > 5)

    # Normalize: -5% = 0, +5% = 100
    raw_score = ((avg_change + 5) / 10) * 100
    score = round(min(100, max(0, raw_score)))

    sentiment = "热点过热" if avg_change > 3 else "热点恐慌" if avg_change < -3 else "正常"

    return {
        "score": score,
        "weight": 0.20,
        "details": {
            "hot_stock_count": len(stocks),
            "avg_change": round(avg_change, 2),
            "extreme_count": extreme_count,
            "sentiment": sentiment,
        },
    }


def _analyze_market_trend(data: dict[str, Any]) -> dict[str, Any]:
    """Analyze market trend via indices."""
    indices = data.get("indices", {})
    if not indices:
        return {"score": None, "weight": 0.15, "details": {"error": "无指数数据"}}

    changes = [float(idx.get("change_pct", 0)) for idx in indices.values()]
    if not changes:
        return {"score": None, "weight": 0.15, "details": {"error": "无有效指数涨跌幅"}}

    avg_change = sum(changes) / len(changes)
    advancing = sum(1 for c in changes if c > 0)
    declining = sum(1 for c in changes if c < 0)

    # Normalize: -3% = 0, +3% = 100
    raw_score = ((avg_change + 3) / 6) * 100
    score = round(min(100, max(0, raw_score)))

    trend = "强势上涨" if avg_change > 0.5 else "明显下跌" if avg_change < -0.5 else "震荡整理"

    return {
        "score": score,
        "weight": 0.15,
        "details": {
            "avg_change": round(avg_change, 2),
            "advancing_indices": advancing,
            "declining_indices": declining,
            "trend": trend,
        },
    }


def _analyze_macro(data: dict[str, Any]) -> dict[str, Any]:
    """Analyze macro sentiment via PMI."""
    pmi_data = data.get("pmi")
    if not pmi_data or not isinstance(pmi_data, list) or len(pmi_data) == 0:
        return {"score": None, "weight": 0.15, "details": {"error": "无PMI数据"}}

    latest_pmi = pmi_data[0]
    pmi_value = float(latest_pmi.get("value", 50))
    pmi_date = latest_pmi.get("date", "")

    # Normalize: 48 = 0, 52 = 100
    raw_score = ((pmi_value - 48) / 4) * 50 + 50
    score = round(min(100, max(0, raw_score)))

    trend = "扩张区间" if pmi_value > 50 else "收缩区间" if pmi_value < 50 else "荣枯线"

    return {
        "score": score,
        "weight": 0.15,
        "details": {
            "pmi_value": round(pmi_value, 2),
            "pmi_date": pmi_date,
            "trend": trend,
        },
    }


def _get_sentiment_label(score: int) -> str:
    """Map sentiment score to label."""
    if score >= 80:
        return "极度贪婪"
    if score >= 65:
        return "贪婪"
    if score >= 55:
        return "偏贪婪"
    if score >= 45:
        return "中性"
    if score >= 35:
        return "偏恐惧"
    if score >= 20:
        return "恐惧"
    return "极度恐惧"


def _get_sentiment_advice(label: str) -> str:
    """Get actionable advice based on sentiment label."""
    advice_map = {
        "极度贪婪": "⚠️ 市场情绪极度亢奋，短期回调风险极高。建议减仓锁定利润，避免追高。",
        "贪婪": "⚡ 市场情绪偏热，部分板块可能已透支。建议控制仓位，分批止盈。",
        "偏贪婪": "📈 市场情绪积极，但需警惕过热信号。持有为主，谨慎加仓。",
        "中性": "➖ 市场情绪中性，无明显极端信号。维持现有策略，按计划执行。",
        "偏恐惧": "📉 市场情绪偏冷，部分优质资产可能被错杀。关注超跌机会，分批建仓。",
        "恐惧": "🔦 市场恐慌蔓延，但往往孕育机会。检查持仓基本面，考虑逢低吸纳优质股。",
        "极度恐惧": "🛡️ 市场极度恐慌，历史经验表明这是中长期布局良机。保持冷静，做好资金管理。",
    }
    return advice_map.get(label, "")
