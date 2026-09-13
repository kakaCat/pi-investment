"""横截面 v2：动态股票池（每个调仓日按"当时可见"数据重算），消除前视偏差

为什么必须重做（2026-09-13 w-c8cae280）：
  第一版用「候选池 35 的今日成员」回测 2023-2026，而 pool_change_log 为空、无法重建历史成分
  ⇒ 那是**前视偏差**（今天的成员之所以在池里，部分因为后来表现好）。池上 +35% 的 Sharpe 1.21 不可采信。

本版口径：
  1. **候选集合**只用窗口开始前的数据挑（2021-06~2022-05 的日均成交额 TopN），此后不再变；
  2. 每个调仓日**只用当日及以前**的数据做筛选（20日均额、close>MA120、历史长度），
     再按 mom60 排序取 TopN —— 无任何未来信息；
  3. 成本买 7.5bp / 卖 12.5bp；次日开盘成交；可选广度 regime 闸门与个股止损；
  4. 基准三条：(a) 同一候选集合买入持有；(b) 同池"只过滤不排序"等权（隔离排序的贡献）。

用法：
  python scripts/strategy_xsec2.py --mode mom|hold|fixed --topn 20 [--regime] [--stop-loss -0.15]
"""
import argparse, io, os, subprocess, sys
from pathlib import Path

import numpy as np
import pandas as pd

ENV = dict(os.environ, PATH="/opt/homebrew/bin:/usr/local/bin:" + os.environ.get("PATH", ""))
COST_BUY, COST_SELL = 7.5 / 10000.0, 12.5 / 10000.0
LIQ_MIN = 3e7
PRE_START, PRE_END = "2021-06-01", "2022-05-31"
TEST_START, TEST_END = "2022-06-01", "2026-09-11"
CAND_N = 500


def psql_csv(q):
    out = subprocess.run(["psql", "-d", "quant_investment", "-c", "copy (" + q + ") to stdout with csv header"],
                         capture_output=True, text=True, env=ENV, check=True).stdout
    df = pd.read_csv(io.StringIO(out), dtype={"symbol": str})
    df["symbol"] = df["symbol"].astype(str).str.zfill(6)   # 教训：不补零会与列名类型不一致、交易被静默跳过
    return df


def psql(q):
    return subprocess.run(["psql", "-d", "quant_investment", "-At", "-c", q],
                          capture_output=True, text=True, env=ENV, check=True).stdout.strip()


def candidate_set(n=CAND_N):
    """只用窗口开始前的数据挑候选集合（消除"用今天的池成员"这类前视偏差）。"""
    rows = psql("select symbol, avg_amount, bars from (select symbol, avg(amount) avg_amount, count(*) bars "
                "from quant.daily_klines where trade_date between '" + PRE_START + "' and '" + PRE_END + "' "
                "group by symbol having count(*) >= 220) t where avg_amount is not null "
                "order by avg_amount desc limit " + str(n))
    out = []
    for line in rows.split("\n"):
        if not line.strip():
            continue
        sym, _amt, _bars = line.split("|")
        out.append(sym.zfill(6))
    return out


def load(symbols, start):
    syms = ",".join("'" + s + "'" for s in symbols)
    df = psql_csv("select symbol, trade_date, open, close, amount from quant.daily_klines "
                  "where symbol in (" + syms + ") and trade_date >= '" + start + "' order by trade_date, symbol")
    df["trade_date"] = pd.to_datetime(df["trade_date"])
    close = df.pivot_table(index="trade_date", columns="symbol", values="close")
    open_ = df.pivot_table(index="trade_date", columns="symbol", values="open")
    amount = df.pivot_table(index="trade_date", columns="symbol", values="amount")

    # 2026-09-13 修复（w-c8cae280）：停牌/缺 K 线时 close 为 NaN，原实现按"当日无价→不计市值"
    # 处理 ⇒ 持仓在净值里凭空消失，产生假暴跌（实测某些方案假回撤 -80%~-89%）。
    # 估值必须用**前值填充后**的价格序列；成交仍用当日真实 open（无 bar 则不交易）。
    close = close.ffill()
    return close, open_, amount


def simulate(close, open_, amount, mode, topn, start, end, regime=False, stop_loss=None):
    mom60 = close / close.shift(60) - 1.0
    ma120 = close.rolling(120).mean()
    liq = amount.rolling(20).mean() > LIQ_MIN
    trend = close > ma120
    eligible = trend & liq
    dates = close.index[(close.index >= pd.Timestamp(start)) & (close.index <= pd.Timestamp(end))]
    iso = dates.isocalendar()
    weekly_last = pd.Series(dates, index=dates).groupby([iso.year.values, iso.week.values]).last().values
    rebal = [pd.Timestamp(d) for d in weekly_last]

    cash, shares, entry = 1.0, {}, {}
    equity, last_rebal, turnover = [], None, 0.0

    for i, d in enumerate(dates):
        if stop_loss is not None:
            for s in list(shares.keys()):
                px = open_.loc[d, s] if s in open_.columns else np.nan
                if pd.notna(px) and entry.get(s) and px < entry[s] * (1 + stop_loss):
                    val = shares[s] * px * (1 - COST_SELL)
                    cash += val; turnover += abs(val)
                    shares.pop(s, None); entry.pop(s, None)

        if i > 0 and dates[i - 1] in rebal and (last_rebal is None or dates[i - 1] != last_rebal):
            dec = dates[i - 1]
            last_rebal = dec
            el = eligible.loc[dec].fillna(False)
            breadth = float(el.mean())
            if mode == "fixed":
                # 真基准：一次买入候选集合全体并持有（首个调仓日建仓，此后不变）
                targets = [str(x) for x in close.columns] if last_rebal == dec and not shares else []
            elif regime and breadth < 0.4:
                targets = []
            elif mode == "hold":
                targets = [str(x) for x in el[el].index]           # 只过滤不排序
            else:
                if mode == "mom":
                    sc = mom60.loc[dec][el].dropna()
                    targets = [str(x) for x in sc.sort_values(ascending=False).head(topn).index] if len(sc) else []
                elif mode in ("rev", "rev5"):
                    # 反转：买"跌得最多"的（mom60 升序 / 5 日收益升序）
                    base = mom60 if mode == "rev" else (close / close.shift(5) - 1.0)
                    sc = base.loc[dec][el].dropna()
                    targets = [str(x) for x in sc.sort_values(ascending=True).head(topn).index] if len(sc) else []
                else:
                    targets = []
            if len(targets) > 40:
                targets = targets[:40]

            total_val = cash + sum(sh * close.loc[d, s] for s, sh in shares.items() if pd.notna(close.loc[d, s]))
            for s in list(shares.keys()):
                if s not in targets:
                    px = open_.loc[d, s] if s in open_.columns else np.nan
                    if pd.notna(px):
                        val = shares[s] * px * (1 - COST_SELL)
                        cash += val; turnover += abs(val)
                        shares.pop(s, None); entry.pop(s, None)
            w = 1.0 / len(targets) if targets else 0.0
            for s in targets:
                px = open_.loc[d, s] if s in open_.columns else np.nan
                if pd.isna(px) or px <= 0:
                    continue
                diff = total_val * w - shares.get(s, 0.0) * px
                if diff > 0:
                    cost = min(diff, cash)
                    if cost > 0:
                        shares[s] = shares.get(s, 0.0) + cost * (1 - COST_BUY) / px
                        entry[s] = px; cash -= cost; turnover += cost
        mv = sum(sh * close.loc[d, s] for s, sh in shares.items() if pd.notna(close.loc[d, s]))
        equity.append(cash + mv)
    return pd.Series(equity, index=dates), turnover


def stats(eq, turnover):
    if len(eq) < 60:
        return {"ok": False}
    yrs = (eq.index[-1] - eq.index[0]).days / 365.0
    cagr = (eq.iloc[-1] / eq.iloc[0]) ** (1 / max(yrs, .1)) - 1
    dd = float((eq / eq.cummax() - 1).min())
    dr = eq.pct_change().dropna()
    return {"cagr": round(float(cagr), 4), "max_dd": round(dd, 4),
            "sharpe": round(float(dr.mean() / dr.std() * np.sqrt(252)) if dr.std() > 0 else 0, 2),
            "turnover": round(float(turnover), 1)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default="mom", choices=["mom", "rev", "rev5", "hold", "fixed"])
    ap.add_argument("--topn", type=int, default=20)
    ap.add_argument("--regime", action="store_true")
    ap.add_argument("--stop-loss", type=float, default=None)
    ap.add_argument("--cand", type=int, default=CAND_N)
    a = ap.parse_args()

    syms = candidate_set(a.cand)
    print("候选集合（仅用 2021-06~2022-05 数据挑，%d 只，避免前视偏差）: %s …" % (len(syms), syms[:5]))
    close, open_, amount = load(syms, "2021-06-01")
    print("数据窗口 %s ~ %s，交易日 %d，标的 %d" % (close.index[0].date(), close.index[-1].date(), len(close), close.shape[1]))

    windows = {"全窗口": (TEST_START, TEST_END), "2022H2": ("2022-06-01", "2022-12-31"),
               "2023": ("2023-01-01", "2023-12-31"), "2024": ("2024-01-01", "2024-12-31"),
               "2025-26": ("2025-01-01", TEST_END)}
    for label, (s, e) in windows.items():
        eq, to = simulate(close, open_, amount, a.mode, a.topn, s, e, regime=a.regime, stop_loss=a.stop_loss)
        print("%-8s %s" % (label, stats(eq, to)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
