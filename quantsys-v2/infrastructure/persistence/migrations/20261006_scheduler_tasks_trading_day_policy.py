#!/usr/bin/env python
"""quant.scheduler_tasks 加交易日门策略列（2026-10-06 · REQ-261006093620-a315 t2 · FR-1/FR-4/FR-5）

## 背景

② 库表调度（APScheduler，读 `quant.scheduler_tasks`）原先**没有任何交易日门**：
2026-10-06（国庆休市·周二）09:25 实测 `pre-market-scan`（task 250）照常开火并记 success
（`run_id=3379`、129ms）。本迁移为「逐任务声明该在什么日子自动开火」提供数据位。

## 三值策略（为什么不是布尔）

| policy | 语义 | 谁用 |
|---|---|---|
| `always`（**缺省**） | 不判门，照跑——既有行行为完全不变 | `252`/`253`/`262` 等不吃当日行情者 |
| `trading-days` | 非交易日一律跳过 | 7 条「吃当日行情」的工作日任务 |
| `holidays` | **只跳法定节假日**，周末照跑 | `232`（`0 0 * * *`，排班含周末，需求 D-6） |

布尔无法同时表达后两档：`232` 若用 `trading-days`，周末会被一并跳掉（行为扩大）。

## 幂等

`ADD COLUMN IF NOT EXISTS` + `DROP CONSTRAINT IF EXISTS` + 按 id 精确 UPDATE；
回填行 rowcount=0 时**只告警不算失败**（任务可能已被删）。

## 两个库都要跑（否则 `tests/test_orm_db_drift.py` 红）

    用法（在 quantsys-v2/ 下）：
    PYTHONPATH=. ./venv/bin/python infrastructure/persistence/migrations/20261006_scheduler_tasks_trading_day_policy.py            # dry-run
    PYTHONPATH=. ./venv/bin/python infrastructure/persistence/migrations/20261006_scheduler_tasks_trading_day_policy.py --apply
    PYTHONPATH=. ./venv/bin/python infrastructure/persistence/migrations/20261006_scheduler_tasks_trading_day_policy.py --apply \\
        --dsn postgresql://mac@127.0.0.1:5432/quant_test
"""
import argparse
import os
import sys

from sqlalchemy import create_engine, text  # noqa: E402


def _engine(dsn: str | None = None):
    if dsn:
        return create_engine(dsn)
    url = os.environ.get('QUANT_DATABASE_URL') or 'postgresql+psycopg2:///quant_investment'
    return create_engine(url)


DDL = [
    "ALTER TABLE quant.scheduler_tasks ADD COLUMN IF NOT EXISTS "
    "trading_day_policy varchar(16) NOT NULL DEFAULT 'always'",
    "ALTER TABLE quant.scheduler_tasks "
    "DROP CONSTRAINT IF EXISTS scheduler_tasks_trading_day_policy_check",
    "ALTER TABLE quant.scheduler_tasks "
    "ADD CONSTRAINT scheduler_tasks_trading_day_policy_check "
    "CHECK (trading_day_policy IN ('always', 'trading-days', 'holidays'))",
    "COMMENT ON COLUMN quant.scheduler_tasks.trading_day_policy IS "
    "'交易日门策略: always=不判门 / trading-days=非交易日跳过 / holidays=只跳法定节假日"
    "（REQ-261006093620-a315）'",
]

#: 按 **id** 精确回填（不用 name 匹配：name 虽是 UNIQUE，但历史上有改名记录）。
#: 只列非缺省行——其余任务保持 DEFAULT 'always'，即行为与装门之前完全一致。
BACKFILL = {
    250: 'trading-days',  # pre-market-scan：真实选股打分，吃当日行情（本次实证的那一条）
    247: 'trading-days',  # daily-signal-generate：池内扫描出信号
    242: 'trading-days',  # 每日信号执行：推当日 pending 信号
    259: 'trading-days',  # daily-signal-push-fallback：同上（同一 handler）
    249: 'trading-days',  # v13-simulation-trading：模拟交易检查，休市无成交
    261: 'trading-days',  # chan-scan-daily：收盘后买卖点扫描，休市日重扫冻结快照
    237: 'trading-days',  # 每周报告生成（周五 18:00）：吃本周行情
    232: 'holidays',      # 每日数据质量检查（0 0 * * *，排班含周末）→ 需求 D-6 分档
}

VERIFY = ("select id, name, trading_day_policy from quant.scheduler_tasks "
          "where trading_day_policy <> 'always' order by id")
COUNTS = ("select trading_day_policy, count(*) from quant.scheduler_tasks "
          "group by 1 order by 1")


def main() -> int:
    ap = argparse.ArgumentParser(description='给 scheduler_tasks 加交易日门策略列')
    ap.add_argument('--apply', action='store_true', help='真正执行（默认仅 dry-run）')
    ap.add_argument('--dsn', default=None, help='覆盖 DSN（如测试库）')
    args = ap.parse_args()

    engine = _engine(args.dsn)
    with engine.begin() as conn:
        # 测试库 DDL 会被 `idle in transaction` 连接锁住 → 无上限的 DDL 会无限等锁
        # （CLAUDE.md 记过：漂移门禁曾因此让整套测试停在 78% 跑不完）。挂死要变响亮报错。
        conn.execute(text("SET LOCAL lock_timeout = '30s'"))

        have = {r[0] for r in conn.execute(text(
            "select column_name from information_schema.columns "
            "where table_schema = 'quant' and table_name = 'scheduler_tasks'"
        ))}
        if 'trading_day_policy' in have:
            print("[跳过] trading_day_policy 已存在（幂等）")
        elif not args.apply:
            for stmt in DDL:
                print(f"[dry-run] {stmt}")
            for tid, policy in sorted(BACKFILL.items()):
                print(f"[dry-run] 回填计划: id={tid} → {policy}")
            print("[dry-run] 未做任何写入。加 --apply 执行。")
            return 0
        else:
            for stmt in DDL:
                conn.execute(text(stmt))
                print(f"[apply] {stmt}")
            print("[apply] 列已创建（既有行按 DEFAULT 全部为 always）")

        if not args.apply:
            print("[dry-run] 未做任何写入。加 --apply 执行。")
            return 0

        for tid, policy in sorted(BACKFILL.items()):
            res = conn.execute(text(
                "update quant.scheduler_tasks set trading_day_policy = :p, updated_at = now() "
                "where id = :i and trading_day_policy is distinct from :p"
            ), {'p': policy, 'i': tid})
            if res.rowcount:
                print(f"[apply] 任务 {tid} → {policy}")
                continue
            exists = conn.execute(text(
                "select count(*) from quant.scheduler_tasks where id = :i"), {'i': tid}
            ).scalar()
            if not exists:
                print(f"[warn] 任务 {tid} 不存在（可能已删除）→ 跳过，不算失败")
            else:
                print(f"[跳过] 任务 {tid} 策略已是 {policy}（幂等）")

        rows = conn.execute(text(VERIFY)).fetchall()
        if not rows:
            # 空表不是错误：DDL 一样已应用（20261002 的老坑：空表上 row[0] 会 TypeError）
            print("[verify] 无「策略非 always」的行（表可能为空）；DDL 已应用")
        else:
            for r in rows:
                print(f"[verify] id={r[0]} name={r[1]!r} policy={r[2]}")
        for c in conn.execute(text(COUNTS)).fetchall():
            print(f"[count] {c[0]} = {c[1]}")

    print("[完成] trading_day_policy 已就位")
    return 0


if __name__ == '__main__':
    sys.exit(main())
