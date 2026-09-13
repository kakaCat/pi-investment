"""基本面/资金面截面因子检验（strategy_fund.py，2026-09-13 w-c8cae280）

背景：三轮证据已证伪价格类信号（单标的择时、截面动量、截面反转）。本脚本检验另一大类：
基本面（ROE / 盈利收益率 / 负债率）与资金面（主力净流入率）。

时点纪律（关键）：
  · 财务数据按 **报告期 + 90 天** 作为"可获得日"（保守，避免用未公布的报表）；
  · 价格按 T 日信号 → T+1 开盘成交；月频调仓降低换手；
  · 成本买 7.5bp / 卖 12.5bp。

用法：
  python scripts/strategy_fund.py --factor roe|ey|debt|flow --topn 20 [--universe fin|all] [--start ...] [--end ...]
"""
import argparse, io, os, subprocess, sys
import numpy as np
import pandas as pd

ENV = dict(os.environ, PATH="/opt/homebrew/bin:/usr/local/bin:" + os.environ.get("PATH", ""))
COST_BUY, COST_SELL = 7.5 / 10000.0, 12.5 / 10000.0


def psql_csv(q):
    out = subprocess.run(["psql", "-d", "quant_investment", "-c", "copy (" + q + ") to stdout with csv header"],
                         capture_output=True, text=True, env=ENV, check=True).stdout
    df = pd.read_csv(io.StringIO(out), dtype={"symbol": str})
    df["symbol"] = df["symbol"].astype(str).str.zfill(6)
    return df


def load_fin():
    df = psql_csv("select symbol, report_date, net_profit_parent, total_equity, eps, debt_ratio, gross_margin, revenue "
                  "from quant.v_key_financial_indicators where report_date >= '2021-01-01'")
    df["report_date"] = pd.to_datetime(df["report_date"])
    df["avail_date"] = df["report_date"] + pd.Timedelta(days=90)      # 保守的可获得日
    df["roe_calc"] = np.where(df["total_equity"].notna() & (df["total_equity"] != 0),
                              df["net_profit_parent"] / df["total_equity"] * 100.0, np.nan)
    return df.dropna(subset=["avail_date"]).sort_values("avail_date")


def load_px(symbols, start):
    syms = ",".join("'" + s + "'" for s in symbols)
    df = psql_csv("select symbol, trade_date, open, close, amount from quant.daily_klines "
                  "where symbol in (" + syms + ") and trade_date >= '" + start + "' order by trade_date, symbol")
    df["trade_date"] = pd.to_datetime(df["trade_date"])
    close = df.pivot_table(index="trade_date", columns="symbol", values="close").ffill()

    # 2026-09-13 修复（w-c8cae280）：停牌/缺 K 线时 close 为 NaN，原实现按"当日无价→不计市值"
    # 处理 ⇒ 持仓在净值里凭空消失，产生假暴跌（实测某些方案假回撤 -80%~-89%）。
    # 估值必须用**前值填充后**的价格序列；成交仍用当日真实 open（无 bar 则不交易）。
    open_ = df.pivot_table(index="trade_date", columns="symbol", values="open")
    amount = df.pivot_table(index="trade_date", columns="symbol", values="amount")
    return close, open_, amount


def load_flow(symbols, start):
    syms = ",".join("'" + s + "'" for s in symbols)
    df = psql_csv("select symbol, trade_date, main_net_inflow_rate from quant.stock_fund_flow "
                  "where symbol in (" + syms + ") and trade_date >= '" + start + "' order by trade_date, symbol")
    df["trade_date"] = pd.to_datetime(df["trade_date"])
    return df.pivot_table(index="trade_date", columns="symbol", values="main_net_inflow_rate")


def factor_panel(fin, close, flow, factor):
    """每个调仓日按"当日已可获得"的报表构造因子面板（无未来信息）。"""
    out = {}
    if factor in ("roe", "ey", "debt"):
        for d in close.index:
            sub = fin[fin["avail_date"] <= d]
            if sub.empty:
                continue
            latest = sub.sort_values("avail_date").groupby("symbol").tail(1).set_index("symbol")
            if factor == "roe":
                out[d] = latest["roe_calc"].reindex(close.columns)
            elif factor == "ey":
                out[d] = (latest["eps"].reindex(close.columns) / close.loc[d]).replace([np.inf, -np.inf], np.nan)
            else:
                out[d] = -latest["debt_ratio"].reindex(close.columns)      # 负债率越低越好
    else:
        f20 = flow.rolling(20).mean()
        for d in close.index:
            if d in f20.index:
                out[d] = f20.loc[d].reindex(close.columns)
    return pd.DataFrame(out).T


def simulate(close, open_, amount, panel, topn, start, end, liq_min=2e7, monthly=True):
    liq = amount.rolling(20).mean() > liq_min
    trend = close > close.rolling(120).mean()
    dates = close.index[(close.index >= pd.Timestamp(start)) & (close.index <= pd.Timestamp(end))]
    if monthly:
        key = [dates.year, dates.month]
    else:
        key = [dates.isocalendar().year.values, dates.isocalendar().week.values]
    rebal = pd.Series(dates, index=dates).groupby(key).last().values

    cash, shares, entry = 1.0, {}, {}
    equity, last_rebal, turnover = [], None, 0.0
    for i, d in enumerate(dates):
        if i > 0 and dates[i - 1] in rebal and (last_rebal is None or dates[i - 1] != last_rebal):
            dec = dates[i - 1]
            last_rebal = dec
            if dec in panel.index:
                sc = panel.loc[dec]
                el = (liq.loc[dec] if dec in liq.index else False) & (trend.loc[dec] if dec in trend.index else False)
                sc = sc[el.reindex(sc.index, fill_value=False)].dropna()
                sc = sc[np.isfinite(sc)]
                targets = [str(x) for x in sc.sort_values(ascending=False).head(topn).index] if len(sc) else []
            else:
                targets = []
            total_val = cash + sum(sh * close.loc[d, s] for s, sh in shares.items() if pd.notna(close.loc[d, s]))
            for s in list(shares.keys()):
                if s not in targets:
                    px = open_.loc[d, s] if s in open_.columns else np.nan
                    if pd.notna(px):
                        val = shares[s] * px * (1 - COST_SELL); cash += val; turnover += abs(val)
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
    if len(eq) < 40:
        return {"ok": False}
    yrs = (eq.index[-1] - eq.index[0]).days / 365.0
    cagr = (eq.iloc[-1] / eq.iloc[0]) ** (1 / max(yrs, .1)) - 1
    dd = float((eq / eq.cummax() - 1).min())
    dr = eq.pct_change().dropna()
    return {"cagr": round(float(cagr), 4), "max_dd": round(dd, 4),
            "sharpe": round(float(dr.mean() / dr.std() * np.sqrt(252)) if dr.std() > 0 else 0, 2),
            "turnover": round(float(turnover), 1)}



def bench_eq(close, start, end):
    """基准：同池等权买入持有（窗口首日建仓、此后不动）。用于分离 alpha 与 beta。"""
    sub = close[(close.index >= pd.Timestamp(start)) & (close.index <= pd.Timestamp(end))].ffill()
    sub = sub.dropna(axis=1, how="all")
    base = sub.apply(lambda col: col.dropna().iloc[0] if col.notna().any() else np.nan)
    rel = sub.divide(base, axis=1).mean(axis=1)
    return rel.dropna()


def bench_stats(close, start, end):
    eq = bench_eq(close, start, end)
    if len(eq) < 20:
        return {}
    yrs = (eq.index[-1] - eq.index[0]).days / 365.0
    dd = float((eq / eq.cummax() - 1).min())
    dr = eq.pct_change().dropna()
    return {"cagr": round(float((eq.iloc[-1] / eq.iloc[0]) ** (1 / max(yrs, .1)) - 1), 4),
            "max_dd": round(dd, 4),
            "sharpe": round(float(dr.mean() / dr.std() * np.sqrt(252)) if dr.std() > 0 else 0, 2)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--factor", default="roe", choices=["roe", "ey", "debt", "flow"])
    ap.add_argument("--topn", type=int, default=20)
    ap.add_argument("--start", default="2023-01-01")
    ap.add_argument("--end", default="2026-09-11")
    ap.add_argument("--flow-start", default="2025-12-15")
    ap.add_argument("--monthly", action="store_true", default=True)
    a = ap.parse_args()

    if a.factor == "flow":
        syms = [s.strip() for s in subprocess.run(
            ["psql", "-d", "quant_investment", "-At", "-c",
             "select symbol from quant.stock_fund_flow where trade_date = '2026-09-11'"],
            capture_output=True, text=True, env=ENV, check=True).stdout.split() if s.strip()]
        flow = load_flow(syms, a.flow_start)
        close, open_, amount = load_px(list(flow.columns), a.flow_start)
        panel = factor_panel(None, close, flow, "flow")
        print("资金面 universe=%d 只，窗口 %s ~ %s" % (close.shape[1], close.index[0].date(), close.index[-1].date()))
        for lbl, (s, e) in {"全窗口": (a.flow_start, a.end)}.items():
            eq, to = simulate(close, open_, amount, panel, a.topn, s, e, monthly=False)
            st = stats(eq, to)
            bs = bench_stats(close, s, e)
            ex = (round(st.get("cagr", 0) - bs.get("cagr", 0), 4) if bs else None)
            print("%-8s %s | 基准等权 %s | **超额 %s**" % (lbl, st, bs, ex))
        return 0

    fin = load_fin()
    syms = sorted(fin["symbol"].unique())
    close, open_, amount = load_px(syms, "2021-06-01")
    panel = factor_panel(fin, close, None, a.factor)
    print("基本面 universe=%d 只（有财务数据且价格充足），因子=%s，窗口 %s ~ %s"
          % (close.shape[1], a.factor, close.index[0].date(), close.index[-1].date()))
    for lbl, (s, e) in {"全窗口": (a.start, a.end), "2023": ("2023-01-01", "2023-12-31"),
                        "2024": ("2024-01-01", "2024-12-31"), "2025-26": ("2025-01-01", a.end)}.items():
        eq, to = simulate(close, open_, amount, panel, a.topn, s, e, monthly=a.monthly)
        st = stats(eq, to)
        bs = bench_stats(close, s, e)
        ex = round(st.get("cagr", 0) - bs.get("cagr", 0), 4) if bs else None
        print("%-8s %s | 基准等权 %s | **超额 %s**" % (lbl, st, bs, ex))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
