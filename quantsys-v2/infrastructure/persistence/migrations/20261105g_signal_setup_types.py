#!/usr/bin/env python
"""计划项交易场景 setup_type（REQ-261026140857-c192）

为 trading_plan_item_versions 增加 setup_type，区分 breakout/pullback/trend_follow/
mean_reversion/risk_off/event_driven 等业务场景，便于计划生成、审计和复盘。

默认 dry-run；--apply 写库；支持 --dsn 指向 quant_test。
"""
from __future__ import annotations

import argparse
from typing import Optional, Sequence

from sqlalchemy import create_engine, text

SCHEMA = "quant"
TABLE = "trading_plan_item_versions"
COLUMN = "setup_type"


def _engine(dsn: Optional[str]):
    if dsn:
        return create_engine(dsn)
    from qs_kernel.infrastructure.persistence.database.engine import get_engine

    return get_engine()


def _column_exists(conn) -> bool:
    return bool(
        conn.execute(
            text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_schema=:s AND table_name=:t AND column_name=:c"
            ),
            {"s": SCHEMA, "t": TABLE, "c": COLUMN},
        ).scalar()
    )


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--dsn", default=None)
    args = parser.parse_args(argv)
    eng = _engine(args.dsn)
    with eng.begin() as conn:
        exists = _column_exists(conn)
        print(
            "%s setup_type: %s"
            % ("APPLY" if args.apply else "DRY", "exists" if exists else "would-add")
        )
        if args.apply and not exists:
            conn.execute(
                text(
                    "ALTER TABLE quant.trading_plan_item_versions "
                    "ADD COLUMN IF NOT EXISTS setup_type varchar(32)"
                )
            )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_trading_plan_item_versions_setup_type "
                "ON quant.trading_plan_item_versions (setup_type)"
            )
            if args.apply
            else text("SELECT 1")
        )
    if args.apply:
        with eng.connect() as conn:
            assert _column_exists(conn)
            assert conn.execute(
                text(
                    "SELECT 1 FROM pg_indexes WHERE schemaname='quant' "
                    "AND tablename='trading_plan_item_versions' "
                    "AND indexname='idx_trading_plan_item_versions_setup_type'"
                )
            ).scalar()
        print("VERIFY OK: setup_type")
    else:
        print("DRY-RUN done（--apply 才写库）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
