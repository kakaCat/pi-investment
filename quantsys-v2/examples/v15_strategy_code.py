# v15-multi-alpha
# ============================================================
# 核心创新 vs v11-v14:
#   1. ROC动量因子（全新 - 各版本均无）
#   2. 波动率分位数判断（全新 - 用于自适应阈值）
#   3. 成交量确认（升级 - 从简单量比→量价配合）
#   4. 价格延伸度（全新 - ATR标准化距离）
#   5. 连续加权评分（升级 - 从等权投票→加权连续评分）
#   6. 波动率自适应阈值（全新 - 低波降门槛/高波升门槛）
# ============================================================
my_indicator_name = "v15-multi-alpha"
my_indicator_description = "多Alpha策略：ROC动量+波动率分位+量价确认+价格延伸度+加权评分+波动率自适应阈值。打破v11-v14因子同质化。"

# @param roc_fast int 10 快ROC周期
# @param roc_slow int 20 慢ROC周期
# @param roc_weight float 0.20 动量因子权重
# @param vol_lookback int 60 波动率分位数回溯期
# @param hv_period int 20 历史波动率周期
# @param vol_climax_ratio float 2.0 量能爆发阈值(倍)
# @param vol_weight float 0.15 量能因子权重
# @param ma_fast int 10 快均线
# @param ma_mid int 20 中均线
# @param ma_slow int 60 慢均线
# @param adx_period int 14 ADX周期
# @param adx_threshold int 20 ADX趋势阈值
# @param trend_weight float 0.25 趋势因子权重
# @param rsi_period int 14 RSI周期
# @param rsi_low int 30 RSI超卖线
# @param rsi_high int 75 RSI超买线
# @param rsi_weight float 0.15 RSI因子权重
# @param bb_period int 20 布林带周期
# @param flow_weight float 0.05 资金流因子权重
# @param buy_threshold_low_vol float 0.45 低波动买入阈值
# @param buy_threshold_normal float 0.50 正常波动买入阈值
# @param buy_threshold_high_vol float 0.58 高波动买入阈值
# @param sell_threshold float 0.55 卖出阈值
# @param trail_window int 15 跟踪止损窗口
# @param trail_pct float 0.07 跟踪止损回撤
# @strategy stopLossPct 0.08
# @strategy takeProfitPct 0.50

# ── 参数 ──
rf = params.get("roc_fast", 10)
rs = params.get("roc_slow", 20)
rw = params.get("roc_weight", 0.20)
vl = params.get("vol_lookback", 60)
hp = params.get("hv_period", 20)
vcr = params.get("vol_climax_ratio", 2.0)
vw = params.get("vol_weight", 0.15)
mf = params.get("ma_fast", 10)
mm = params.get("ma_mid", 20)
ms_ = params.get("ma_slow", 60)
ap = params.get("adx_period", 14)
at = params.get("adx_threshold", 20)
tw = params.get("trend_weight", 0.25)
rp = params.get("rsi_period", 14)
rl = params.get("rsi_low", 30)
rh = params.get("rsi_high", 75)
iw = params.get("rsi_weight", 0.15)
bp = params.get("bb_period", 20)
fw = params.get("flow_weight", 0.05)
btl = params.get("buy_threshold_low_vol", 0.45)
btn = params.get("buy_threshold_normal", 0.50)
bth = params.get("buy_threshold_high_vol", 0.58)
st = params.get("sell_threshold", 0.55)
tw_ = params.get("trail_window", 15)
tp = params.get("trail_pct", 0.07)

# ═══════════════════════════════════════════════════════════
# 因子1: ROC动量（全新 — v11-v14完全没有）
# ═══════════════════════════════════════════════════════════
c = df["close"]
roc10 = (c - c.shift(rf)) / c.shift(rf)
roc20 = (c - c.shift(rs)) / c.shift(rs)
# 复合动量: 快+慢平均，近期权重更高
roc_composite = roc10 * 0.6 + roc20 * 0.4
# Sigmoid归一化到0-1 (中心在0，范围大约-0.15到+0.15)
momentum_score = 1.0 / (1.0 + np.exp(-roc_composite * 15))
# 动量方向一致性加分：快慢同向时boost
same_direction = ((roc10 > 0) & (roc20 > 0)) | ((roc10 < 0) & (roc20 < 0))
momentum_score = momentum_score * 0.8 + same_direction.astype(float) * 0.2

# ═══════════════════════════════════════════════════════════
# 因子2: 波动率分位数（全新 — 用于判断市场状态和自适应阈值）
# ═══════════════════════════════════════════════════════════
log_ret = np.log(c / c.shift(1))
hv = log_ret.rolling(hp).std() * np.sqrt(252)  # 年化历史波动率
# 波动率在60日内的分位数（高=高波，低=低波）
hv_rank = hv.rolling(vl).apply(lambda x: (x < x.iloc[-1]).mean(), raw=False)
is_high_vol = hv_rank > 0.70
is_low_vol = hv_rank < 0.30
# 波动率分数: 低波=高分(好入场), 高波=低分(等一等)
vol_score = 1.0 - hv_rank.fillna(0.5)

# ═══════════════════════════════════════════════════════════
# 因子3: 量能确认（升级 — v11-v14只用简单量比，这里加入量价配合和量能爆发）
# ═══════════════════════════════════════════════════════════
vol = df["volume"]
vol_ma = vol.rolling(20).mean()
vol_ratio = vol / (vol_ma + 1e-10)
# 量能爆发：当日量超过N倍均量
vol_climax = vol_ratio >= vcr
# 量价配合：放量上涨/缩量下跌=健康，放量下跌/缩量上涨=异常
up_day = c > c.shift(1)
vol_confirm = ((vol_ratio > 1.2) & up_day) | ((vol_ratio < 0.8) & ~up_day)
# 量能分数
vol_score = np.clip(vol_ratio / 3.0, 0, 1) * 0.4  # 量能大小
vol_score += vol_confirm.astype(float) * 0.3        # 量价配合
vol_score += vol_climax.astype(float) * up_day.astype(float) * 0.3  # 放量上涨额外加分

# ═══════════════════════════════════════════════════════════
# 因子4: 趋势强度（升级 — 加入价格延伸度，避免追高）
# ═══════════════════════════════════════════════════════════
ma_f = c.rolling(mf).mean()
ma_m = c.rolling(mm).mean()
ma_s = c.rolling(ms_).mean()

# 均线排列 0-1
ma_alignment = ((ma_f > ma_m).astype(float) + (ma_m > ma_s).astype(float) + (c > ma_m).astype(float)) / 3.0

# ADX + 方向
h = df["high"]; l = df["low"]
tr1 = h - l
tr2 = (h - c.shift(1)).abs()
tr3 = (l - c.shift(1)).abs()
tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
atr14 = tr.rolling(14).mean()
um = h.diff(); dmv = -l.diff()
pdm = ((um > dmv) & (um > 0)).astype(float) * um
mdm = ((dmv > um) & (dmv > 0)).astype(float) * dmv
pdi = 100 * (pdm.rolling(ap).mean() / atr14.replace(0, np.nan))
ndi = 100 * (mdm.rolling(ap).mean() / atr14.replace(0, np.nan))
dxd = pdi + ndi
dx = np.where(dxd > 0, 100 * np.abs(pdi - ndi) / dxd, 0)
adx = pd.Series(dx, index=df.index).rolling(ap).mean()
adx_ok = adx > at
di_bullish = pdi > ndi
trend_strong = adx_ok & di_bullish

# 价格延伸度: 距离MA20多少个ATR（全新 — v11-v14无此因子）
price_ext = (c - ma_m) / (atr14 + 1e-10)
# 理想买入区：-0.5到+0.5 ATR（不追高+不接飞刀）
ext_score = 1.0 - np.clip(np.abs(price_ext) / 2.0, 0, 1)

# 趋势综合分数
trend_score = ma_alignment * 0.35 + trend_strong.astype(float) * 0.35 + ext_score * 0.30

# ═══════════════════════════════════════════════════════════
# 因子5: RSI（升级 — 连续评分替代二值判定）
# ═══════════════════════════════════════════════════════════
delta = c.diff()
gain = delta.where(delta > 0, 0.0).rolling(rp).mean()
loss = (-delta).where(delta < 0, 0.0).rolling(rp).mean()
rsi = 100.0 - (100.0 / (1.0 + gain / loss.replace(0, np.nan)))
# RSI分数: 30以下=1分, 30-50=线性下降, 50-75=低分, 75以上=0
rsi_score = np.clip(1.0 - (rsi - rl) / (rh - rl), 0, 1)

# ═══════════════════════════════════════════════════════════
# 因子6: 资金流向（保留但降权 — 数据覆盖率低）
# ═══════════════════════════════════════════════════════════
fp = df["main_net_pct"].fillna(0) > 0
fi = df["main_net_inflow"].fillna(0).rolling(3).mean() > df["main_net_inflow"].fillna(0).rolling(3).mean().shift(1)
flow_score = (fp.astype(float) * 0.5 + fi.astype(float) * 0.5).fillna(0.5)

# ═══════════════════════════════════════════════════════════
# 因子7: 布林带低位（保留 — 有效因子，但改为连续评分）
# ═══════════════════════════════════════════════════════════
bb_mid = c.rolling(bp).mean()
bb_std = c.rolling(bp).std()
bb_lower = bb_mid - 2.0 * bb_std
bb_upper = bb_mid + 2.0 * bb_std
bb_pct_b = (c - bb_lower) / (bb_upper - bb_lower + 1e-10)
# BB分数: %B越低分数越高
bb_score = np.clip(1.0 - bb_pct_b * 2, 0, 1)

# ═══════════════════════════════════════════════════════════
# 加权综合评分（核心创新: 不等权）
# ═══════════════════════════════════════════════════════════
buy_score = (
    rw * momentum_score.fillna(0.5) +
    vw * vol_score.fillna(0.5) +
    tw * trend_score.fillna(0.5) +
    iw * rsi_score.fillna(0.5) +
    fw * flow_score.fillna(0.5) +
    (1.0 - rw - vw - tw - iw - fw) * bb_score.fillna(0.5)
)

# ═══════════════════════════════════════════════════════════
# 波动率自适应买入阈值（核心创新: 市场状态自适应）
# ═══════════════════════════════════════════════════════════
threshold = pd.Series(btn, index=df.index)
threshold[is_low_vol.fillna(False)] = btl
threshold[is_high_vol.fillna(False)] = bth

# 趋势强劲时额外降门槛
trend_bonus = trend_strong.astype(float) * 0.03
df["buy"] = buy_score > (threshold - trend_bonus)

# ═══════════════════════════════════════════════════════════
# 卖出: 多信号综合 + 跟踪止损
# ═══════════════════════════════════════════════════════════
# MACD卖出
ema_f = c.ewm(span=12, adjust=False).mean()
ema_s = c.ewm(span=26, adjust=False).mean()
dif = ema_f - ema_s
dea = dif.ewm(span=9, adjust=False).mean()
death_cross = (dif < dea) & (dif.shift(1) >= dea.shift(1))

# 卖出维度
sell_momentum = 1.0 - momentum_score.fillna(0.5)
sell_rsi = (rsi > rh).astype(float)
sell_trend = (c < ma_s).astype(float)
sell_macd = death_cross.astype(float)
sell_flow = (df["main_net_pct"].fillna(0) < -5).astype(float)

# 跟踪止损
trail_high = c.rolling(tw_).max().shift(1)
trail_trigger = c < trail_high * (1.0 - tp)

sell_score = (
    0.20 * sell_momentum +
    0.20 * sell_rsi +
    0.20 * sell_trend +
    0.20 * sell_macd +
    0.10 * sell_flow +
    0.10 * trail_trigger.astype(float)
)

df["sell"] = (sell_score > st) | trail_trigger.fillna(False)
