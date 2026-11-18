#!/usr/bin/env python
"""扩展账户计划信号类型与失效阈值（REQ-261026140857-c192）

- trading_plan_conditions.role 支持 add_position/trend_observe/exit_reduce
- trading_plan_item_versions.action 支持 add/observe/reduce_risk
- trading_plan_conditions 增加 invalidation_threshold_pct
- watch_rules.invalidation_threshold_pct 若缺失则补齐

默认 dry-run；--apply 写库；支持 --dsn 指向 quant_test。
"""
from __future__ import annotations

import argparse
from typing import Optional, Sequence

from sqlalchemy import create_engine, text

SCHEMA = "quant"
CONDITIONS = "trading_plan_conditions"
ITEM_VERSIONS = "trading_plan_item_versions"
WATCH_RULES = "watch_rules"
NEW_COLUMN = ("trading_plan_conditions", "invalidation_threshold_pct", "numeric(6,2)")

CHECKS = (
    (
        CONDITIONS,
        "chk_trading_plan_conditions_role",
        "CHECK (role IN ('entry','add_position','trend_observe','stop_loss','reduce','exit_reduce'))",
        ("add_position", "trend_observe", "exit_reduce"),
    ),
    (
        ITEM_VERSIONS,
        "chk_trading_plan_item_versions_action",
        "CHECK (action IN ('buy','add','observe','sell','reduce_risk','hold','avoid'))",
        ("add", "observe", "reduce_risk"),
    ),
)


def _engine(dsn: Optional[str]):
    if dsn:
        return create_engine(dsn)
    from qs_kernel.infrastructure.persistence.database.engine import get_engine

    return get_engine()


def _column_exists(conn, table: str, column: str) -> bool:
    return bool(
        conn.execute(
            text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_schema=:s AND table_name=:t AND column_name=:c"
            ),
            {"s": SCHEMA, "t": table, "c": column},
        ).scalar()
    )


def _constraint_def(conn, table: str, name: str) -> str:
    return (
        conn.execute(
            text(
                "SELECT pg_get_constraintdef(c.oid) FROM pg_constraint c "
                "JOIN pg_class t ON t.oid=c.conrelid "
                "JOIN pg_namespace n ON n.oid=t.relnamespace "
                "WHERE n.nspname=:s AND t.relname=:t AND c.conname=:name"
            ),
            {"s": SCHEMA, "t": table, "name": name},
        ).scalar()
        or ""
    )


def apply_migration(conn, *, apply: bool = False) -> dict:
    changes = []
    table, column, ddl = NEW_COLUMN
    if not _column_exists(conn, table, column):
        changes.append("add column %s.%s" % (table, column))
        if apply:
            conn.execute(
                text("ALTER TABLE quant.%s ADD COLUMN IF NOT EXISTS %s %s" % (table, column, ddl))
            )
    for table, name, definition, keywords in CHECKS:
        current = _constraint_def(conn, table, name)
        if all(keyword in current for keyword in keywords):
            continue
        changes.append("replace constraint %s.%s" % (table, name))
        if apply:
            conn.execute(text("ALTER TABLE quant.%s DROP CONSTRAINT IF EXISTS %s" % (table, name)))
            conn.execute(
                text("ALTER TABLE quant.%s ADD CONSTRAINT %s %s" % (table, name, definition))
            )
    if not _column_exists(conn, WATCH_RULES, "invalidation_threshold_pct"):
        changes.append("add column watch_rules.invalidation_threshold_pct")
        if apply:
            conn.execute(
                text(
                    "ALTER TABLE quant.watch_rules ADD COLUMN IF NOT EXISTS "
                    "invalidation_threshold_pct numeric(6,2)"
                )
            )
    return {"changes": changes}


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--dsn", default=None)
    args = parser.parse_args(argv)
    eng = _engine(args.dsn)
    with eng.begin() as conn:
        report = apply_migration(conn, apply=args.apply)
        print("%s changes=%d" % ("APPLY" if args.apply else "DRY", len(report["changes"])))
        for change in report["changes"]:
            print(change)
    if args.apply:
        with eng.connect() as conn:
            assert _column_exists(conn, CONDITIONS, "invalidation_threshold_pct")
            assert _column_exists(conn, WATCH_RULES, "invalidation_threshold_pct")
            for table, name, _definition, keywords in CHECKS:
                current = _constraint_def(conn, table, name)
                assert all(keyword in current for keyword in keywords), (table, name, current)
        print("VERIFY OK: signal types and invalidation thresholds")
    else:
        print("DRY-RUN done（--apply 才写库）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
