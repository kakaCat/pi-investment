"""Auxiliary tools for market analysis - geopolitical detection and objective scoring."""

from __future__ import annotations

import re
from typing import Any
from datetime import datetime


def detect_geopolitical(text: str) -> dict[str, Any]:
    """检测地缘政治风险 - 基于关键词匹配"""
    if not text or not isinstance(text, str):
        return {
            "risk_level": "none",
            "sentiment_penalty": 0,
            "matched_keywords": [],
            "interpretation": "无文本输入",
        }

    # 地缘政治关键词库（中英文）
    keywords = {
        "severe": ["战争", "核武器", "军事冲突", "war", "nuclear", "military conflict"],
        "high": ["制裁", "封锁", "禁运", "军事", "sanctions", "blockade", "embargo", "military"],
        "moderate": ["冲突", "贸易战", "关税", "conflict", "trade war", "tariff"],
        "low": ["紧张", "谈判", "争端", "tension", "negotiation", "dispute"],
    }

    matched = []
    max_level = "none"
    sentiment_penalty = 0

    text_lower = text.lower()

    # 检测关键词
    for level, words in keywords.items():
        for word in words:
            if word.lower() in text_lower:
                matched.append(word)
                if level == "severe":
                    max_level = "severe"
                    sentiment_penalty = -50
                elif level == "high" and max_level not in ["severe"]:
                    max_level = "high"
                    sentiment_penalty = -30
                elif level == "moderate" and max_level not in ["severe", "high"]:
                    max_level = "moderate"
                    sentiment_penalty = -15
                elif level == "low" and max_level == "none":
                    max_level = "low"
                    sentiment_penalty = -5

    # 去重
    matched = list(set(matched))

    # 解读
    if max_level == "severe":
        interpretation = f"检测到严重地缘政治风险（关键词: {', '.join(matched[:3])}），建议大幅降低风险敞口"
    elif max_level == "high":
        interpretation = f"检测到较高地缘政治风险（关键词: {', '.join(matched[:3])}），建议谨慎操作"
    elif max_level == "moderate":
        interpretation = f"检测到中等地缘政治风险（关键词: {', '.join(matched[:3])}），建议关注事态发展"
    elif max_level == "low":
        interpretation = f"检测到轻微地缘政治风险（关键词: {', '.join(matched[:3])}），影响有限"
    else:
        interpretation = "未检测到明显地缘政治风险"

    return {
        "risk_level": max_level,
        "sentiment_penalty": sentiment_penalty,
        "matched_keywords": matched[:5],  # 最多返回5个
        "interpretation": interpretation,
        "analyzed_at": _now(),
    }


def calculate_objective_score(symbol: str) -> dict[str, Any]:
    """计算客观评分 - 技术面 + 基本面综合评分"""
    try:
        # 导入必要的模块
        from .analysis_query import calculate_technical_indicators, analyze_price_action
        from .financial_query import get_financial_indicators

        # 获取技术指标
        tech_indicators = calculate_technical_indicators(symbol)
        price_action = analyze_price_action(symbol)

        # 技术面评分（0-100）
        tech_score = _calculate_technical_score(tech_indicators, price_action)

        # 获取基本面数据
        try:
            financial = get_financial_indicators(symbol)
            fundamental_score = _calculate_fundamental_score(financial)
        except Exception:
            financial = {}
            fundamental_score = 50  # 默认中性分数

        # 综合评分（技术面60%，基本面40%）
        overall_score = tech_score * 0.6 + fundamental_score * 0.4

        # 操作建议
        if overall_score >= 75:
            recommendation = "BUY"
            interpretation = f"综合评分 {overall_score:.1f}/100 - 强烈看好，建议买入"
        elif overall_score >= 60:
            recommendation = "HOLD_BUY"
            interpretation = f"综合评分 {overall_score:.1f}/100 - 偏向看好，可考虑买入"
        elif overall_score >= 40:
            recommendation = "HOLD"
            interpretation = f"综合评分 {overall_score:.1f}/100 - 中性观望，持有为主"
        elif overall_score >= 25:
            recommendation = "HOLD_SELL"
            interpretation = f"综合评分 {overall_score:.1f}/100 - 偏向看空，可考虑减仓"
        else:
            recommendation = "SELL"
            interpretation = f"综合评分 {overall_score:.1f}/100 - 强烈看空，建议卖出"

        return {
            "symbol": symbol,
            "overall_score": round(overall_score, 1),
            "technical_score": round(tech_score, 1),
            "fundamental_score": round(fundamental_score, 1),
            "recommendation": recommendation,
            "interpretation": interpretation,
            "breakdown": {
                "technical": _get_technical_breakdown(tech_indicators, price_action),
                "fundamental": _get_fundamental_breakdown(financial),
            },
            "calculated_at": _now(),
        }
    except Exception as exc:
        return {
            "error": str(exc),
            "symbol": symbol,
            "overall_score": 50.0,
            "recommendation": "HOLD",
            "interpretation": "评分计算失败，建议人工分析",
        }


def _calculate_technical_score(indicators: dict, price_action: dict) -> float:
    """计算技术面评分"""
    score = 50.0  # 基础分数

    # RSI 评分（±15分）
    rsi_data = indicators.get("rsi", {})
    if isinstance(rsi_data, dict):
        rsi_value = rsi_data.get("value", 50)
    else:
        rsi_value = rsi_data if isinstance(rsi_data, (int, float)) else 50

    if rsi_value < 30:
        score += 15  # 超卖，加分
    elif rsi_value < 40:
        score += 8
    elif rsi_value > 70:
        score -= 15  # 超买，减分
    elif rsi_value > 60:
        score -= 8

    # MACD 评分（±15分）
    macd_data = indicators.get("macd", {})
    if isinstance(macd_data, dict):
        dif = macd_data.get("dif", 0)
        dea = macd_data.get("dea", 0)
        if dif > dea and dif > 0:
            score += 15  # 金叉且在零轴上方
        elif dif > dea:
            score += 8  # 金叉但在零轴下方
        elif dif < dea and dif < 0:
            score -= 15  # 死叉且在零轴下方
        elif dif < dea:
            score -= 8  # 死叉但在零轴上方

    # 布林带评分（±10分）
    bollinger_data = indicators.get("bollinger", {})
    if isinstance(bollinger_data, dict):
        interpretation = bollinger_data.get("interpretation", "")
        if "超卖" in interpretation or "下轨" in interpretation:
            score += 10
        elif "超买" in interpretation or "上轨" in interpretation:
            score -= 10

    # 价格行为评分（±10分）
    if isinstance(price_action, dict):
        support_resistance = price_action.get("support_resistance", {})
        if isinstance(support_resistance, dict):
            distance_to_support = support_resistance.get("distance_to_support_pct", 0)
            if distance_to_support < 2:
                score += 10  # 接近支撑位
            elif distance_to_support > 10:
                score -= 5  # 远离支撑位

    return max(0, min(100, score))


def _calculate_fundamental_score(financial: dict) -> float:
    """计算基本面评分"""
    if not financial or not isinstance(financial, dict):
        return 50.0

    score = 50.0

    # ROE 评分（±15分）
    roe = financial.get("roe")
    if roe is not None:
        if roe > 20:
            score += 15
        elif roe > 15:
            score += 10
        elif roe > 10:
            score += 5
        elif roe < 5:
            score -= 10

    # 负债率评分（±10分）
    debt_ratio = financial.get("debt_to_asset_ratio")
    if debt_ratio is not None:
        if debt_ratio < 30:
            score += 10
        elif debt_ratio < 50:
            score += 5
        elif debt_ratio > 70:
            score -= 10
        elif debt_ratio > 60:
            score -= 5

    # 毛利率评分（±10分）
    gross_margin = financial.get("gross_profit_margin")
    if gross_margin is not None:
        if gross_margin > 50:
            score += 10
        elif gross_margin > 30:
            score += 5
        elif gross_margin < 15:
            score -= 10

    # 营收增长评分（±15分）
    revenue_growth = financial.get("revenue_growth_yoy")
    if revenue_growth is not None:
        if revenue_growth > 30:
            score += 15
        elif revenue_growth > 15:
            score += 10
        elif revenue_growth > 5:
            score += 5
        elif revenue_growth < -10:
            score -= 15
        elif revenue_growth < 0:
            score -= 8

    return max(0, min(100, score))


def _get_technical_breakdown(indicators: dict, price_action: dict) -> dict:
    """获取技术面评分细节"""
    breakdown = {}

    rsi_data = indicators.get("rsi", {})
    if isinstance(rsi_data, dict):
        breakdown["rsi"] = rsi_data.get("interpretation", "")

    macd_data = indicators.get("macd", {})
    if isinstance(macd_data, dict):
        breakdown["macd"] = macd_data.get("interpretation", "")

    bollinger_data = indicators.get("bollinger", {})
    if isinstance(bollinger_data, dict):
        breakdown["bollinger"] = bollinger_data.get("interpretation", "")

    return breakdown


def _get_fundamental_breakdown(financial: dict) -> dict:
    """获取基本面评分细节"""
    if not financial or not isinstance(financial, dict):
        return {}

    breakdown = {}

    roe = financial.get("roe")
    if roe is not None:
        breakdown["roe"] = f"ROE {roe:.2f}%"

    debt_ratio = financial.get("debt_to_asset_ratio")
    if debt_ratio is not None:
        breakdown["debt_ratio"] = f"负债率 {debt_ratio:.2f}%"

    gross_margin = financial.get("gross_profit_margin")
    if gross_margin is not None:
        breakdown["gross_margin"] = f"毛利率 {gross_margin:.2f}%"

    revenue_growth = financial.get("revenue_growth_yoy")
    if revenue_growth is not None:
        breakdown["revenue_growth"] = f"营收增长 {revenue_growth:.2f}%"

    return breakdown


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# === Daemon handler registration ===

from .daemon import register_daemon_method
from .context import build_context


def register_daemon_handlers() -> None:
    build_context(db_path=None, output_dir=None, python="python3")

    def _detect_geopolitical(params):
        return detect_geopolitical(params.get("text", ""))

    def _calculate_objective_score(params):
        return calculate_objective_score(params.get("symbol"))

    register_daemon_method("detect_geopolitical", _detect_geopolitical)
    register_daemon_method("calculate_objective_score", _calculate_objective_score)
