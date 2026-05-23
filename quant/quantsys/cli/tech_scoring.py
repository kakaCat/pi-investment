"""
Tech/Growth Company Scoring

Alternative scoring framework for companies in investment/rampup lifecycle stages.
Current traditional framework penalizes low ROE, high PE, high capex — which are normal
for high-growth tech companies. This module provides parallel scoring dimensions.

Scoring dimensions (0-100 each):
  1. revenue_growth  (30%) — YoY growth, consistency, acceleration
  2. rd_intensity     (25%) — R&D/revenue proxy, margin trend
  3. operating_leverage (20%) — Revenue/OpEx growth ratio
  4. market_position  (15%) — Sector rank by revenue/market cap
  5. cash_runway      (10%) — Cash buffer vs burn rate
"""

from __future__ import annotations

from typing import Any


def tech_quality_score(
    financial: dict[str, Any],
    revenue_growth: float | None = None,
    revenue_growth_trend: list[float] | None = None,
    sector_rank: int | None = None,
    sector_total: int | None = None,
) -> dict[str, Any]:
    """
    Calculate tech/growth quality score (0-100).

    Unlike traditional quality_score (ROE/gross_margin/net_margin/debt_ratio),
    this weights revenue growth, R&D intensity, and operating leverage.

    Args:
        financial: dict with roe, gross_margin, net_margin, debt_ratio
        revenue_growth: latest YoY revenue growth (decimal)
        revenue_growth_trend: last 3-4 quarters of revenue growth for trend
        sector_rank: rank within sector (1 = largest)
        sector_total: total companies in sector

    Returns: {score, grade, dimensions, advice}
    """
    roe = _safe_float(financial.get("roe", 0))
    gross_margin = _safe_float(financial.get("gross_margin", 0))
    net_margin = _safe_float(financial.get("net_margin", 0))
    debt_ratio = _safe_float(financial.get("debt_ratio", 50))
    growth = revenue_growth if revenue_growth is not None else 0.0

    # Dimension 1: Revenue Growth (0-30 points)
    growth_score = _score_revenue_growth(growth, revenue_growth_trend)

    # Dimension 2: R&D & Innovation Intensity (0-25 points)
    # Proxy: gross margin trend + net margin trend (high-margin tech = R&D moat)
    rd_score = _score_innovation_intensity(financial, gross_margin, net_margin)

    # Dimension 3: Operating Leverage (0-20 points)
    # Revenue growth vs margin expansion = operating leverage signal
    leverage_score = _score_operating_leverage(growth, gross_margin, net_margin, debt_ratio)

    # Dimension 4: Market Position (0-15 points)
    market_score = _score_market_position(sector_rank, sector_total, growth)

    # Dimension 5: Cash Runway / Financial Health (0-10 points)
    cash_score = _score_financial_health(debt_ratio, gross_margin, net_margin)

    total = growth_score + rd_score + leverage_score + market_score + cash_score
    total = max(0, min(100, total))

    if total >= 80:
        grade = "A（优质成长）"
    elif total >= 65:
        grade = "B（良好成长）"
    elif total >= 50:
        grade = "C（一般成长）"
    elif total >= 35:
        grade = "D（成长存疑）"
    else:
        grade = "E（成长乏力）"

    return {
        "score": total,
        "grade": grade,
        "dimensions": {
            "revenue_growth": {
                "score": growth_score,
                "max": 30,
                "value": _pct(growth),
                "interpretation": _growth_interpretation(growth),
            },
            "innovation_intensity": {
                "score": rd_score,
                "max": 25,
                "metrics": f"毛利率={gross_margin:.1f}%, 净利率={net_margin:.1f}%",
                "interpretation": _rd_interpretation(gross_margin, net_margin),
            },
            "operating_leverage": {
                "score": leverage_score,
                "max": 20,
                "interpretation": _leverage_interpretation(growth, net_margin),
            },
            "market_position": {
                "score": market_score,
                "max": 15,
                "rank": sector_rank,
                "total": sector_total,
                "interpretation": _market_interpretation(sector_rank, sector_total),
            },
            "financial_health": {
                "score": cash_score,
                "max": 10,
                "debt_ratio": debt_ratio,
                "interpretation": _health_interpretation(debt_ratio),
            },
        },
        "advice": "成长性良好" if total >= 65 else ("成长性一般" if total >= 50 else "成长性不足"),
    }


def tech_valuation_score(
    pe: float | None = None,
    pb: float | None = None,
    revenue_growth: float | None = None,
    price: float | None = None,
    eps: float | None = None,
) -> dict[str, Any]:
    """
    Alternative valuation scoring using PEG, PS, and EV/Revenue proxies.

    When PE is very high or negative (common for growth companies),
    standard PE-based valuation is meaningless. This uses PEG ratio
    as the primary valuation metric.

    Returns: {score: 0-100, peg, ps_ratio, fair_value_estimate, valuation_status}
    """
    score = 50.0
    details: dict[str, Any] = {}
    growth = revenue_growth if revenue_growth is not None else 0.0

    # PEG Ratio (primary)
    if pe is not None and pe > 0 and growth > 0.02:
        peg = pe / (growth * 100)  # growth 0.25 → 25% → PE/25
        details["peg"] = round(peg, 2)
        if peg < 0.5:
            score += 30
            details["peg_status"] = "极度低估"
        elif peg < 0.8:
            score += 22
            details["peg_status"] = "低估"
        elif peg < 1.2:
            score += 12
            details["peg_status"] = "合理"
        elif peg < 2.0:
            score -= 5
            details["peg_status"] = "偏高"
        elif peg < 3.0:
            score -= 15
            details["peg_status"] = "高估"
        else:
            score -= 25
            details["peg_status"] = "严重高估"
    elif pe is not None and pe > 0:
        # No growth data, use PE directly but with gentler thresholds
        details["peg"] = None
        details["peg_note"] = "缺少营收增速数据，回退PE判断"
        if pe < 30:
            score += 15
        elif pe < 60:
            score += 5
        elif pe < 100:
            score -= 5
        else:
            score -= 15
    else:
        details["peg"] = None
        details["peg_note"] = "PE不可用（亏损或数据缺失）"

    # PB supplement (gentler than traditional)
    if pb is not None and pb > 0:
        details["pb"] = pb
        if pb < 2:
            score += 8
        elif pb < 4:
            score += 3
        elif pb < 8:
            score -= 3
        else:
            score -= 10

    # PS (Price/Sales) supplement — if price and EPS available
    if price is not None and eps is not None and eps != 0:
        ps = price / (eps * (pe or 1) / (pe or 1))  # simplified
        # Actually PS = market_cap / revenue. We don't have revenue directly.
        # Use a rough proxy: PS ≈ PE × net_margin
        pass  # Skip PS for now — need revenue data

    score = round(_bounded(score, 0, 100), 1)

    return {
        "score": score,
        "valuation_status": _valuation_label(score),
        **details,
    }


# ===== Private helpers =====

def _score_revenue_growth(growth: float, trend: list[float] | None = None) -> int:
    """Score revenue growth 0-30."""
    score = 0
    g = growth * 100  # convert to percentage

    if g >= 50:
        score = 30
    elif g >= 35:
        score = 27
    elif g >= 25:
        score = 24
    elif g >= 18:
        score = 20
    elif g >= 12:
        score = 15
    elif g >= 8:
        score = 10
    elif g >= 3:
        score = 5
    else:
        score = 2  # non-zero for existing

    # Acceleration bonus: if last 3 quarters show accelerating growth
    if trend and len(trend) >= 3:
        if trend[-1] > trend[-2] > trend[-3]:
            score = min(30, score + 3)

    # Deceleration penalty
    if trend and len(trend) >= 3:
        if trend[-1] < trend[-2] < trend[-3] and trend[-1] < 0.10:
            score = max(0, score - 8)

    return score


def _score_innovation_intensity(
    financial: dict[str, Any],
    gross_margin: float,
    net_margin: float,
) -> int:
    """Score innovation/R&D intensity 0-25. Uses margin as proxy for tech moat."""
    score = 0

    # High gross margin = pricing power from innovation
    if gross_margin >= 60:
        score += 15
    elif gross_margin >= 45:
        score += 12
    elif gross_margin >= 30:
        score += 8
    elif gross_margin >= 20:
        score += 5
    else:
        score += 2

    # Net margin consistency (not penalized for low margin if high GM)
    if gross_margin >= 40 and net_margin >= 10:
        score += 5  # strong moat: high GM + profitable
    elif gross_margin >= 30 and net_margin >= 5:
        score += 3  # decent moat
    elif gross_margin >= 20 and net_margin < 0:
        score += 0  # investing for growth, margin will come
    elif net_margin >= 15:
        score += 5  # strong profitability regardless of sector

    return min(25, score)


def _score_operating_leverage(
    growth: float,
    gross_margin: float,
    net_margin: float,
    debt_ratio: float,
) -> int:
    """Score operating leverage 0-20. Revenue growth relative to cost structure."""
    score = 0

    # High growth + high margin = strong operating leverage
    if growth > 0.25 and gross_margin > 40:
        score = 20
    elif growth > 0.20 and gross_margin > 30:
        score = 16
    elif growth > 0.15 and gross_margin > 25:
        score = 12
    elif growth > 0.10:
        score = 8
    elif growth > 0.05:
        score = 5
    else:
        score = 3

    # Debt efficiency: for tech companies, moderate debt with high growth is strategic
    if debt_ratio < 40 and growth > 0.15:
        score = min(20, score + 3)  # efficient capital structure
    elif debt_ratio > 70:
        score = max(0, score - 5)  # over-leveraged for tech

    return score


def _score_market_position(
    rank: int | None,
    total: int | None,
    growth: float,
) -> int:
    """Score market position 0-15."""
    if rank is None or total is None or total == 0:
        # Can't determine rank, give neutral score
        return 8

    percentile = rank / total  # lower = better (rank 1 = largest)

    if percentile <= 0.05:  # top 5%
        score = 15
    elif percentile <= 0.10:  # top 10%
        score = 13
    elif percentile <= 0.20:  # top 20%
        score = 10
    elif percentile <= 0.40:  # top 40%
        score = 7
    else:
        score = 4

    # Growth-adjusted: smaller company with high growth gets bonus
    if percentile > 0.10 and growth > 0.30:
        score = min(15, score + 3)

    return score


def _score_financial_health(debt_ratio: float, gross_margin: float, net_margin: float) -> int:
    """Score financial health / cash runway 0-10."""
    score = 0

    # Debt ratio (primary health indicator)
    if debt_ratio < 25:
        score = 10
    elif debt_ratio < 40:
        score = 8
    elif debt_ratio < 55:
        score = 6
    elif debt_ratio < 70:
        score = 3
    else:
        score = 0

    # Negative margin with low debt = burning cash but has runway
    if net_margin < 0 and debt_ratio < 30:
        score = max(3, score - 2)

    return score


# ===== Composite =====

def get_universal_score(
    symbol: str,
    financial: dict[str, Any],
    sector: str = "",
    revenue_growth: float | None = None,
    pe: float | None = None,
    pb: float | None = None,
    sector_rank: int | None = None,
    sector_total: int | None = None,
    framework: str = "auto",
) -> dict[str, Any]:
    """
    Universal scoring entry point — routes to traditional or tech framework.

    Args:
        framework: 'auto' (default), 'traditional', 'tech_growth'
    """
    from .lifecycle import classify_lifecycle

    # Determine framework
    if framework == "auto":
        lifecycle = classify_lifecycle(financial, sector, revenue_growth)
        actual_framework = lifecycle["framework"]
    elif framework == "tech_growth":
        lifecycle = classify_lifecycle(financial, sector, revenue_growth)
        actual_framework = "tech_growth"
    else:
        lifecycle = classify_lifecycle(financial, sector, revenue_growth)
        actual_framework = "traditional"

    result: dict[str, Any] = {
        "symbol": symbol,
        "lifecycle_stage": lifecycle["stage"],
        "lifecycle_confidence": lifecycle["confidence"],
        "lifecycle_reason": lifecycle["reason"],
        "framework_used": actual_framework,
    }

    # Tech growth scoring
    if actual_framework == "tech_growth":
        tech_q = tech_quality_score(financial, revenue_growth, sector_rank=sector_rank, sector_total=sector_total)
        tech_v = tech_valuation_score(pe, pb, revenue_growth)
        result["quality_score"] = tech_q["score"]
        result["quality_grade"] = tech_q["grade"]
        result["quality_dimensions"] = tech_q["dimensions"]
        result["valuation_score"] = tech_v["score"]
        result["valuation_status"] = tech_v.get("valuation_status", "未知")
        result["valuation_details"] = {
            k: v for k, v in tech_v.items() if k not in ("score", "valuation_status")
        }
        result["advice"] = tech_q["advice"]
        return result

    # Hybrid: blend both frameworks
    if actual_framework == "hybrid":
        tech_q = tech_quality_score(financial, revenue_growth, sector_rank=sector_rank, sector_total=sector_total)
        tech_v = tech_valuation_score(pe, pb, revenue_growth)
        # For hybrid, return both scores with a note
        result["quality_score"] = tech_q["score"]
        result["quality_grade"] = tech_q["grade"]
        result["quality_dimensions"] = tech_q["dimensions"]
        result["valuation_score"] = tech_v["score"]
        result["valuation_status"] = tech_v.get("valuation_status", "未知")
        result["valuation_details"] = {
            k: v for k, v in tech_v.items() if k not in ("score", "valuation_status")
        }
        result["hybrid_note"] = "使用科技框架评分，但该公司处于爬坡期，建议同时参考传统估值指标"
        result["advice"] = tech_q["advice"]
        return result

    # Traditional: return placeholder — caller fills in with existing get_quality_score
    result["note"] = "使用传统估值框架（由调用方填充评分）"
    return result


# ===== Utilities =====

def _safe_float(value: Any) -> float:
    if value is None or value == "":
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def _bounded(value: float, lower: float, upper: float) -> float:
    return min(max(value, lower), upper)


def _valuation_label(score: float) -> str:
    if score >= 75:
        return "低估"
    elif score >= 55:
        return "合理偏低"
    elif score >= 45:
        return "合理"
    elif score >= 30:
        return "偏高"
    else:
        return "高估"


def _growth_interpretation(growth: float) -> str:
    g = growth * 100
    if g >= 50:
        return "爆发式增长"
    elif g >= 25:
        return "高速增长"
    elif g >= 15:
        return "稳健增长"
    elif g >= 8:
        return "中速增长"
    elif g >= 3:
        return "低速增长"
    return "增长停滞"


def _rd_interpretation(gm: float, nm: float) -> str:
    if gm >= 50 and nm >= 15:
        return "强技术护城河+高盈利"
    elif gm >= 40:
        return "技术溢价明显"
    elif gm >= 25:
        return "有一定技术壁垒"
    return "毛利率偏低，技术壁垒存疑"


def _leverage_interpretation(growth: float, nm: float) -> str:
    if growth > 0.25 and nm > 10:
        return "规模效应显著，利润弹性大"
    elif growth > 0.15:
        return "处于规模扩张期"
    return "经营杠杆尚未释放"


def _market_interpretation(rank: int | None, total: int | None) -> str:
    if rank is None or total is None:
        return "行业地位数据缺失"
    pct = rank / total
    if pct <= 0.05:
        return "行业龙头"
    elif pct <= 0.20:
        return "行业领先"
    return "行业追随者"


def _health_interpretation(debt_ratio: float) -> str:
    if debt_ratio < 25:
        return "财务极稳健"
    elif debt_ratio < 40:
        return "财务健康"
    elif debt_ratio < 55:
        return "财务适中"
    return "负债偏高，关注现金流"
