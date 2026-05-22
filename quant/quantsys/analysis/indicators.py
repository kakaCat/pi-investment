"""
Technical indicators calculation using pandas_ta
"""
import pandas as pd
import pandas_ta as ta
from typing import Dict, Any, List, Optional
from ..cli.stock_query import get_stock_history


def calculate_technical_indicators(
    symbol: str,
    indicators: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    计算技术指标：MA, MACD, RSI, BOLL

    Args:
        symbol: 股票代码
        indicators: 指标列表，默认全部 ['ma', 'macd', 'rsi', 'boll']

    Returns:
        {
            "symbol": "600519",
            "current_price": 1293.25,
            "ma": {"ma5": 1280.5, "ma10": 1275.3, "ma20": 1260.8, "ma60": 1240.2},
            "macd": {"dif": 2.34, "dea": 1.56, "histogram": 0.78},
            "rsi_14": 65.5,
            "bollinger": {"upper": 1320.5, "mid": 1280.3, "lower": 1240.1},
            "signals": ["短期多头排列", "站上60日均线", "MACD金叉"],
            "data_date": "2026-05-22"
        }
    """
    if indicators is None:
        indicators = ['ma', 'macd', 'rsi', 'boll']

    # 获取历史数据
    history = get_stock_history(symbol, period='daily', limit=120)
    if not history or 'data' not in history or len(history['data']) < 30:
        raise ValueError(f"历史数据不足: {symbol}")

    # 转换为 DataFrame
    df = pd.DataFrame(history['data'])
    df['close'] = df['close'].astype(float)
    df['high'] = df['high'].astype(float)
    df['low'] = df['low'].astype(float)
    df['volume'] = df['volume'].astype(float)

    result = {
        "symbol": symbol,
        "current_price": round(float(df['close'].iloc[-1]), 2),
        "data_date": df['date'].iloc[-1]
    }

    signals = []

    # 1. 移动平均线
    if 'ma' in indicators:
        df['ma5'] = ta.sma(df['close'], length=5)
        df['ma10'] = ta.sma(df['close'], length=10)
        df['ma20'] = ta.sma(df['close'], length=20)
        df['ma60'] = ta.sma(df['close'], length=60) if len(df) >= 60 else None

        ma_data = {
            "ma5": round(float(df['ma5'].iloc[-1]), 2) if pd.notna(df['ma5'].iloc[-1]) else None,
            "ma10": round(float(df['ma10'].iloc[-1]), 2) if pd.notna(df['ma10'].iloc[-1]) else None,
            "ma20": round(float(df['ma20'].iloc[-1]), 2) if pd.notna(df['ma20'].iloc[-1]) else None,
            "ma60": round(float(df['ma60'].iloc[-1]), 2) if df['ma60'] is not None and pd.notna(df['ma60'].iloc[-1]) else None,
        }
        result['ma'] = ma_data

        # MA 信号
        cur_price = result['current_price']
        ma5 = ma_data['ma5']
        ma20 = ma_data['ma20']
        ma60 = ma_data['ma60']

        if ma5 and ma20:
            if cur_price > ma5 > ma20:
                signals.append("短期多头排列")
            elif cur_price < ma5 < ma20:
                signals.append("短期空头排列")

        if ma60:
            if cur_price > ma60:
                signals.append("站上60日均线")
            else:
                signals.append("跌破60日均线")

    # 2. MACD
    if 'macd' in indicators:
        macd = ta.macd(df['close'], fast=12, slow=26, signal=9)
        if macd is not None:
            dif = float(macd['MACD_12_26_9'].iloc[-1])
            dea = float(macd['MACDs_12_26_9'].iloc[-1])
            histogram = float(macd['MACDh_12_26_9'].iloc[-1])

            result['macd'] = {
                "dif": round(dif, 4),
                "dea": round(dea, 4),
                "histogram": round(histogram, 4)
            }

            # MACD 信号
            if dif > dea:
                signals.append("MACD金叉")
            else:
                signals.append("MACD死叉")

    # 3. RSI
    if 'rsi' in indicators:
        df['rsi'] = ta.rsi(df['close'], length=14)
        rsi_val = float(df['rsi'].iloc[-1])
        result['rsi_14'] = round(rsi_val, 2)

        # RSI 信号
        if rsi_val > 70:
            signals.append("RSI超买")
        elif rsi_val < 30:
            signals.append("RSI超卖")

    # 4. Bollinger Bands
    if 'boll' in indicators:
        bbands = ta.bbands(df['close'], length=20, std=2)
        if bbands is not None and len(bbands.columns) >= 3:
            # pandas_ta 返回的列名可能是 BBL_20_2.0, BBM_20_2.0, BBU_20_2.0
            cols = bbands.columns.tolist()
            result['bollinger'] = {
                "upper": round(float(bbands[cols[2]].iloc[-1]), 2),  # BBU
                "mid": round(float(bbands[cols[1]].iloc[-1]), 2),    # BBM
                "lower": round(float(bbands[cols[0]].iloc[-1]), 2)   # BBL
            }

    result['signals'] = signals
    return result


def analyze_candlestick_patterns(
    symbol: str,
    lookback: int = 120
) -> Dict[str, Any]:
    """
    K线形态识别（简化版）

    Args:
        symbol: 股票代码
        lookback: 回溯天数

    Returns:
        {
            "symbol": "600519",
            "current_price": 1293.25,
            "patterns": [
                {"date": "2026-05-20", "pattern": "锤子线", "type": "bullish"},
                {"date": "2026-05-15", "pattern": "吞没形态", "type": "bearish"}
            ],
            "gaps": [
                {"date": "2026-05-10", "type": "gap_up", "gap_pct": 2.5, "filled": false}
            ],
            "summary": "最近出现锤子线（看涨信号），存在1个未回补跳空缺口。",
            "data_date": "2026-05-22"
        }
    """
    # 获取历史数据
    history = get_stock_history(symbol, period='daily', limit=lookback)
    if not history or 'data' not in history or len(history['data']) < 30:
        raise ValueError(f"历史数据不足: {symbol}")

    df = pd.DataFrame(history['data'])
    df['open'] = df['open'].astype(float)
    df['high'] = df['high'].astype(float)
    df['low'] = df['low'].astype(float)
    df['close'] = df['close'].astype(float)

    result = {
        "symbol": symbol,
        "current_price": round(float(df['close'].iloc[-1]), 2),
        "data_date": df['date'].iloc[-1]
    }

    # 1. 使用 pandas_ta 的 CDL 模式识别
    patterns = []

    # 常见的看涨形态
    bullish_patterns = {
        'cdl_hammer': '锤子线',
        'cdl_morningstar': '早晨之星',
        'cdl_engulfing': '看涨吞没'
    }

    # 常见的看跌形态
    bearish_patterns = {
        'cdl_hangingman': '上吊线',
        'cdl_eveningstar': '黄昏之星',
        'cdl_engulfing': '看跌吞没'
    }

    # 检测形态（最近10天）
    for i in range(max(0, len(df) - 10), len(df)):
        row = df.iloc[i]
        date = row['date']

        # 简单的形态识别逻辑
        body = abs(row['close'] - row['open'])
        upper_shadow = row['high'] - max(row['open'], row['close'])
        lower_shadow = min(row['open'], row['close']) - row['low']

        # 锤子线：下影线长，上影线短，实体小
        if lower_shadow > body * 2 and upper_shadow < body * 0.5:
            patterns.append({
                "date": date,
                "pattern": "锤子线",
                "type": "bullish"
            })

        # 上吊线：上影线长，下影线短，实体小
        elif upper_shadow > body * 2 and lower_shadow < body * 0.5:
            patterns.append({
                "date": date,
                "pattern": "上吊线",
                "type": "bearish"
            })

    result['patterns'] = patterns[-5:] if len(patterns) > 5 else patterns  # 最近5个形态

    # 2. 跳空缺口检测
    gaps = []
    for i in range(1, len(df)):
        prev_high = df['high'].iloc[i-1]
        prev_low = df['low'].iloc[i-1]
        curr_high = df['high'].iloc[i]
        curr_low = df['low'].iloc[i]

        # 向上跳空
        if curr_low > prev_high:
            gap_pct = round((curr_low - prev_high) / prev_high * 100, 2)
            if gap_pct > 0.5:  # 跳空超过0.5%才记录
                # 检查是否已回补
                filled = False
                for j in range(i+1, len(df)):
                    if df['low'].iloc[j] <= prev_high:
                        filled = True
                        break

                gaps.append({
                    "date": df['date'].iloc[i],
                    "type": "gap_up",
                    "gap_pct": gap_pct,
                    "filled": filled
                })

        # 向下跳空
        elif curr_high < prev_low:
            gap_pct = round((prev_low - curr_high) / prev_low * 100, 2)
            if gap_pct > 0.5:
                filled = False
                for j in range(i+1, len(df)):
                    if df['high'].iloc[j] >= prev_low:
                        filled = True
                        break

                gaps.append({
                    "date": df['date'].iloc[i],
                    "type": "gap_down",
                    "gap_pct": gap_pct,
                    "filled": filled
                })

    result['gaps'] = gaps[-10:] if len(gaps) > 10 else gaps  # 最近10个缺口

    # 3. 生成摘要
    summary_parts = []
    if patterns:
        latest = patterns[-1]
        signal_type = "看涨" if latest['type'] == 'bullish' else "看跌"
        summary_parts.append(f"最近出现{latest['pattern']}（{signal_type}信号）")

    unfilled_gaps = [g for g in gaps if not g['filled']]
    if unfilled_gaps:
        latest_gap = unfilled_gaps[-1]
        gap_direction = "跳空向上" if latest_gap['type'] == 'gap_up' else "跳空向下"
        summary_parts.append(f"存在{len(unfilled_gaps)}个未回补跳空缺口（最近：{latest_gap['date']} {gap_direction}{latest_gap['gap_pct']}%）")

    result['summary'] = "，".join(summary_parts) + "。" if summary_parts else "未检测到显著K线形态信号。"

    return result
