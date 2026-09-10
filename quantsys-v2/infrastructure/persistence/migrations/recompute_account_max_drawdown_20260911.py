"""回填/校正 simulation_account.max_drawdown 口径 — 2026-09-11 w-8f2c4cc5

背景：账户表 max_drawdown 此前由 paper_trading_engine 写入**当日**回撤且取**正号**
（实测 agent_virtual = +0.0043），而快照 drawdown 与 risk_metrics 用「负号峰谷最大回撤」
（-1.83%）——符号与语义双双不一致，读到该字段的一方（如 quantsys_v2_status 的 balance）
会得到「最大回撤 +0.43%」这种无意义值。

口径（与 SimulationORMRepository.recompute_account_max_drawdown 一致，唯一真源=净值序列）：
- max_drawdown = min over t of (total_t / peak_t - 1)，peak_t = 截至 t 的运行峰值（<=0）
- 残缺估值行（total_value <= 0 或 total_value < cash）不参与
- peak_value 同步取「已有峰值与序列峰值的较大者」

用法：
  python infrastructure/persistence/migrations/recompute_account_max_drawdown_20260911.py            # dry-run
  python infrastructure/persistence/migrations/recompute_account_max_drawdown_20260911.py --apply
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import psycopg2  # noqa: E402

DB = {'dbname': 'quant_investment'}
SCAN = 400


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true', help='实际落库（默认 dry-run）')
    args = ap.parse_args()

    conn = psycopg2.connect(**DB)
    try:
        cur = conn.cursor()
        cur.execute('select account_name, max_drawdown, peak_value from quant.simulation_account order by account_name')
        accounts = cur.fetchall()
        changed, rows = [], 0
        for account, cur_dd, cur_peak in accounts:
            cur.execute(
                """select total_value, cash from quant.simulation_equity_snapshot
                   where account_name = %s order by snapshot_date asc limit %s""",
                (account, SCAN),
            )
            peak, worst = None, 0.0
            for total_value, cash in cur.fetchall():
                total, cash_f = float(total_value or 0), float(cash or 0)
                if total <= 0 or total < cash_f:
                    continue
                peak = total if peak is None else max(peak, total)
                if peak > 0:
                    worst = min(worst, total / peak - 1.0)
                rows += 1
            new_peak = max(float(cur_peak or 0), peak or 0)
            dd_old = None if cur_dd is None else float(cur_dd)
            if dd_old is None or abs(dd_old - worst) > 1e-4 or abs(new_peak - float(cur_peak or 0)) > 1e-4:
                changed.append((account, dd_old, worst, float(cur_peak or 0), new_peak))

        print(f"扫描 {len(accounts)} 个账户、{rows} 条有效净值点；需校正 {len(changed)} 个")
        for account, old, new, old_peak, new_peak in changed:
            print(f"  {account}: max_drawdown {old} -> {round(new, 4)}   peak_value {old_peak} -> {round(new_peak, 2)}")

        if not args.apply:
            print('dry-run：未落库（加 --apply 执行）')
            return
        for account, _old, new, _op, new_peak in changed:
            cur.execute(
                'update quant.simulation_account set max_drawdown=%s, peak_value=%s where account_name=%s',
                (new, new_peak, account),
            )
        conn.commit()
        print(f"已校正 {len(changed)} 个账户")
        cur.close()
    finally:
        conn.close()


if __name__ == '__main__':
    main()
