"""Global macro indicators for market analysis."""

from __future__ import annotations

from typing import Any
from datetime import datetime


def fetch_vix() -> dict[str, Any]:
    """获取 VIX 恐慌指数（CBOE Volatility Index）"""
    try:
        import yfinance as yf

        ticker = yf.Ticker("^VIX")
        hist = ticker.history(period="5d")

        if hist is None or hist.empty or len(hist) < 1:
            return _default_vix()

        current = float(hist["Close"].iloc[-1])
        if current <= 0:
            return _default_vix()

        prev_close = float(hist["Close"].iloc[-2]) if len(hist) >= 2 else current
        change = ((current - prev_close) / prev_close) * 100 if prev_close else 0

        # VIX 解读
        if current < 12:
            level = "very_low"
            interpretation = f"VIX {current:.2f} 极低波动 - 市场极度乐观，警惕自满情绪"
        elif current < 20:
            level = "low"
            interpretation = f"VIX {current:.2f} 低波动 - 市场稳定，风险偏好较高"
        elif current < 25:
            level = "moderate"
            interpretation = f"VIX {current:.2f} 中等波动 - 正常水平，市场健康"
        elif current < 30:
            level = "high"
            interpretation = f"VIX {current:.2f} 高波动 - 市场担忧，注意风险"
        else:
            level = "very_high"
            interpretation = f"VIX {current:.2f} 极高波动 - 市场恐慌，可能是买入机会"

        return {
            "value": round(current, 2),
            "change": round(change, 2),
            "level": level,
            "interpretation": interpretation,
            "data_date": _today(),
        }
    except Exception as exc:
        return {"error": str(exc), **_default_vix()}


def fetch_dxy() -> dict[str, Any]:
    """获取美元指数（US Dollar Index）"""
    try:
        import yfinance as yf

        ticker = yf.Ticker("DX-Y.NYB")
        hist = ticker.history(period="5d")

        if hist is None or hist.empty or len(hist) < 1:
            return _default_dxy()

        current = float(hist["Close"].iloc[-1])
        if current <= 0:
            return _default_dxy()

        prev_close = float(hist["Close"].iloc[-2]) if len(hist) >= 2 else current
        change = ((current - prev_close) / prev_close) * 100 if prev_close else 0

        # DXY 解读
        if current > 105:
            level = "strong"
            interpretation = f"美元指数 {current:.2f} 强势 - 利空大宗商品和新兴市场，A股承压"
        elif current > 100:
            level = "moderate_strong"
            interpretation = f"美元指数 {current:.2f} 偏强 - 关注资金流向，可能影响A股"
        elif current > 95:
            level = "neutral"
            interpretation = f"美元指数 {current:.2f} 中性 - 市场均衡，对A股影响有限"
        elif current > 90:
            level = "moderate_weak"
            interpretation = f"美元指数 {current:.2f} 偏弱 - 利多风险资产，A股受益"
        else:
            level = "weak"
            interpretation = f"美元指数 {current:.2f} 疲软 - 利多黄金和大宗商品，A股受益"

        return {
            "value": round(current, 2),
            "change": round(change, 2),
            "level": level,
            "interpretation": interpretation,
            "data_date": _today(),
        }
    except Exception as exc:
        return {"error": str(exc), **_default_dxy()}


def fetch_tnx() -> dict[str, Any]:
    """获取美国10年期国债收益率（Treasury Yield 10Y）"""
    try:
        import yfinance as yf

        ticker = yf.Ticker("^TNX")
        hist = ticker.history(period="5d")

        if hist is None or hist.empty or len(hist) < 1:
            return _default_tnx()

        current = float(hist["Close"].iloc[-1])
        if current <= 0:
            return _default_tnx()

        prev_close = float(hist["Close"].iloc[-2]) if len(hist) >= 2 else current
        change = ((current - prev_close) / prev_close) * 100 if prev_close else 0

        # TNX 解读
        if current > 5.0:
            level = "very_high"
            interpretation = f"10年期美债收益率 {current:.2f}% 极高 - 资金成本高，利空股市"
        elif current > 4.5:
            level = "high"
            interpretation = f"10年期美债收益率 {current:.2f}% 偏高 - 关注利率压力"
        elif current > 3.5:
            level = "moderate"
            interpretation = f"10年期美债收益率 {current:.2f}% 中性 - 正常水平"
        elif current > 2.5:
            level = "low"
            interpretation = f"10年期美债收益率 {current:.2f}% 偏低 - 利好股市"
        else:
            level = "very_low"
            interpretation = f"10年期美债收益率 {current:.2f}% 极低 - 宽松环境，利好风险资产"

        return {
            "value": round(current, 2),
            "change": round(change, 2),
            "level": level,
            "interpretation": interpretation,
            "data_date": _today(),
        }
    except Exception as exc:
        return {"error": str(exc), **_default_tnx()}


def fetch_gold() -> dict[str, Any]:
    """获取黄金价格（Gold Futures）"""
    try:
        import yfinance as yf

        ticker = yf.Ticker("GC=F")
        hist = ticker.history(period="5d")

        if hist is None or hist.empty or len(hist) < 1:
            return _default_gold()

        current = float(hist["Close"].iloc[-1])
        if current <= 0:
            return _default_gold()

        prev_close = float(hist["Close"].iloc[-2]) if len(hist) >= 2 else current
        change = ((current - prev_close) / prev_close) * 100 if prev_close else 0

        # 黄金价格解读
        if current > 2400:
            level = "very_high"
            interpretation = f"黄金价格 ${current:.2f} 极高 - 避险情绪高涨，市场担忧"
        elif current > 2200:
            level = "high"
            interpretation = f"黄金价格 ${current:.2f} 偏高 - 避险需求上升"
        elif current > 1900:
            level = "moderate"
            interpretation = f"黄金价格 ${current:.2f} 中性 - 正常水平"
        elif current > 1700:
            level = "low"
            interpretation = f"黄金价格 ${current:.2f} 偏低 - 风险偏好较高"
        else:
            level = "very_low"
            interpretation = f"黄金价格 ${current:.2f} 极低 - 市场乐观，避险需求低"

        return {
            "value": round(current, 2),
            "change": round(change, 2),
            "level": level,
            "interpretation": interpretation,
            "data_date": _today(),
        }
    except Exception as exc:
        return {"error": str(exc), **_default_gold()}


def get_global_macro_indicators() -> dict[str, Any]:
    """获取全球宏观指标汇总"""
    vix = fetch_vix()
    dxy = fetch_dxy()
    tnx = fetch_tnx()
    gold = fetch_gold()

    # 综合市场情绪评估
    risk_score = 0
    signals = []

    # VIX 评分
    vix_level = vix.get("level", "unknown")
    if vix_level == "very_high":
        risk_score += 2
        signals.append("VIX极高-市场恐慌")
    elif vix_level == "high":
        risk_score += 1
        signals.append("VIX偏高-市场担忧")
    elif vix_level == "very_low":
        risk_score -= 1
        signals.append("VIX极低-警惕自满")

    # DXY 评分
    dxy_level = dxy.get("level", "unknown")
    if dxy_level == "strong":
        risk_score += 1
        signals.append("美元强势-资金外流压力")
    elif dxy_level == "weak":
        risk_score -= 1
        signals.append("美元疲软-利好新兴市场")

    # TNX 评分
    tnx_level = tnx.get("level", "unknown")
    if tnx_level == "very_high":
        risk_score += 1
        signals.append("美债收益率极高-资金成本高")
    elif tnx_level == "very_low":
        risk_score -= 1
        signals.append("美债收益率极低-宽松环境")

    # 黄金评分
    gold_level = gold.get("level", "unknown")
    if gold_level == "very_high":
        risk_score += 1
        signals.append("黄金价格极高-避险情绪高")

    # 综合评估
    if risk_score >= 3:
        overall_sentiment = "高风险"
        overall_interpretation = "多个指标显示市场风险偏高，建议谨慎操作，降低仓位"
    elif risk_score >= 1:
        overall_sentiment = "偏谨慎"
        overall_interpretation = "市场存在一定风险，建议适度控制仓位"
    elif risk_score <= -2:
        overall_sentiment = "偏乐观"
        overall_interpretation = "宏观环境相对友好，可适度增加风险敞口"
    else:
        overall_sentiment = "中性"
        overall_interpretation = "宏观指标整体中性，关注个股基本面"

    return {
        "vix": vix,
        "dxy": dxy,
        "tnx": tnx,
        "gold": gold,
        "overall": {
            "risk_score": risk_score,
            "sentiment": overall_sentiment,
            "interpretation": overall_interpretation,
            "signals": signals,
        },
        "data_date": _today(),
    }


def _default_vix() -> dict[str, Any]:
    return {
        "value": 18.0,
        "change": 0.0,
        "level": "low",
        "interpretation": "VIX 数据暂不可用（默认值18）",
        "data_date": _today(),
    }


def _default_dxy() -> dict[str, Any]:
    return {
        "value": 104.0,
        "change": 0.0,
        "level": "moderate_strong",
        "interpretation": "美元指数数据暂不可用（默认值104）",
        "data_date": _today(),
    }


def _default_tnx() -> dict[str, Any]:
    return {
        "value": 4.2,
        "change": 0.0,
        "level": "moderate",
        "interpretation": "美债收益率数据暂不可用（默认值4.2%）",
        "data_date": _today(),
    }


def _default_gold() -> dict[str, Any]:
    return {
        "value": 2000.0,
        "change": 0.0,
        "level": "moderate",
        "interpretation": "黄金价格数据暂不可用（默认值$2000）",
        "data_date": _today(),
    }


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


# === Daemon handler registration ===

from .daemon import register_daemon_method
from .context import build_context


def register_daemon_handlers() -> None:
    build_context(db_path=None, output_dir=None, python="python3")

    def _fetch_vix(params):
        return fetch_vix()

    def _fetch_dxy(params):
        return fetch_dxy()

    def _fetch_tnx(params):
        return fetch_tnx()

    def _fetch_gold(params):
        return fetch_gold()

    def _get_global_macro(params):
        return get_global_macro_indicators()

    register_daemon_method("fetch_vix", _fetch_vix)
    register_daemon_method("fetch_dxy", _fetch_dxy)
    register_daemon_method("fetch_tnx", _fetch_tnx)
    register_daemon_method("fetch_gold", _fetch_gold)
    register_daemon_method("get_global_macro_indicators", _get_global_macro)
    register_daemon_method("get_global_macro", _get_global_macro)
