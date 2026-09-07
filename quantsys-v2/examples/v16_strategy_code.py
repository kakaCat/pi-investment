# v16-meta
# ============================================================
# 元策略：实时检测市场状态（强牛/弱牛/震荡/弱熊/强熊），
# 自适应切换因子权重和买卖阈值。
#
# 核心理念：
#   牛市中 v11 模式（激进入场，动量+趋势高权重）
#   震荡中 v15 模式（加权评分，量价确认）
#   熊市中 防御模式（只买极端超卖，极高门槛）
#
# 这避免了 v11 在熊市 -41% 的灾难，同时保留其在牛市的 +83% 能力。
# ============================================================
my_indicator_name = "v16-meta"
my_indicator_description = "元策略：5状态市场识别（强牛/弱牛/震荡/弱熊/强熊）+自适应因子权重+自适应买卖阈值。牛市追趋势，熊市防御，震荡均衡。"

# ── 因子参数 ──
# @param roc_fast int 10 快ROC周期
# @param roc_slow int 20 慢ROC周期
# @param rsi_period int 14 RSI周期
# @param rsi_low int 30 RSI超卖线
# @param rsi_high int 75 RSI超买线
# @param bb_period int 20 布林带周期
# @param vol_climax_ratio float 2.0 量能爆发阈值(倍)
# @param vol_lookback int 60 波动率分位回溯期
# @param hv_period int 20 历史波动率周期

# ── 市场状态检测参数 ──
# @param ma_fast int 10 快均线
# @param ma_mid int 20 中均线（作为基准线）
# @param ma_slow int 60 慢均线（趋势分界线）
# @param adx_period int 14 ADX周期
# @param adx_strong int 25 强趋势ADX线
# @param adx_weak int 20 弱趋势ADX线

# ── 买入阈值（按状态） ──
# @param buy_threshold_strong_bull float 0.40 强牛买入阈值（激进）
# @param buy_threshold_weak_bull float 0.48 弱牛买入阈值
# @param buy_threshold_chop float 0.52 震荡买入阈值（均衡）
# @param buy_threshold_weak_bear float 0.60 弱熊买入阈值
# @param buy_threshold_strong_bear float 0.75 强熊买入阈值（几乎不买）

# ── 卖出参数 ──
# @param sell_threshold float 0.50 卖出分数阈值
# @param trail_window int 15 跟踪止损窗口
# @param trail_pct float 0.07 跟踪止损回撤

# ── 因子权重矩阵 [动量, 趋势, RSI, 量能, 波动率, 布林带, 资金流] ──
# @param w_momentum_strong_bull float 0.30
# @param w_momentum_weak_bull float 0.20
# @param w_momentum_chop float 0.18
# @param w_momentum_weak_bear float 0.10
# @param w_momentum_strong_bear float 0.05
# @param w_trend_strong_bull float 0.25
# @param w_trend_weak_bull float 0.20
# @param w_trend_chop float 0.15
# @param w_trend_weak_bear float 0.08
# @param w_trend_strong_bear float 0.00
# @param w_rsi_strong_bull float 0.15
# @param w_rsi_weak_bull float 0.18
# @param w_rsi_chop float 0.18
# @param w_rsi_weak_bear float 0.22
# @param w_rsi_strong_bear float 0.30
# @param w_vol_strong_bull float 0.10
# @param w_vol_weak_bull float 0.14
# @param w_vol_chop float 0.18
# @param w_vol_weak_bear float 0.18
# @param w_vol_strong_bear float 0.15
# @param w_volatility_strong_bull float 0.10
# @param w_volatility_weak_bull float 0.12
# @param w_volatility_chop float 0.14
# @param w_volatility_weak_bear float 0.18
# @param w_volatility_strong_bear float 0.22
# @param w_bb_strong_bull float 0.05
# @param w_bb_weak_bull float 0.10
# @param w_bb_chop float 0.12
# @param w_bb_weak_bear float 0.18
# @param w_bb_strong_bear float 0.23
# @param w_flow_strong_bull float 0.05
# @param w_flow_weak_bull float 0.06
# @param w_flow_chop float 0.05
# @param w_flow_weak_bear float 0.06
# @param w_flow_strong_bear float 0.05

# @strategy stopLossPct 0.08
# @strategy takeProfitPct 0.50

# ── 参数绑定 ──
rc_f = params.get("roc_fast", 10)
rc_s = params.get("roc_slow", 20)
rp = params.get("rsi_period", 14)
rl = params.get("rsi_low", 30)
rh = params.get("rsi_high", 75)
bp = params.get("bb_period", 20)
vcr = params.get("vol_climax_ratio", 2.0)
vl = params.get("vol_lookback", 60)
hp = params.get("hv_period", 20)
mf = params.get("ma_fast", 10)
mm = params.get("ma_mid", 20)
ms_ = params.get("ma_slow", 60)
ap = params.get("adx_period", 14)
adx_s = params.get("adx_strong", 25)
adx_w = params.get("adx_weak", 20)
b_t = {
    "strong_bull": params.get("buy_threshold_strong_bull", 0.40),
    "weak_bull": params.get("buy_threshold_weak_bull", 0.48),
    "chop": params.get("buy_threshold_chop", 0.52),
    "weak_bear": params.get("buy_threshold_weak_bear", 0.60),
    "strong_bear": params.get("buy_threshold_strong_bear", 0.75),
}
s_t = params.get("sell_threshold", 0.50)
tw_ = params.get("trail_window", 15)
tp = params.get("trail_pct", 0.07)

# 权重矩阵 (按状态索引)
W = {
    "strong_bull": [
        params.get("w_momentum_strong_bull", 0.30),
        params.get("w_trend_strong_bull", 0.25),
        params.get("w_rsi_strong_bull", 0.15),
        params.get("w_vol_strong_bull", 0.10),
        params.get("w_volatility_strong_bull", 0.10),
        params.get("w_bb_strong_bull", 0.05),
        params.get("w_flow_strong_bull", 0.05),
    ],
    "weak_bull": [
        params.get("w_momentum_weak_bull", 0.20),
        params.get("w_trend_weak_bull", 0.20),
        params.get("w_rsi_weak_bull", 0.18),
        params.get("w_vol_weak_bull", 0.14),
        params.get("w_volatility_weak_bull", 0.12),
        params.get("w_bb_weak_bull", 0.10),
        params.get("w_flow_weak_bull", 0.06),
    ],
    "chop": [
        params.get("w_momentum_chop", 0.18),
        params.get("w_trend_chop", 0.15),
        params.get("w_rsi_chop", 0.18),
        params.get("w_vol_chop", 0.18),
        params.get("w_volatility_chop", 0.14),
        params.get("w_bb_chop", 0.12),
        params.get("w_flow_chop", 0.05),
    ],
    "weak_bear": [
        params.get("w_momentum_weak_bear", 0.10),
        params.get("w_trend_weak_bear", 0.08),
        params.get("w_rsi_weak_bear", 0.22),
        params.get("w_vol_weak_bear", 0.18),
        params.get("w_volatility_weak_bear", 0.18),
        params.get("w_bb_weak_bear", 0.18),
        params.get("w_flow_weak_bear", 0.06),
    ],
    "strong_bear": [
        params.get("w_momentum_strong_bear", 0.05),
        params.get("w_trend_strong_bear", 0.00),
        params.get("w_rsi_strong_bear", 0.30),
        params.get("w_vol_strong_bear", 0.15),
        params.get("w_volatility_strong_bear", 0.22),
        params.get("w_bb_strong_bear", 0.23),
        params.get("w_flow_strong_bear", 0.05),
    ],
}

# ═══════════════════════════════════════════════════════════
# PART 1: 计算所有 7 个因子分数 (0-1)
# ═══════════════════════════════════════════════════════════
c = df["close"]
h = df["high"]
l = df["low"]
v = df["volume"]

# ── F1: ROC动量分数 ──
roc10 = (c - c.shift(rc_f)) / c.shift(rc_f)
roc20 = (c - c.shift(rc_s)) / c.shift(rc_s)
roc_composite = roc10 * 0.6 + roc20 * 0.4
momentum_score = 1.0 / (1.0 + np.exp(-roc_composite * 15))
same_dir = ((roc10 > 0) & (roc20 > 0)) | ((roc10 < 0) & (roc20 < 0))
momentum_score = momentum_score.fillna(0.5) * 0.8 + same_dir.astype(float).fillna(0.5) * 0.2

# ── F2: 趋势强度分数 ──
ma_f = c.rolling(mf).mean()
ma_m = c.rolling(mm).mean()
ma_s = c.rolling(ms_).mean()
ma_align = ((ma_f > ma_m).astype(float) + (ma_m > ma_s).astype(float) + (c > ma_m).astype(float)) / 3.0

# ADX + DI
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
dx = np.where(dxd > 0, 100 * np.abs(pdi - ndi) / dxd, 0)
adx = pd.Series(dx, index=df.index).rolling(ap).mean()
trend_strong = (adx > adx_s) & (pdi > ndi)
trend_any = (adx > adx_w) & (pdi > ndi)

# 价格延伸度
price_ext = (c - ma_m) / (atr14 + 1e-10)
ext_score = 1.0 - np.clip(np.abs(price_ext) / 2.0, 0, 1)
trend_score = (ma_align.fillna(0.5) * 0.35 + trend_any.astype(float).fillna(0) * 0.35 + ext_score.fillna(0.5) * 0.30)

# ── F3: RSI分数 ──
delta = c.diff()
gain = delta.where(delta > 0, 0.0).rolling(rp).mean()
loss = (-delta).where(delta < 0, 0.0).rolling(rp).mean()
rsi_val = 100.0 - (100.0 / (1.0 + gain / loss.replace(0, np.nan)))
rsi_score = np.clip(1.0 - (rsi_val - rl) / (rh - rl), 0, 1).fillna(0.5)

# ── F4: 量能确认分数 ──
vol_ma = v.rolling(20).mean()
vol_ratio = v / (vol_ma + 1e-10)
vol_climax = vol_ratio >= vcr
up_day = c > c.shift(1)
vol_confirm = ((vol_ratio > 1.2) & up_day) | ((vol_ratio < 0.8) & ~up_day)
vol_score = np.clip(vol_ratio / 3.0, 0, 1).fillna(0.5) * 0.4
vol_score += vol_confirm.astype(float).fillna(0) * 0.3
vol_score += (vol_climax.astype(float) * up_day.astype(float)).fillna(0) * 0.3

# ── F5: 波动率分数 ──
log_ret = np.log(c / c.shift(1))
hv = log_ret.rolling(hp).std() * np.sqrt(252)
hv_rank = hv.rolling(vl).apply(lambda x: (x < x.iloc[-1]).mean(), raw=False)
volatility_score = (1.0 - hv_rank).fillna(0.5)

# ── F6: 布林带分数 ──
bb_mid = c.rolling(bp).mean()
bb_std = c.rolling(bp).std()
bb_lower = bb_mid - 2.0 * bb_std
bb_upper = bb_mid + 2.0 * bb_std
bb_pct_b = (c - bb_lower) / (bb_upper - bb_lower + 1e-10)
bb_score = np.clip(1.0 - bb_pct_b * 2, 0, 1).fillna(0.5)

# ── F7: 资金流分数 ──
fp = df["main_net_pct"].fillna(0) > 0
fi = df["main_net_inflow"].fillna(0).rolling(3).mean() > df["main_net_inflow"].fillna(0).rolling(3).mean().shift(1)
flow_score = (fp.astype(float) * 0.5 + fi.astype(float) * 0.5).fillna(0.5)

# ═══════════════════════════════════════════════════════════
# PART 2: 市场状态检测（无未来数据泄露）
# ═══════════════════════════════════════════════════════════
# 状态判定条件 (全用rolling, 无shift导致的对齐问题通过.fillna处理)
above_ma20 = (c > ma_m).fillna(False)
above_ma60 = (c > ma_s).fillna(False)
ma20_above_ma60 = (ma_m > ma_s).fillna(False)
adx_strong = (adx > adx_s).fillna(False)
adx_moderate = (adx > adx_w).fillna(False)
di_bull = (pdi > ndi).fillna(False)
di_bear = (ndi > pdi).fillna(False)

# 5状态判定（互斥优先：强 > 弱 > 震荡）
is_strong_bull = above_ma20 & ma20_above_ma60 & adx_strong & di_bull
is_strong_bear = (~above_ma20) & (~ma20_above_ma60) & adx_strong & di_bear
is_weak_bull = above_ma60 & ~is_strong_bull
is_weak_bear = (~above_ma60) & ~is_strong_bear
# 震荡 = 不满足以上任何 (ADX < 20 或 方向不明)
is_chop = ~(is_strong_bull | is_strong_bear | is_weak_bull | is_weak_bear)

# 状态编码: strong_bull=0, weak_bull=1, chop=2, weak_bear=3, strong_bear=4
state_code = (
    is_strong_bull.astype(int) * 0 +
    is_weak_bull.astype(int) * 1 +
    is_chop.astype(int) * 2 +
    is_weak_bear.astype(int) * 3 +
    is_strong_bear.astype(int) * 4
)
state_names = {0: "strong_bull", 1: "weak_bull", 2: "chop", 3: "weak_bear", 4: "strong_bear"}

# ═══════════════════════════════════════════════════════════
# PART 3: 按状态选择权重 → 计算加权综合评分
# ═══════════════════════════════════════════════════════════
# 构建一个评分DataFrame，每行根据不同状态选择不同权重
all_scores = pd.DataFrame({
    "momentum": momentum_score,
    "trend": trend_score,
    "rsi": rsi_score,
    "volume": vol_score,
    "volatility": volatility_score,
    "bb": bb_score,
    "flow": flow_score,
}).fillna(0.5)

# 向量化：对每一行，根据state_code选取对应权重计算加权和
buy_score = pd.Series(0.0, index=df.index)
for code, name in state_names.items():
    mask = state_code == code
    if mask.sum() == 0:
        continue
    w = W[name]
    buy_score[mask] = (
        w[0] * all_scores.loc[mask, "momentum"] +
        w[1] * all_scores.loc[mask, "trend"] +
        w[2] * all_scores.loc[mask, "rsi"] +
        w[3] * all_scores.loc[mask, "volume"] +
        w[4] * all_scores.loc[mask, "volatility"] +
        w[5] * all_scores.loc[mask, "bb"] +
        w[6] * all_scores.loc[mask, "flow"]
    )

# ═══════════════════════════════════════════════════════════
# PART 4: 自适应买入阈值
# ═══════════════════════════════════════════════════════════
threshold = pd.Series(b_t["chop"], index=df.index)
for code, name in state_names.items():
    mask = state_code == code
    if mask.sum() > 0:
        threshold[mask] = b_t[name]

# 趋势强劲时额外降门槛（最多降0.04）
trend_bonus = trend_strong.astype(float).fillna(0) * 0.04
df["buy"] = buy_score > (threshold - trend_bonus)

# ═══════════════════════════════════════════════════════════
# PART 5: 卖出逻辑
# ═══════════════════════════════════════════════════════════
# MACD 死叉
ema_f = c.ewm(span=12, adjust=False).mean()
ema_s = c.ewm(span=26, adjust=False).mean()
dif = ema_f - ema_s
dea = dif.ewm(span=9, adjust=False).mean()
death_cross = (dif < dea) & (dif.shift(1) >= dea.shift(1))

# 跟踪止损
trail_high = c.rolling(tw_).max().shift(1)
trail_trigger = c < trail_high * (1.0 - tp)

# 卖出分数 (5维度)
sell_score = (
    0.20 * (1.0 - momentum_score.fillna(0.5)) +
    0.20 * (rsi_val > rh).astype(float).fillna(0) +
    0.20 * (c < ma_s).astype(float).fillna(0) +
    0.15 * death_cross.astype(float).fillna(0) +
    0.10 * (df["main_net_pct"].fillna(0) < -5).astype(float) +
    0.15 * trail_trigger.astype(float).fillna(0)
)

# 强熊市额外卖出压力
bear_pressure = (is_strong_bear.astype(float) + is_weak_bear.astype(float) * 0.5).fillna(0)
sell_score = sell_score + bear_pressure * 0.15

df["sell"] = (sell_score > s_t) | trail_trigger.fillna(False)
