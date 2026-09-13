"""分事件类型的事件研究（event_type_study.py，2026-09-13 w-a9ec14d7）

回答：回购/定增/股权激励/监管/并购…哪一类在本市场有可交易的方向性效应。

口径（沿用已建立纪律）：T0=事件日 → T+1 开盘进场 → 持 1/5/20 日；超额 = 个股 − 同期全市场等权；成本 20bp；
**安慰剂对照**（同批标的取随机交易日跑同一流程）。

稳健性明细（必须看，否则会把运气当效应）：
  · 均值 vs **中位数**（均值易被少数暴涨股主导）；
  · 独立事件日数（事件高度聚集时有效样本量远小于条数）；
  · 前 5 名贡献占比（看是不是"几只票撑起整个均值"）；
  · 事件前 5 日超额（若显著为正 → 信号在进场前已反映，那不是事件效应而是动量）。
"""
import argparse, io, os, subprocess
import numpy as np
import pandas as pd

ENV = dict(os.environ, PATH="/opt/homebrew/bin:/usr/local/bin:" + os.environ.get("PATH", ""))
COST = (7.5 + 12.5) / 1e4
WINDOWS = (1, 5, 20)
CANDIDATES = ("m_and_a", "insider", "regulatory", "equity_incentive", "placement")


def csv(sql):
    out = subprocess.run(["psql", "-d", "quant_investment", "-c", "copy (" + sql + ") to stdout with csv header"],
                         capture_output=True, text=True, env=ENV, check=True).stdout
    return pd.read_csv(io.StringIO(out), dtype={"symbol": str})


ap = argparse.ArgumentParser()
ap.add_argument("--source", default="cninfo_disclosure")
ap.add_argument("--start", default="2026-01-01")
ap.add_argument("--end", default="2026-09-11")
ap.add_argument("--min-events", type=int, default=30)
a = ap.parse_args()

ev = csv("select symbol, event_date, event_type from quant.event_calendar "
         "where source = '%s' and symbol is not null and event_date >= '%s' and event_date <= '%s'"
         % (a.source, a.start, a.end))
ev["symbol"] = ev["symbol"].str.zfill(6)
ev["event_date"] = pd.to_datetime(ev["event_date"])
print("事件 %d 条 / %d 只 / 类型 %d 种（来源 %s）" % (len(ev), ev.symbol.nunique(), ev.event_type.nunique(), a.source))

k = csv("select symbol, trade_date, open, close from quant.daily_klines "
        "where trade_date between '2026-01-01' and '2026-09-11' and symbol in (%s) order by symbol, trade_date"
        % ",".join("'" + s + "'" for s in sorted(ev.symbol.unique())))
k["trade_date"] = pd.to_datetime(k["trade_date"])
close = k.pivot_table(index="trade_date", columns="symbol", values="close").ffill()
opn = k.pivot_table(index="trade_date", columns="symbol", values="open")
mkt = close.pct_change().mean(axis=1).fillna(0)
print("价格面板 %d 日 × %d 只" % close.shape)


def collect(events):
    rows = []
    for sym, d0 in zip(events["symbol"].values, events["event_date"].values):
        if sym not in close.columns:
            continue
        s = close[sym]
        dates = s.index
        i0 = dates.searchsorted(pd.Timestamp(d0))
        if i0 >= len(dates) - 2 or i0 < 6:
            continue
        i1 = i0 + 1
        entry = opn[sym].iloc[i1]
        if not np.isfinite(entry) or entry <= 0:
            continue
        rec = {"symbol": sym, "event_date": str(pd.Timestamp(d0).date())}
        rec["pre5"] = float(s.iloc[i0] / s.iloc[i0 - 5] - 1) - float((1 + mkt.iloc[i0 - 4:i0 + 1]).prod() - 1)
        for w in WINDOWS:
            j = i1 + w - 1
            if j >= len(dates) or not np.isfinite(s.iloc[j]):
                rec["x%d" % w] = np.nan
                continue
            mkt_r = float((1 + mkt.iloc[i1:j + 1]).prod() - 1)
            rec["x%d" % w] = float(s.iloc[j] / entry - 1 - mkt_r - COST)
        rows.append(rec)
    return pd.DataFrame(rows)


rng = np.random.default_rng(7)
tradable = close.index[5:-25]
pl = collect(pd.DataFrame({"symbol": ev.symbol.values,
                           "event_date": [tradable[rng.integers(0, len(tradable))] for _ in range(len(ev))]}))
print()
print("%-20s %5s %8s %8s %9s %9s %11s" % ("事件类型", "n", "1日", "5日", "20日", "20日中位", "vs安慰剂20日"))
for t, g in ev.groupby("event_type"):
    if len(g) < a.min_events:
        continue
    r = collect(g[["symbol", "event_date"]])
    if len(r) == 0:
        continue
    print("%-20s %5d %+7.2f%% %+7.2f%% %+8.2f%% %+8.2f%% %+10.2f%%"
          % (t, len(g), r.x1.mean() * 100, r.x5.mean() * 100, r.x20.mean() * 100,
             r.x20.median() * 100, (r.x20.mean() - pl.x20.mean()) * 100))
print()
print("安慰剂基线：1日 %+.2f%% | 5日 %+.2f%% | 20日 %+.2f%%（n=%d）"
      % (pl.x1.mean() * 100, pl.x5.mean() * 100, pl.x20.mean() * 100, len(pl)))

print()
print("=== 稳健性明细（候选类型）===")
for t in CANDIDATES:
    g = ev[ev.event_type == t]
    if len(g) == 0:
        continue
    r = collect(g[["symbol", "event_date"]])
    if len(r) == 0:
        continue
    v = r["x20"].dropna()
    vc = r["event_date"].value_counts()
    top5 = 0.0
    if len(v) > 5 and abs(v.sum()) > 1e-9:
        top5 = float(v.nlargest(5).sum() / v.sum()) * 100
    print("  %-18s n=%4d | 独立事件日 %3d（最多一日 %2d 条） | 20日中位 %+7.2f%% | 前5名贡献 %s | 事件前5日(中位) %+.2f%%"
          % (t, len(r), len(vc), int(vc.max()), v.median() * 100,
             ("%.0f%%" % top5) if top5 else "n/a", r["pre5"].median() * 100))