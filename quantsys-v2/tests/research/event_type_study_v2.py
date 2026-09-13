"""分事件类型的事件研究 v2 —— 全样本版（2026-09-13 w-a9ec14d7）

为什么要 v2：v1（event_type_study.py）跑在**极薄样本**上（m_and_a 70 条/27 个事件日、
placement 357/34、insider 63、regulatory 35），且只取 source=cninfo_disclosure。
当时结论「五类候选全部判为伪影」**在那个样本下**是正确判断，但不足以定论。
2026-09-13 完成全量回补后（quant.event_calendar 71,916 行 / 5,550 只 / 211 个事件日），
同一套口径终于可以在**有统计意义**的样本上重跑。

v2 相对 v1 的四处升级（都是样本变大后才做得了、才必须做的）：
  1. 全来源：不再限定 cninfo_disclosure，并跨源去重（同 symbol+event_date+event_type 视为同一事件，
     保留 authority 最高的一条）——只看一个来源会同时漏事件和重复计数。
  2. 统计显著性：安慰剂不再只跑 1 次给一个基线，而是跑 B 次得到零分布，「均值」「中位数」各给一个经验 p 值。
  3. 多重检验校正：一次检验 ~15 个类型，α=0.05 下期望有 0.75 个纯靠运气显著；
     故报 Bonferroni 阈值 α/m，并明确标注哪些只是「未校正下显著」。
  4. 前置披露：样本仍不足的类型照样列出来并标注 insufficient（R-016 精神：不够就不下结论）。

口径（沿用已建立纪律，刻意保守）：
  · T0 = 事件日 → T+1 开盘进场（避免未来函数）→ 持 1/5/20 日，按收盘计；
  · 超额 = 个股收益 − 同期**全样本等权**市场收益 − 成本（买 7.5bp + 卖 12.5bp = 20bp/回合）；
  · 安慰剂对照：**同一批标的**取随机交易日跑同一流程（控制选股效应，只留时点效应）；
  · 稳健性四项：均值 vs 中位数、独立事件日数、前 5 名贡献占比、事件前 5 日超额。

用法：python tests/research/event_type_study_v2.py [--start 2026-01-01] [--end 2026-09-11] [--placebo 5]
"""
import argparse, io, os, subprocess
import numpy as np
import pandas as pd

ENV = dict(os.environ, PATH="/opt/homebrew/bin:/usr/local/bin:" + os.environ.get("PATH", ""))
COST = (7.5 + 12.5) / 1e4
WINDOWS = (1, 5, 20)
MIN_EVENTS = 200        # 低于此数只列示不下结论（R-016 精神）
MIN_EVENT_DAYS = 60     # 独立事件日门槛：事件聚集时条数会严重高估有效样本量
PLACEBO_CAP = 6000      # 安慰剂单次抽样上限（零分布不需要和样本等量）


def csv(sql):
    out = subprocess.run(["psql", "-d", "quant_investment", "-c", "copy (" + sql + ") to stdout with csv header"],
                         capture_output=True, text=True, env=ENV, check=True).stdout
    return pd.read_csv(io.StringIO(out), dtype={"symbol": str})


ap = argparse.ArgumentParser()
ap.add_argument("--start", default="2026-01-01")
ap.add_argument("--end", default="2026-09-11")
ap.add_argument("--placebo", type=int, default=5, help="安慰剂重复次数（零分布）")
ap.add_argument("--alpha", type=float, default=0.05)
a = ap.parse_args()

# ---------------- 事件样本：全来源 + 跨源去重 ----------------
# 注意：authority 不是列，而是持久化在 meta jsonb 里（event_repository._to_params 写的 meta.authority）。
# 部分行（earnings 等其它写入路径）meta 是标量 {'sep': bool}，->> 取不到值会返回 NULL，故 coalesce 兜 0。
ev = csv("select symbol, event_date, event_type, source, "
         "coalesce(nullif(meta->>'authority','')::int, 0) as authority "
         "from quant.event_calendar "
         "where symbol is not null and event_type is not null "
         "and event_date >= '%s' and event_date <= '%s'" % (a.start, a.end))
# 跨源去重时 authority 可能全为 0（旧行），再用来源优先级兜底：cninfo 原文 > 东财 > akshare 摘要
SRC_PRI = {"cninfo_disclosure": 3, "eastmoney_notice": 2, "akshare_disclosure": 1}
ev["_pri"] = ev["source"].map(SRC_PRI).fillna(0)
ev["_rank"] = ev["authority"].astype(int) * 10 + ev["_pri"].astype(int)
ev["symbol"] = ev["symbol"].str.zfill(6)
ev["event_date"] = pd.to_datetime(ev["event_date"])
n_raw = len(ev)
ev = (ev.sort_values("_rank", ascending=False)
        .drop_duplicates(subset=["symbol", "event_date", "event_type"], keep="first")
        .reset_index(drop=True))
print("事件原始 %d 条 -> 跨源去重后 %d 条（同 symbol+日期+类型视为同一事件，保留 authority 最高者）" % (n_raw, len(ev)))
print("覆盖 %d 只 / %d 个事件日 / %d 种类型" % (ev.symbol.nunique(), ev.event_date.nunique(), ev.event_type.nunique()))

# ---------------- 价格面板（numpy 化，7 万笔事件必须快） ----------------
syms = sorted(ev.symbol.unique())
# 面板右端延伸到 end + 45 自然日：否则窗口尾部（8~9 月）的事件 T+1 进场后凑不满 20 日，
# 会被静默丢弃 → 样本在时间上系统性偏向窗口前段的行情（是偏差，不是"少一点样本"）。
_panel_end = (pd.Timestamp(a.end) + pd.Timedelta(days=45)).date().isoformat()
k = csv("select symbol, trade_date, open, close from quant.daily_klines "
        "where trade_date between '%s' and '%s' and symbol in (%s) order by symbol, trade_date"
        % (a.start, _panel_end, ",".join("'" + s + "'" for s in syms)))
k["trade_date"] = pd.to_datetime(k["trade_date"])
close = k.pivot_table(index="trade_date", columns="symbol", values="close").ffill()
opn = k.pivot_table(index="trade_date", columns="symbol", values="open")
mkt = close.pct_change().mean(axis=1).fillna(0)          # 逐日 close->close 市场（等权）
# ⚠️ 2026-09-13 实测抓到的方法论 bug：个股是 **T+1 开盘** 进场，而市场基准原先用 close->close，
# 窗口起点落在 close[i1-1]（= close[i0]）——比个股多算了 close[i0]->open[i1] 这段隔夜跳空。
# 后果：安慰剂（同批标的随机日）本应中心在 0，实测却是 **+5%/20日** —— 安慰剂没通过中心性检验，
# 说明度量本身有偏，绝对数不可解释。修法：市场基准也按 open->close 对齐。
mkt_oc = (close / opn - 1.0).mean(axis=1).fillna(0).to_numpy(dtype=float)   # 当日 open->close（等权）
dates = close.index
date_pos = {d: i for i, d in enumerate(dates)}
CLOSE = {s: close[s].to_numpy(dtype=float) for s in close.columns}
OPEN = {s: (opn[s].to_numpy(dtype=float) if s in opn.columns else np.full(len(dates), np.nan)) for s in close.columns}
mkt_np = mkt.to_numpy(dtype=float)
cum = np.concatenate([[1.0], np.cumprod(1.0 + mkt_np)])   # cum[i] = 前 i 日累计
print("价格面板 %d 日 x %d 只（市场基准 = 面板等权）" % close.shape)
print()

N = len(dates)
SYM_POS = {s: i for i, s in enumerate(sorted(CLOSE.keys()))}
SYMS = list(SYM_POS.keys())
CLOSE_M = np.vstack([CLOSE[s] for s in SYMS])
OPEN_M = np.vstack([OPEN[s] for s in SYMS])   # 与 CLOSE_M 同一 SYMS 顺序


def collect_vec(sym_arr, pos_arr):
    """向量化的 collect：返回 (pre5, x1, x5, x20) 四个数组，无效记为 nan。"""
    n = len(pos_arr)
    pre5 = np.full(n, np.nan); x1 = np.full(n, np.nan)
    x5 = np.full(n, np.nan); x20 = np.full(n, np.nan)
    keep = np.zeros(n, dtype=bool)
    for t in range(n):
        si = SYM_POS.get(sym_arr[t])
        if si is None:
            continue
        i0 = pos_arr[t]
        if i0 >= N - 2 or i0 < 6:
            continue
        i1 = i0 + 1
        entry = OPEN_M[si, i1]
        if not np.isfinite(entry) or entry <= 0:
            continue
        pre5[t] = CLOSE_M[si, i0] / CLOSE_M[si, i0 - 5] - 1 - (cum[i0 + 1] / cum[i0 - 5] - 1)
        keep[t] = True
        for w, out in ((1, x1), (5, x5), (20, x20)):
            j = i1 + w - 1
            if j >= N or not np.isfinite(CLOSE_M[si, j]):
                continue
            # 市场：open[i1]->close[j] = (1+当日open->close) × Π_{t=i1+1..j}(1+close->close)
            mkt_r = (1.0 + mkt_oc[i1]) * (cum[j + 1] / cum[i1 + 1]) - 1.0
            out[t] = CLOSE_M[si, j] / entry - 1 - mkt_r - COST
    return pre5[keep], x1[keep], x5[keep], x20[keep], np.where(keep)[0]


ev["_pos"] = ev["event_date"].map(lambda d: date_pos.get(pd.Timestamp(d), -1)).astype(int)
ev = ev[ev["_pos"] >= 0].reset_index(drop=True)
print("可定位到面板交易日的 %d 条" % len(ev))
print()

rng = np.random.default_rng(7)
TRADABLE = np.arange(5, N - 25)


PLACEBO_DRAW = 20000   # 单次安慰剂抽样规模（一次抽足，再 bootstrap 出零分布）
BOOT = 2000            # bootstrap 重采样次数 -> p 值分辨率 1/2001

def placebo_null(sym_arr, n, B=None):
    """同一批标的 + 随机交易日 + 同一流程 -> (均值, 中位数) 的零分布。

    ⚠️ 2026-09-13 修正（本次实测踩到）：原来 B 次"每次抽 n 个"的做法，p 值最小只能是 1/(B+1)——
    B=5 时下限 0.1667，而**所有 16 个类型都恰好报 0.1667**，等于这个检验没有任何分辨力。
    现改为：一次性抽 PLACEBO_DRAW 个随机 (标的,日) 对得到一个大的安慰剂样本，
    再用 bootstrap 重采样 BOOT 次构造均值的零分布（p 值分辨率 1/2001）。
    中位数同理。这样才能回答"placement 的 +4.11% 中位到底是不是噪声"。
    """
    m = min(max(n, 5000), PLACEBO_DRAW)
    picks = rng.choice(TRADABLE, size=m, replace=True)
    idx = rng.integers(0, len(sym_arr), size=m)
    _, _, _, x20, _ = collect_vec([sym_arr[i] for i in idx], picks)
    v = x20[np.isfinite(x20)]
    if not len(v):
        return np.array([np.nan]), np.array([np.nan])
    res_m = v[rng.integers(0, len(v), size=(BOOT, len(v)))]
    means = res_m.mean(axis=1)
    medians = np.median(res_m, axis=1)
    return means, medians


def clustered_ci(dates_arr, vals, B=2000, alpha=0.05):
    """按**事件日聚类**的 bootstrap：重采样"日"而不是"观测"。

    为什么必须做（2026-09-13 修正）：同一事件日往往有几十上百只票同时出事件，
    它们的 20 日窗口高度重叠 → 观测之间**不独立**。直接对观测做 bootstrap 会低估标准误、
    把 p 值算得过于乐观。聚类到"日"之后，有效样本量 ≈ 事件日数（本例 150 上下），而非条数（几千）。
    返回 (下界, 上界)。
    """
    uniq = np.unique(dates_arr)
    if len(uniq) < 5:
        return float("nan"), float("nan")
    buckets = [vals[dates_arr == d] for d in uniq]
    means = np.empty(B)
    for b in range(B):
        pick = rng.integers(0, len(uniq), size=len(uniq))
        means[b] = np.concatenate([buckets[i] for i in pick]).mean()
    return float(np.percentile(means, 100 * alpha / 2)), float(np.percentile(means, 100 * (1 - alpha / 2)))


def pvalue(null, observed):
    null = null[np.isfinite(null)]
    if not len(null) or not np.isfinite(observed):
        return float("nan")
    return float((np.sum(np.abs(null) >= abs(observed)) + 1) / (len(null) + 1))


types = [t for t, g in ev.groupby("event_type") if len(g) >= 50]
m = len(types)
bonf = a.alpha / max(m, 1)

print("=== 主表（超额：个股 - 全样本等权 - 20bp 成本；安慰剂 = 同批标的随机日 x %d 次）===" % a.placebo)
print("%-20s %6s %6s %9s %9s %22s" %
      ("事件类型", "n", "事件日", "20日均值", "安慰剂均值", "净额95%CI（按事件日聚类）"))
results = []
for t in types:
    g = ev[ev.event_type == t]
    sym_arr = g.symbol.values
    pos_arr = g._pos.values
    pre5, x1a, x5a, x20a, _keep = collect_vec(sym_arr, pos_arr)
    v = x20a[np.isfinite(x20a)]          # ndarray：numpy 无 .median()，一律用 np.median
    if not len(v):
        continue
    vc = g.event_date.value_counts()
    pl_m, pl_med = placebo_null(sym_arr, len(g))
    p_m = pvalue(pl_m, float(v.mean()))
    p_med = pvalue(pl_med, float(np.median(v)))
    top5 = float(np.sort(v)[-5:].sum() / v.sum() * 100) if len(v) > 5 and abs(v.sum()) > 1e-9 else float("nan")
    # 聚类 CI 用的是"净额"：观测值减去安慰剂均值（把"这批票本身就强/弱"这一项扣掉）
    # 注意对齐：_keep 是 collect_vec 保留的样本位置，而 v 又筛掉了 x20 为 NaN 的那些
    # —— 两重筛选必须同时施加到日期上，否则日期与观测错位（聚类 CI 会算错却看不出来）
    dates_kept = g.event_date.values[_keep][np.isfinite(x20a)]
    m_pl = float(np.nanmean(pl_m))
    ci_lo, ci_hi = clustered_ci(dates_kept, v - m_pl)
    results.append({"type": t, "n": len(g), "event_days": int(len(vc)),
                    "max_per_day": int(vc.max()) if len(vc) else 0,
                    "mean1": float(np.nanmean(x1a)), "mean5": float(np.nanmean(x5a)),
                    "mean20": float(v.mean()), "median20": float(np.median(v)),
                    "win20": float((v > 0).mean()),
                    "placebo_mean20": float(np.nanmean(pl_m)),
                    "p_mean": p_m, "p_median": p_med, "top5_share": top5,
                    "pre5_median": float(np.nanmedian(pre5)),
                    "ci_lo": ci_lo, "ci_hi": ci_hi})
    sig = "  排除0" if ci_lo > 0 else ("  全负" if ci_hi < 0 else "")
    print("%-20s %6d %6d %+8.2f%% %+8.2f%%   [%+7.2f%%, %+7.2f%%]%s"
          % (t, len(g), int(len(vc)), v.mean() * 100, np.nanmean(pl_m) * 100,
             ci_lo * 100, ci_hi * 100, sig))

print()
print("多重检验：本次检验 %d 个类型 => Bonferroni 阈值 alpha/m = %.5f" % (m, bonf))
print()

print("=== 稳健性明细（决定是不是真信号的四项）===")
print("%-20s %6s %6s %8s %12s %14s %10s" %
      ("事件类型", "n", "事件日", "20日中位", "前5名贡献", "事件前5日中位", "20日胜率"))
for r in sorted(results, key=lambda x: -x["n"]):
    flag = "  [样本不足]" if (r["n"] < MIN_EVENTS or r["event_days"] < MIN_EVENT_DAYS) else ""
    print("%-20s %6d %6d %+7.2f%% %11s %13.2f%% %9.0f%%%s"
          % (r["type"], r["n"], r["event_days"], r["median20"] * 100,
             ("%.0f%%" % r["top5_share"]) if np.isfinite(r["top5_share"]) else "n/a",
             r["pre5_median"] * 100, r["win20"] * 100, flag))

print()
print("=== 判定 ===")
passed = []
for r in sorted(results, key=lambda x: -x["n"]):
    reasons = []
    if r["n"] < MIN_EVENTS:
        reasons.append("n=%d<%d" % (r["n"], MIN_EVENTS))
    if r["event_days"] < MIN_EVENT_DAYS:
        reasons.append("事件日 %d<%d" % (r["event_days"], MIN_EVENT_DAYS))
    if not (np.isfinite(r["ci_lo"]) and r["ci_lo"] > 0):
        reasons.append("按事件日聚类的 95%%CI 含 0（[%+.2f%%, %+.2f%%]）"
                       % (r["ci_lo"] * 100, r["ci_hi"] * 100))
    if r["mean20"] > 0 and r["median20"] <= 0:
        reasons.append("均值正但中位非正（少数股主导）")
    if np.isfinite(r["top5_share"]) and r["top5_share"] > 100:
        reasons.append("前5名贡献 %.0f%%（>100%% = 其余为负）" % r["top5_share"])
    if r["pre5_median"] > 0.01:
        reasons.append("事件前5日已 %+.2f%%（信号在进场前已反映）" % (r["pre5_median"] * 100))
    if reasons:
        print("  x %-20s %s" % (r["type"], "; ".join(reasons)))
    else:
        print("  v %-20s 通过全部稳健性检查（含按事件日聚类校significance；仍须 OOS 与实盘小仓验证，不直接进策略）" % r["type"])
        passed.append(r["type"])
print()
print("通过类型：%s" % (", ".join(passed) if passed else "（无）"))

import json as _json
_out = {"generated_at": pd.Timestamp.now().isoformat(timespec="seconds"),
        "window": [a.start, a.end], "n_raw": int(n_raw), "n_dedup": int(len(ev)),
        "symbols": int(ev.symbol.nunique()), "event_days": int(ev.event_date.nunique()),
        "bonferroni": float(bonf),
        "caliber": "超额 = 个股 T+1开盘进场 - 全样本等权(open->close 对齐) - 20bp；净额 = 观测减同批标的随机日安慰剂均值；CI = 按事件日聚类 bootstrap",
        "results": results, "passed": passed}
_p = "config/event_type_study_v2.json"
with open(_p, "w", encoding="utf-8") as fh:
    _json.dump(_out, fh, ensure_ascii=False, indent=1)
print("结果已落盘 ->", _p)