#!/usr/bin/env python
"""计划项执行批次与追高上限字段。

默认 dry-run；--apply 写库；支持 --dsn 指向 quant_test。
"""
from __future__ import annotations

import argparse
from typing import Optional, Sequence

from sqlalchemy import create_engine, text

COLUMNS = {
    "execution_batch": "integer",
    "max_chase_pct": "numeric(6,3)",
}


def _engine(dsn: Optional[str]):
    if dsn:
        return create_engine(dsn)
    from qs_kernel.infrastructure.persistence.database.engine import get_engine

    return get_engine()


def _column_exists(conn, column: str) -> bool:
    return bool(
        conn.execute(
            text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_schema='quant' AND table_name='trading_plan_item_versions' "
                "AND column_name=:column"
            ),
            {"column": column},
        ).scalar()
    )


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--dsn", default=None)
    args = parser.parse_args(argv)
    eng = _engine(args.dsn)
    with eng.begin() as conn:
        for column, ddl in COLUMNS.items():
            exists = _column_exists(conn, column)
            print("%s %s: %s" % ("APPLY" if args.apply else "DRY", column, "exists" if exists else "would-add"))
            if args.apply and not exists:
                conn.execute(
                    text(
                        "ALTER TABLE quant.trading_plan_item_versions "
                        "ADD COLUMN IF NOT EXISTS %s %s" % (column, ddl)
                    )
                )
        if args.apply:
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_trading_plan_item_versions_execution_batch "
                    "ON quant.trading_plan_item_versions (execution_batch)"
                )
            )
    if args.apply:
        with eng.connect() as conn:
            assert all(_column_exists(conn, column) for column in COLUMNS)
        print("VERIFY OK: execution_batch, max_chase_pct")
    else:
        print("DRY-RUN done（--apply 才写库）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
