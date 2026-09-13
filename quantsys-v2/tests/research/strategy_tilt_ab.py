"""行业动量 tilt 的 A/B 检验（2026-09-13 w-a9ec14d7）

被测对象就是 core_plan 里真实部署的东西：**在同一个分散篮子内，按行业动量给权重乘 1.3 / 1.0 / 0.5**。
与"动量轮动策略"不同，这里 universe 与调仓频率完全相同，只有**权重**不同 —— 因此能干净地回答：
这个 tilt 到底有没有贡献？（若 A/B 无差 → tilt 是装饰品，应当中性化）

口径：同池 800 只、每月调仓；A=等权，B=按行业动量分位乘 1.3/1.0/0.5 后归一；两者都含换手成本。
"""
import io, os, subprocess
import numpy as np
import pandas as pd

ENV = dict(os.environ, PATH="/opt/homebrew/bin:/usr/local/bin:" + os.environ.get("PATH", ""))
DEF_START, DEF_END = "2024-01-01", "2024-06-30"
TEST_START = "2024-07-01"
COST_BUY, COST_SELL = 7.5 / 1e4, 12.5 / 1e4


def psql_csv(q):
    out = subprocess.run(["psql", "-d", "quant_investment", "-c", "copy (" + q + ") to stdout with csv header"],
                         capture_output=True, text=True, env=ENV, check=True).stdout
    df = pd.read_csv(io.StringIO(out), dtype={"symbol": str})
    df["symbol"] = df["symbol"].astype(str).str.zfill(6)
    return df


px = psql_csv("select symbol, avg(amount) as amt from quant.daily_klines where trade_date between '%s' and '%s' "
              "group by symbol having count(*) >= 100 order by amt desc limit 800" % (DEF_START, DEF_END))
syms = list(px["symbol"])
ind = psql_csv("select symbol, industry from quant.stocks where symbol in (" + ",".join("'" + s + "'" for s in syms) + ")")
imap = dict(zip(ind["symbol"], ind["industry"].fillna("未知")))

k = psql_csv("select symbol, trade_date, close from quant.daily_klines where symbol in (" +
             ",".join("'" + s + "'" for s in syms) + ") and trade_date >= '2024-01-01' order by trade_date")
k["trade_date"] = pd.to_datetime(k["trade_date"])
close = k.pivot_table(index="trade_date", columns="symbol", values="close").ffill()
close = close.loc[close.index >= pd.Timestamp(TEST_START)]
ret = close.pct_change()

inds = sorted(set(imap.get(s, "未知") for s in close.columns))
memb = {i: [s for s in close.columns if imap.get(s, "未知") == i] for i in inds}


def month_ends(idx):
    return sorted(set(idx.to_series().groupby([idx.year, idx.month]).apply(lambda x: x.index[-1]).values))


def run(mode, lookback=60, tilt=(1.3, 1.0, 0.5)):
    cur, prev_w = 1.0, pd.Series(dtype=float)
    port = pd.Series(1.0, index=close.index)
    cost_total = 0.0
    me = month_ends(close.index)
    for i, d in enumerate(me[:-1]):
        pos = close.index.get_indexer([d])[0]
        if pos < lookback:
            continue
        hist = ret.iloc[pos - lookback:pos]
        ir = {n: float((1 + hist[m].mean(axis=1).dropna()).prod() - 1)
              for n, m in memb.items() if len(hist[m].dropna(how="all")) >= lookback // 2}
        if len(ir) < 10:
            continue
        ranked = sorted(ir.items(), key=lambda kv: kv[1], reverse=True)
        n = len(ranked)
        mult = {}
        for j, (name, _) in enumerate(ranked):
            q = j / n
            mult[name] = tilt[0] if q < 1 / 3 else (tilt[1] if q < 2 / 3 else tilt[2])
        cols = [c for c in close.columns if c in imap]
        if mode == "equal":
            w = pd.Series(1.0, index=cols)
        else:
            w = pd.Series([mult.get(imap.get(c, "未知"), 1.0) for c in cols], index=cols)
        w = w / w.sum()
        seg = close.index[(close.index > d) & (close.index <= me[i + 1])]
        if len(seg) == 0:
            continue
        if len(prev_w):
            turn = float((w - prev_w.reindex(w.index).fillna(0)).abs().sum())
            cost_total += turn * 0.5 * (COST_BUY + COST_SELL)
        prev_w = w
        r = (ret.loc[seg, cols] * w).sum(axis=1).fillna(0)
        daily = (1 + r).cumprod()
        port.loc[seg] = cur * daily.values
        cur = float(port.loc[seg].iloc[-1])
    return port, cost_total


def st(series, name, cost=0.0):
    eq = series / series.iloc[0]
    yrs = (eq.index[-1] - eq.index[0]).days / 365.0
    dd = float((eq / eq.cummax() - 1).min())
    r = eq.pct_change().dropna()
    sh = float(r.mean() / r.std() * np.sqrt(252)) if r.std() > 0 else 0
    cagr = float(eq.iloc[-1] ** (1 / max(yrs, .1)) - 1)
    print("%-22s CAGR %+7.2f%%（费后 %+7.2f%%）  回撤 %+7.2f%%  Sharpe %5.2f  成本 %.2f%%"
          % (name, cagr * 100, (cagr - cost) * 100, dd * 100, sh, cost * 100))
    return {"cagr": cagr, "dd": dd, "sharpe": sh, "cost": cost}


print("universe %d 只 / %d 行业，窗口 %s ~ %s" % (close.shape[1], len(memb), close.index[0].date(), close.index[-1].date()))
pa, ca = run("equal")
pb, cb = run("tilt")
a = st(pa, "A) 等权（无 tilt）", ca)
b = st(pb, "B) 动量 tilt 1.3/1.0/0.5", cb)
print()
print("=== 结论 ===")
print("tilt 相对等权的超额：CAGR %+.2f pp，Sharpe %+.2f" % ((b["cagr"] - cb - (a["cagr"] - ca)) * 100, b["sharpe"] - a["sharpe"]))
print("（≈0 或负 → tilt 不贡献超额，应中性化）")
