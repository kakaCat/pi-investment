"""
Company Lifecycle Classifier

Classifies companies into 3 stages based on financial ratios + sector:
  - investment: Heavy capex/R&D phase, low ROE, high growth → use tech framework
  - rampup:    Assets coming online, ROE improving → use hybrid framework  
  - mature:    Stable ROE, moderate capex → use traditional framework

Used by get_quality_score() to route to the appropriate scoring framework.
"""

from __future__ import annotations

from typing import Any

# Sectors where tech/growth framework may apply
TECH_SECTORS = frozenset({
    "半导体", "芯片", "集成电路", "电子", "计算机", "软件",
    "人工智能", "AI", "云计算", "大数据", "互联网", "SaaS",
    "新能源", "光伏", "锂电池", "储能", "氢能源",
    "生物医药", "创新药", "医疗器械", "基因",
    "机器人", "无人机", "自动驾驶", "航空航天",
    "通信", "5G", "6G", "物联网",
})

# Sectors that are ALWAYS mature (overrides tech signals)
MATURE_SECTORS = frozenset({
    "银行", "保险", "煤炭", "钢铁", "水泥", "电力",
    "高速公路", "铁路", "港口", "水务", "燃气",
    "白酒", "食品", "饮料", "农业", "养殖",
    "房地产",
})


def classify_lifecycle(
    financial: dict[str, Any],
    sector: str = "",
    revenue_growth: float | None = None,
    market_cap_billion: float | None = None,
) -> dict[str, Any]:
    """
    Classify a company's lifecycle stage.

    Args:
        financial: dict with keys: roe, gross_margin, net_margin, debt_ratio
        sector: Chinese sector/industry name
        revenue_growth: YoY revenue growth rate (decimal, e.g. 0.25 = 25%)
        market_cap_billion: Market cap in billions CNY (for context)

    Returns:
        {
            "stage": "investment" | "rampup" | "mature",
            "confidence": 0.0-1.0,
            "reason": str,
            "framework": "tech_growth" | "traditional" | "hybrid",
        }
    """
    # Guard: mature sectors always use traditional framework
    for ms in MATURE_SECTORS:
        if ms in sector:
            return {
                "stage": "mature",
                "confidence": 0.95,
                "reason": f"行业'{sector}'属于成熟行业，使用传统估值框架",
                "framework": "traditional",
            }

    roe = _safe_float(financial.get("roe", 0))
    net_margin = _safe_float(financial.get("net_margin", 0))
    debt_ratio = _safe_float(financial.get("debt_ratio", 50))
    growth = revenue_growth if revenue_growth is not None else 0.0

    # Check if sector is tech-related
    is_tech = _sector_matches(sector, TECH_SECTORS)

    # === Investment Phase Detection ===
    investment_signals = 0
    investment_reasons: list[str] = []

    if is_tech:
        investment_signals += 1
        investment_reasons.append(f"行业'{sector}'属于科技/成长型行业")

    if roe < 8 and net_margin < 10:
        investment_signals += 1
        investment_reasons.append(f"ROE={roe:.1f}%+净利率={net_margin:.1f}%，典型投资期特征")

    if growth > 0.25:
        investment_signals += 1
        investment_reasons.append(f"营收增速{_pct(growth)}，高速成长期")

    if debt_ratio < 50 and growth > 0.15:
        # Low debt + high growth = likely equity-funded growth phase
        investment_signals += 1
        investment_reasons.append("低负债+高增长，股权融资驱动扩张期")

    # Strong investment phase: ≥3 signals
    if investment_signals >= 3:
        return {
            "stage": "investment",
            "confidence": min(0.6 + investment_signals * 0.1, 0.95),
            "reason": "；".join(investment_reasons),
            "framework": "tech_growth",
        }

    # Moderate: 2 signals with tech sector
    if investment_signals >= 2 and is_tech:
        return {
            "stage": "investment",
            "confidence": 0.6,
            "reason": "；".join(investment_reasons),
            "framework": "tech_growth",
        }

    # === Ramp-up Phase Detection ===
    ramp_signals = 0
    ramp_reasons: list[str] = []

    if is_tech:
        ramp_signals += 1
        ramp_reasons.append(f"行业'{sector}'具有成长属性")

    if 8 <= roe < 15:
        ramp_signals += 1
        ramp_reasons.append(f"ROE={roe:.1f}%处于改善期")

    if 0.10 <= growth < 0.30:
        ramp_signals += 1
        ramp_reasons.append(f"营收增速{_pct(growth)}，稳健成长期")

    if ramp_signals >= 2:
        return {
            "stage": "rampup",
            "confidence": 0.5 + ramp_signals * 0.1,
            "reason": "；".join(ramp_reasons),
            "framework": "hybrid",
        }

    # If in tech sector but didn't trigger investment or rampup, still check
    if is_tech and investment_signals == 2:
        return {
            "stage": "rampup",
            "confidence": 0.5,
            "reason": f"行业'{sector}'属于科技行业但财务指标接近传统公司，使用混合框架",
            "framework": "hybrid",
        }

    # === Default: Mature ===
    return {
        "stage": "mature",
        "confidence": 0.7,
        "reason": f"ROE={roe:.1f}%, 净利率={net_margin:.1f}%, 负债率={debt_ratio:.1f}%，符合成熟公司特征",
        "framework": "traditional",
    }


def _sector_matches(sector: str, sector_set: frozenset[str]) -> bool:
    """Check if sector string contains any known tech/mature sector keyword."""
    if not sector:
        return False
    for keyword in sector_set:
        if keyword in sector:
            return True
    return False


def _safe_float(value: Any) -> float:
    if value is None or value == "":
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _pct(value: float) -> str:
    return f"{value * 100:.0f}%"
