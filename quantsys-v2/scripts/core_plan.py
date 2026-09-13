"""投资脑 core 建仓计划（core_plan.py，2026-09-13 w-c8cae280）——**只出计划，不自动下单**

依据（当日研究结论）：选股型叠层全部负超额；**等权 core + 波动目标 + 回撤闸门**稳健
（2024-07~2026-09：Sharpe 0.98→1.22、回撤 -17.9%→-10.6%，9 组参数/3 种池子规模一致）。

本脚本产出：
  1. 目标暴露 = min(regime 上限, 波动目标暴露 × 回撤闸门系数)，并给出各因子明细；
  2. 目标持仓 = 流动性 Top 且价格可负担的 N 只等权（A股 100 股整数倍约束下可落地）；
  3. 与当前持仓的差额（需要买/卖多少股）；
  4. 写入 quantsys-v2/config/core_plan.json + 打印人类可读摘要。**不下任何委托。**

用法：python scripts/core_plan.py [--names 15] [--target-vol 0.15] [--max-exposure 0.25] [--account agent_brain]
"""
import argparse, json, os, subprocess, sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import io

ROOT = Path(__file__).resolve().parents[1]
ENV = dict(os.environ, PATH="/opt/homebrew/bin:/usr/local/bin:" + os.environ.get("PATH", ""))
DEF_START, DEF_END = "2024-01-01", "2024-06-30"
OUT = ROOT / "config" / "core_plan.json"


def psql(q):
    return subprocess.run(["psql", "-d", "quant_investment", "-At", "-c", q],
                          capture_output=True, text=True, env=ENV, check=True).stdout


def psql_csv(q):
    out = subprocess.run(["psql", "-d", "quant_investment", "-c", "copy (" + q + ") to stdout with csv header"],
                         capture_output=True, text=True, env=ENV, check=True).stdout
    df = pd.read_csv(io.StringIO(out), dtype={"symbol": str})
    df["symbol"] = df["symbol"].astype(str).str.zfill(6)
    return df


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--names", type=int, default=15)
    ap.add_argument("--target-vol", type=float, default=0.15)
    ap.add_argument("--max-exposure", type=float, default=0.25)   # 首期上限：25%（regime 允许 40% 以内）
    ap.add_argument("--account", default="agent_brain")
    ap.add_argument("--max-price", type=float, default=30.0)      # 100 股整手可负担
    ap.add_argument("--exclude-near-high", type=float, default=-0.05)  # 排除"距52周高 <5%"的追高标的
    a = ap.parse_args()

    # 1) 候选池：窗口前定义（2024H1）流动性 Top，含价格与流动性明细
    px = psql_csv("select symbol, max(trade_date)::text as d, avg(amount) as amt from quant.daily_klines "
                  "where trade_date between '" + DEF_START + "' and '" + DEF_END + "' group by symbol "
                  "having count(*) >= 100 order by amt desc limit 400")
    px["symbol"] = px["symbol"].astype(str).str.zfill(6)
    latest = psql_csv("select symbol, close, amount from quant.daily_klines where trade_date = "
                      "(select max(trade_date) from quant.daily_klines)")
    latest["symbol"] = latest["symbol"].astype(str).str.zfill(6)
    uni = px.merge(latest, on="symbol", how="inner", suffixes=("_def", "_now"))
    uni = uni[(uni["close"] > 0) & (uni["close"] <= a.max_price)]
    uni = uni.sort_values("amt", ascending=False)
    # 不追高（2026-09-13 基准率检验）：距 52 周高 ≤3% 的标的，未来 20/60 日**中位收益为负**、胜率<50%；
    # 而距高 <-30% 的深跌标的 120 日中位 +11.1%、胜率 66.8%。故默认排除近高标的。
    hi = psql_csv("select symbol, max(close) as hi52 from quant.daily_klines where trade_date >= "
                  "(select max(trade_date) - 365 from quant.daily_klines) group by symbol")
    hi["symbol"] = hi["symbol"].astype(str).str.zfill(6)
    uni = uni.merge(hi, on="symbol", how="left")
    uni["dist_high"] = uni["close"] / uni["hi52"] - 1
    before = len(uni)
    uni = uni[uni["dist_high"] <= a.exclude_near_high]
    print("不追高过滤：%d → %d 只（排除距52周高 > %.0f%% 的标的）" % (before, len(uni), a.exclude_near_high * 100))
    picks = uni.head(a.names)

    # 2) 账户与持仓
    acct = psql("select coalesce(total_value,0) || '|' || coalesce(cash_available,0) from quant.simulation_account "
                "where account_name='" + a.account + "'").strip().split("|")
    total, cash = float(acct[0] or 0), float(acct[1] or 0)
    poss = psql_csv("select symbol, shares_total as shares, avg_cost from quant.simulation_positions "
                    "where account_name='" + a.account + "'") if False else None

    # 3) 暴露：波动目标 × 回撤闸门（用 core 指数的日收益重建）
    hist = psql_csv("select symbol, trade_date, close from quant.daily_klines where symbol in ("
                    + ",".join("'" + s + "'" for s in picks["symbol"])
                    + ") and trade_date >= '2024-06-01' order by trade_date")
    hist["trade_date"] = pd.to_datetime(hist["trade_date"])
    close = hist.pivot_table(index="trade_date", columns="symbol", values="close").ffill()
    core_ret = close.pct_change().mean(axis=1).dropna()
    vol_ann = float(core_ret.tail(20).std() * np.sqrt(252)) if len(core_ret) >= 20 else np.nan
    eq = (1 + core_ret).cumprod()
    dd = float(eq.iloc[-1] / eq.cummax().iloc[-1] - 1) if len(eq) else 0.0
    w_vol = min(1.0, a.target_vol / vol_ann) if vol_ann and vol_ann > 0 else 1.0
    gate = 0.5 if dd < -0.10 else 1.0
    target_expo = round(min(a.max_exposure, a.max_exposure * w_vol * gate), 4)

    # 现实约束：A股 100 股整手。按目标金额与股价反推"可承受的持仓只数"，保证每只至少 1 手。
    target_amount_pre = total * target_expo
    lots_ok = uni[uni["close"] * 100 <= target_amount_pre / max(a.names, 1) if False else uni["close"] > 0]
    # 先按目标金额/计划只数算单只预算，再筛掉"单只预算买不起 1 手"的标的
    budget_per_name = target_amount_pre / max(a.names, 1)
    affordable = uni[uni["close"] * 100 <= budget_per_name]
    if len(affordable) >= min(a.names, 3):
        picks = affordable.head(a.names)
    else:
        # 预算不够分散时，减少只数以保证每只 ≥1 手
        n_fit = max(1, int(target_amount_pre // (uni["close"].min() * 100)))
        n_fit = min(n_fit, a.names)
        picks = uni.head(n_fit)
        budget_per_name = target_amount_pre / max(n_fit, 1)

    plan = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "account": a.account, "mode": "PLAN_ONLY（不下单）",
        "account_total": total, "cash": cash,
        "exposure": {"target_pct": target_expo, "first_phase_cap_pct": a.max_exposure,
                     "core_realized_vol_ann": round(vol_ann, 4) if vol_ann else None,
                     "vol_target": a.target_vol, "w_vol": round(w_vol, 3),
                     "core_drawdown": round(dd, 4), "dd_gate": gate},
        "holdings": [{"symbol": r.symbol, "close": float(r.close), "amount_def_avg": float(r.amt),
                      "target_weight_pct": round(100.0 / len(picks), 2)} for r in picks.itertuples()],
        "phase_plan": "分 4 批、每批约 1 周；每批按当时 vol-target 与回撤闸门重算",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(plan, ensure_ascii=False, indent=1), encoding="utf-8")

    print("=== 投资脑 core 建仓计划（只出计划，不下单）===")
    print("账户 %s 总资产 %.0f 现金 %.0f" % (a.account, total, cash))
    print("目标暴露 %.1f%%（首期上限 %.0f%%｜core 20 日年化波动 %.1f%%｜波动系数 %.2f｜回撤 %.1f%%→闸门 %.1f）"
          % (target_expo * 100, a.max_exposure * 100, (vol_ann or 0) * 100, w_vol, dd * 100, gate))
    target_amount = total * target_expo
    print("计划投入 %.0f 元，分 4 批（每批约 %.0f 元）" % (target_amount, target_amount / 4))
    print("目标持仓 %d 只等权（每只约 %.0f 元 ≈ %.0f 股 @现价）：" % (len(picks), target_amount / len(picks), 0))
    for r in picks.itertuples():
        lots = int((target_amount / len(picks)) // (float(r.close) * 100))
        print("  %s  现价 %6.2f  每只 %.0f 元 ≈ %d 手(%d 股)" % (r.symbol, float(r.close),
              target_amount / len(picks), lots, lots * 100))
    print("计划已写入", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
