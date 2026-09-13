# 自研候选 #4：上升趋势中的超卖回调买入（短线反转 × 趋势闸门）（w-c8cae280，2026-09-13）
#
# 为什么换思路：v1-v3 都是趋势跟随，实测在 2025-2026 的震荡/弱势市里被反复洗（样本外 -0.5%~-1.0%），
# 而 A 股有更强的**短期反转**效应：强势股急跌后往往有技术性反弹。
#  1. 闸门：close > MA120（只在大趋势向上的标的上做反转，避免"接飞刀"）；
#  2. 入场：RSI(3) < 15（三日急跌）或 5 日收益 < -8%，两者取或；
#  3. 出场：close > MA20（回到均值）或 RSI(3) > 60，或持有满 10 日强制离场（避免变"长期套牢"）；
#  4. 频率目标：每标的每年 4-10 次，单笔持有 3-10 天。
# @param ma_gate int 120 趋势闸门均线
# @param rsi_n int 3 RSI 周期
# @param rsi_entry float 15 入场 RSI 阈值
# @param rsi_exit float 60 离场 RSI 阈值
# @param drop5 float -0.08 5 日跌幅阈值
# @param max_hold int 10 最长持有天数
my_indicator_name = "trend-pullback-reversal-v4"
my_indicator_description = "MA120 上方 + RSI3<15 或 5 日跌 8% 买入；回到 MA20 / RSI3>60 / 持有满 10 日离场"

ma_gate = int(params.get("ma_gate", 120))
rsi_n = int(params.get("rsi_n", 3))
rsi_entry = float(params.get("rsi_entry", 15))
rsi_exit = float(params.get("rsi_exit", 60))
drop5 = float(params.get("drop5", -0.08))
max_hold = int(params.get("max_hold", 10))

close = df["close"].astype(float)
maG = close.rolling(ma_gate).mean()
maS = close.rolling(20).mean()

# RSI(n)（Wilder 简化：SMA 版）
delta = close.diff()
gain = delta.clip(lower=0).rolling(rsi_n).mean()
loss = (-delta.clip(upper=0)).rolling(rsi_n).mean()
rs = gain / loss.replace(0, float("nan"))
rsi = 100 - 100 / (1 + rs)

ret5 = close.pct_change(5)
in_uptrend = (close > maG) & maG.notna()
entry = in_uptrend & ((rsi < rsi_entry) | (ret5 < drop5))

# 持有天数上限：用"入场后连续未离场天数"近似（向量化：自上次入场起的累计计数）
entry_flag = entry.fillna(False).astype(int)
since_entry = entry_flag.groupby(entry_flag.cumsum()).cumcount()

exit_mean = close > maS
exit_rsi = rsi > rsi_exit
exit_time = since_entry >= max_hold

df["buy"] = entry.fillna(False)
df["sell"] = (exit_mean | exit_rsi | exit_time).fillna(False)
