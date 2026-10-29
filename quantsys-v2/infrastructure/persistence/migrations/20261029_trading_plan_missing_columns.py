#!/usr/bin/env python
"""Add trading-plan columns missing from production (2026-10-29).

ORM expects:
- trading_plan_item_versions.setup_type
- trading_plan_conditions.invalidation_threshold_pct

Both are nullable, so adding them is online-safe and does not rewrite rows.
The 2026-10-29 09:05 plan generation failed on the first missing column before
business logic could run; this migration makes the schema match the model.
"""
from __future__ import annotations

import argparse

from sqlalchemy import text

STATEMENTS = (
    (
        "trading_plan_item_versions.setup_type",
        "ALTER TABLE quant.trading_plan_item_versions "
        "ADD COLUMN IF NOT EXISTS setup_type VARCHAR(32)",
    ),
    (
        "trading_plan_conditions.invalidation_threshold_pct",
        "ALTER TABLE quant.trading_plan_conditions "
        "ADD COLUMN IF NOT EXISTS invalidation_threshold_pct NUMERIC(6, 2)",
    ),
)

VERIFY = text("""
    SELECT table_name, column_name
    FROM information_schema.columns
    WHERE table_schema = 'quant'
      AND (
        (table_name = 'trading_plan_item_versions' AND column_name = 'setup_type')
        OR (table_name = 'trading_plan_conditions' AND column_name = 'invalidation_threshold_pct')
      )
""")


def _engine(dsn: str | None = None):
    if dsn:
        from sqlalchemy import create_engine
        return create_engine(dsn)
    from qs_kernel.infrastructure.persistence.database.engine import get_engine
    return get_engine()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--dsn")
    args = parser.parse_args()

    eng = _engine(args.dsn)
    with eng.begin() as conn:
        for label, sql in STATEMENTS:
            print(f"{'APPLY' if args.apply else 'DRY'} {label}")
            if args.apply:
                conn.execute(text(sql))

    if args.apply:
        with eng.connect() as conn:
            found = {(r[0], r[1]) for r in conn.execute(VERIFY).all()}
            expected = {
                ("trading_plan_item_versions", "setup_type"),
                ("trading_plan_conditions", "invalidation_threshold_pct"),
            }
            if found != expected:
                print(f"VERIFY FAILED: missing {expected - found}")
                return 2
            print("VERIFY OK: trading plan columns present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
