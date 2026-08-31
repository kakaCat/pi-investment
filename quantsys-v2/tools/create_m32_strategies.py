#!/usr/bin/env python3
"""
创建 M3-2 回测矩阵所需的 5 个经典 indicator 策略（对应 m3-2-backtest-matrix-execution-plan.md）。

计划中的 macd_golden_cross / bollinger_breakout / rsi_oversold / dual_ma / momentum
在系统中不存在（176 个现有策略中 178/193/266 等信号过于苛刻，全年 0 交易），
因此按计划语义创建 5 个经典简单策略，保证信号密度可支撑回测矩阵。

用法:
    python3 tools/create_m32_strategies.py
"""
import json
import requests

API = "http://localhost:5001/api/strategies/create"

STRATEGIES = [
    {
        "name": "macd-golden-cross-v1",
        "code_type": "indicator",
        "description": "M3-2: MACD金叉买入/死叉卖出（经典趋势跟踪）",
        "code": """# MACD 金叉策略
# @param fast_period int 12 快线周期
# @param slow_period int 26 慢线周期
# @param signal_period int 9 信号线周期
my_indicator_name = "macd-golden-cross-v1"
my_indicator_description = "MACD金叉买入，死叉卖出"

fast = params.get("fast_period", 12)
slow = params.get("slow_period", 26)
signal = params.get("signal_period", 9)

ema_fast = df["close"].ewm(span=fast, adjust=False).mean()
ema_slow = df["close"].ewm(span=slow, adjust=False).mean()
dif = ema_fast - ema_slow
dea = dif.ewm(span=signal, adjust=False).mean()

# 金叉买入：DIF 上穿 DEA
df["buy"] = (dif > dea) & (dif.shift(1) <= dea.shift(1))
# 死叉卖出：DIF 下穿 DEA
df["sell"] = (dif < dea) & (dif.shift(1) >= dea.shift(1))
""",
    },
    {
        "name": "bollinger-breakout-v1",
        "code_type": "indicator",
        "description": "M3-2: 布林带突破（价格突破上轨买入，跌破中轨卖出）",
        "code": """# 布林带突破策略
# @param bb_period int 20 布林周期
# @param bb_std float 2.0 标准差倍数
my_indicator_name = "bollinger-breakout-v1"
my_indicator_description = "突破布林上轨买入，跌破中轨卖出"

period = params.get("bb_period", 20)
std_mult = params.get("bb_std", 2.0)

mid = df["close"].rolling(period).mean()
std = df["close"].rolling(period).std()
upper = mid + std_mult * std
lower = mid - std_mult * std

# 突破上轨买入
df["buy"] = (df["close"] > upper) & (df["close"].shift(1) <= upper.shift(1))
# 跌破中轨卖出
df["sell"] = (df["close"] < mid) & (df["close"].shift(1) >= mid.shift(1))
""",
    },
    {
        "name": "rsi-oversold-v1",
        "code_type": "indicator",
        "description": "M3-2: RSI超卖反弹（RSI低于超卖线后回升买入，超买卖出）",
        "code": """# RSI 超卖反弹策略
# @param rsi_period int 14 RSI周期
# @param rsi_oversold int 30 超卖阈值
# @param rsi_overbought int 70 超买阈值
my_indicator_name = "rsi-oversold-v1"
my_indicator_description = "RSI超卖回升买入，超买回落卖出"

period = params.get("rsi_period", 14)
oversold = params.get("rsi_oversold", 30)
overbought = params.get("rsi_overbought", 70)

delta = df["close"].diff()
gain = delta.where(delta > 0, 0).rolling(period).mean()
loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
rs = gain / (loss + 0.0001)
rsi = 100 - (100 / (1 + rs))

# RSI 上穿超卖线买入
df["buy"] = (rsi > oversold) & (rsi.shift(1) <= oversold)
# RSI 下穿超买线卖出
df["sell"] = (rsi < overbought) & (rsi.shift(1) >= overbought)
""",
    },
    {
        "name": "dual-ma-cross-v1",
        "code_type": "indicator",
        "description": "M3-2: 双均线金叉/死叉（经典趋势跟踪）",
        "code": """# 双均线策略
# @param fast_ma int 10 快线周期
# @param slow_ma int 30 慢线周期
my_indicator_name = "dual-ma-cross-v1"
my_indicator_description = "快线上穿慢线买入，下穿卖出"

fast = params.get("fast_ma", 10)
slow = params.get("slow_ma", 30)

ma_fast = df["close"].rolling(fast).mean()
ma_slow = df["close"].rolling(slow).mean()

# 金叉买入
df["buy"] = (ma_fast > ma_slow) & (ma_fast.shift(1) <= ma_slow.shift(1))
# 死叉卖出
df["sell"] = (ma_fast < ma_slow) & (ma_fast.shift(1) >= ma_slow.shift(1))
""",
    },
    {
        "name": "momentum-breakout-v1",
        "code_type": "indicator",
        "description": "M3-2: 动量突破（N日涨幅突破阈值买入，动量转负卖出）",
        "code": """# 动量策略
# @param mom_lookback int 10 动量回看周期
# @param mom_threshold float 5.0 动量阈值(%)
my_indicator_name = "momentum-breakout-v1"
my_indicator_description = "N日动量突破阈值买入，动量转负卖出"

lookback = params.get("mom_lookback", 10)
threshold = params.get("mom_threshold", 5.0)

momentum = df["close"].pct_change(lookback) * 100

# 动量突破阈值买入
df["buy"] = (momentum > threshold) & (momentum.shift(1) <= threshold)
# 动量转负卖出
df["sell"] = (momentum < 0) & (momentum.shift(1) >= 0)
""",
    },
]


def main():
    for s in STRATEGIES:
        try:
            resp = requests.post(API, json=s, timeout=30)
            d = resp.json()
            if d.get("success"):
                data = d.get("data") or {}
                sid = data.get("id") or data.get("strategy_id")
                validation = data.get("validation") or {}
                print(f"[OK] {s['name']} -> id={sid} valid={validation.get('status')}")
            else:
                print(f"[FAIL] {s['name']}: {d.get('message') or d}")
        except Exception as e:
            print(f"[EXC] {s['name']}: {e}")


if __name__ == "__main__":
    main()
