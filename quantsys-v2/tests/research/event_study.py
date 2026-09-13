"""财报披露事件研究（PEAD 检验，2026-09-13 w-a9ec14d7）

数据来源：quant.event_calendar 里 source='akshare_disclosure' 且标题含「已披露」的事件
（= **实际披露日**，point-in-time 正确；预约日只用于前瞻排期，不能当事件日）。

口径（沿用 strategy_lab 纪律，刻意保守，避免自欺）：
  1. T0 = 实际披露日（非交易日则顺延到下一交易日）；**T+1 开盘进场**（公告多在盘后，这是可实现的时点）；
  2. 持有 k ∈ {1, 5, 20} 个交易日，收盘出场；
  3. **超额 = 个股窗口收益 − 同期全市场等权收益**（该窗口市场整体上行，不做市场调整会得出假 alpha）；
  4. 成本：买 7.5bp + 卖 12.5bp（与 strategy_lab 一致），每笔一次往返；
  5. **安慰剂对照**：把每只股票的事件日换成随机交易日，同一套流程跑一遍——
     若"事件组的超额"与"随机日期组的超额"无差别，说明测到的是噪声而不是财报效应。

PEAD 假设：公告当日的市场反应（surprise 代理）应**延续**到之后 N 日。
故按 T0 当日超额分 5 档，看后续窗口超额是否单调（这才是漂移，而不是"买到就涨"）。
"""
import io, os, subprocess, sys
import numpy as np
import pandas as pd

ENV = dict(os.environ, PATH="/opt/homebrew/bin:/usr/local/bin:" + os.environ.get("PATH", ""))
START, END = "2026-01-01", "2026-09-11"
COST = (7.5 + 12.5) / 1e4
WINDOWS = (1, 5, 20)


def csv(sql):
    out = subprocess.run(["psql", "-d", "quant_investment", "-c", "copy (" + sql + ") to stdout with csv header"],
                         capture_output=True, text=True, env=ENV, check=True).stdout
    return pd.read_csv(io.StringIO(out), dtype={"symbol": str})


ev = csv("select symbol, event_date from quant.event_calendar "
         "where source='akshare_disclosure' and title like '%已披露%' and symbol is not null")
ev["symbol"] = ev["symbol"].str.zfill(6)
ev["event_date"] = pd.to_datetime(ev["event_date"])
print("事件数 %d，涉及 %d 只，日期 %s ~ %s" % (len(ev), ev.symbol.nunique(),
      ev.event_date.min().date(), ev.event_date.max().date()))
print("按期分布:", ev.event_date.dt.to_period("M").value_counts().sort_index().to_dict())

syms = sorted(ev.symbol.unique())
k = csv("select symbol, trade_date, open, close from quant.daily_klines where trade_date between '%s' and '%s' "
        "and symbol in (%s) order by symbol, trade_date" % (START, END, ",".join("'" + s + "'" for s in syms)))
k["trade_date"] = pd.to_datetime(k["trade_date"])
close = k.pivot_table(index="trade_date", columns="symbol", values="close").ffill()
opn = k.pivot_table(index="trade_date", columns="symbol", values="open")
ret = close.pct_change()
mkt = ret.mean(axis=1).fillna(0)          # 全市场等权（同期对照）
print("价格面板 %d 日 × %d 只" % close.shape)


def run(events, label):
    rows = []
    for sym, d0 in zip(events["symbol"].values, events["event_date"].values):
        if sym not in close.columns:
            continue
        s = close[sym]
        dates = s.index
        # T0：事件日或其后第一个交易日
        pos = dates.searchsorted(pd.Timestamp(d0))
        if pos >= len(dates) - 2:
            continue
        i0, i1 = pos, pos + 1                       # i0=T0, i1=T+1（进场）
        if not np.isfinite(s.iloc[i0]) or not np.isfinite(opn[sym].iloc[i1] or np.nan):
            continue
        entry = opn[sym].iloc[i1]
        if not np.isfinite(entry) or entry <= 0:
            continue
        # 公告当日超额（surprise 代理）：T0 收 vs T0-1 收，减市场
        if i0 < 1:
            continue
        t0_exc = (s.iloc[i0] / s.iloc[i0 - 1] - 1) - mkt.iloc[i0]
        rec = {"symbol": sym, "t0_excess": float(t0_exc)}
        for w in WINDOWS:
            j = i1 + w - 1
            if j >= len(dates):
                rec["x%d" % w] = np.nan
                continue
            exit_px = s.iloc[j]
            if not np.isfinite(exit_px):
                rec["x%d" % w] = np.nan
                continue
            stock = exit_px / entry - 1
            mkt_r = float((1 + mkt.iloc[i1:j + 1]).prod() - 1)
            rec["x%d" % w] = float(stock - mkt_r - COST)
        rows.append(rec)
    df = pd.DataFrame(rows)
    print()
    print("=== %s（n=%d）===" % (label, len(df)))
    for w in WINDOWS:
        col = "x%d" % w
        v = df[col].dropna()
        if len(v) == 0:
            continue
        print("  T+1 持有 %2d 日：均值超额 %+6.2f%%  中位 %+6.2f%%  胜率 %5.1f%%  （费后）"
              % (w, v.mean() * 100, v.median() * 100, 100 * (v > 0).mean()))
    # PEAD：按 T0 反应分档
    q = df.dropna(subset=["x5"]).copy()
    if len(q) > 200:
        q["bucket"] = pd.qcut(q["t0_excess"], 5, labels=["Q1 最差", "Q2", "Q3", "Q4", "Q5 最好"])
        print("  PEAD 分档（按公告当日超额）：")
        for name, g in q.groupby("bucket", observed=True):
            print("    %-8s n=%5d | T0 超额 %+6.2f%% | T+1..5 超额 %+6.2f%% | T+1..20 超额 %+6.2f%%"
                  % (name, len(g), g["t0_excess"].mean() * 100, g["x5"].mean() * 100,
                     (g["x20"].mean() * 100) if "x20" in g else float("nan")))
        hi, lo = q[q["bucket"] == "Q5 最好"], q[q["bucket"] == "Q1 最差"]
        print("    **多空价差（Q5−Q1）T+1..5: %+.2f%% | T+1..20: %+.2f%%**"
              % ((hi["x5"].mean() - lo["x5"].mean()) * 100, (hi["x20"].mean() - lo["x20"].mean()) * 100))
    return df


main_df = run(ev, "财报披露事件组")

# 安慰剂：每只股票随机取一个交易日当"事件日"
rng = np.random.default_rng(42)
tradable = close.index[5:-25]
placebo = ev.copy()
placebo["event_date"] = [tradable[rng.integers(0, len(tradable))] for _ in range(len(placebo))]
run(placebo, "安慰剂组（随机日期，同股票池同流程）")
