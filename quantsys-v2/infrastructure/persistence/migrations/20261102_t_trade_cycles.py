#!/usr/bin/env python
from __future__ import annotations

import argparse
import os

from sqlalchemy import create_engine, text

DEFAULT_SCHEMA = "quant"
TABLE = "t_trade_cycles"
TABLE_DDL = """CREATE TABLE IF NOT EXISTS {schema}.t_trade_cycles (
    id serial PRIMARY KEY,
    account varchar(60) NOT NULL,
    symbol varchar(20) NOT NULL,
    mode varchar(20) NOT NULL,
    status varchar(24) NOT NULL DEFAULT 'waiting_sell',
    upper_price numeric(15,4) NOT NULL,
    lower_price numeric(15,4) NOT NULL,
    shares integer NOT NULL,
    available_shares_at_creation integer NOT NULL,
    slippage_bps numeric(8,2) NOT NULL DEFAULT 10,
    expected_gross_pnl numeric(15,2) NOT NULL,
    expected_fees numeric(15,2) NOT NULL,
    expected_slippage_cost numeric(15,2) NOT NULL,
    expected_net_pnl numeric(15,2) NOT NULL,
    reason varchar(500) NOT NULL,
    invalidation text,
    sell_trade_id integer UNIQUE REFERENCES {schema}.simulation_trades(id),
    sell_price numeric(15,4),
    sell_commission numeric(15,2),
    sell_stamp_duty numeric(15,2),
    sell_transfer_fee numeric(15,2),
    sell_filled_at timestamp,
    buyback_trade_id integer UNIQUE REFERENCES {schema}.simulation_trades(id),
    buyback_price numeric(15,4),
    buyback_commission numeric(15,2),
    buyback_stamp_duty numeric(15,2),
    buyback_transfer_fee numeric(15,2),
    buyback_filled_at timestamp,
    gross_pnl numeric(15,2),
    total_fees numeric(15,2),
    net_pnl numeric(15,2),
    sell_rule_id integer,
    buyback_rule_id integer,
    cancel_reason text,
    rule_sync jsonb,
    lock_version integer NOT NULL DEFAULT 1,
    created_at timestamp NOT NULL DEFAULT now(),
    updated_at timestamp NOT NULL DEFAULT now(),
    completed_at timestamp,
    cancelled_at timestamp,
    CONSTRAINT chk_t_trade_cycles_range CHECK (upper_price > lower_price),
    CONSTRAINT chk_t_trade_cycles_shares CHECK (shares > 0 AND shares % 100 = 0),
    CONSTRAINT chk_t_trade_cycles_mode CHECK (mode IN ('remind_only','auto_sim')),
    CONSTRAINT chk_t_trade_cycles_status CHECK (
        status IN ('waiting_sell','waiting_buyback','completed','cancelled')
    )
)"""
INDEXES = (
    "CREATE INDEX IF NOT EXISTS idx_t_trade_cycles_account_status "
    "ON {schema}.t_trade_cycles(account, status)",
    "CREATE INDEX IF NOT EXISTS idx_t_trade_cycles_symbol "
    "ON {schema}.t_trade_cycles(symbol)",
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_t_trade_cycles_active_symbol "
    "ON {schema}.t_trade_cycles(account, symbol) "
    "WHERE status IN ('waiting_sell','waiting_buyback')",
)


def apply_migration(connection, schema: str = DEFAULT_SCHEMA) -> None:
    connection.execute(text(TABLE_DDL.format(schema=schema)))
    for ddl in INDEXES:
        connection.execute(text(ddl.format(schema=schema)))


def verify(connection, schema: str = DEFAULT_SCHEMA) -> None:
    row = connection.execute(
        text(
            "SELECT COUNT(*) FROM information_schema.columns "
            "WHERE table_schema=:schema AND table_name=:table"
        ),
        {"schema": schema, "table": TABLE},
    ).scalar_one()
    if row < 35:
        raise RuntimeError(f"t_trade_cycles 列数异常: {row}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--dsn")
    parser.add_argument("--schema", default=DEFAULT_SCHEMA)
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    if not args.apply:
        print(TABLE_DDL.format(schema=args.schema))
        for ddl in INDEXES:
            print(ddl.format(schema=args.schema) + ";")
        print("DRY-RUN done（--apply 生效）")
        return 0
    dsn = args.dsn or os.environ.get("QUANT_DATABASE_URL") or "postgresql+psycopg2:///quant_investment"
    engine = create_engine(dsn)
    with engine.begin() as connection:
        apply_migration(connection, args.schema)
    with engine.connect() as connection:
        verify(connection, args.schema)
    print("VERIFY OK: quant.t_trade_cycles")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
