# v17-dual-mode
# ============================================================
# 双模策略：close > MA60 → v11激进模式(等权投票) | close ≤ MA60 → v15防御模式(加权评分)
#
# 设计哲学：
#   MA60是慢指标，不会频繁翻转 → 状态切换稳定
#   牛市中用v11的7因子等权投票（已被证明在牛市中有效：宁德+84%，平安+65%）
#   熊市中用v15的加权评分+波动率自适应阈值（已被证明在熊市中最扛跌：浦发银行-5.25%）
# ============================================================
my_indicator_name = "v17-dual-mode"
my_indicator_description = "双模策略：MA60以上用v11激进投票(牛市追趋势)，MA60以下用v15加权评分+自适应阈值(熊市防御)。2状态，简单稳定。"

# ── v11模式参数 ──
# @param rsi_period int 14 RSI周期
# @param rsi_oversold int 25 RSI超卖线(v11模式)
# @param rsi_overbought int 70 RSI超买线
# @param macd_fast int 12 MACD快线
# @param macd_slow int 26 MACD慢线
# @param macd_signal int 9 MACD信号线
# @param bb_period int 20 布林带周期
# @param bb_std float 2.0 布林带标准差倍数
# @param ma1 int 5 短均线
# @param ma2 int 10 中均线
# @param ma3 int 20 长均线
# @param ma_trend int 60 趋势线(状态判定用)
# @param vol_ma_period int 20 成交量均线周期
# @param vol_ratio float 1.5 放量阈值
# @param adx_period int 14 ADX周期
# @param adx_threshold int 20 ADX趋势门槛
# @param vote_threshold int 4 v11买入所需票数(1-7)

# ── v15模式参数 ──
# @param roc_fast int 10 快ROC周期
# @param roc_slow int 20 慢ROC周期
# @param vol_lookback int 60 波动率分位回溯期
# @param hv_period int 20 历史波动率周期
# @param vol_climax_ratio float 2.0 量能爆发阈值(倍)
# @param buy_threshold_low_vol float 0.45 低波动买入阈值
# @param buy_threshold_normal float 0.50 正常波动买入阈值
# @param buy_threshold_high_vol float 0.58 高波动买入阈值
# @param sell_threshold float 0.55 卖出阈值

# ── 公用参数 ──
# @param trail_window int 15 跟踪止损窗口
# @param trail_pct float 0.07 跟踪止损回撤

# @strategy stopLossPct 0.08
# @strategy takeProfitPct 0.50

# ── 参数绑定 ──
# v11
rp = params.get("rsi_period", 14)
rl = params.get("rsi_oversold", 25)
rh = params.get("rsi_overbought", 70)
mf = params.get("macd_fast", 12)
ms_ = params.get("macd_slow", 26)
msig = params.get("macd_signal", 9)
bp = params.get("bb_period", 20)
bs = params.get("bb_std", 2.0)
m1 = params.get("ma1", 5)
m2 = params.get("ma2", 10)
m3 = params.get("ma3", 20)
mt = params.get("ma_trend", 60)
vp = params.get("vol_ma_period", 20)
vr = params.get("vol_ratio", 1.5)
ap = params.get("adx_period", 14)
at = params.get("adx_threshold", 20)
vt = params.get("vote_threshold", 4)

# v15
rc_f = params.get("roc_fast", 10)
rc_s = params.get("roc_slow", 20)
vl = params.get("vol_lookback", 60)
hp = params.get("hv_period", 20)
vcr = params.get("vol_climax_ratio", 2.0)
btl = params.get("buy_threshold_low_vol", 0.45)
btn = params.get("buy_threshold_normal", 0.50)
bth = params.get("buy_threshold_high_vol", 0.58)
st = params.get("sell_threshold", 0.55)

# 公用
tw_ = params.get("trail_window", 15)
tp = params.get("trail_pct", 0.07)

# ═══════════════════════════════════════════════════════════
# PART 1: 状态判定 — 只用一个条件: close > MA60
# ═══════════════════════════════════════════════════════════
c = df["close"]
h = df["high"]
l = df["low"]
v = df["volume"]

ma60 = c.rolling(mt).mean()
is_bull = (c > ma60).fillna(False)
is_bear = ~is_bull

# ═══════════════════════════════════════════════════════════
# PART 2A: v11 模式 — 7因子等权投票 (牛市用)
# ═══════════════════════════════════════════════════════════

# RSI
delta = c.diff()
gain = delta.where(delta > 0, 0.0).rolling(rp).mean()
loss = (-delta).where(delta < 0, 0.0).rolling(rp).mean()
rsi_val = 100.0 - (100.0 / (1.0 + gain / loss.replace(0, np.nan)))
vote_rsi = (rsi_val <= rl).astype(int)

# MACD金叉
ema_f = c.ewm(span=mf, adjust=False).mean()
ema_s = c.ewm(span=ms_, adjust=False).mean()
dif = ema_f - ema_s
dea = dif.ewm(span=msig, adjust=False).mean()
macd_hist = (dif - dea) * 2
vote_macd = ((dif > dea) & (dif.shift(1) <= dea.shift(1))).astype(int)

# 成交量放大
vol_ma = v.rolling(vp).mean()
vote_vol = (v > vol_ma * vr).astype(int)

# 均线多头排列
ma5 = c.rolling(m1).mean()
ma10 = c.rolling(m2).mean()
ma20 = c.rolling(m3).mean()
vote_ma = ((ma5 > ma10) & (ma10 > ma20)).astype(int)

# 资金净流入
vote_flow = (df["main_net_pct"].fillna(0) > 0).astype(int)

# ADX趋势
tr1 = h - l
tr2 = (h - c.shift(1)).abs()
tr3 = (l - c.shift(1)).abs()
tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
atr14 = tr.rolling(14).mean()
um = h.diff(); dmv = -l.diff()
pdm_raw = ((um > dmv) & (um > 0)).astype(float) * um
mdm_raw = ((dmv > um) & (dmv > 0)).astype(float) * dmv
pdi = 100 * (pdm_raw.rolling(ap).mean() / atr14.replace(0, np.nan))
ndi = 100 * (mdm_raw.rolling(ap).mean() / atr14.replace(0, np.nan))
dxd = pdi + ndi
adx = pd.Series(np.where(dxd > 0, 100 * np.abs(pdi - ndi) / dxd, 0), index=df.index).rolling(ap).mean()
vote_adx = ((adx > at) & (pdi > ndi)).astype(int)

# 布林带下轨
bb_mid = c.rolling(bp).mean()
bb_std = c.rolling(bp).std()
bb_lower = bb_mid - bs * bb_std
vote_bb = (c <= bb_lower * 1.02).astype(int)

# v11总票数
vote_sum = (vote_rsi.fillna(0) + vote_macd.fillna(0) + vote_vol.fillna(0) +
            vote_ma.fillna(0) + vote_flow.fillna(0) + vote_adx.fillna(0) + vote_bb.fillna(0))
buy_v11 = vote_sum >= vt

# ═══════════════════════════════════════════════════════════
# PART 2B: v15 模式 — 加权连续评分 (熊市用)
# ═══════════════════════════════════════════════════════════

# F1: ROC动量
roc10 = (c - c.shift(rc_f)) / c.shift(rc_f)
roc20 = (c - c.shift(rc_s)) / c.shift(rc_s)
roc_comp = roc10 * 0.6 + roc20 * 0.4
mom_score = 1.0 / (1.0 + np.exp(-roc_comp * 15))
same_dir = ((roc10 > 0) & (roc20 > 0)) | ((roc10 < 0) & (roc20 < 0))
mom_score = mom_score.fillna(0.5) * 0.8 + same_dir.astype(float).fillna(0.5) * 0.2

# F2: 波动率
log_ret = np.log(c / c.shift(1))
hv = log_ret.rolling(hp).std() * np.sqrt(252)
hv_rank = hv.rolling(vl).apply(lambda x: (x < x.iloc[-1]).mean(), raw=False)
is_high_vol = hv_rank > 0.70
is_low_vol = hv_rank < 0.30
vol_score = (1.0 - hv_rank).fillna(0.5)

# F3: 量能
vol_ratio = v / (vol_ma + 1e-10)
vol_climax = vol_ratio >= vcr
up_day = c > c.shift(1)
vol_confirm = ((vol_ratio > 1.2) & up_day) | ((vol_ratio < 0.8) & ~up_day)
vol_score2 = np.clip(vol_ratio / 3.0, 0, 1).fillna(0.5) * 0.4
vol_score2 += vol_confirm.astype(float).fillna(0) * 0.3
vol_score2 += (vol_climax.astype(float) * up_day.astype(float)).fillna(0) * 0.3

# F4: 趋势
ma_align = ((ma5 > ma10).astype(float) + (ma10 > ma20).astype(float) + (c > ma20).astype(float)) / 3.0
trend_strong = ((adx > at) & (pdi > ndi)).fillna(False)
price_ext = (c - ma20) / (atr14 + 1e-10)
ext_score = 1.0 - np.clip(np.abs(price_ext) / 2.0, 0, 1)
trend_score = ma_align.fillna(0.5) * 0.35 + trend_strong.astype(float).fillna(0) * 0.35 + ext_score.fillna(0.5) * 0.30

# F5: RSI连续
rsi_score = np.clip(1.0 - (rsi_val - 30) / (75 - 30), 0, 1).fillna(0.5)

# F6: BB
bb_pct_b = (c - bb_lower) / (bb_mid * 2 * bs - bb_lower + 1e-10)
bb_score = np.clip(1.0 - bb_pct_b * 2, 0, 1).fillna(0.5)

# F7: 资金流
fp = df["main_net_pct"].fillna(0) > 0
fi = df["main_net_inflow"].fillna(0).rolling(3).mean() > df["main_net_inflow"].fillna(0).rolling(3).mean().shift(1)
flow_score = (fp.astype(float) * 0.5 + fi.astype(float) * 0.5).fillna(0.5)

# v15加权评分
buy_v15_score = (
    0.20 * mom_score.fillna(0.5) +
    0.10 * vol_score.fillna(0.5) +
    0.15 * vol_score2.fillna(0.5) +
    0.25 * trend_score.fillna(0.5) +
    0.15 * rsi_score.fillna(0.5) +
    0.05 * flow_score.fillna(0.5) +
    0.10 * bb_score.fillna(0.5)
)

# v15自适应阈值
threshold_v15 = pd.Series(btn, index=df.index)
threshold_v15[is_low_vol.fillna(False)] = btl
threshold_v15[is_high_vol.fillna(False)] = bth
buy_v15 = buy_v15_score > threshold_v15

# ═══════════════════════════════════════════════════════════
# PART 3: 双模合成
# ═══════════════════════════════════════════════════════════
df["buy"] = pd.Series(False, index=df.index)
df.loc[is_bull, "buy"] = buy_v11[is_bull]
df.loc[is_bear, "buy"] = buy_v15[is_bear]

# ═══════════════════════════════════════════════════════════
# PART 4: 卖出 (含跟踪止损)
# ═══════════════════════════════════════════════════════════
death_cross = (dif < dea) & (dif.shift(1) >= dea.shift(1))
trail_high = c.rolling(tw_).max().shift(1)
trail_trigger = c < trail_high * (1.0 - tp)

sell_score = (
    0.20 * (1.0 - mom_score.fillna(0.5)) +
    0.20 * (rsi_val > rh).astype(float).fillna(0) +
    0.20 * (c < ma60).astype(float).fillna(0) +
    0.15 * death_cross.astype(float).fillna(0) +
    0.10 * (df["main_net_pct"].fillna(0) < -5).astype(float) +
    0.15 * trail_trigger.astype(float).fillna(0)
)

df["sell"] = (sell_score > st) | trail_trigger.fillna(False)
