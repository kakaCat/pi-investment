"""安慰剂中心性诊断（2026-09-13 w-a9ec14d7）

事件研究 v2 的安慰剂（同批标的 + 随机交易日）本该中心在 0，实测却是 +5%/20 日。
本脚本只回答一个问题：这 5% 偏在哪一条腿上。
"""
import io, os, subprocess
import numpy as np
import pandas as pd

ENV = dict(os.environ, PATH="/opt/homebrew/bin:/usr/local/bin:" + os.environ.get("PATH", ""))


def csv(sql):
    out = subprocess.run(["psql", "-d", "quant_investment", "-c", "copy (" + sql + ") to stdout with csv header"],
                         capture_output=True, text=True, env=ENV, check=True).stdout
    return pd.read_csv(io.StringIO(out), dtype={"symbol": str})


START, END = "2026-01-01", "2026-09-11"
sym = csv("select distinct symbol from quant.event_calendar where symbol is not null "
          "and event_date between '" + START + "' and '" + END + "'")
syms = sorted(sym.symbol.str.zfill(6).unique())
k = csv("select symbol, trade_date, open, close from quant.daily_klines "
        "where trade_date between '" + START + "' and '" + END + "' and symbol in (%s) order by symbol, trade_date"
        % ",".join("'" + s + "'" for s in syms))
k["trade_date"] = pd.to_datetime(k["trade_date"])
close = k.pivot_table(index="trade_date", columns="symbol", values="close").ffill()
opn = k.pivot_table(index="trade_date", columns="symbol", values="open")
N = len(close)
print("面板 %d 日 x %d 只" % close.shape)
print("K线原始采样：%d 只 x %d 日 = %d 行（pivot 后 %d x %d）"
      % (k.symbol.nunique(), k.trade_date.nunique(), len(k), close.shape[0], close.shape[1]))

# 1) 每天有多少只真的有 K 线（未被 ffill 顶替）
real = k.groupby("trade_date")["symbol"].nunique()
print()
print("每日真实有 K 线的标的数：min=%d  median=%d  max=%d" % (real.min(), int(real.median()), real.max()))

# 2) 市场基准：两种口径对比
cc = close.pct_change()
cc_mean = cc.mean(axis=1).fillna(0)
mkt_total_reb = (1 + cc_mean).prod() - 1
oc_mean = (close / opn - 1.0).mean(axis=1).fillna(0)

# 3) 全体个股的"买入持有"平均收益（同等权、同区间，但不日度再平衡）
first, last = 5, N - 1
bh = (close.iloc[last] / opn.iloc[first + 1] - 1.0).dropna()
print()
print("区间 pos %d -> %d（%s -> %s）" % (first, last, close.index[first].date(), close.index[last].date()))
print("  等权日度再平衡市场收益(复利) : %+.2f%%" % (mkt_total_reb * 100))
print("  全体个股买入持有平均收益      : %+.2f%%  (n=%d)" % (bh.mean() * 100, len(bh)))
print("  全体个股买入持有中位          : %+.2f%%" % (bh.median() * 100))
print("  两者之差(应接近 0，正=市场基准偏高/个股偏低) : %+.2f pp"
      % ((mkt_total_reb - bh.mean()) * 100))

# 4) 随机配对：个股 vs 市场，20 日，看两条腿各自多大
rng = np.random.default_rng(7)
colnames = list(close.columns)
CLOSE = close.to_numpy(dtype=float).T   # (n_symbols, n_days)
OPEN = opn.to_numpy(dtype=float).T
pos_of = {c: i for i, c in enumerate(colnames)}
cum = np.concatenate([[1.0], np.cumprod(1.0 + cc_mean.to_numpy(dtype=float))])
mkt_oc = oc_mean.to_numpy(dtype=float)

S, M, D = [], [], []
for _ in range(4000):
    ci = rng.integers(0, len(colnames))
    i1 = int(rng.integers(6, N - 21))
    j = i1 + 20 - 1
    e = OPEN[ci, i1]
    if not np.isfinite(e) or e <= 0 or not np.isfinite(CLOSE[ci, j]):
        continue
    s = CLOSE[ci, j] / e - 1
    m = (1 + mkt_oc[i1]) * (cum[j + 1] / cum[i1 + 1]) - 1
    S.append(s); M.append(m); D.append(s - m)
S, M, D = np.array(S), np.array(M), np.array(D)
print()
print("随机 (标的, 起始日) 配对 n=%d，20 日：", len(S))
print("  个股 open->close 平均        : %+.3f%%" % (S.mean() * 100))
print("  市场 open->close 平均        : %+.3f%%" % (M.mean() * 100))
print("  个股 − 市场 (即安慰剂应有值) : %+.3f%%   <- 这就是那个 +5%% 的来源" % (D.mean() * 100))
print("  个股中位 %+.3f%% | 市场中位 %+.3f%%" % (np.median(S) * 100, np.median(M) * 100))