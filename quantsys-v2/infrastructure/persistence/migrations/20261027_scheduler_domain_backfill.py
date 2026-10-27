#!/usr/bin/env python
"""Backfill six-domain labels for enabled scheduler tasks (2026-10-27).

The scheduler itself does not require ``domain`` to execute, but the V2 health
check treats enabled tasks without a domain as degraded. This migration is
idempotent: it only fills NULL domains, never overwrites an existing label.

Default is dry-run; use --apply to write.
"""
from __future__ import annotations

import argparse

from sqlalchemy import text

from infrastructure.scheduler.task_fields import SCHEDULER_DOMAINS

# command -> canonical six-domain label
DOMAIN_BY_COMMAND = {
    "data_update": "data",
    "weekly_profit_report": "report",
    "plan_reflect_daily": "analysis",
    "plan_reflect_weekly": "analysis",
    "watch_scan_30s": "signal",
    "watch_scan_10m": "signal",
    "watch_scan_30m": "signal",
    "opportunity_scan_daily": "signal",
    "trading_plan_generate_daily": "trading",
    "trading_plan_readiness": "trading",
    "watch_open_am": "signal",
    "watch_open_pm": "signal",
    "v13_risk_check": "trading",
    "v13_verification": "trading",
    "v14_daily_check": "trading",
    "v13_weekly_report": "report",
    "financial_statement_update": "data",
}

SELECT_NULL = text("""
    SELECT id, name, command
    FROM quant.scheduler_tasks
    WHERE is_enabled = true AND domain IS NULL
    ORDER BY id
""")

UPDATE_DOMAIN = text("""
    UPDATE quant.scheduler_tasks
    SET domain = :domain, updated_at = now()
    WHERE id = :task_id AND is_enabled = true AND domain IS NULL
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

    assert set(DOMAIN_BY_COMMAND.values()) <= set(SCHEDULER_DOMAINS)
    eng = _engine(args.dsn)
    with eng.begin() as conn:
        rows = conn.execute(SELECT_NULL).mappings().all()
        print(f"{'APPLY' if args.apply else 'DRY'} domain_backfill: {len(rows)} enabled NULL")
        missing = []
        for row in rows:
            domain = DOMAIN_BY_COMMAND.get(row["command"])
            if domain is None:
                missing.append(dict(row))
                continue
            print(f"  {row['id']} {row['name']} -> {domain}")
            if args.apply:
                conn.execute(UPDATE_DOMAIN, {"task_id": row["id"], "domain": domain})
        if missing:
            print(f"UNMAPPED enabled tasks: {missing}")
            return 2

    if args.apply:
        with eng.connect() as conn:
            remaining = conn.execute(SELECT_NULL).mappings().all()
            if remaining:
                print(f"VERIFY FAILED: still NULL: {[dict(r) for r in remaining]}")
                return 2
            print("VERIFY OK: no enabled task has domain NULL")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
