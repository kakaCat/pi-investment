# 自研候选 #2：趋势跟随 v2（低频、状态型信号）（w-c8cae280，2026-09-13）
#
# 与 v1 的差异（v1 实测暴露的问题：闸门"首次打开"才入场 + ATR 移动止损 → 敞口仅 10%、
# 交易 15-24 笔、几乎空仓，等于没参与）：
#  1. 入场改为**状态型**信号（条件成立即可持仓），不在持有期重复买入由模拟器保证；
#  2. 去掉 ATR 移动止损（实测它把持仓周期压到几天），出场只认"跌破中期均线"；
#  3. 长期闸门 200 → 120 日，提高参与度；
#  4. 保留波动率分位过滤（不追急涨急跌），阈值放宽到 0.85。
# @param ma_gate int 120 长期闸门均线
# @param ma_mid int 60 中期均线
# @param ma_short int 20 短期均线
# @param vol_window int 20 波动率窗口
# @param vol_pct_max float 0.85 波动率分位上限
my_indicator_name = "trend-following-v2"
my_indicator_description = "MA120 闸门 + MA20>MA60 共振 + 波动率过滤；跌破 MA60 离场"

ma_gate = int(params.get("ma_gate", 120))
ma_mid = int(params.get("ma_mid", 60))
ma_short = int(params.get("ma_short", 20))
vol_window = int(params.get("vol_window", 20))
vol_pct_max = float(params.get("vol_pct_max", 0.85))

close = df["close"].astype(float)
maG = close.rolling(ma_gate).mean()
maM = close.rolling(ma_mid).mean()
maS = close.rolling(ma_short).mean()
vol = close.pct_change().rolling(vol_window).std()
vol_pct = vol.rolling(250).rank(pct=True)

ok_entry = (close > maG) & (maM > maS) & (vol_pct < vol_pct_max) & maG.notna()
df["buy"] = ok_entry.fillna(False)
df["sell"] = (close < maM).fillna(False)
