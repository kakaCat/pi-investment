# 自研候选 #1：长期趋势 + 中期趋势共振，ATR 移动止损（w-c8cae280，2026-09-13）
#
# 设计依据（不是拍脑袋）：
#  1. 现有策略几乎全是单标的择时（MACD/RSI），实测 648 两年 200 笔交易 → 成本极高、样本外为负；
#     故本策略刻意**低频**：只在趋势确认时持有，靠 ATR 止损离场，目标每标的每年 2-6 次交易；
#  2. 用 MA200 做"长期趋势闸门"（等价于个股自身 regime），避开熊市里反复抄底；
#  3. 用 MA20>MA60 做中期共振，避免长期均线滞后导致的假信号；
#  4. 用波动率分位过滤：波动过大（>75 分位）时不入，规避情绪化急涨急跌；
#  5. 出场用"跌破 MA60"或"从持有期最高价回撤 2.5×ATR20"，控制单笔亏损。
# @param ma_long int 200 长期趋势均线
# @param ma_mid int 60 中期均线
# @param ma_short int 20 短期均线
# @param vol_window int 20 波动率窗口
# @param vol_pct_max float 0.75 波动率分位上限
# @param atr_mult float 2.5 ATR 止损倍数
my_indicator_name = "trend-resonance-atr-v1"
my_indicator_description = "MA200 趋势闸门 + MA20>MA60 共振 + 波动率过滤入场；跌破 MA60 或 ATR 回撤离场"

ma_long = int(params.get("ma_long", 200))
ma_mid = int(params.get("ma_mid", 60))
ma_short = int(params.get("ma_short", 20))
vol_window = int(params.get("vol_window", 20))
vol_pct_max = float(params.get("vol_pct_max", 0.75))
atr_mult = float(params.get("atr_mult", 2.5))

close = df["close"].astype(float)
high = df["high"].astype(float)
low = df["low"].astype(float)

maL = close.rolling(ma_long).mean()
maM = close.rolling(ma_mid).mean()
maS = close.rolling(ma_short).mean()

# ATR20
prev_close = close.shift(1)
tr = pd.concat([(high - low).abs(), (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
atr = tr.rolling(vol_window).mean()

# 波动率分位（20 日收益标准差在近 250 日中的分位）
vol = close.pct_change().rolling(vol_window).std()
vol_pct = vol.rolling(250).rank(pct=True)

gate = (close > maL) & (maM > maS) & (vol_pct < vol_pct_max) & maL.notna() & atr.notna()
entry = gate & (~gate.shift(1).fillna(False))      # 闸门首次打开
exit_trend = close < maM                          # 跌破中期均线

# 移动止损：以近 60 日最高价为基准，回撤超过 atr_mult × ATR20 即离场
# （2026-09-13 修正：初版用全局 cummax，等于把历史最高价当基准，会永久压制后续入场）
peak = close.rolling(60, min_periods=5).max()
stop_hit = close < (peak - atr_mult * atr)

df["buy"] = entry.fillna(False)
df["sell"] = (exit_trend | stop_hit).fillna(False)
