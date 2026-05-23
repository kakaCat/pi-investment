"""Analysis helpers exposed through the QuantSys CLI."""

from __future__ import annotations

import math
from datetime import datetime
from typing import Any

from .market_query import get_sector_list
from .stock_query import (
    _clean_symbol,
    _disable_proxy_env,
    _safe_float,
    get_stock_history,
    get_stock_info,
    get_stock_quote,
)


def calculate_technical_indicators(symbol: str) -> dict[str, Any]:
    """Calculate MA, MACD, RSI, Bollinger Bands, and compact signals."""
    clean = _clean_symbol(symbol)
    try:
        frame = _history_frame(clean, limit=90)
        if len(frame) < 30:
            return {"error": "历史数据不足", "symbol": clean}

        close = frame["close"].astype(float)
        ma5 = close.rolling(5).mean().iloc[-1]
        ma10 = close.rolling(10).mean().iloc[-1]
        ma20 = close.rolling(20).mean().iloc[-1]
        ma60 = close.rolling(60).mean().iloc[-1] if len(frame) >= 60 else None

        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()
        dif = ema12 - ema26
        dea = dif.ewm(span=9, adjust=False).mean()

        delta = close.diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss.replace(0, float("nan"))
        rsi = 100 - (100 / (1 + rs))

        bb_mid = close.rolling(20).mean()
        bb_std = close.rolling(20).std()
        current = _safe_float(close.iloc[-1])
        signals: list[str] = []

        if current > _safe_float(ma5) > _safe_float(ma20):
            signals.append("短期多头排列")
        elif current < _safe_float(ma5) < _safe_float(ma20):
            signals.append("短期空头排列")
        if ma60 is not None and not _is_nan(ma60):
            if current > _safe_float(ma60):
                signals.append("站上60日均线")
            elif current < _safe_float(ma60):
                signals.append("跌破60日均线")
        rsi_value = _safe_float(rsi.iloc[-1])
        if rsi_value > 70:
            signals.append("RSI超买")
        elif rsi_value < 30:
            signals.append("RSI超卖")
        signals.append("MACD金叉" if _safe_float(dif.iloc[-1]) > _safe_float(dea.iloc[-1]) else "MACD死叉")

        dif_val = _safe_float(dif.iloc[-1])
        dea_val = _safe_float(dea.iloc[-1])
        histogram_val = _safe_float((dif - dea).iloc[-1] * 2)
        bb_upper = _safe_float((bb_mid + 2 * bb_std).iloc[-1])
        bb_mid_val = _safe_float(bb_mid.iloc[-1])
        bb_lower = _safe_float((bb_mid - 2 * bb_std).iloc[-1])

        return {
            "symbol": clean,
            "current_price": current,
            "ma": {
                "ma5": _safe_float(ma5),
                "ma10": _safe_float(ma10),
                "ma20": _safe_float(ma20),
                "ma60": _safe_float(ma60) if ma60 is not None and not _is_nan(ma60) else None,
            },
            "macd": {
                "dif": dif_val,
                "dea": dea_val,
                "histogram": histogram_val,
                "interpretation": _interpret_macd(dif_val, dea_val, histogram_val),
            },
            "rsi": {
                "value": rsi_value,
                "interpretation": _interpret_rsi(rsi_value),
            },
            "rsi_14": rsi_value,  # 保留向后兼容
            "bollinger": {
                "upper": bb_upper,
                "mid": bb_mid_val,
                "lower": bb_lower,
                "interpretation": _interpret_bollinger(current, bb_upper, bb_mid_val, bb_lower),
            },
            "signals": signals,
            "data_date": _today(),
        }
    except Exception as exc:
        return {"error": str(exc), "symbol": clean}


def analyze_price_action(symbol: str, period: int = 60) -> dict[str, Any]:
    """Analyze recent trend, momentum, volatility, volume, and key levels."""
    clean = _clean_symbol(symbol)
    if not (clean.isdigit() and len(clean) == 6):
        return {"error": "symbol 必须为 6 位 A 股代码", "symbol": clean}

    try:
        lookback = max(int(period or 60), 60)
        frame = _history_frame(clean, limit=max(lookback, 260))
        if len(frame) < 60:
            return {"error": "历史数据不足（需要至少60个交易日）", "symbol": clean}

        recent = frame.tail(lookback).copy().reset_index(drop=True)
        close = recent["close"].astype(float)
        high = recent["high"].astype(float)
        low = recent["low"].astype(float)
        volume = recent["volume"].astype(float)
        current = float(close.iloc[-1])

        ma5 = close.rolling(5, min_periods=5).mean().iloc[-1]
        ma20 = close.rolling(20, min_periods=20).mean().iloc[-1]
        ma60 = close.rolling(60, min_periods=60).mean().iloc[-1]
        direction, strength = _trend_strength(current, ma5, ma20, ma60)

        kdj = _kdj(high.tolist(), low.tolist(), close.tolist())
        kdj_k, kdj_d, kdj_j = kdj["k"][-1], kdj["d"][-1], kdj["j"][-1]
        if kdj_k >= 80 and kdj_d >= 80:
            kdj_signal = "超买"
        elif kdj_k <= 20 and kdj_d <= 20:
            kdj_signal = "超卖"
        else:
            kdj_signal = "中性"

        cci_value = _cci(high.tolist(), low.tolist(), close.tolist())[-1]
        if cci_value >= 100:
            cci_signal = "超买"
        elif cci_value <= -100:
            cci_signal = "超卖"
        else:
            cci_signal = "中性"

        prev_close = close.shift(1)
        true_range = _concat_max(high - low, (high - prev_close).abs(), (low - prev_close).abs())
        atr = float(true_range.rolling(14, min_periods=14).mean().iloc[-1])

        rolling_peak = close.cummax()
        max_drawdown = float((close / rolling_peak - 1).min() * 100)
        obv = (_sign(close.diff().fillna(0)) * volume).cumsum()
        obv_anchor = obv.iloc[-5] if len(obv) >= 5 else obv.iloc[0]
        if obv.iloc[-1] > obv_anchor:
            obv_trend = "上升"
        elif obv.iloc[-1] < obv_anchor:
            obv_trend = "下降"
        else:
            obv_trend = "震荡"

        recent_52w = frame.tail(250).reset_index(drop=True)
        high_52w = float(recent_52w["high"].astype(float).max())
        low_52w = float(recent_52w["low"].astype(float).min())
        streak_direction, streak_days = _streak(close.tolist())

        # 计算交易建议价格
        support = _safe_float(low.min())
        resistance = _safe_float(high.max())
        suggested_stop_loss = _safe_float(current - atr * 2)  # 当前价 - 2倍ATR
        suggested_take_profit = _safe_float(current + atr * 3)  # 当前价 + 3倍ATR

        return {
            "symbol": clean,
            "period": lookback,
            "trend": {
                "ma5": _safe_float(ma5),
                "ma20": _safe_float(ma20),
                "ma60": _safe_float(ma60),
                "direction": direction,
                "strength": strength,
            },
            "momentum": {
                "kdj_k": _safe_float(kdj_k),
                "kdj_d": _safe_float(kdj_d),
                "kdj_j": _safe_float(kdj_j),
                "signal": kdj_signal,
            },
            "cci": {"cci": _safe_float(cci_value), "signal": cci_signal},
            "support_resistance": {
                "support": support,
                "resistance": resistance,
            },
            "volatility": {
                "atr": _safe_float(atr),
                "atr_pct": _safe_float(atr / current * 100 if current else 0),
                "max_drawdown_pct": _safe_float(max_drawdown),
            },
            "trading_levels": {
                "suggested_stop_loss": suggested_stop_loss,
                "suggested_take_profit": suggested_take_profit,
                "risk_reward_ratio": _safe_float((suggested_take_profit - current) / (current - suggested_stop_loss) if current > suggested_stop_loss else 0),
            },
            "volume": {
                "obv": _safe_float(obv.iloc[-1], decimals=0),
                "obv_trend": obv_trend,
                "volume_ma5": _safe_float(volume.rolling(5).mean().iloc[-1], decimals=0),
            },
            "price_range_52w": {
                "high_52w": _safe_float(high_52w),
                "low_52w": _safe_float(low_52w),
                "distance_to_high_52w_pct": _safe_float((current - high_52w) / high_52w * 100 if high_52w else 0),
                "distance_to_low_52w_pct": _safe_float((current - low_52w) / low_52w * 100 if low_52w else 0),
            },
            "streak": {"direction": streak_direction, "days": streak_days},
            "current_price": _safe_float(current),
            "data_date": _today(),
        }
    except Exception as exc:
        return {"error": str(exc), "symbol": clean}


def analyze_candlestick(symbol: str) -> dict[str, Any]:
    """Detect candlestick patterns, trend lines, Fibonacci levels, and gaps."""
    clean = _clean_symbol(symbol)
    try:
        frame = _history_frame(clean, limit=120)
        if len(frame) < 30:
            return {"error": "历史数据不足，无法进行K线形态分析", "symbol": clean}

        dates = [str(item) for item in frame["date"].tolist()]
        open_values = frame["open"].astype(float).tolist()
        high = frame["high"].astype(float).tolist()
        low = frame["low"].astype(float).tolist()
        close = frame["close"].astype(float).tolist()

        patterns = _candlestick_patterns(dates, open_values, high, low, close)
        trend_lines = _trend_lines(high, low, close)
        fib = _fibonacci(high, low, close)
        gaps = _price_gaps(dates, high, low)
        summary = _candlestick_summary(patterns, trend_lines, fib, gaps)

        return {
            "symbol": clean,
            "current_price": _safe_float(close[-1]),
            "patterns": patterns,
            "trend_lines": trend_lines,
            "fibonacci": fib,
            "gaps": gaps,
            "summary": summary,
            "data_date": _today(),
        }
    except Exception as exc:
        return {"error": str(exc), "symbol": clean}


def calculate_buy_range(symbol: str, current_price: float | None = None) -> dict[str, Any]:
    """Calculate reference buy ranges from technical and PE-derived support."""
    clean = _clean_symbol(symbol)
    try:
        frame = _history_frame(clean, limit=90)
        if frame.empty:
            return {"error": f"无历史数据: {clean}", "symbol": clean}

        close = frame["close"].astype(float)
        low = frame["low"].astype(float)
        current = float(current_price) if current_price is not None else float(close.iloc[-1])
        ma20 = _safe_float(close.rolling(20).mean().iloc[-1])
        ma60 = _safe_float(close.rolling(60).mean().iloc[-1]) if len(frame) >= 60 else _safe_float(ma20 * 0.95)
        recent_low = _safe_float(low.tail(20).min())
        bb_lower = _safe_float((close.rolling(20).mean() - 2 * close.rolling(20).std()).iloc[-1])

        fundamental_support = _fundamental_support(clean, current)
        tech_supports = sorted([value for value in [ma20, ma60, recent_low, bb_lower] if value > 0])
        if not tech_supports:
            return {"error": f"无法计算技术支撑位: {clean}", "symbol": clean}

        tech_support = _safe_float(sum(tech_supports[:2]) / min(2, len(tech_supports)))
        if fundamental_support and fundamental_support > 0:
            ideal_buy = _safe_float(tech_support * 0.7 + fundamental_support * 0.3)
            safe_buy = _safe_float(tech_supports[0])
        else:
            ideal_buy = tech_support
            safe_buy = _safe_float(tech_supports[0])

        stop_loss = _safe_float(safe_buy * 0.92)
        target = _safe_float(ideal_buy + (ideal_buy - stop_loss) * 2)
        if current <= ideal_buy:
            advice = f"当前价{current}已在买入区间内，可分批建仓。止损位{stop_loss}"
        elif current <= ma20 * 1.05:
            advice = f"当前价{current}接近支撑区，可在{ideal_buy}~{safe_buy}区间分批买入。"
        else:
            advice = f"当前价{current}高于支撑区({ideal_buy})，建议等待回调。"

        result: dict[str, Any] = {
            "symbol": clean,
            "current_price": _safe_float(current),
            "safe_buy": safe_buy,
            "ideal_buy": ideal_buy,
            "stop_loss": stop_loss,
            "target_price": target,
            "support_levels": {
                "ma20": ma20,
                "ma60": ma60,
                "recent_low_20d": recent_low,
                "bollinger_lower": bb_lower,
            },
            "advice": advice,
            "risk_check": {
                "passed": True,
                "level": "reference_only",
                "reason": "CLI analysis provides price reference only; validate trend, quality, and portfolio risk separately.",
            },
            "position_advice": {
                "method": "reference_only",
                "position_pct": 0.1,
                "note": "Use portfolio/risk CLI tools for final position sizing.",
            },
            "stop_loss_method": "technical_support_8pct",
            "data_date": _today(),
        }
        if fundamental_support:
            result["fundamental_support"] = fundamental_support
        return result
    except Exception as exc:
        return {"error": str(exc), "symbol": clean}


# ⚠️ DEPRECATED — 实际生效的是 financial_query.py 的同名函数。
# main.py 导入 get_stock_valuation 来自 financial_query，
# daemon 也只注册了 financial_query 版本。保留此函数以避免
# 潜在的未发现调用方报错，但不再维护。
def get_stock_valuation(symbol: str) -> dict[str, Any]:
    """⚠️ DEPRECATED — 请使用 financial_query.get_stock_valuation。"""
    clean = _clean_symbol(symbol)
    try:
        quote = get_stock_quote(clean)
        if "error" in quote:
            return quote
        current_price = _safe_float(quote.get("price"))
        pe = _safe_float(quote.get("pe_dynamic"))
        pb = _safe_float(quote.get("pb"))
        if pe <= 0:
            status = "unknown"
        elif pe < 15:
            status = "cheap"
        elif pe < 25:
            status = "fair"
        elif pe < 40:
            status = "slightly_expensive"
        else:
            status = "expensive"
        fair_value = _safe_float((current_price / pe) * 28.5) if pe > 0 and current_price > 0 else None
        return {
            "symbol": clean,
            "name": quote.get("name", ""),
            "current_price": current_price,
            "pe": pe,
            "pb": pb,
            "valuation_status": status,
            "fair_value_estimate": fair_value,
            "data_date": _today(),
        }
    except Exception as exc:
        return {"error": str(exc), "symbol": clean}


def get_pe_percentile(symbol: str, years: int = 5) -> dict[str, Any]:
    """Estimate current PE percentile using current EPS and historical closes."""
    clean = _clean_symbol(symbol)
    try:
        bounded_years = max(1, min(int(years or 5), 5))
        frame = _history_frame(clean, limit=min(bounded_years * 250, 1200))
        if len(frame) < 60:
            return {"error": f"历史数据不足，无法计算PE分位数: {clean}", "symbol": clean}

        quote = get_stock_quote(clean)
        if "error" in quote:
            return quote
        current_pe = _safe_float(quote.get("pe_dynamic"))
        current_price = _safe_float(quote.get("price"))
        if current_pe <= 0:
            return {"error": f"当前PE无效（{current_pe}），可能是亏损股或数据缺失", "symbol": clean}
        eps = current_price / current_pe if current_price > 0 else None
        if not eps:
            return {"error": "无法计算EPS", "symbol": clean}

        hist_pe = [float(close) / eps for close in frame["close"].astype(float).tolist() if float(close) > 0]
        if not hist_pe:
            return {"error": f"无有效历史PE: {clean}", "symbol": clean}

        hist_pe_sorted = sorted(hist_pe)
        percentile = _safe_float(sum(1 for value in hist_pe if value < current_pe) / len(hist_pe) * 100)
        zone, signal = _pe_zone(percentile)

        return {
            "symbol": clean,
            "name": quote.get("name", ""),
            "current_pe": current_pe,
            "pe_percentile": percentile,
            "valuation_zone": zone,
            "signal": signal,
            "pe_stats": {
                "min": _safe_float(hist_pe_sorted[0]),
                "max": _safe_float(hist_pe_sorted[-1]),
                "median": _safe_float(_median(hist_pe_sorted)),
                "mean": _safe_float(sum(hist_pe_sorted) / len(hist_pe_sorted)),
            },
            "years_of_data": bounded_years,
            "data_points": len(hist_pe),
            "note": "历史PE基于当前EPS反推，适合盈利稳定的公司；高成长/周期股仅供参考",
            "data_date": _today(),
        }
    except Exception as exc:
        return {"error": str(exc), "symbol": clean}


def get_quality_score(symbol: str, framework: str = "auto") -> dict[str, Any]:
    """Score company quality from recent financial indicators.

    Args:
        symbol: Stock code
        framework: 'auto' (detect lifecycle → route), 'traditional' (original),
                   'tech_growth' (new tech framework)

    When framework='auto' (default), the function:
    1. Detects company lifecycle stage (investment / rampup / mature)
    2. Routes to appropriate scoring framework
    3. Returns additional lifecycle metadata fields

    Traditional framework (unchanged): ROE, gross_margin, net_margin, debt_ratio
    Tech framework: revenue_growth, innovation_intensity, operating_leverage,
                    market_position, financial_health
    """
    clean = _clean_symbol(symbol)
    try:
        financial = _get_financial_indicators(clean)
        if "error" in financial:
            return financial
        data = financial.get("data", [])
        if not data:
            return {"error": f"无财务数据: {clean}", "symbol": clean}

        latest = data[0]

        # ---- Lifecycle detection & routing ----
        if framework in ("auto", "tech_growth"):
            # Fetch sector info for lifecycle classification
            sector = ""
            revenue_growth = None
            try:
                info = get_stock_info(clean)
                if "error" not in info:
                    sector = str(info.get("sector") or info.get("industry") or "")
                    # Try to get revenue growth from market data
                    quote = get_stock_quote(clean)
                    rev_growth = info.get("revenue_growth")
                    if rev_growth is not None:
                        revenue_growth = _safe_float(rev_growth)
            except Exception:
                pass

            from .lifecycle import classify_lifecycle

            fin_dict = {
                "roe": _safe_float(latest.get("roe", 0)),
                "gross_margin": _safe_float(latest.get("gross_margin", 0)),
                "net_margin": _safe_float(latest.get("net_margin", 0)),
                "debt_ratio": _safe_float(latest.get("debt_ratio", 100)),
            }
            lifecycle = classify_lifecycle(fin_dict, sector, revenue_growth)

            # If framework=auto and lifecycle says tech → use tech scoring
            if framework == "auto" and lifecycle["framework"] == "tech_growth":
                return _get_tech_quality_score(clean, fin_dict, lifecycle, revenue_growth, sector)
            elif framework == "auto" and lifecycle["framework"] == "hybrid":
                return _get_hybrid_quality_score(clean, fin_dict, lifecycle, revenue_growth)
            elif framework == "tech_growth":
                return _get_tech_quality_score(clean, fin_dict, lifecycle, revenue_growth, sector)
            # else: framework=auto + lifecycle=mature → fall through to traditional

        # ---- Traditional scoring (original, unchanged) ----
        score = 0
        details: dict[str, Any] = {}
        roe = _safe_float(latest.get("roe", 0))
        details["roe"] = roe
        if roe >= 20:
            score += 40
        elif roe >= 15:
            score += 32
        elif roe >= 12:
            score += 24
        elif roe >= 8:
            score += 12

        if len(data) >= 3:
            roe_trend = [_safe_float(item.get("roe", 0)) for item in data[:3]]
            if roe_trend[2] >= roe_trend[1] >= roe_trend[0]:
                score -= 5
                details["roe_trend"] = "下降"
            elif roe_trend[0] >= roe_trend[1] >= roe_trend[2]:
                score += 5
                details["roe_trend"] = "上升"
            else:
                details["roe_trend"] = "稳定"

        debt_ratio = _safe_float(latest.get("debt_ratio", 100))
        details["debt_ratio"] = debt_ratio
        if debt_ratio < 30:
            score += 25
        elif debt_ratio < 50:
            score += 18
        elif debt_ratio < 65:
            score += 10
        elif debt_ratio < 80:
            score += 3

        gross_margin = _safe_float(latest.get("gross_margin", 0))
        details["gross_margin"] = gross_margin
        if gross_margin >= 50:
            score += 20
        elif gross_margin >= 35:
            score += 15
        elif gross_margin >= 20:
            score += 10
        elif gross_margin >= 10:
            score += 5

        net_margin = _safe_float(latest.get("net_margin", 0))
        details["net_margin"] = net_margin
        if net_margin >= 20:
            score += 15
        elif net_margin >= 10:
            score += 10
        elif net_margin >= 5:
            score += 5

        score = max(0, min(100, score))
        if score >= 80:
            grade = "A（优质）"
        elif score >= 65:
            grade = "B（良好）"
        elif score >= 50:
            grade = "C（一般）"
        elif score >= 35:
            grade = "D（较差）"
        else:
            grade = "E（差）"

        return {
            "symbol": clean,
            "score": score,
            "grade": grade,
            "details": details,
            "advice": "建议投资" if score >= 65 else ("谨慎考虑" if score >= 50 else "建议回避"),
            "framework_used": "traditional",
            "lifecycle_stage": "mature",
            "data_date": _today(),
        }
    except Exception as exc:
        return {"error": str(exc), "symbol": clean}


def _get_tech_quality_score(
    symbol: str,
    fin_dict: dict[str, Any],
    lifecycle: dict[str, Any],
    revenue_growth: float | None = None,
    sector: str = "",
) -> dict[str, Any]:
    """Route to tech_growth scoring framework."""
    from .tech_scoring import tech_quality_score, tech_valuation_score

    # Get PE/PB for valuation
    pe = None
    pb = None
    try:
        quote = get_stock_quote(symbol)
        if "error" not in quote:
            pe = _safe_float(quote.get("pe_dynamic"))
            pb = _safe_float(quote.get("pb"))
    except Exception:
        pass

    q = tech_quality_score(fin_dict, revenue_growth)
    v = tech_valuation_score(pe, pb, revenue_growth)

    # Determine overall grade from tech score
    score = q["score"]
    if score >= 80:
        overall_grade = "A（优质成长）"
    elif score >= 65:
        overall_grade = "B（良好成长）"
    elif score >= 50:
        overall_grade = "C（一般成长）"
    elif score >= 35:
        overall_grade = "D（成长存疑）"
    else:
        overall_grade = "E（成长乏力）"

    return {
        "symbol": symbol,
        "score": score,
        "grade": overall_grade,
        "details": {
            **q["dimensions"],
            # Flat fallbacks for backward compat (screening_query expects these)
            "roe": fin_dict.get("roe", 0),
            "gross_margin": fin_dict.get("gross_margin", 0),
            "net_margin": fin_dict.get("net_margin", 0),
            "debt_ratio": fin_dict.get("debt_ratio", 0),
        },
        "valuation_score": v["score"],
        "valuation_status": v.get("valuation_status", "未知"),
        "valuation_details": {k: vv for k, vv in v.items() if k not in ("score", "valuation_status")},
        "advice": "成长性良好" if score >= 65 else ("成长性一般" if score >= 50 else "成长性不足"),
        "framework_used": "tech_growth",
        "lifecycle_stage": lifecycle["stage"],
        "lifecycle_reason": lifecycle["reason"],
        "lifecycle_confidence": lifecycle["confidence"],
        "data_date": _today(),
    }


def _get_hybrid_quality_score(
    symbol: str,
    fin_dict: dict[str, Any],
    lifecycle: dict[str, Any],
    revenue_growth: float | None = None,
) -> dict[str, Any]:
    """Blend traditional and tech scoring for rampup-phase companies.

    Returns both scores + a blended recommendation, with traditional
    scoring as the primary grade but tech dimensions visible.
    """
    from .tech_scoring import tech_quality_score, tech_valuation_score

    # Traditional score (for backward compat)
    roe = fin_dict["roe"]
    gross_margin = fin_dict["gross_margin"]
    net_margin = fin_dict["net_margin"]
    debt_ratio = fin_dict["debt_ratio"]

    trad_score = 0
    if roe >= 20:
        trad_score += 40
    elif roe >= 15:
        trad_score += 32
    elif roe >= 12:
        trad_score += 24
    elif roe >= 8:
        trad_score += 12
    if debt_ratio < 30:
        trad_score += 25
    elif debt_ratio < 50:
        trad_score += 18
    elif debt_ratio < 65:
        trad_score += 10
    elif debt_ratio < 80:
        trad_score += 3
    if gross_margin >= 50:
        trad_score += 20
    elif gross_margin >= 35:
        trad_score += 15
    elif gross_margin >= 20:
        trad_score += 10
    elif gross_margin >= 10:
        trad_score += 5
    if net_margin >= 20:
        trad_score += 15
    elif net_margin >= 10:
        trad_score += 10
    elif net_margin >= 5:
        trad_score += 5
    trad_score = max(0, min(100, trad_score))

    # Tech score
    q = tech_quality_score(fin_dict, revenue_growth)
    tech_score = q["score"]

    # Blended: 60% traditional + 40% tech
    blended = round(trad_score * 0.6 + tech_score * 0.4, 1)

    if blended >= 80:
        grade = "A（优质）"
    elif blended >= 65:
        grade = "B（良好）"
    elif blended >= 50:
        grade = "C（一般）"
    elif blended >= 35:
        grade = "D（较差）"
    else:
        grade = "E（差）"

    return {
        "symbol": symbol,
        "score": blended,
        "grade": grade,
        "details": {
            "traditional_score": trad_score,
            "tech_growth_score": tech_score,
            "tech_dimensions": q["dimensions"],
            "blend_ratio": "传统60% + 科技40%",
            "roe": roe,
            "gross_margin": gross_margin,
            "net_margin": net_margin,
            "debt_ratio": debt_ratio,
        },
        "advice": "混合评估" if blended >= 50 else "建议回避",
        "framework_used": "hybrid",
        "lifecycle_stage": lifecycle["stage"],
        "lifecycle_reason": lifecycle["reason"],
        "hybrid_note": "处于爬坡期，同时参考传统和科技框架",
        "data_date": _today(),
    }


def get_exit_plan(symbol: str, buy_price: float, shares: int = 100) -> dict[str, Any]:
    """Calculate three-tier profit-taking targets and current P&L."""
    clean = _clean_symbol(symbol)
    try:
        quote = get_stock_quote(clean)
        if "error" in quote:
            return quote
        current_price = _safe_float(quote.get("price"))
        pe = _safe_float(quote.get("pe_dynamic"))
        buy = float(buy_price)
        share_count = int(shares or 100)

        if pe > 0 and current_price > 0:
            eps = current_price / pe
            base_pe = min(pe, 28.5)
            target_conservative = _safe_float(eps * base_pe * 1.2)
            target_moderate = _safe_float(eps * base_pe * 1.5)
            target_aggressive = _safe_float(eps * base_pe * 2.0)
        else:
            target_conservative = _safe_float(buy * 1.20)
            target_moderate = _safe_float(buy * 1.40)
            target_aggressive = _safe_float(buy * 1.60)

        pnl_pct = _safe_float((current_price - buy) / buy * 100 if buy else 0)
        pnl_amount = _safe_float((current_price - buy) * share_count)
        sell_plan = []
        if current_price >= target_conservative:
            sell_plan.append(f"已达保守目标({target_conservative})，建议卖出30%")
        if current_price >= target_moderate:
            sell_plan.append(f"已达中等目标({target_moderate})，建议再卖40%")
        if current_price >= target_aggressive:
            sell_plan.append(f"已达激进目标({target_aggressive})，建议清仓剩余30%")
        if not sell_plan:
            pct_to_target = _safe_float((target_conservative - current_price) / current_price * 100 if current_price else 0)
            sell_plan.append(f"距保守目标({target_conservative})还有{pct_to_target}%，继续持有")

        return {
            "symbol": clean,
            "name": quote.get("name", ""),
            "buy_price": buy,
            "current_price": current_price,
            "shares": share_count,
            "pnl_pct": pnl_pct,
            "pnl_amount": pnl_amount,
            "targets": {
                "conservative": target_conservative,
                "moderate": target_moderate,
                "aggressive": target_aggressive,
            },
            "sell_plan": sell_plan,
            "data_date": _today(),
        }
    except Exception as exc:
        return {"error": str(exc), "symbol": clean}


def compare_peers(symbol: str) -> dict[str, Any]:
    """Return target stock metrics and sector name for peer comparison workflow."""
    clean = _clean_symbol(symbol)
    try:
        info = get_stock_info(clean)
        if "error" in info:
            return info
        sector = str(info.get("sector") or info.get("industry") or "")
        if not sector:
            return {"error": f"无法获取 {clean} 的行业信息", "symbol": clean}

        sectors = get_sector_list()
        sector_items = sectors.get("data", []) if isinstance(sectors, dict) else []
        matched = next(
            (
                item
                for item in sector_items
                if item.get("name") and (str(item["name"]).find(sector) >= 0 or sector.find(str(item["name"])) >= 0)
            ),
            None,
        )
        sector_name = str(matched.get("name")) if matched else sector
        quote = get_stock_quote(clean)

        return {
            "symbol": clean,
            "name": info.get("name") or quote.get("name") or clean,
            "sector": sector_name,
            "target": {
                "symbol": clean,
                "name": info.get("name") or quote.get("name") or clean,
                "current_price": _safe_float(quote.get("price")),
                "change_pct": _safe_float(quote.get("change_pct")),
                "pe": _safe_float(info.get("pe_ttm") or info.get("pe_dynamic") or quote.get("pe_dynamic")),
                "pb": _safe_float(info.get("pb") or quote.get("pb")),
                "market_cap_billion": _safe_float(info.get("market_cap_billion") or quote.get("market_cap_billion")),
                "roe": _safe_float(info.get("roe", 0)),
                "gross_margin": _safe_float(info.get("gross_margin", 0)),
            },
            "peers_note": f"同行业（{sector_name}）对比数据需调用 screen_stocks_quality 获取，本工具已返回目标股基础数据。",
            "usage_hint": f"推荐工作流：1）已有目标股数据；2）调用 screen_stocks_quality(sector=\"{sector_name}\") 拿同行 Top 10；3）对比 PE/ROE/毛利率/市值。",
            "data_date": _today(),
        }
    except Exception as exc:
        return {"error": str(exc), "symbol": clean}


def _history_frame(symbol: str, limit: int):
    import pandas as pd

    history = get_stock_history(symbol=symbol, period="daily", limit=limit)
    if "error" in history:
        raise RuntimeError(str(history["error"]))
    records = history.get("data", [])
    if not records:
        return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])
    frame = pd.DataFrame(records).copy()
    for col in ["open", "high", "low", "close", "volume"]:
        frame[col] = pd.to_numeric(frame[col], errors="coerce")
    frame["date"] = frame["date"].astype(str)
    return frame.dropna(subset=["open", "high", "low", "close", "volume"]).sort_values("date").reset_index(drop=True)


def _annualize_quarterly(value: float, report_date: str) -> float:
    """年化单季度ROE（Q1×4, 中报×2, 三季报×4/3, 年报不变）。

    同花顺「按报告期」返回的 ROE 是各报告期独立值：
    - 一季报(03-31): 仅Q1 → ×4
    - 中报(06-30):  仅Q2或H1 → 按H1处理 ×2
    - 三季报(09-30): 前三季度 → ×4/3
    - 年报(12-31):   全年 → 不变

    报告日格式支持 YYYYMMDD 和 YYYY-MM-DD。
    """
    try:
        clean_date = report_date.replace("-", "")
        if clean_date.endswith("1231"):
            return value
        month = int(clean_date[4:6])
        if month == 3:
            return round(value * 4, 2)
        elif month == 6:
            return round(value * 2, 2)
        elif month == 9:
            return round(value * 4 / 3, 2)
    except Exception:
        pass
    return value


def _get_financial_indicators(symbol: str) -> dict[str, Any]:
    try:
        _disable_proxy_env()
        import akshare as ak

        frame = ak.stock_financial_abstract_ths(symbol=symbol, indicator="按报告期")
        if frame is None or frame.empty:
            return {"error": f"无财务数据: {symbol}", "symbol": symbol}
        frame = frame.tail(4).iloc[::-1]
        quarters = []

        def parse_pct(value: Any) -> float:
            if isinstance(value, str) and "%" in value:
                return _safe_float(value.replace("%", ""))
            return _safe_float(value)

        for _, row in frame.iterrows():
            report_date = str(row.get("报告期", ""))
            roe_raw = parse_pct(row.get("净资产收益率", 0))
            quarters.append({
                "report_date": report_date,
                "roe": _annualize_quarterly(roe_raw, report_date),
                "gross_margin": parse_pct(row.get("销售毛利率", 0)),
                "net_margin": parse_pct(row.get("销售净利率", 0)),
                "debt_ratio": parse_pct(row.get("资产负债率", 0)),
                "current_ratio": _safe_float(row.get("流动比率", 0)),
            })

        return {"symbol": symbol, "quarters": quarters, "data": quarters, "data_date": _today()}
    except Exception as exc:
        return {"error": str(exc), "symbol": symbol}


def _fundamental_support(symbol: str, current_price: float) -> float | None:
    quote = get_stock_quote(symbol)
    pe = _safe_float(quote.get("pe_dynamic")) if "error" not in quote else 0.0
    if pe <= 0 or current_price <= 0:
        return None
    eps = current_price / pe
    percentile = get_pe_percentile(symbol)
    median_pe = _safe_float((percentile.get("pe_stats") or {}).get("median", 0)) if "error" not in percentile else 0.0
    fair_pe = median_pe if median_pe > 0 else min(pe, 15.0)
    return _safe_float(eps * fair_pe)


def _trend_strength(current: float, ma5: float, ma20: float, ma60: float) -> tuple[str, str]:
    if current > ma5 > ma20 > ma60:
        gap_short = (ma5 - ma20) / ma20 * 100 if ma20 else 0
        gap_mid = (ma20 - ma60) / ma60 * 100 if ma60 else 0
        if gap_short >= 1 and gap_mid >= 2:
            return "上升", "强"
        if gap_short >= 0.3 and gap_mid >= 0.8:
            return "上升", "中"
        return "上升", "弱"
    if current < ma5 < ma20 < ma60:
        gap_short = (ma20 - ma5) / ma20 * 100 if ma20 else 0
        gap_mid = (ma60 - ma20) / ma60 * 100 if ma60 else 0
        if gap_short >= 1 and gap_mid >= 2:
            return "下降", "强"
        if gap_short >= 0.3 and gap_mid >= 0.8:
            return "下降", "中"
        return "下降", "弱"
    return "震荡", "弱"


def _kdj(high: list[float], low: list[float], close: list[float], n: int = 9) -> dict[str, list[float]]:
    k_values: list[float] = []
    d_values: list[float] = []
    j_values: list[float] = []
    last_k = 50.0
    last_d = 50.0
    for idx, close_value in enumerate(close):
        start = max(0, idx - n + 1)
        highest = max(high[start:idx + 1])
        lowest = min(low[start:idx + 1])
        rsv = 50.0 if highest == lowest else (close_value - lowest) / (highest - lowest) * 100
        last_k = rsv / 3 + last_k * 2 / 3
        last_d = last_k / 3 + last_d * 2 / 3
        last_j = 3 * last_k - 2 * last_d
        k_values.append(last_k)
        d_values.append(last_d)
        j_values.append(last_j)
    return {"k": k_values, "d": d_values, "j": j_values}


def _cci(high: list[float], low: list[float], close: list[float], period: int = 20) -> list[float]:
    values: list[float] = []
    typical = [(h + l + c) / 3 for h, l, c in zip(high, low, close)]
    for idx, value in enumerate(typical):
        if idx + 1 < period:
            values.append(0.0)
            continue
        window = typical[idx - period + 1:idx + 1]
        mean = sum(window) / len(window)
        mean_deviation = sum(abs(item - mean) for item in window) / len(window)
        values.append(0.0 if mean_deviation == 0 else (value - mean) / (0.015 * mean_deviation))
    return values


def _candlestick_patterns(
    dates: list[str],
    open_values: list[float],
    high: list[float],
    low: list[float],
    close: list[float],
    lookback: int = 10,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    start = max(2, len(close) - lookback)
    for idx in range(start, len(close)):
        o, h, l, c = open_values[idx], high[idx], low[idx], close[idx]
        body = abs(c - o)
        candle_range = h - l
        if c and body / c < 0.003 and candle_range > 0:
            results.append({"date": dates[idx], "pattern": "十字星", "type": "neutral", "strength": "moderate"})
            continue
        upper_shadow = h - max(o, c)
        lower_shadow = min(o, c) - l
        if candle_range > 0 and lower_shadow > 2 * body and upper_shadow < 0.3 * max(body, 0.01):
            pattern_type = "bullish" if _prior_trend(close, idx) == "down" else "bearish"
            pattern = "锤子线" if pattern_type == "bullish" else "上吊线"
            results.append({"date": dates[idx], "pattern": pattern, "type": pattern_type, "strength": "strong"})
            continue
        if idx >= 1:
            prev_o, prev_c = open_values[idx - 1], close[idx - 1]
            prev_body = abs(prev_c - prev_o)
            if prev_body > 0 and body > prev_body:
                if c > o and prev_c < prev_o and o <= prev_c and c >= prev_o:
                    results.append({"date": dates[idx], "pattern": "看涨吞没", "type": "bullish", "strength": "strong"})
                    continue
                if c < o and prev_c > prev_o and o >= prev_c and c <= prev_o:
                    results.append({"date": dates[idx], "pattern": "看跌吞没", "type": "bearish", "strength": "strong"})
                    continue
    return results


def _trend_lines(high: list[float], low: list[float], close: list[float], window: int = 5, lookback: int = 60) -> list[dict[str, Any]]:
    start = max(window, len(close) - lookback)
    swing_highs: list[tuple[int, float]] = []
    swing_lows: list[tuple[int, float]] = []
    for idx in range(start + window, len(close) - window):
        if high[idx] == max(high[idx - window:idx + window + 1]):
            swing_highs.append((idx, high[idx]))
        if low[idx] == min(low[idx - window:idx + window + 1]):
            swing_lows.append((idx, low[idx]))

    lines: list[dict[str, Any]] = []
    for points, line_type in [(swing_highs, "resistance"), (swing_lows, "support")]:
        if len(points) < 2:
            continue
        slope, intercept, r2 = _linear_regression(points)
        current_value = slope * (len(close) - 1) + intercept
        is_breaking = close[-1] > current_value * 1.01 if line_type == "resistance" else close[-1] < current_value * 0.99
        touch_count = sum(1 for x, y in points if y and abs(y - (slope * x + intercept)) / y < 0.01)
        lines.append({
            "type": line_type,
            "slope": _safe_float(slope, decimals=4),
            "currentValue": _safe_float(current_value),
            "touchCount": touch_count,
            "r2": _safe_float(r2, decimals=3),
            "isBreaking": is_breaking,
        })
    return lines


def _fibonacci(high: list[float], low: list[float], close: list[float], lookback: int = 60) -> dict[str, Any]:
    hi_slice = high[-lookback:]
    low_slice = low[-lookback:]
    swing_high = max(hi_slice)
    swing_low = min(low_slice)
    current = close[-1]
    direction = "retracing_down" if current >= (swing_high + swing_low) / 2 else "retracing_up"
    range_value = swing_high - swing_low
    levels = []
    for ratio in [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1]:
        price = swing_high - ratio * range_value if direction == "retracing_down" else swing_low + (1 - ratio) * range_value
        formatted = _safe_float(price)
        levels.append({
            "level": ratio,
            "price": formatted,
            "label": f"{ratio * 100:.1f}%",
            "isNearCurrent": abs(current - formatted) / current < 0.02 if current else False,
        })
    nearest = min(levels, key=lambda item: abs(item["price"] - current)) if levels else None
    return {
        "swingHigh": _safe_float(swing_high),
        "swingLow": _safe_float(swing_low),
        "direction": direction,
        "levels": levels,
        "nearestLevel": nearest,
    }


def _price_gaps(dates: list[str], high: list[float], low: list[float], min_gap_pct: float = 0.5, lookback: int = 60) -> list[dict[str, Any]]:
    gaps: list[dict[str, Any]] = []
    start = max(1, len(dates) - lookback)
    for idx in range(start, len(dates)):
        prev_high, prev_low = high[idx - 1], low[idx - 1]
        cur_low, cur_high = low[idx], high[idx]
        if cur_low > prev_high:
            gap_size = cur_low - prev_high
            gap_pct = gap_size / prev_high * 100 if prev_high else 0
            if gap_pct >= min_gap_pct:
                filled, fill_date = _gap_filled("up", idx, prev_high, high, low, dates)
                gaps.append({"date": dates[idx], "type": "gap_up", "gapSize": _safe_float(gap_size), "gapPct": _safe_float(gap_pct), "filled": filled, "fillDate": fill_date})
        if cur_high < prev_low:
            gap_size = prev_low - cur_high
            gap_pct = gap_size / prev_low * 100 if prev_low else 0
            if gap_pct >= min_gap_pct:
                filled, fill_date = _gap_filled("down", idx, prev_low, high, low, dates)
                gaps.append({"date": dates[idx], "type": "gap_down", "gapSize": _safe_float(gap_size), "gapPct": _safe_float(gap_pct), "filled": filled, "fillDate": fill_date})
    return gaps


def _gap_filled(gap_type: str, start_idx: int, boundary: float, high: list[float], low: list[float], dates: list[str]) -> tuple[bool, str | None]:
    for idx in range(start_idx + 1, len(dates)):
        if gap_type == "up" and low[idx] <= boundary:
            return True, dates[idx]
        if gap_type == "down" and high[idx] >= boundary:
            return True, dates[idx]
    return False, None


def _candlestick_summary(patterns: list[dict[str, Any]], trend_lines: list[dict[str, Any]], fib: dict[str, Any], gaps: list[dict[str, Any]]) -> str:
    parts = []
    if patterns:
        latest = patterns[-1]
        signal = "看涨" if latest.get("type") == "bullish" else ("看跌" if latest.get("type") == "bearish" else "中性")
        parts.append(f"最近出现{latest.get('pattern')}（{signal}信号）")
    nearest = fib.get("nearestLevel")
    if nearest:
        parts.append(f"价格在斐波那契{nearest.get('label')}回调位({nearest.get('price')})附近")
    breaking = [line for line in trend_lines if line.get("isBreaking")]
    if breaking:
        line = breaking[0]
        parts.append(f"正在突破{'阻力' if line.get('type') == 'resistance' else '支撑'}趋势线({line.get('currentValue')})")
    unfilled = [gap for gap in gaps if not gap.get("filled")]
    if unfilled:
        latest_gap = unfilled[-1]
        direction = "跳空向上" if latest_gap.get("type") == "gap_up" else "跳空向下"
        parts.append(f"存在{len(unfilled)}个未回补跳空缺口（最近：{latest_gap.get('date')} {direction}{latest_gap.get('gapPct')}%）")
    return "，".join(parts) + "。" if parts else "未检测到显著K线形态信号。"


def _linear_regression(points: list[tuple[int, float]]) -> tuple[float, float, float]:
    n = len(points)
    sum_x = sum(point[0] for point in points)
    sum_y = sum(point[1] for point in points)
    sum_xy = sum(point[0] * point[1] for point in points)
    sum_x2 = sum(point[0] ** 2 for point in points)
    denominator = n * sum_x2 - sum_x ** 2
    slope = (n * sum_xy - sum_x * sum_y) / denominator if denominator else 0.0
    intercept = (sum_y - slope * sum_x) / n
    y_mean = sum_y / n
    total = sum((point[1] - y_mean) ** 2 for point in points)
    residual = sum((point[1] - (slope * point[0] + intercept)) ** 2 for point in points)
    r2 = max(0.0, 1 - residual / total) if total else 0.0
    return slope, intercept, r2


def _prior_trend(close: list[float], idx: int) -> str:
    window = min(idx, 5)
    if window < 2:
        return "up"
    average = sum(close[idx - window:idx]) / window
    return "up" if close[idx - 1] > average else "down"


def _streak(close: list[float]) -> tuple[str, int]:
    if len(close) < 2:
        return "平", 0
    last_change = close[-1] - close[-2]
    if last_change == 0:
        return "平", 0
    direction = "上涨" if last_change > 0 else "下跌"
    days = 0
    for idx in range(len(close) - 1, 0, -1):
        change = close[idx] - close[idx - 1]
        if (last_change > 0 and change > 0) or (last_change < 0 and change < 0):
            days += 1
        else:
            break
    return direction, days


def _pe_zone(percentile: float) -> tuple[str, str]:
    if percentile <= 20:
        return "历史低估区（底部20%）", "bullish"
    if percentile <= 40:
        return "偏低估值区（20-40%）", "mild_bullish"
    if percentile <= 60:
        return "历史中位区（40-60%）", "neutral"
    if percentile <= 80:
        return "偏高估值区（60-80%）", "mild_bearish"
    return "历史高估区（顶部20%）", "bearish"


def _concat_max(*series: Any):
    import pandas as pd

    return pd.concat(series, axis=1).max(axis=1)


def _sign(series: Any):
    import numpy as np

    return np.sign(series)


def _median(values: list[float]) -> float:
    size = len(values)
    middle = size // 2
    if size % 2:
        return values[middle]
    return (values[middle - 1] + values[middle]) / 2


def _is_nan(value: Any) -> bool:
    try:
        return math.isnan(float(value))
    except (TypeError, ValueError):
        return False


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _interpret_rsi(rsi_value: float) -> str:
    """解读 RSI 指标"""
    if rsi_value >= 70:
        return f"RSI {rsi_value:.1f} 处于超买区域，短期可能面临回调压力"
    elif rsi_value >= 60:
        return f"RSI {rsi_value:.1f} 偏强，但尚未超买"
    elif rsi_value >= 40:
        return f"RSI {rsi_value:.1f} 在中性区域，无明显超买超卖"
    elif rsi_value >= 30:
        return f"RSI {rsi_value:.1f} 偏弱，但尚未超卖"
    else:
        return f"RSI {rsi_value:.1f} 处于超卖区域，可能存在反弹机会"


def _interpret_macd(dif: float, dea: float, histogram: float) -> str:
    """解读 MACD 指标"""
    if dif > dea:
        if histogram > 0 and dif > 0:
            return f"MACD 金叉且在零轴上方（DIF={dif:.2f}, DEA={dea:.2f}），多头趋势强劲"
        elif histogram > 0:
            return f"MACD 金叉（DIF={dif:.2f}, DEA={dea:.2f}），短期看涨信号"
        else:
            return f"MACD 在零轴下方但金叉（DIF={dif:.2f}, DEA={dea:.2f}），弱势反弹"
    else:
        if histogram < 0 and dif < 0:
            return f"MACD 死叉且在零轴下方（DIF={dif:.2f}, DEA={dea:.2f}），空头趋势强劲"
        elif histogram < 0:
            return f"MACD 死叉（DIF={dif:.2f}, DEA={dea:.2f}），短期看跌信号"
        else:
            return f"MACD 在零轴上方但死叉（DIF={dif:.2f}, DEA={dea:.2f}），强势回调"


def _interpret_bollinger(current: float, upper: float, mid: float, lower: float) -> str:
    """解读布林带指标"""
    if current >= upper:
        return f"价格触及布林带上轨（{upper:.2f}），可能超买"
    elif current >= mid + (upper - mid) * 0.5:
        return f"价格在布林带上半部（中轨={mid:.2f}），偏强"
    elif current >= mid:
        return f"价格在布林带中轨上方（{mid:.2f}），中性偏强"
    elif current >= lower + (mid - lower) * 0.5:
        return f"价格在布林带下半部（中轨={mid:.2f}），偏弱"
    else:
        return f"价格接近布林带下轨（{lower:.2f}），可能超卖"


# === Daemon handler registration ===

from .daemon import register_daemon_method
from .context import build_context


def register_daemon_handlers() -> None:
    build_context(db_path=None, output_dir=None, python="python3")

    def _calculate_technical(params):
        return calculate_technical_indicators(params.get("symbol"))

    def _analyze_candlestick(params):
        return analyze_candlestick(params.get("symbol"))

    def _analyze_price_action(params):
        return analyze_price_action(
            symbol=params.get("symbol"),
            period=params.get("period", 60),
        )

    def _calculate_buy_range(params):
        return calculate_buy_range(
            symbol=params.get("symbol"),
            current_price=params.get("current_price"),
        )

    def _get_exit_plan(params):
        return get_exit_plan(
            symbol=params.get("symbol"),
            buy_price=params.get("buy_price"),
            shares=params.get("shares", 100),
        )

    def _compare_peers(params):
        return compare_peers(params.get("symbol"))

    def _get_quality_score(params):
        return get_quality_score(
            params.get("symbol"),
            framework=params.get("framework", "auto"),
        )

    register_daemon_method("calculate_technical_indicators", _calculate_technical)
    register_daemon_method("analyze_technical", _calculate_technical)
    register_daemon_method("analyze_candlestick", _analyze_candlestick)
    register_daemon_method("analyze_price_action", _analyze_price_action)
    register_daemon_method("calculate_buy_range", _calculate_buy_range)
    register_daemon_method("get_buy_range", _calculate_buy_range)
    register_daemon_method("get_exit_plan", _get_exit_plan)
    register_daemon_method("compare_peers", _compare_peers)
    register_daemon_method("get_quality_score", _get_quality_score)
    register_daemon_method("get_tech_score", _get_quality_score)  # alias for explicit tech scoring
