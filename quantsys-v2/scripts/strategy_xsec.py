"""横截面选股研究（strategy_xsec.py，2026-09-13 w-c8cae280）

为什么换到截面：第一轮证明单标的择时在 A 股（尤其大盘股）是负期望，且交易成本吃掉全部边际。
A 股的 alpha 更多来自"在一堆票里挑相对强的"，即截面选股。

口径（与 strategy_lab 一致地保守）：
  · 调仓：每周最后一个交易日计算因子 → **次日开盘成交**（不用调仓日收盘，避免未来函数）；
  · 成本：买入 7.5bp、卖出 12.5bp（佣金+印花+滑点）；
  · 持仓：等权 TopN；无杠杆；不足 N 只时持有能持有的；
  · 过滤：长期趋势（close > MA120）、流动性（20 日均成交额 ≥ 阈值）；
  · 组合净值按日 mark-to-market，含现金。

用法：
  python scripts/strategy_xsec.py --mode A|B|C --universe pool|control --topn 10 --start 2022-06-01
"""
import argparse, io, os, subprocess, sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
ENV = dict(os.environ, PATH="/opt/homebrew/bin:/usr/local/bin:" + os.environ.get("PATH", ""))

COST_BUY = 7.5 / 10000.0
COST_SELL = 12.5 / 10000.0
LIQ_MIN = 5e7


def psql_csv(q):
    out = subprocess.run(["psql", "-d", "quant_investment", "-c", "copy (" + q + ") to stdout with csv header"],
                         capture_output=True, text=True, env=ENV, check=True).stdout
    df = pd.read_csv(io.StringIO(out), dtype={"symbol": str})
    # 2026-09-13 教训：pandas 会把 "000858" 推断成整数 858 → 与价格矩阵的列名类型不一致 →
    # 交易被静默跳过（回测看起来"没有交易"，实为代码 bug）。必须按字符串读 + 补足 6 位。
    df["symbol"] = df["symbol"].astype(str).str.zfill(6)
    return df


def universes():
    q = "select jsonb_array_elements(members)->>'symbol' as symbol from quant.stock_pools where id=35"
    pool = [s.strip() for s in subprocess.run(["psql", "-d", "quant_investment", "-At", "-c", q],
                                              capture_output=True, text=True, env=ENV, check=True).stdout.split() if s.strip()]
    ctrl = [s.strip() for s in subprocess.run(
        ["psql", "-d", "quant_investment", "-At", "-c",
         "select symbol from quant.daily_klines where trade_date >= '2023-01-01' group by 1 having count(*) > 600 order by symbol limit 120"],
        capture_output=True, text=True, env=ENV, check=True).stdout.split() if s.strip()]
    return {"pool": pool, "control": ctrl}


def load(start, symbols):
    syms = ",".join("'" + s + "'" for s in symbols)
    df = psql_csv("select symbol, trade_date, open, close, amount from quant.daily_klines "
                  "where symbol in (" + syms + ") and trade_date >= '" + start + "' order by trade_date, symbol")
    df["trade_date"] = pd.to_datetime(df["trade_date"])
    close = df.pivot_table(index="trade_date", columns="symbol", values="close")
    open_ = df.pivot_table(index="trade_date", columns="symbol", values="open")
    amount = df.pivot_table(index="trade_date", columns="symbol", values="amount")
    return close, open_, amount


def factors(close, amount):
    mom60 = close / close.shift(60) - 1.0
    mom20 = close / close.shift(20) - 1.0
    ret5 = close / close.shift(5) - 1.0
    vol20 = close.pct_change().rolling(20).std()
    ma120 = close.rolling(120).mean()
    trend = close > ma120
    liq = amount.rolling(20).mean() > LIQ_MIN
    return {"mom60": mom60, "mom20": mom20, "ret5": ret5, "vol20": vol20, "trend": trend, "liq": liq}


def zscore(s):
    s = s.astype(float)
    if s.notna().sum() < 5:
        return s * 0
    return (s - s.mean()) / (s.std() if s.std() > 0 else 1.0)


def score_panel(mode, f):
    if mode == "A":
        return f["mom60"]
    if mode == "B":
        return f["mom60"] / f["vol20"].replace(0, np.nan)
    if mode == "C":
        return zscore(f["mom60"]) - zscore(f["vol20"]) + 0.3 * zscore(f["ret5"])
    if mode == "D":
        return f["mom60"]
    raise SystemExit("unknown mode")


def simulate(close, open_, amount, mode, topn, rebal_weeks, start, end, regime=False, stop_loss=None):
    """周频截面调仓：决策日收盘算因子 → 次日开盘成交；含成本；可选 regime 闸门与个股硬止损。"""
    f = factors(close, amount)
    score = score_panel(mode, f)
    dates = close.index[(close.index >= pd.Timestamp(start)) & (close.index <= pd.Timestamp(end))]
    iso = dates.isocalendar()
    weekly_last = pd.Series(dates, index=dates).groupby([iso.year.values, iso.week.values]).last().values
    rebal = [pd.Timestamp(d) for d in weekly_last][::rebal_weeks]

    cash = 1.0
    shares, entry = {}, {}
    equity, last_rebal, turnover_notional = [], None, 0.0

    _hits = 0
    for i, d in enumerate(dates):
        # 0) 个股硬止损（当日开盘跌破入场价 stop_loss 即离场）
        if stop_loss is not None:
            for s in list(shares.keys()):
                px = open_.loc[d, s] if s in open_.columns else np.nan
                if pd.notna(px) and entry.get(s) and px < entry[s] * (1 + stop_loss):
                    val = shares[s] * px * (1 - COST_SELL)
                    cash += val
                    turnover_notional += abs(val)
                    shares.pop(s, None); entry.pop(s, None)

        # 1) 执行上一决策日的目标（当日开盘）
        if i > 0 and dates[i - 1] in rebal and (last_rebal is None or dates[i - 1] != last_rebal):
            dec = dates[i - 1]
            last_rebal = dec
            breadth = float(f["trend"].loc[dec].mean())
            if regime and breadth < 0.4:
                targets = []
            else:
                elig = f["trend"].loc[dec] & f["liq"].loc[dec]
                sc = score.loc[dec][elig.reindex(score.columns, fill_value=False)].dropna()
                targets = [str(x) for x in sc.sort_values(ascending=False).head(topn).index] if len(sc) else []

            total_val = cash + sum(sh * close.loc[d, s] for s, sh in shares.items() if pd.notna(close.loc[d, s]))
            w = 1.0 / len(targets) if targets else 0.0
            for s in list(shares.keys()):                      # 卖出不在目标里的
                if s not in targets:
                    px = open_.loc[d, s] if s in open_.columns else np.nan
                    if pd.notna(px):
                        val = shares[s] * px * (1 - COST_SELL)
                        cash += val
                        turnover_notional += abs(val)
                        shares.pop(s, None); entry.pop(s, None)
            for s in targets:                                   # 买入/调平
                px = open_.loc[d, s] if s in open_.columns else np.nan
                if pd.isna(px) or px <= 0:
                    continue
                cur_val = shares.get(s, 0.0) * px
                diff = total_val * w - cur_val
                if diff > 0:
                    cost = min(diff, cash)
                    if cost > 0:
                        shares[s] = shares.get(s, 0.0) + cost * (1 - COST_BUY) / px
                        entry[s] = px
                        cash -= cost
                        turnover_notional += cost
                elif diff < 0:
                    sell_val = min(-diff, cur_val)
                    shares[s] = shares.get(s, 0.0) - sell_val / px
                    cash += sell_val * (1 - COST_SELL)
                    turnover_notional += sell_val

        # 2) 收盘估值
        mv = sum(sh * close.loc[d, s] for s, sh in shares.items() if pd.notna(close.loc[d, s]))
        equity.append(cash + mv)

    return pd.Series(equity, index=dates), turnover_notional


def metrics(eq, turnover, years):
    if len(eq) < 60:
        return {"ok": False}
    cagr = (eq.iloc[-1] / eq.iloc[0]) ** (1.0 / max(years, 0.1)) - 1.0
    dd = float((eq / eq.cummax() - 1.0).min())
    dr = eq.pct_change().dropna()
    sharpe = float(dr.mean() / dr.std() * np.sqrt(252)) if dr.std() > 0 else 0.0
    return {"ok": True, "cagr": round(float(cagr), 4), "max_dd": round(dd, 4),
            "sharpe": round(sharpe, 2), "turnover_x": round(float(turnover), 1)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default="A")
    ap.add_argument("--universe", default="pool")
    ap.add_argument("--topn", type=int, default=10)
    ap.add_argument("--rebal-weeks", type=int, default=1)
    ap.add_argument("--start", default="2022-06-01")
    ap.add_argument("--end", default="2026-09-11")
    ap.add_argument("--regime", action="store_true")
    ap.add_argument("--stop-loss", type=float, default=None)
    a = ap.parse_args()

    syms = universes()[a.universe]
    close, open_, amount = load("2021-06-01", syms)
    print("universe=%s(%d 只) 数据窗口 %s ~ %s，交易日 %d" % (a.universe, close.shape[1], close.index[0].date(), close.index[-1].date(), len(close)))
    for label, (s, e) in {"全窗口": (a.start, a.end), "2023": ("2023-01-01", "2023-12-31"),
                          "2024": ("2024-01-01", "2024-12-31"), "2025-26": ("2025-01-01", a.end)}.items():
        eq, to = simulate(close, open_, amount, a.mode, a.topn, a.rebal_weeks, s, e, regime=a.regime, stop_loss=a.stop_loss)
        years = (eq.index[-1] - eq.index[0]).days / 365.0
        m = metrics(eq, to, years)
        print("%-8s %s" % (label, m))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
