"""回填 quant.simulation_equity_snapshot 的日收益/累计收益/回撤口径 — 2026-09-11 w-8f2c4cc5

背景：daily_return 长期基准错位（2026-07-27 记 +24.08%，真实 +0.72%），cumulative_return
与净值不符（0.3746 vs 0.0518），drawdown 亦非按运行峰值计算。这些列被 benchmark_comparison、
evolution_fitness、simulation_service 及历史 risk_metrics 消费，必须与账户净值对齐。

口径（与 upsert_equity_snapshot 的写入口径一致）：
- daily_return      = (total_value - 当日外部入金) / 上一有效快照 total_value - 1
                      上一有效 = total_value > 0 且 >= cash（排除早盘残缺估值行）
                      外部入金只算 flow_type='deposit'；buy_debit/sell_credit 是交易内生现金流；
                      adjustment 语义含糊，不并入分子，但当日出现即标记「口径存疑」
- cumulative_return = total_value / initial_capital - 1（initial_capital 缺失则不写）
- drawdown          = total_value / 运行峰值 - 1

安全阀：|计算值| > 15%（SUSPICIOUS）的行默认**不写回**，只列入人工复核清单
（避免把无法解释的净值跳变当成真实收益写进风控数据源）；用 --force-suspicious 才落库。

用法：
  python scripts/backfill_equity_snapshot_returns.py                    # dry-run，只打印差异
  python scripts/backfill_equity_snapshot_returns.py --apply            # 落库（跳过可疑行）
  python scripts/backfill_equity_snapshot_returns.py --apply --force-suspicious
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import psycopg2  # noqa: E402

DB = {'dbname': 'quant_investment'}
SUSPICIOUS = 0.15


def fetch(conn):
    cur = conn.cursor()
    cur.execute("select account_name, initial_capital from quant.simulation_account")
    capital = {r[0]: (float(r[1]) if r[1] is not None else None) for r in cur.fetchall()}
    cur.execute(
        """select id, account_name, snapshot_date, cash, total_value,
                  daily_return, cumulative_return, drawdown
           from quant.simulation_equity_snapshot
           order by account_name, snapshot_date"""
    )
    rows = cur.fetchall()
    cur.execute(
        """select account_name, flow_type, created_at, amount
           from quant.simulation_cash_flow
           order by account_name, created_at"""
    )
    flows = {}
    seen_deposit = set()
    for account, ftype, created, amount in cur.fetchall():
        day = created.date() if created is not None else None
        amount = float(amount or 0)
        if ftype == 'deposit':
            # 账户首笔 deposit = 成立资金：本库其 created_at 是迁移时间而非真实入金日
            # （2026-07-21 agent_virtual 才落 147070.15），当当日流入会算出 -147% 荒谬日收益。
            if account not in seen_deposit:
                seen_deposit.add(account)
                continue
        bucket = flows.setdefault((account, day), {})
        bucket[ftype] = bucket.get(ftype, 0.0) + amount
    cur.close()
    return capital, rows, flows


def compute(capital, rows, flows):
    by_account = {}
    for r in rows:
        by_account.setdefault(r[1], []).append(r)

    updates, skipped, stats = {}, [], {
        'rows': 0, 'changed': 0, 'suspicious_before': 0, 'suspicious_after': 0,
        'adjustment_days': 0,
    }
    for account, acc_rows in by_account.items():
        init = capital.get(account)
        prev_valid, peak = None, None
        for r in acc_rows:
            rid, _, day, cash, total = r[0], r[1], r[2], float(r[3] or 0), float(r[4] or 0)
            stored_dr = float(r[5]) if r[5] is not None else None
            stored_cr = float(r[6]) if r[6] is not None else None
            stored_dd = float(r[7]) if r[7] is not None else None

            day_flows = flows.get((account, day), {})
            # 外部入金只算「非成立资金」的 deposit（fetch 已剔除账户首笔 deposit）
            external_in = day_flows.get('deposit', 0.0)
            has_adjustment = 'adjustment' in day_flows
            if has_adjustment:
                stats['adjustment_days'] += 1

            dr = None
            if prev_valid is not None and prev_valid > 0:
                dr = (total - external_in - prev_valid) / prev_valid

            cr = total / init - 1 if init and init > 0 else None

            dd = None
            if total > 0:
                peak = total if peak is None else max(peak, total)
                dd = total / peak - 1 if peak > 0 else None

            stats['rows'] += 1
            if stored_dr is not None and abs(stored_dr) > SUSPICIOUS:
                stats['suspicious_before'] += 1
            if dr is not None and abs(dr) > SUSPICIOUS:
                stats['suspicious_after'] += 1

            def _differ(a, b):
                if a is None and b is None:
                    return False
                if a is None or b is None:
                    return True
                return abs(a - b) > 1e-4

            if _differ(stored_dr, dr) or _differ(stored_cr, cr) or _differ(stored_dd, dd):
                stats['changed'] += 1
                item = (rid, account, day, total, dr, cr, dd, stored_dr, stored_cr, stored_dd,
                        has_adjustment)
                if dr is not None and abs(dr) > SUSPICIOUS:
                    skipped.append(item)
                else:
                    updates[rid] = item

            if total > 0 and total >= cash:
                prev_valid = total
    return updates, skipped, stats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true', help='实际落库（默认 dry-run）')
    ap.add_argument('--force-suspicious', action='store_true',
                    help='连 |daily_return| > 15% 的可疑行一并落库（默认跳过并列入复核）')
    ap.add_argument('--limit-print', type=int, default=12)
    args = ap.parse_args()

    conn = psycopg2.connect(**DB)
    try:
        capital, rows, flows = fetch(conn)
        updates, skipped, stats = compute(capital, rows, flows)
        print(f"快照 {stats['rows']} 条；待修正 {stats['changed']} 条（可落库 {len(updates)}，"
              f"可疑挂起 {len(skipped)}）；|daily_return|>15%：修正前 {stats['suspicious_before']} 条"
              f"→ 修正后 {stats['suspicious_after']} 条；含 adjustment 流水的快照日 "
              f"{stats['adjustment_days']} 个")

        worst = sorted(updates.values(), key=lambda u: -abs((u[7] or 0) - (u[4] or 0)))
        for rid, account, day, total, dr, cr, dd, sdr, scr, sdd, adj in worst[:args.limit_print]:
            print(f"  {account} {day} total={total:.2f}  daily {sdr} -> "
                  f"{None if dr is None else round(dr, 4)}  cum {scr} -> "
                  f"{None if cr is None else round(cr, 4)}  dd {sdd} -> "
                  f"{None if dd is None else round(dd, 4)}")

        if skipped:
            print('需人工复核（未落库，请对照资金流水/持仓估值核查）:')
            for rid, account, day, total, dr, cr, dd, sdr, scr, sdd, adj in skipped:
                print(f"  {account} {day} total={total:.2f} 计算 daily_return="
                      f"{None if dr is None else round(dr, 4)}  原值={sdr}"
                      f"{'  [当日有 adjustment 流水]' if adj else ''}")

        if not args.apply:
            print('dry-run：未落库（加 --apply 执行）')
            return

        write = dict(updates)
        if args.force_suspicious:
            for item in skipped:
                write[item[0]] = item
        cur = conn.cursor()
        for rid, (_rid, _a, _d, _t, dr, cr, dd, *_rest) in write.items():
            cur.execute(
                """update quant.simulation_equity_snapshot
                   set daily_return=%s, cumulative_return=%s, drawdown=%s
                   where id=%s""",
                (dr, cr, dd, rid),
            )
        conn.commit()
        cur.close()
        print(f"已回填 {len(write)} 行"
              + (f"（含 {len(skipped)} 行可疑值，--force-suspicious）" if args.force_suspicious else ""))
    finally:
        conn.close()


if __name__ == '__main__':
    main()
