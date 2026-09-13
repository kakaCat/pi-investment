"""行业动量轮动检验（strategy_industry_mom.py，2026-09-13 w-a9ec14d7）

为什么做这个：core_plan 里对"强动量行业 ×1.3 / 弱动量行业 ×0.5"做了加权，
但**从未验证过行业动量在本市场有没有预测力**。如果它没有，那这个加权就是装饰品，
甚至会把组合推向已经涨完的行业。这是"我建的东西到底成不成立"的直接检验。

口径（与 strategy_lab 一致，刻意保守）：
  · 每月最后交易日按"行业过去 60 交易日等权收益"排名，取前 1/5 行业，下月持有其成员股等权；
  · 对照组 = 同池等权买入持有（超额口径的基准）；
  · 成本：换月换手按单边买入 7.5bp / 卖出 12.5bp；
  · 同时给出**多空价差**（动量前 1/5 − 后 1/5）作为信号强度检验。

已知局限（诚实标注）：行业分类用 quant.stocks.industry 的**当前**归属，
回溯应用有轻微前视偏差（分类不是信号，但仍是近似）。
"""
import argparse, io, os, subprocess, sys
import numpy as np
import pandas as pd

ROOT = "/Users/yunpeng/pi-investment/quantsys-v2"
ENV = dict(os.environ, PATH="/opt/homebrew/bin:/usr/local/bin:" + os.environ.get("PATH", ""))
DEF_START, DEF_END = "2024-01-01", "2024-06-30"
TEST_START, TEST_END = "2024-07-01", "2026-09-11"
COST_BUY, COST_SELL = 7.5 / 1e4, 12.5 / 1e4


def psql_csv(q):
    out = subprocess.run(["psql", "-d", "quant_investment", "-c", "copy (" + q + ") to stdout with csv header"],
                         capture_output=True, text=True, env=ENV, check=True).stdout
    df = pd.read_csv(io.StringIO(out), dtype={"symbol": str})
    df["symbol"] = df["symbol"].astype(str).str.zfill(6)
    return df


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lookback", type=int, default=60)
    ap.add_argument("--top-frac", type=float, default=0.2)
    ap.add_argument("--cand", type=int, default=800)
    a = ap.parse_args()

    px = psql_csv("select symbol, avg(amount) as amt from quant.daily_klines "
                  "where trade_date between '" + DEF_START + "' and '" + DEF_END + "' group by symbol "
                  "having count(*) >= 100 order by amt desc limit %d" % a.cand)
    syms = list(px["symbol"])
    ind = psql_csv("select symbol, industry from quant.stocks where symbol in (" +
                   ",".join("'" + s + "'" for s in syms) + ")")
    ind["industry"] = ind["industry"].fillna("未知")
    imap = dict(zip(ind["symbol"], ind["industry"]))

    k = psql_csv("select symbol, trade_date, close from quant.daily_klines where symbol in (" +
                 ",".join("'" + s + "'" for s in syms) + ") and trade_date >= '2024-01-01' order by trade_date")
    k["trade_date"] = pd.to_datetime(k["trade_date"])
    close = k.pivot_table(index="trade_date", columns="symbol", values="close")
    close = close.ffill().loc[close.index >= pd.Timestamp(TEST_START)]
    ret = close.pct_change()
    print("universe %d 只，窗口 %s ~ %s（%d 交易日）" % (close.shape[1], close.index[0].date(), close.index[-1].date(), len(close)))

    # 基准：同池等权买入持有
    bench = (1 + ret.mean(axis=1).fillna(0)).cumprod()

    # 行业归属矩阵
    inds = sorted(set(imap.get(s, "未知") for s in close.columns))
    memb = {i: [s for s in close.columns if imap.get(s, "未知") == i] for i in inds}
    memb = {i: v for i, v in memb.items() if len(v) >= 1}
    print("行业数 %d（中位成员 %d 只）" % (len(memb), int(np.median([len(v) for v in memb.values()]))))

    rebal = close.resample("ME").last().index
    rebal = [d for d in rebal if d in close.index or True]
    # 用每月最后一个交易日
    month_last = close.groupby([close.index.year, close.index.month]).apply(lambda x: x.index[-1])
    month_last = sorted(set(month_last.values))

    port = pd.Series(1.0, index=close.index)
    bench_aligned = bench.copy()
    prev_top, prev_bot = set(), set()
    cur = 1.0  # 复利净值游标（见下方修 bug 注释）
    top_rets, bot_rets = [], []
    turnover = 0.0
    for i, d in enumerate(month_last[:-1]):
        pos = close.index.get_indexer([d])[0]
        if pos < a.lookback:
            continue
        hist = ret.iloc[pos - a.lookback:pos]
        ir = {}
        for name, mem in memb.items():
            r = hist[mem].mean(axis=1).dropna()
            if len(r) >= a.lookback // 2:
                ir[name] = float((1 + r).prod() - 1)
        if len(ir) < 10:
            continue
        ranked = sorted(ir.items(), key=lambda kv: kv[1], reverse=True)
        ntop = max(1, int(len(ranked) * a.top_frac))
        top = set(sum([memb[n] for n, _ in ranked[:ntop]], []))
        bot = set(sum([memb[n] for n, _ in ranked[-ntop:]], []))
        nxt = month_last[i + 1]
        seg = close.index[(close.index > d) & (close.index <= nxt)]
        if len(seg) == 0:
            continue
        # 换手成本：进出各按一半计（保守）
        turnover += len(top - prev_top) / max(len(top), 1) + len(prev_top - top) / max(len(prev_top), 1)
        prev_top, prev_bot = top, bot
        r_top = ret.loc[seg, sorted(top)].mean(axis=1).fillna(0)
        r_bot = ret.loc[seg, sorted(bot)].mean(axis=1).fillna(0)
        # 2026-09-13 修 bug：原写成 port.loc[seg] = port.loc[seg] * (1+r)，
        # 而 port 在这些日期上从未被写过（恒为 1.0）→ 每月覆盖而非复利，权益曲线成锯齿，结论完全无效。
        # 正确做法：把当月日收益累乘后，接到上月末的净值上。
        daily = (1 + r_top).cumprod()
        port.loc[seg] = cur * daily.values
        cur = float(port.loc[seg].iloc[-1])
        top_rets.append(float(daily.iloc[-1] - 1))
        bot_rets.append(float((1 + r_bot).prod() - 1))

    # 成本折算：按换手次数 × 单边成本
    cost = turnover * 0.5 * (COST_BUY + COST_SELL)
    port_final = port.iloc[-1] * (1 - cost)

    def st(series, name):
        eq = series / series.iloc[0]
        yrs = (eq.index[-1] - eq.index[0]).days / 365.0
        dd = float((eq / eq.cummax() - 1).min())
        r = eq.pct_change().dropna()
        sharpe = float(r.mean() / r.std() * np.sqrt(252)) if r.std() > 0 else 0
        cagr = float(eq.iloc[-1] ** (1 / max(yrs, .1)) - 1)
        print("%-26s CAGR %+7.2f%%  最大回撤 %+7.2f%%  Sharpe %5.2f" % (name, cagr * 100, dd * 100, sharpe))
        return {"cagr": round(cagr, 4), "dd": round(dd, 4), "sharpe": round(sharpe, 2)}

    b = st(bench_aligned, "同池等权（基准）")
    p = st(port, "行业动量 top%.0f%%（费前）" % (a.top_frac * 100))
    print("累计换手 %.1fx，成本折算 %.2f%% → 费后 CAGR %+.2f%%" % (turnover, cost * 100, (p["cagr"] - cost) * 100))
    excess = round(p["cagr"] - cost - b["cagr"], 4)
    print()
    print("=== 结论 ===")
    print("超额 CAGR（费后）: %+.2f%%  超额 Sharpe: %+.2f" % (excess * 100, p["sharpe"] - b["sharpe"]))
    print("多空价差（月均，top − bottom）: %+.2f%%（正=动量有效，≈0或负=无预测力）"
          % (np.mean(np.array(top_rets) - np.array(bot_rets)) * 100))
    print("月度胜率 top: %.1f%% | bottom: %.1f%%" % (
        100 * np.mean(np.array(top_rets) > 0), 100 * np.mean(np.array(bot_rets) > 0)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
