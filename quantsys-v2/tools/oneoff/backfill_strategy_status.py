"""策略两轴状态回填（2026-09-13, w-a9ec14d7）

把 quant.strategy_configs 的 validation_status（结构语义）拆成两根轴：
  structure_status   ← validation_status（结构有效）
  performance_status ← 相对同池等权基准的业绩判定（passing/underperform/failing/unmeasured）
  performance_evidence / performance_checked_at ← 证据与时点（R-013）

证据优先级：① --lab 指定的体检结果 JSON（strategy_lab.py 口径，OOS，最可信）
            ② quant.strategy_validation_reports 最近一次 annual_return（平台回测口径）
            ③ 无证据 → unmeasured（不冒充达标）

用法：venv/bin/python scripts/backfill_strategy_status.py [--dry-run] [--lab /path/to/lab.json]
lab.json 形如：[{"strategy_id": 245, "cagr_oos": -0.0216, "sharpe_oos": -0.49, "dd_oos": -0.0716}]
"""
import argparse, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))  # 归档到 tools/oneoff/ 后多一层
import psycopg2
from application.services.strategy_status import (
    classify_structure, classify_performance, performance_evidence,
)

DSN = os.environ.get("DATABASE_URL", "dbname=quant_investment")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--lab", default=None)
    a = ap.parse_args()

    lab = {}
    if a.lab and os.path.exists(a.lab):
        for row in json.load(open(a.lab)):
            lab[int(row["strategy_id"])] = row
        print("lab 证据 %d 条" % len(lab))

    conn = psycopg2.connect(DSN)
    cur = conn.cursor()
    cur.execute("select id, strategy_name, validation_status, is_active from quant.strategy_configs order by id")
    rows = cur.fetchall()
    print("待回填 %d 条" % len(rows))

    updated, unmeasured = 0, 0
    for sid, name, vstatus, is_active in rows:
        structure = classify_structure(vstatus)
        perf, ev = "unmeasured", None
        if sid in lab:
            row = lab[sid]
            ar = row.get("cagr_oos")
            perf = classify_performance(ar, row.get("sharpe_oos"))
            ev = performance_evidence(ar, row.get("sharpe_oos"), row.get("dd_oos"),
                                      "strategy_lab.py（T+1/次日开盘/含成本，OOS 段）",
                                      row.get("window"))
        else:
            cur.execute("""
                select annual_return, sharpe_ratio, max_drawdown, validation_date, start_date, end_date
                from quant.strategy_validation_reports where strategy_id = %s
                order by validation_date desc limit 1""", (sid,))
            rep = cur.fetchone()
            if rep:
                perf = classify_performance(rep[0], rep[1])
                ev = performance_evidence(rep[0], rep[1], rep[2],
                                          "quant.strategy_validation_reports（平台批量回测，单标的默认池）",
                                          "%s~%s" % (rep[4], rep[5]))
        if perf == "unmeasured":
            unmeasured += 1
        print("  %-4s %-38s 结构=%-8s 业绩=%-12s %s" % (
            sid, str(name)[:36], structure, perf,
            ("证据年化=%s" % ev["annual_return"]) if ev else "(无证据)"))
        if not a.dry_run:
            cur.execute("""
                update quant.strategy_configs
                set structure_status = %s, performance_status = %s,
                    performance_evidence = %s, performance_checked_at = now()
                where id = %s""",
                (structure, perf, json.dumps(ev, ensure_ascii=False) if ev else None, sid))
            updated += 1
    if not a.dry_run:
        conn.commit()
    print("回填 %d 条（其中无证据 unmeasured %d 条）%s" % (updated, unmeasured, "(dry-run 未写库)" if a.dry_run else ""))
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())