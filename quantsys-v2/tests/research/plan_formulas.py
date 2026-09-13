"""投资学核心公式透镜（plan_formulas.py，2026-09-13 w-c8cae280）

对 config/core_plan.json 的**计划组合**（core + 成长板子额度）逐条套用投资学核心公式：
  1 复利/72法则  2 夏普/索提诺  3 CAPM(beta/alpha)  4 马科维茨(相关/有效注数)
  5 VaR/CVaR     6 凯利公式     7 股息贴现锚(Gordon)
只读；不下单。所有输出标注窗口与数据来源（R-013）。
"""
import argparse, io, json, os, subprocess
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]   # quantsys-v2/
ENV = dict(os.environ, PATH="/opt/homebrew/bin:/usr/local/bin:" + os.environ.get("PATH", ""))
PLAN = ROOT / "config" / "core_plan.json"
OUT = ROOT / "tests" / "research" / "out" / "plan_formulas.json"
RF = 0.02          # 无风险利率假设 2%（年化）
FRAC = 0.25        # 分数凯利系数
G = 0.02           # 股息永续增长率假设 2%


def psql_csv(q):
    out = subprocess.run(["psql", "-d", "quant_investment", "-c", "copy (" + q + ") to stdout with csv header"],
                         capture_output=True, text=True, env=ENV, check=True).stdout
    df = pd.read_csv(io.StringIO(out), dtype={"symbol": str})
    if "symbol" in df.columns:
        df["symbol"] = df["symbol"].astype(str).str.zfill(6)
    return df


def index_series():
    """沪深300 日收盘：库内无指数日线（实测），改走 akshare；失败则降级为 None。"""
    try:
        import akshare as ak
        df = ak.stock_zh_index_daily(symbol="sh000300")
        df["trade_date"] = pd.to_datetime(df["date"])
        df = df.sort_values("trade_date")
        df["bm"] = df["close"].astype(float).pct_change()   # 必须用收益率：点位是随机游走，与组合收益率协方差≈0
        return df[["trade_date", "bm"]].dropna(), "akshare:stock_zh_index_daily(sh000300) 日收益率"
    except Exception as e:  # noqa: BLE001
        return None, "unavailable: %s" % e


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2024-07-01")
    ap.add_argument("--include-sleeve", type=int, default=1)
    a = ap.parse_args()

    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    total = float(plan["account_total"])
    rows = []
    core_expo = float(plan["exposure"]["target_pct"])
    for h in plan["holdings"]:
        rows.append({"symbol": h["symbol"], "sleeve": "core", "expo_pct": core_expo * h["weight_pct_of_core"] / 100.0})
    if a.include_sleeve and plan.get("growth_sleeve", {}).get("holdings"):
        sm = plan["growth_sleeve"]["meta"]
        for h in plan["growth_sleeve"]["holdings"]:
            rows.append({"symbol": h["symbol"], "sleeve": "growth",
                         "expo_pct": float(sm["exposure_pct_of_total"]) * h["weight_pct_of_sleeve"] / 100.0})
    w = pd.Series({r["symbol"]: r["expo_pct"] for r in rows})
    w = w / w.sum()   # 组合内相对权重
    syms = list(w.index)
    expo_total = sum(r["expo_pct"] for r in rows)

    px = psql_csv("select symbol, trade_date, close from quant.daily_klines where symbol in ("
                  + ",".join("'" + s + "'" for s in syms)
                  + ") and trade_date >= '" + a.start + "' order by trade_date")
    px["trade_date"] = pd.to_datetime(px["trade_date"])
    close = px.pivot_table(index="trade_date", columns="symbol", values="close").ffill()
    ret = close.pct_change().dropna(how="all")
    ret = ret[w.index.intersection(ret.columns)]
    rp = (ret * w[ret.columns]).sum(axis=1).dropna()
    T = len(rp) / 252.0
    mu_ann = float(rp.mean() * 252)
    sig_ann = float(rp.std() * np.sqrt(252))
    dd = float(((1 + rp).cumprod() / (1 + rp).cumprod().cummax() - 1).min())
    var95 = float(np.percentile(rp, 5))
    cvar95 = float(rp[rp <= var95].mean())
    sortino = float((mu_ann - RF) / (rp[rp < 0].std() * np.sqrt(252)))

    bm, bm_src = index_series()
    beta = alpha = None
    if bm is not None:
        j = rp.to_frame("rp").join(bm.set_index("trade_date"), how="inner").dropna()
        if len(j) > 30:
            beta = float(np.cov(j["rp"], j["bm"], ddof=1)[0, 1] / np.var(j["bm"], ddof=1))
            alpha = float((j["rp"].mean() - beta * j["bm"].mean()) * 252)
            bm_src += "（对齐 %d 个交易日）" % len(j)

    corr = ret.corr()
    iu = np.triu_indices_from(corr.values, k=1)
    corr_mean = float(np.nanmean(corr.values[iu]))
    ev = np.linalg.eigvalsh(corr.values.astype(float))
    enb_pca = float(ev.sum() ** 2 / (ev ** 2).sum())
    enb_w = float(1.0 / (w.values ** 2).sum())

    mu_ex = mu_ann - RF
    kelly_full = float(mu_ex / sig_ann ** 2)
    se_mu = float(sig_ann / np.sqrt(T))
    kel = {"point": kelly_full}
    for z, k in ((1, "lcb1"), (2, "lcb2")):
        kel[k] = float((mu_ex - z * se_mu) / sig_ann ** 2)

    dbl_years = float(np.log(2) / np.log(1 + mu_ann)) if mu_ann > 0 else None

    out = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "window": {"start": str(ret.index.min().date()), "end": str(ret.index.max().date()),
                   "trading_days": int(len(rp)), "years": round(T, 2)},
        "portfolio": {"names": len(syms), "plan_exposure_pct_of_total": round(expo_total, 4),
                      "weights": {k: round(float(v), 4) for k, v in w.items()}},
        "1_compound": {"mu_ann": round(mu_ann, 4), "doubling_years": round(dbl_years, 2) if dbl_years else None,
                       "rule_of_72_check": round(0.72 / mu_ann, 2) if mu_ann > 0 else None,
                       "note": "μ 为被动持有计划组合的窗口年化，含 2024-07 起多头市，外推需谨慎"},
        "2_sharpe": {"sharpe": round((mu_ann - RF) / sig_ann, 3), "sortino": round(sortino, 3), "vol_ann": round(sig_ann, 4)},
        "3_capm": {"beta_vs_hs300": round(beta, 3) if beta is not None else None,
                   "alpha_ann": round(alpha, 4) if alpha is not None else None, "benchmark_source": bm_src},
        "4_markowitz": {"mean_pairwise_corr": round(corr_mean, 3), "enb_pca": round(enb_pca, 2),
                        "enb_weight": round(enb_w, 2), "note": "enb_pca=相关矩阵特征值口径的有效独立注数；enb_weight=1/Σw² 的名义注数"},
        "5_var": {"var95_daily": round(var95, 4), "cvar95_daily": round(cvar95, 4),
                  "var95_amount_at_plan_exposure": round(var95 * expo_total * total, 0),
                  "max_drawdown_window": round(dd, 4)},
        "6_kelly": {"mu_excess": round(mu_ex, 4), "sigma": round(sig_ann, 4), "se_mu": round(se_mu, 4),
                    "f_point": round(kel["point"], 3), "f_lcb1": round(kel["lcb1"], 3), "f_lcb2": round(kel["lcb2"], 3),
                    "frac": FRAC, "f_point_frac": round(kel["point"] * FRAC, 3), "f_lcb1_frac": round(kel["lcb1"] * FRAC, 3),
                    "verdict": ("不下注（2σ 下界为负）" if kel["lcb2"] <= 0 else
                                "顶到宪法 90% 上限（无刻度作用）" if kel["point"] * FRAC > 0.9 else
                                "约 %.0f%%" % (kel["point"] * FRAC * 100))},
        "7_dividend_anchor": {"note": "库内无分红表（实测）；akshare 分红记录截至 2025-01，已陈旧，仅作粗锚；Gordon: 隐含长期回报 = 股息率 + g(%.0f%%)" % (G * 100)},
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

    print("=== 计划组合公式透镜（%s ~ %s，%d 个交易日，%.2f 年）===" % (out["window"]["start"], out["window"]["end"], len(rp), T))
    print("组合：%d 只，计划暴露 %.2f%% 总资产（¥%.0f）" % (len(syms), expo_total * 100, expo_total * total))
    print("[1 复利] 窗口年化 μ=%.1f%% → 翻倍需 %.1f 年（72法则校验 %.1f 年）" % (mu_ann * 100, dbl_years or 0, 0.72 / mu_ann if mu_ann > 0 else 0))
    print("[2 夏普] Sharpe=%.2f  Sortino=%.2f  年化波动 %.1f%%" % ((mu_ann - RF) / sig_ann, sortino, sig_ann * 100))
    print("[3 CAPM] beta=%s  alpha=%s  （基准 %s）" % (round(beta, 3) if beta is not None else "n/a",
          ("%.1f%%" % (alpha * 100)) if alpha is not None else "n/a", bm_src))
    print("[4 马科维茨] 平均两两相关 %.2f｜有效注数(特征值) %.2f｜名义注数(1/Σw²) %.2f" % (corr_mean, enb_pca, enb_w))
    print("[5 VaR] 日 VaR95=%.2f%%（占计划 ¥%.0f）｜CVaR95=%.2f%%｜窗口内最大回撤 %.1f%%"
          % (var95 * 100, var95 * expo_total * total, cvar95 * 100, dd * 100))
    print("[6 凯利] μ_ex=%.1f%% σ=%.1f%% SE(μ)=%.1f%% → f*: 点估计 %.0f%%｜1σ下界 %.0f%%｜2σ下界 %.0f%%"
          % (mu_ex * 100, sig_ann * 100, se_mu * 100, kel["point"] * 100, kel["lcb1"] * 100, kel["lcb2"] * 100))
    print("         1/4 凯利: 点估计 %.0f%%｜1σ下界 %.0f%%  → 判定：%s" % (kel["point"] * FRAC * 100, kel["lcb1"] * FRAC * 100, out["6_kelly"]["verdict"]))
    print("[7 股息锚] %s" % out["7_dividend_anchor"]["note"])
    print("已写入", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())