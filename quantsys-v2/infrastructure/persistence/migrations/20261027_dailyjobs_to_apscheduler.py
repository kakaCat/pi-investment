#!/usr/bin/env python
"""Migrate the 11 legacy DailyJobs schedules to APScheduler (2026-10-27).

What it does:
1. Upserts one ``quant.scheduler_tasks`` row per legacy JobDef.
   Rows are created **disabled** so operators can deploy code before cutover.
2. Disables the old duplicate ``daily-pool-refresh`` APScheduler row; the
   migrated ``pool_daily_refresh`` row becomes the single stock-pool owner.
3. ``--activate`` enables the 11 migrated rows and computes next_run_at.
4. ``--rollback`` disables the migrated rows and re-enables the old pool row.

The business handlers are unchanged: the bridge in
``daily_jobs/apscheduler_bridge.py`` maps command -> original callable.

Usage (repo root, quantsys-v2 venv):
    PYTHONPATH=. ./venv/bin/python \
      infrastructure/persistence/migrations/20261027_dailyjobs_to_apscheduler.py --apply
    PYTHONPATH=. ./venv/bin/python \
      infrastructure/persistence/migrations/20261027_dailyjobs_to_apscheduler.py --activate

After --activate, call POST /api/scheduler/reload or restart the service.
"""
from __future__ import annotations

import argparse
import json
from typing import Any, Dict, Optional

from sqlalchemy import text

from adapters.inbound.fastapi_app.daily_jobs.apscheduler_bridge import DAILY_TASK_SPECS
from infrastructure.scheduler.scheduler import next_run_time

MIGRATION_ID = "20261027_dailyjobs_to_apscheduler"
POOL_DUPLICATE_NAME = "daily-pool-refresh"
NEW_NAMES = tuple(spec.job_id for spec in DAILY_TASK_SPECS)

INSERT_TASK = text("""
INSERT INTO quant.scheduler_tasks
    (name, description, cron_expression, command, params, is_enabled,
     task_type, executor_type, misfire_grace_time_seconds, domain)
VALUES
    (:name, :description, :cron_expression, :command, CAST(:params AS jsonb), false,
     :task_type, 'system', :misfire_grace_time_seconds, :domain)
ON CONFLICT (name) DO UPDATE SET
    description = EXCLUDED.description,
    cron_expression = EXCLUDED.cron_expression,
    command = EXCLUDED.command,
    task_type = EXCLUDED.task_type,
    executor_type = EXCLUDED.executor_type,
    misfire_grace_time_seconds = EXCLUDED.misfire_grace_time_seconds,
    domain = EXCLUDED.domain,
    updated_at = now()
""")

DISABLE_POOL_DUPLICATE = text("""
UPDATE quant.scheduler_tasks
SET is_enabled = false,
    params = COALESCE(params, '{}'::jsonb) || CAST(:params AS jsonb),
    updated_at = now()
WHERE name = :name
""")


def _engine(dsn: str | None = None):
    if dsn:
        from sqlalchemy import create_engine
        return create_engine(dsn)
    from qs_kernel.infrastructure.persistence.database.engine import get_engine
    return get_engine()


def _spec_params(spec) -> Dict[str, Any]:
    return {
        **(spec.params or {}),
        "_migrated_from": "daily_jobs",
        "_migration": MIGRATION_ID,
    }


def _apply(conn) -> None:
    for spec in DAILY_TASK_SPECS:
        conn.execute(INSERT_TASK, {
            "name": spec.job_id,
            "description": spec.description,
            "cron_expression": spec.cron_expression,
            "command": spec.job_id,
            "params": json.dumps(_spec_params(spec), ensure_ascii=False),
            "task_type": spec.task_type,
            "misfire_grace_time_seconds": spec.misfire_grace_time_seconds,
            "domain": spec.domain,
        })
        print(f"APPLY task {spec.job_id}: {spec.cron_expression} (disabled)")

    old = conn.execute(text("""
        SELECT id, is_enabled, params
        FROM quant.scheduler_tasks
        WHERE name = :name
    """), {"name": POOL_DUPLICATE_NAME}).mappings().first()
    if old is None:
        print(f"WARN duplicate pool task not found: {POOL_DUPLICATE_NAME}")
        return

    marker = {"_disabled_by": MIGRATION_ID,
              "_replacement": "pool_daily_refresh"}
    conn.execute(DISABLE_POOL_DUPLICATE, {
        "name": POOL_DUPLICATE_NAME,
        "params": json.dumps(marker, ensure_ascii=False),
    })
    print(
        f"APPLY duplicate {POOL_DUPLICATE_NAME} id={old['id']}: "
        f"enabled {old['is_enabled']} -> false"
    )


def _activate(conn) -> None:
    for spec in DAILY_TASK_SPECS:
        nxt = next_run_time(spec.cron_expression)
        conn.execute(text("""
            UPDATE quant.scheduler_tasks
            SET is_enabled = true,
                next_run_at = :next_run_at,
                updated_at = now()
            WHERE name = :name
        """), {
            "name": spec.job_id,
            "next_run_at": nxt,
        })
        print(f"ACTIVATE task {spec.job_id}: next={nxt.isoformat()}")


def _rollback(conn) -> None:
    for spec in DAILY_TASK_SPECS:
        conn.execute(text("""
            UPDATE quant.scheduler_tasks
            SET is_enabled = false, updated_at = now()
            WHERE name = :name
        """), {"name": spec.job_id})
        print(f"ROLLBACK task {spec.job_id}: disabled")

    old = conn.execute(text("""
        SELECT id, params
        FROM quant.scheduler_tasks
        WHERE name = :name
    """), {"name": POOL_DUPLICATE_NAME}).mappings().first()
    if old is None:
        return
    params = old.get("params") or {}
    if isinstance(params, str):
        try:
            params = json.loads(params)
        except json.JSONDecodeError:
            params = {}
    if params.get("_disabled_by") != MIGRATION_ID:
        print(f"ROLLBACK {POOL_DUPLICATE_NAME}: not disabled by this migration, skipped")
        return
    new_params = {k: v for k, v in params.items()
                  if k not in {"_disabled_by", "_replacement"}}
    conn.execute(text("""
        UPDATE quant.scheduler_tasks
        SET is_enabled = true,
            params = CAST(:params AS jsonb),
            updated_at = now()
        WHERE name = :name
    """), {
        "name": POOL_DUPLICATE_NAME,
        "params": json.dumps(new_params, ensure_ascii=False),
    })
    print(f"ROLLBACK {POOL_DUPLICATE_NAME}: re-enabled")


def _verify(conn, expect_enabled: Optional[bool]) -> bool:
    rows = conn.execute(text("""
        SELECT name, cron_expression, command, is_enabled, domain,
               misfire_grace_time_seconds
        FROM quant.scheduler_tasks
        WHERE name = ANY(:names)
        ORDER BY name
    """), {"names": list(NEW_NAMES)}).mappings().all()
    found = {row["name"]: row for row in rows}
    missing = [name for name in NEW_NAMES if name not in found]
    wrong = [
        name for name in NEW_NAMES
        if name in found and (
            found[name]["command"] != name
            or not found[name]["domain"]
            or not found[name]["misfire_grace_time_seconds"]
            or (expect_enabled is not None
                and bool(found[name]["is_enabled"]) != expect_enabled)
        )
    ]
    old = conn.execute(text("""
        SELECT is_enabled FROM quant.scheduler_tasks
        WHERE name = :name
    """), {"name": POOL_DUPLICATE_NAME}).scalar()
    print(f"VERIFY migrated={len(found)}/{len(NEW_NAMES)} missing={missing} wrong={wrong}")
    print(f"VERIFY {POOL_DUPLICATE_NAME} enabled={old}")
    ok = not missing and not wrong
    if expect_enabled and old:
        print("VERIFY FAILED: duplicate pool task is still enabled")
        ok = False
    return ok


def main() -> int:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--apply", action="store_true")
    group.add_argument("--activate", action="store_true")
    group.add_argument("--rollback", action="store_true")
    parser.add_argument("--dsn")
    args = parser.parse_args()

    eng = _engine(args.dsn)
    mode = "DRY"
    if args.apply:
        mode = "APPLY"
    elif args.activate:
        mode = "ACTIVATE"
    elif args.rollback:
        mode = "ROLLBACK"
    print(f"{mode} {MIGRATION_ID}: {len(NEW_NAMES)} tasks")

    with eng.begin() as conn:
        if args.apply:
            _apply(conn)
        elif args.activate:
            _activate(conn)
        elif args.rollback:
            _rollback(conn)

    if args.apply:
        with eng.connect() as conn:
            return 0 if _verify(conn, expect_enabled=None) else 2
    if args.activate:
        with eng.connect() as conn:
            return 0 if _verify(conn, expect_enabled=True) else 2
    if not (args.activate or args.rollback or args.apply):
        print("DRY-RUN done（--apply / --activate / --rollback 才写库）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
