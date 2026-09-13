"""等权 core + 风控叠层（strategy_core.py，2026-09-13 w-c8cae280）

证据结论（今日）：所有"选择型叠层"（动量/反转/ROE/估值）在覆盖完整窗口上超额均为负；
而**等权持有流动性宽基**（800 只，2024H1 定义）CAGR +23.3%、Sharpe 0.91、DD -22.4%。
⇒ 不再找选股 alpha，改为研究**风控型叠层**：不动成分，只调"总暴露"，目标是同收益、更小回撤。

叠层：
  A. 波动率目标化：w_t = min(1, target_vol / 近 20 日已实现波动)，月度调整，带成本；
  B. 回撤闸门：core 自身回撤 > 10% → 暴露减半；回撤回到 < 5% → 恢复满仓；
  C. A+B 叠加。

用法：python scripts/strategy_core.py [--target-vol 0.15] [--cand 800]
"""
import argparse, os, subprocess, sys
import numpy as np
import pandas as pd
import io

ENV = dict(os.environ, PATH="/opt/homebrew/bin:/usr/local/bin:" + os.environ.get("PATH", ""))
COST = 7.5 / 10000.0
DEF_START, DEF_END = "2024-01-01", "2024-06-30"
TEST_START, TEST_END = "2024-07-01", "2026-09-11"


def psql(q):
    return subprocess.run(["psql", "-d", "quant_investment", "-At", "-c", q],
                          capture_output=True, text=True, env=ENV, check=True).stdout


def psql_csv(q):
    out = subprocess.run(["psql", "-d", "quant_investment", "-c", "copy (" + q + ") to stdout with csv header"],
                         capture_output=True, text=True, env=ENV, check=True).stdout
    df = pd.read_csv(io.StringIO(out), dtype={"symbol": str})
    df["symbol"] = df["symbol"].astype(str).str.zfill(6)
    return df


def core_returns(cand=800, min_bars=100):
    syms = [s.strip().zfill(6) for s in psql(
        "select symbol from (select symbol, avg(amount) a, count(*) c from quant.daily_klines "
        "where trade_date between '" + DEF_START + "' and '" + DEF_END + "' group by symbol having count(*) >= "
        + str(min_bars) + ") t where a is not null order by a desc limit " + str(cand)).split() if s.strip()]
    print("core 候选集合: %d 只（%s~%s 定义）" % (len(syms), DEF_START, DEF_END))
    df = psql_csv("select symbol, trade_date, close from quant.daily_klines where symbol in ("
                  + ",".join("'" + s + "'" for s in syms) + ") and trade_date >= '2024-06-01' order by trade_date")
    df["trade_date"] = pd.to_datetime(df["trade_date"])
    close = df.pivot_table(index="trade_date", columns="symbol", values="close").ffill()
    rets = close.pct_change()
    core = rets.mean(axis=1).dropna()          # 等权日收益（每日再平衡近似；成本极低）
    return core


def stats(r, name, turnover=0.0):
    eq = (1 + r).cumprod()
    yrs = (eq.index[-1] - eq.index[0]).days / 365.0
    dd = float((eq / eq.cummax() - 1).min())
    sharpe = float(r.mean() / r.std() * np.sqrt(252)) if r.std() > 0 else 0
    cagr = float(eq.iloc[-1] ** (1 / max(yrs, .1)) - 1)
    print("%-22s CAGR %+7.2f%%  最大回撤 %+7.2f%%  Sharpe %5.2f  年换手 %.1fx"
          % (name, cagr * 100, dd * 100, sharpe, turnover))
    return {"cagr": round(cagr, 4), "dd": round(dd, 4), "sharpe": round(sharpe, 2)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target-vol", type=float, default=0.15)
    ap.add_argument("--cand", type=int, default=800)
    ap.add_argument("--dd-trigger", type=float, default=0.10)
    ap.add_argument("--dd-restore", type=float, default=0.05)
    a = ap.parse_args()

    core_all = core_returns(a.cand)
    core = core_all[(core_all.index >= pd.Timestamp(TEST_START)) & (core_all.index <= pd.Timestamp(TEST_END))]
    print("窗口 %s ~ %s，交易日 %d" % (core.index[0].date(), core.index[-1].date(), len(core)))
    print()
    stats(core, "0) 等权 core（基线）")

    # A. 波动率目标化（月度调整暴露）
    vol20 = core_all.rolling(20).std() * np.sqrt(252)
    month = (core.index.year * 100 + core.index.month)
    w = pd.Series(1.0, index=core.index)
    cur = 1.0
    cost_a = 0.0
    prev_key = None
    for d in core.index:
        k = (d.year, d.month)
        if k != prev_key:
            v = vol20.get(d, np.nan)
            if pd.notna(v) and v > 0:
                new = float(min(1.0, a.target_vol / v))
                cost_a += abs(new - cur) * COST
                cur = new
            prev_key = k
        w[d] = cur
    stats(core * w - core * 0.0, "A) 波动目标 %.0f%%" % (a.target_vol * 100), turnover=cost_a * 100)

    # B. 回撤闸门
    eq = (1 + core).cumprod()
    dd = eq / eq.cummax() - 1
    expo = pd.Series(1.0, index=core.index)
    cur, cost_b = 1.0, 0.0
    for d in core.index:
        if cur == 1.0 and dd[d] < -a.dd_trigger:
            cost_b += abs(0.5 - cur) * COST; cur = 0.5
        elif cur == 0.5 and dd[d] > -a.dd_restore:
            cost_b += abs(1.0 - cur) * COST; cur = 1.0
        expo[d] = cur
    stats(core * expo, "B) 回撤闸门", turnover=cost_b * 100)

    # C. A+B
    stats(core * w * expo, "C) 波动目标+回撤闸门", turnover=(cost_a + cost_b) * 100)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
