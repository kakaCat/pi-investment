"""
Trading strategy analysis functions
"""
import pandas as pd
import pandas_ta as ta
from typing import Dict, Any, Optional
from ..cli.stock_query import get_stock_history, get_stock_quote, get_stock_info


def analyze_price_action(symbol: str, period: int = 60) -> Dict[str, Any]:
    """
    价格行为分析：趋势、支撑阻力、成交量、突破信号、动量、波动率

    Args:
        symbol: 股票代码
        period: 分析周期（天数），默认60天

    Returns:
        {
            "symbol": "600519",
            "period_days": 60,
            "current_price": 1311.0,
            "trend": {
                "direction": "下降",
                "period_return_pct": -8.5,
                "short_term": "偏弱",
                "medium_term": "偏弱",
                "ma_values": {"ma5": 1321.25, "ma20": 1371.03, "ma60": 1415.35}
            },
            "support_levels": [1290.21, 1250.0, 1200.0],
            "resistance_levels": [1350.0, 1400.0, 1450.0],
            "volume_analysis": {
                "latest_volume": 12500000,
                "avg_volume_5d": 10000000,
                "avg_volume_20d": 9500000,
                "volume_change_pct": 25.0,
                "volume_ratio_5d": 1.25,
                "volume_ratio_20d": 1.32,
                "obv_trend": "上升",
                "status": "平稳"
            },
            "breakout_signal": {
                "signal": "未突破",
                "confirmed": false,
                "reference_level": 1350.0,
                "reason": "价格仍处于区间内运行"
            },
            "momentum": {
                "kdj": {"k": 25.5, "d": 28.3, "j": 19.9},
                "cci": -85.2,
                "rsi_14": 26.1
            },
            "volatility": {
                "atr_14": 35.5,
                "atr_pct": 2.7
            },
            "data_date": "2026-05-21"
        }
    """
    lookback = max(60, min(period, 250))

    # 获取历史数据
    history = get_stock_history(symbol, period='daily', limit=lookback)
    if not history or 'data' not in history or len(history['data']) < 60:
        raise ValueError(f"历史数据不足60天: {symbol}")

    df = pd.DataFrame(history['data'])
    df['open'] = df['open'].astype(float)
    df['high'] = df['high'].astype(float)
    df['low'] = df['low'].astype(float)
    df['close'] = df['close'].astype(float)
    df['volume'] = df['volume'].astype(float)

    n = len(df)
    cur_price = float(df['close'].iloc[-1])
    prev_price = float(df['close'].iloc[-2])

    # 1. 趋势分析
    df['ma5'] = ta.sma(df['close'], length=5)
    df['ma20'] = ta.sma(df['close'], length=20)
    df['ma60'] = ta.sma(df['close'], length=60) if n >= 60 else None

    ma5 = float(df['ma5'].iloc[-1])
    ma20 = float(df['ma20'].iloc[-1])
    ma60 = float(df['ma60'].iloc[-1]) if df['ma60'] is not None else ma20

    period_return = round((cur_price - float(df['close'].iloc[0])) / float(df['close'].iloc[0]) * 100, 2)

    if cur_price > ma20 and ma20 >= ma60 and period_return > 5:
        trend_direction = "上升"
    elif cur_price < ma20 and ma20 <= ma60 and period_return < -5:
        trend_direction = "下降"
    else:
        trend_direction = "震荡"

    # 2. 支撑阻力位（简化版：使用MA和近期高低点）
    recent_high = float(df['high'].iloc[-20:].max())
    recent_low = float(df['low'].iloc[-20:].min())

    support_levels = sorted([
        round(ma20, 2),
        round(ma60, 2),
        round(recent_low, 2)
    ])

    resistance_levels = sorted([
        round(recent_high, 2),
        round(ma20 * 1.05, 2),
        round(ma60 * 1.1, 2)
    ])

    # 3. 成交量分析
    latest_volume = float(df['volume'].iloc[-1])
    avg_volume_5d = float(df['volume'].iloc[-6:-1].mean())
    avg_volume_20d = float(df['volume'].iloc[-21:-1].mean())

    volume_ratio_5d = round(latest_volume / avg_volume_5d, 2) if avg_volume_5d > 0 else 1.0
    volume_ratio_20d = round(latest_volume / avg_volume_20d, 2) if avg_volume_20d > 0 else 1.0
    volume_change_pct = round((latest_volume - avg_volume_5d) / avg_volume_5d * 100, 2) if avg_volume_5d > 0 else 0

    # OBV 趋势
    df['obv'] = ta.obv(df['close'], df['volume'])
    obv_trend = "上升" if df['obv'].iloc[-1] >= df['obv'].iloc[-6] else "下降"

    volume_status = "放量" if volume_ratio_5d >= 1.5 else "缩量" if volume_ratio_5d <= 0.8 else "平稳"

    # 4. 突破信号
    if cur_price > recent_high * 1.005 and prev_price <= recent_high and volume_ratio_5d >= 1.2:
        breakout_signal = {
            "signal": "向上突破",
            "confirmed": True,
            "reference_level": round(recent_high, 2),
            "reason": "价格突破近20日高点且放量"
        }
    elif cur_price < recent_low * 0.995 and prev_price >= recent_low and volume_ratio_5d >= 1.2:
        breakout_signal = {
            "signal": "向下跌破",
            "confirmed": True,
            "reference_level": round(recent_low, 2),
            "reason": "价格跌破近20日低点且放量"
        }
    else:
        breakout_signal = {
            "signal": "未突破",
            "confirmed": False,
            "reference_level": round(recent_high if cur_price >= prev_price else recent_low, 2),
            "reason": "价格仍处于区间内运行"
        }

    # 5. 动量指标
    # KDJ
    stoch = ta.stoch(df['high'], df['low'], df['close'], k=9, d=3, smooth_k=3)
    kdj_k = float(stoch['STOCHk_9_3_3'].iloc[-1]) if stoch is not None else 50.0
    kdj_d = float(stoch['STOCHd_9_3_3'].iloc[-1]) if stoch is not None else 50.0
    kdj_j = 3 * kdj_k - 2 * kdj_d

    # CCI
    df['cci'] = ta.cci(df['high'], df['low'], df['close'], length=20)
    cci_val = float(df['cci'].iloc[-1])

    # RSI
    df['rsi'] = ta.rsi(df['close'], length=14)
    rsi_val = float(df['rsi'].iloc[-1])

    # 6. 波动率 (ATR)
    df['atr'] = ta.atr(df['high'], df['low'], df['close'], length=14)
    atr_val = float(df['atr'].iloc[-1])
    atr_pct = round(atr_val / cur_price * 100, 2) if cur_price > 0 else 0

    return {
        "symbol": symbol,
        "period_days": lookback,
        "current_price": round(cur_price, 2),
        "trend": {
            "direction": trend_direction,
            "period_return_pct": period_return,
            "short_term": "偏强" if ma5 > ma20 else "偏弱",
            "medium_term": "偏强" if ma20 > ma60 else "偏弱",
            "ma_values": {
                "ma5": round(ma5, 2),
                "ma20": round(ma20, 2),
                "ma60": round(ma60, 2)
            }
        },
        "support_levels": support_levels[:3],
        "resistance_levels": resistance_levels[:3],
        "volume_analysis": {
            "latest_volume": round(latest_volume, 0),
            "avg_volume_5d": round(avg_volume_5d, 0),
            "avg_volume_20d": round(avg_volume_20d, 0),
            "volume_change_pct": volume_change_pct,
            "volume_ratio_5d": volume_ratio_5d,
            "volume_ratio_20d": volume_ratio_20d,
            "obv_trend": obv_trend,
            "status": volume_status
        },
        "breakout_signal": breakout_signal,
        "momentum": {
            "kdj": {
                "k": round(kdj_k, 2),
                "d": round(kdj_d, 2),
                "j": round(kdj_j, 2)
            },
            "cci": round(cci_val, 2),
            "rsi_14": round(rsi_val, 2)
        },
        "volatility": {
            "atr_14": round(atr_val, 2),
            "atr_pct": atr_pct
        },
        "data_date": df['date'].iloc[-1]
    }


def calculate_buy_range(symbol: str, current_price: Optional[float] = None) -> Dict[str, Any]:
    """
    买入区间计算：基于技术支撑位计算安全价、理想价、止损位、目标价

    Args:
        symbol: 股票代码
        current_price: 当前价格（可选，不提供则使用最新收盘价）

    Returns:
        {
            "symbol": "600519",
            "current_price": 1311.0,
            "safe_buy": 1250.0,
            "ideal_buy": 1280.0,
            "stop_loss": 1150.0,
            "target_price": 1410.0,
            "support_levels": {
                "ma20": 1371.03,
                "ma60": 1415.35,
                "recent_low_20d": 1250.0,
                "bollinger_lower": 1290.21
            },
            "advice": "当前价1311已在买入区间内，可分批建仓...",
            "data_date": "2026-05-21"
        }
    """
    # 获取历史数据
    history = get_stock_history(symbol, period='daily', limit=90)
    if not history or 'data' not in history or len(history['data']) < 20:
        raise ValueError(f"历史数据不足: {symbol}")

    df = pd.DataFrame(history['data'])
    df['close'] = df['close'].astype(float)
    df['low'] = df['low'].astype(float)

    n = len(df)
    cur_price = current_price if current_price else float(df['close'].iloc[-1])

    # 计算技术支撑位
    df['ma20'] = ta.sma(df['close'], length=20)
    df['ma60'] = ta.sma(df['close'], length=60) if n >= 60 else None

    ma20 = float(df['ma20'].iloc[-1])
    ma60 = float(df['ma60'].iloc[-1]) if df['ma60'] is not None else ma20 * 0.95

    recent_low = float(df['low'].iloc[-20:].min())

    # 布林带下轨
    bbands = ta.bbands(df['close'], length=20, std=2)
    bb_lower = float(bbands.iloc[-1, 0]) if bbands is not None else cur_price * 0.9

    # 技术支撑位排序
    tech_supports = sorted([ma20, ma60, recent_low, bb_lower])

    # 计算买入价位
    safe_buy = round(tech_supports[0], 2)  # 最低支撑
    ideal_buy = round((tech_supports[0] + tech_supports[1]) / 2, 2)  # 平均支撑
    stop_loss = round(safe_buy * 0.92, 2)  # 止损位
    target_price = round(ideal_buy + (ideal_buy - stop_loss) * 2, 2)  # 盈亏比2:1

    # 生成建仓建议
    if cur_price <= ideal_buy:
        advice = f"当前价{cur_price}已在买入区间内，可分批建仓: 安全价{safe_buy}(买40%), 理想价{ideal_buy}(买40%), 留10%等更低价. 止损位{stop_loss}"
    elif cur_price <= ma20 * 1.05:
        advice = f"当前价{cur_price}接近支撑区，可在{ideal_buy}~{safe_buy}区间分批买入(30%/40%/30%). 止损位{stop_loss}, 目标价{target_price}"
    else:
        advice = f"当前价{cur_price}高于支撑区({ideal_buy})，建议等待回调至{ideal_buy}附近再建仓. 若追入，止损位{stop_loss}, 目标价{target_price}"

    return {
        "symbol": symbol,
        "current_price": round(cur_price, 2),
        "safe_buy": safe_buy,
        "ideal_buy": ideal_buy,
        "stop_loss": stop_loss,
        "target_price": target_price,
        "support_levels": {
            "ma20": round(ma20, 2),
            "ma60": round(ma60, 2),
            "recent_low_20d": round(recent_low, 2),
            "bollinger_lower": round(bb_lower, 2)
        },
        "advice": advice,
        "data_date": df['date'].iloc[-1]
    }


def compare_peers(symbol: str) -> Dict[str, Any]:
    """
    同行对比：获取目标股票基础数据和行业信息

    Args:
        symbol: 股票代码

    Returns:
        {
            "symbol": "600519",
            "name": "贵州茅台",
            "sector": "白酒",
            "target": {
                "symbol": "600519",
                "name": "贵州茅台",
                "current_price": 1311.0,
                "change_pct": -1.5,
                "pe": 14.86,
                "pb": 5.98,
                "market_cap_billion": 1650.0,
                "roe": 0.28,
                "gross_margin": 0.92
            },
            "peers_note": "同行业对比数据需调用 screen_stocks_quality 获取",
            "usage_hint": "推荐工作流：1）已有目标股数据；2）调用 screen_stocks_quality 拿同行 Top 10；3）对比 PE/ROE/毛利率/市值",
            "data_date": "2026-05-22"
        }
    """
    # 获取股票基本信息
    info = get_stock_info(symbol)
    if not info or 'error' in info:
        raise ValueError(f"无法获取股票信息: {symbol}")

    sector = info.get('sector') or info.get('industry') or ""
    if not sector:
        raise ValueError(f"无法获取 {symbol} 的行业信息")

    # 获取实时价格
    quote = get_stock_quote(symbol)

    return {
        "symbol": symbol,
        "name": info.get('name', symbol),
        "sector": sector,
        "target": {
            "symbol": symbol,
            "name": info.get('name', symbol),
            "current_price": round(float(quote.get('price', 0)), 2),
            "change_pct": round(float(quote.get('change_pct', 0)), 2),
            "pe": round(float(info.get('pe', 0) or info.get('pe_dynamic', 0) or 0), 2),
            "pb": round(float(info.get('pb', 0) or 0), 2),
            "market_cap_billion": round(float(info.get('market_cap_billion', 0) or info.get('total_market_cap', 0) or 0), 2),
            "roe": round(float(info.get('roe', 0) or 0), 4),
            "gross_margin": round(float(info.get('gross_margin', 0) or 0), 4)
        },
        "peers_note": f"同行业（{sector}）对比数据需调用 screen_stocks_quality(\"{sector}\") 获取，本工具已返回目标股基础数据，Agent 可并行调用 screen_stocks_quality 补充对比。",
        "usage_hint": f"推荐工作流：1）已有目标股数据（见 target 字段）；2）调用 screen_stocks_quality(sector=\"{sector}\") 拿同行 Top 10；3）对比 PE/ROE/毛利率/市值。",
        "data_date": quote.get('data_date', '')
    }


def get_exit_plan(symbol: str, entry_price: float, position_size: int = 100) -> Dict[str, Any]:
    """
    止盈计划：基于PE和买入价计算分批止盈目标

    Args:
        symbol: 股票代码
        entry_price: 买入价格
        position_size: 持仓数量（股），默认100股

    Returns:
        {
            "symbol": "600519",
            "name": "贵州茅台",
            "buy_price": 1200.0,
            "current_price": 1311.0,
            "shares": 100,
            "pnl_pct": 9.25,
            "pnl_amount": 11100.0,
            "targets": {
                "conservative": 1440.0,
                "moderate": 1680.0,
                "aggressive": 1920.0
            },
            "sell_plan": ["距保守目标(1440)还有9.8%，继续持有"],
            "data_date": "2026-05-22"
        }
    """
    # 获取实时价格
    quote = get_stock_quote(symbol)
    cur_price = float(quote.get('price', 0))
    pe = float(quote.get('pe_dynamic', 0) or quote.get('pe', 0) or 0)

    # 计算目标价位
    if pe > 0 and cur_price > 0:
        eps = cur_price / pe
        base_pe = min(pe, 28.5)
        target_conservative = round(eps * base_pe * 1.2, 2)
        target_moderate = round(eps * base_pe * 1.5, 2)
        target_aggressive = round(eps * base_pe * 2.0, 2)
    else:
        # 如果没有PE数据，使用固定比例
        target_conservative = round(entry_price * 1.20, 2)
        target_moderate = round(entry_price * 1.40, 2)
        target_aggressive = round(entry_price * 1.60, 2)

    # 计算盈亏
    pnl_pct = round((cur_price - entry_price) / entry_price * 100, 2)
    pnl_amount = round((cur_price - entry_price) * position_size, 2)

    # 生成止盈计划
    sell_plan = []
    if cur_price >= target_conservative:
        sell_plan.append(f"已达保守目标({target_conservative})，建议卖出30%")
    if cur_price >= target_moderate:
        sell_plan.append(f"已达中等目标({target_moderate})，建议再卖40%")
    if cur_price >= target_aggressive:
        sell_plan.append(f"已达激进目标({target_aggressive})，建议清仓剩余30%")

    if not sell_plan:
        pct_to_target = round((target_conservative - cur_price) / cur_price * 100, 2)
        sell_plan.append(f"距保守目标({target_conservative})还有{pct_to_target}%，继续持有")

    return {
        "symbol": symbol,
        "name": quote.get('name', symbol),
        "buy_price": entry_price,
        "current_price": cur_price,
        "shares": position_size,
        "pnl_pct": pnl_pct,
        "pnl_amount": pnl_amount,
        "targets": {
            "conservative": target_conservative,
            "moderate": target_moderate,
            "aggressive": target_aggressive
        },
        "sell_plan": sell_plan,
        "data_date": quote.get('data_date', '')
    }
