"""资金流 quality_flag 误判纠正（2026-09-13 w-a9ec14d7）

背景：2026-09-11 的迁移把 14,314 行（5,436 只）标为 close_mismatch_vs_kline="污染"，
判据是"资金流收盘价 vs K线收盘价偏差 > 0.5%"。但 K线是**前复权**、资金流是**原始价**，
两者本来就存在随除权日阶跃变化的恒定偏移（实测 000408：3月 +3.4% → 9月 +1.3%，平滑衰减）。

决定性检验（本脚本）：同一交易日的**日收益率**对比 —— 若只是复权因子，收益率应几乎处处相等。
实测 196 只有足够样本的被标股票：背离占比中位 0.83%、p90 1.79%、**98.5% 的股票背离占比 ≤5%**，
无一例 >30% → **没有一个真污染**。

本脚本：按证据撤销误标（quality_flag → NULL），保留真污染候选的标记；全程留备份与报告。
"""
import io, json, os, subprocess, sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path("/Users/yunpeng/pi-investment/quantsys-v2")
ENV = dict(os.environ, PATH="/opt/homebrew/bin:/usr/local/bin:" + os.environ.get("PATH", ""))
MIN_OBS = 8
DIVERGE_THR = 0.10


def psql(sql, fetch=False):
    args = ["psql", "-d", "quant_investment"] + (["-Atc", sql] if not fetch else ["-c", sql])
    r = subprocess.run(args, capture_output=True, text=True, env=ENV)
    if r.returncode != 0:
        raise RuntimeError(r.stderr[:300])
    return r.stdout.strip()


def csv(sql):
    out = subprocess.run(["psql", "-d", "quant_investment", "-c", "copy (" + sql + ") to stdout with csv header"],
                         capture_output=True, text=True, env=ENV, check=True).stdout
    return pd.read_csv(io.StringIO(out), dtype={"symbol": str})


def main():
    apply = "--apply" in sys.argv
    # 判据必须在**该股全部行**上做：复权因子是"股级"属性，不是"被标行"的属性。
    # 只用被标行会得到每股平均 2.6 行样本，不足以判断收益率一致性（第一版就踩了这个坑：只判出 50 只）。
    df = csv("""
        select f.symbol, f.trade_date, f.close_price as fclose, k.close as kclose
        from quant.stock_fund_flow f
        join quant.daily_klines k on k.symbol = f.symbol and k.trade_date = f.trade_date
        where f.symbol in (select distinct symbol from quant.stock_fund_flow where quality_flag is not null)
        order by f.symbol, f.trade_date
    """)
    df["trade_date"] = pd.to_datetime(df["trade_date"])
    print("载入被标股票的全部行 %d / %d 只（判据样本=全部行）" % (len(df), df.symbol.nunique()))

    rows = []
    for sym, g in df.groupby("symbol"):
        g = g.sort_values("trade_date")
        if len(g) < MIN_OBS:
            continue
        # 关键：只用**相邻交易日**的收益率对比。
        # 稀疏采样下 pct_change 会跨多日、甚至跨除权日 → 收益率必然背离，
        # 会把"采样稀疏"误判成"污染"（第二版判据就踩了这个坑：中位背离 44%）。
        gap = g["trade_date"].diff().dt.days
        consec = gap <= 4          # 覆盖周末；>4 天视为不连续，剔除
        g2 = g[consec]
        if len(g2) < MIN_OBS - 1:
            continue
        d = (g2["fclose"].pct_change() - g2["kclose"].pct_change()).abs().dropna()
        if len(d) < MIN_OBS - 2:
            continue
        rows.append({"symbol": sym, "n": len(g2), "diverged": float((d > 0.01).mean()),
                     "median_dev_pct": float(((g["fclose"] / g["kclose"] - 1).abs() * 100).median())})
    r = pd.DataFrame(rows)
    adj = r[r.diverged <= DIVERGE_THR]
    sus = r[r.diverged > DIVERGE_THR]
    print("可判定股票 %d 只：复权口径（背离≤%.0f%%）%d 只 / 真污染候选 %d 只"
          % (len(r), DIVERGE_THR * 100, len(adj), len(sus)))
    print("  背离占比 中位 %.4f  p90 %.4f" % (r.diverged.median(), r.diverged.quantile(.9)))
    print("  中位偏差 中位 %.2f%%（恒定偏移 = 复权因子特征）" % r.median_dev_pct.median())

    n_unflagged = int(psql("select count(*) from quant.stock_fund_flow where quality_flag is not null and symbol in (%s)"
                           % ",".join("'" + s + "'" for s in adj.symbol)) or 0)
    print("  将撤销误标：%d 行（涉及 %d 只）" % (n_unflagged, len(adj)))

    report = {"generated_at": pd.Timestamp.now().isoformat(timespec="seconds"),
              "criterion": "同一交易日日收益率背离占比 ≤ %.0f%%（复权因子假设），样本 ≥ %d 日" % (DIVERGE_THR * 100, MIN_OBS),
              "judged_symbols": len(r), "adjustment_artifact_symbols": len(adj),
              "true_corruption_candidates": len(sus), "rows_to_unflag": n_unflagged,
              "evidence": {"diverged_median": round(float(r.diverged.median()), 4),
                           "diverged_p90": round(float(r.diverged.quantile(.9)), 4),
                           "median_dev_pct": round(float(r.median_dev_pct.median()), 2)},
              "true_corruption_symbols": list(sus.symbol[:50])}
    out = ROOT / "config" / "fund_flow_flag_audit.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print("  报告 →", out)

    if not apply:
        print("（dry-run；加 --apply 执行撤标）")
        return 0
    psql("drop table if exists quant.stock_fund_flow_quality_backup_20260913")
    psql("create table quant.stock_fund_flow_quality_backup_20260913 as "
         "select id, symbol, trade_date, quality_flag from quant.stock_fund_flow where quality_flag is not null")
    print("  备份 → quant.stock_fund_flow_quality_backup_20260913（%s 行）"
          % psql("select count(*) from quant.stock_fund_flow_quality_backup_20260913"))
    if len(adj):
        psql("update quant.stock_fund_flow set quality_flag = null where symbol in (%s) and quality_flag is not null"
             % ",".join("'" + s + "'" for s in adj.symbol))
    left = psql("select count(*) from quant.stock_fund_flow where quality_flag is not null")
    print("  撤标完成；剩余被标行 %s（真污染候选，保留过滤）" % left)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
