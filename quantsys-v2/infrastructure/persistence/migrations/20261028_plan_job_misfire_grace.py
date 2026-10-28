#!/usr/bin/env python
"""Set a realistic misfire grace for account trading-plan jobs (2026-10-28).

The replacement plan tasks were inserted without ``misfire_grace_time_seconds``
so APScheduler used its 5-minute default. On 2026-10-28 the host resumed at
09:25:47 after sleep; the 09:05 job was already 20m47s late and the 09:20 job
5m47s late, so both were silently skipped.

This migration is idempotent and only touches the two named tasks.
"""
from __future__ import annotations

import argparse

from sqlalchemy import text

NAMES = ("trading_plan_generate_daily", "trading_plan_readiness")
GRACE_SECONDS = 6 * 60 * 60

UPDATE = text("""
    UPDATE quant.scheduler_tasks
    SET misfire_grace_time_seconds = :grace, updated_at = now()
    WHERE name = :name
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
        rows = conn.execute(text("""
            SELECT id, name, misfire_grace_time_seconds
            FROM quant.scheduler_tasks
            WHERE name = ANY(:names) ORDER BY id
        """), {"names": list(NAMES)}).mappings().all()
        found = {row["name"]: row for row in rows}
        missing = [name for name in NAMES if name not in found]
        if missing:
            print(f"VERIFY FAILED: missing tasks {missing}")
            return 2
        for name in NAMES:
            print(
                f"{'APPLY' if args.apply else 'DRY'} {name}: "
                f"{found[name]['misfire_grace_time_seconds']} -> {GRACE_SECONDS}"
            )
            if args.apply:
                conn.execute(UPDATE, {"name": name, "grace": GRACE_SECONDS})

    if args.apply:
        with eng.connect() as conn:
            values = dict(conn.execute(text("""
                SELECT name, misfire_grace_time_seconds
                FROM quant.scheduler_tasks WHERE name = ANY(:names)
            """), {"names": list(NAMES)}).all())
            if any(values.get(name) != GRACE_SECONDS for name in NAMES):
                print(f"VERIFY FAILED: {values}")
                return 2
            print(f"VERIFY OK: {values}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
