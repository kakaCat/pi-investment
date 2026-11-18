#!/usr/bin/env python
"""账户级交易计划调度任务（REQ-261026140857-c192）

向 quant.scheduler_tasks 注册：
- trading_plan_generate_daily：工作日 09:05 生成 draft revision
- trading_plan_readiness：工作日 09:20 readiness/运行时对账

旧 core_plan_generate 生产任务已退出，迁移时若存在则禁用。
默认 dry-run；--apply 写库；支持 --dsn 指向 quant_test。
"""
import argparse
import sys

from sqlalchemy import text

from qs_kernel.infrastructure.persistence.database.engine import get_engine

ROWS = (
    (
        "trading_plan_generate_daily",
        "账户级交易计划每日生成：组合决策 + 持仓合并 + draft revision 落库",
        "5 9 * * 1-5",
        "trading_plan_generate_daily",
    ),
    (
        "trading_plan_readiness",
        "账户级交易计划盘前 readiness：规则、持仓与执行就绪检查",
        "20 9 * * 1-5",
        "trading_plan_readiness",
    ),
)
LEGACY_TASK = "core_plan_generate"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--dsn", default=None)
    args = ap.parse_args()
    eng = get_engine()
    if args.dsn:
        from sqlalchemy import create_engine

        eng = create_engine(args.dsn)
    with eng.begin() as conn:
        for name, desc, cron, command in ROWS:
            exists = conn.execute(
                text("SELECT 1 FROM quant.scheduler_tasks WHERE name=:n"), {"n": name}
            ).scalar()
            print(
                ("DRY   " if not args.apply else "APPLY ")
                + ("exists" if exists else "would-insert")
                + " "
                + name
            )
            if args.apply and not exists:
                conn.execute(
                    text(
                        "INSERT INTO quant.scheduler_tasks "
                        "(name, description, cron_expression, command, params, is_enabled) "
                        "VALUES (:n, :d, :c, :cmd, '{}'::jsonb, true)"
                    ),
                    {"n": name, "d": desc, "c": cron, "cmd": command},
                )
        old = conn.execute(
            text("SELECT id, is_enabled FROM quant.scheduler_tasks WHERE name=:n"),
            {"n": LEGACY_TASK},
        ).first()
        print(
            ("DRY   " if not args.apply else "APPLY ")
            + ("would-disable" if old and old[1] else "already-absent-or-disabled")
            + " "
            + LEGACY_TASK
        )
        if args.apply and old and old[1]:
            conn.execute(
                text("UPDATE quant.scheduler_tasks SET is_enabled=false WHERE name=:n"),
                {"n": LEGACY_TASK},
            )
    if args.apply:
        with eng.connect() as conn:
            for name, _desc, cron, command in ROWS:
                row = conn.execute(
                    text(
                        "SELECT cron_expression, command, is_enabled "
                        "FROM quant.scheduler_tasks WHERE name=:n"
                    ),
                    {"n": name},
                ).first()
                if not row or row[0] != cron or row[1] != command or not row[2]:
                    print("VERIFY FAILED: %s" % name)
                    return 2
            old = conn.execute(
                text("SELECT is_enabled FROM quant.scheduler_tasks WHERE name=:n"),
                {"n": LEGACY_TASK},
            ).scalar()
            if old:
                print("VERIFY FAILED: legacy core_plan_generate 仍启用")
                return 2
            print("VERIFY OK: account trading plan tasks registered; legacy disabled")
        return 0
    print("DRY-RUN done（--apply 才写库）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
