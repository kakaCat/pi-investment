#!/usr/bin/env python3
"""
Dry-run-first SQLite -> PostgreSQL migration helper for the quant database.

Default mode only compares row counts. Use --execute to copy data. Use
--symbol-limit for a relationally consistent smoke migration before attempting
the full 5.5GB local SQLite DB.
"""
from __future__ import annotations

import argparse
import sqlite3
import subprocess
import sys
from collections.abc import Iterable
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SQLITE = ROOT / ".pi-invest" / "stock-db" / "stocks.db"
DEFAULT_PG_DB = "quant_investment"


TABLES = {
    "stocks": {
        "sqlite": "stocks",
        "pg": "quant.stocks",
        "pk": ["symbol"],
        "columns": [
            "symbol", "name", "market", "industry", "sector", "market_cap", "pe", "pb",
            "total_mv", "circulating_mv", "is_st", "is_suspended", "list_date", "roe",
            "net_profit_growth", "gross_margin", "debt_ratio", "avg_turnover_rate",
            "avg_volume", "avg_amount", "updated_at",
        ],
        "select": """
            SELECT symbol, name, market, industry, sector, market_cap, pe, pb,
                   total_mv, circulating_mv, is_st, is_suspended, list_date, roe,
                   net_profit_growth, gross_margin, debt_ratio, avg_turnover_rate,
                   avg_volume, avg_amount, updated_at
            FROM stocks
        """,
    },
    "daily_klines": {
        "sqlite": "daily_klines",
        "pg": "quant.daily_klines",
        "pk": ["symbol", "trade_date"],
        "date_columns": ["trade_date"],
        "columns": [
            "symbol", "trade_date", "open", "high", "low", "close", "volume",
            "amount", "turnover_rate",
        ],
        "select": """
            SELECT symbol, trade_date, open, high, low, close, volume, amount, turnover_rate
            FROM (
              SELECT
                dk.symbol,
                CASE
                  WHEN length(dk.date) = 8 AND dk.date GLOB '[0-9]*'
                    THEN substr(dk.date, 1, 4) || '-' || substr(dk.date, 5, 2) || '-' || substr(dk.date, 7, 2)
                  ELSE substr(dk.date, 1, 10)
                END AS trade_date,
                dk.open, dk.high, dk.low, dk.close, dk.volume, dk.amount, dk.turnover_rate,
                ROW_NUMBER() OVER (
                  PARTITION BY dk.symbol,
                    CASE
                      WHEN length(dk.date) = 8 AND dk.date GLOB '[0-9]*'
                        THEN substr(dk.date, 1, 4) || '-' || substr(dk.date, 5, 2) || '-' || substr(dk.date, 7, 2)
                      ELSE substr(dk.date, 1, 10)
                    END
                  ORDER BY dk.date
                ) AS rn
              FROM daily_klines dk
              INNER JOIN stocks s ON s.symbol = dk.symbol
            )
            WHERE rn = 1
        """,
    },
    "minute_klines": {
        "sqlite": "minute_klines",
        "pg": "quant.minute_klines",
        "pk": ["symbol", "ts"],
        "columns": ["symbol", "ts", "open", "high", "low", "close", "volume", "amount"],
        "select": """
            SELECT symbol, timestamp AS ts, open, high, low, close, volume, amount
            FROM minute_klines
        """,
    },
    "daily_quotes": {
        "sqlite": "daily_quotes",
        "pg": "quant.daily_quotes",
        "pk": ["symbol", "quote_date"],
        "date_columns": ["quote_date"],
        "columns": ["symbol", "quote_date", "close", "volume", "amount", "turnover_rate"],
        "select": """
            SELECT symbol, quote_date, close, volume, amount, turnover_rate
            FROM (
              SELECT
                dq.symbol,
                CASE
                  WHEN length(dq.date) = 8 AND dq.date GLOB '[0-9]*'
                    THEN substr(dq.date, 1, 4) || '-' || substr(dq.date, 5, 2) || '-' || substr(dq.date, 7, 2)
                  ELSE substr(dq.date, 1, 10)
                END AS quote_date,
                dq.close, dq.volume, dq.amount, dq.turnover_rate,
                ROW_NUMBER() OVER (
                  PARTITION BY dq.symbol,
                    CASE
                      WHEN length(dq.date) = 8 AND dq.date GLOB '[0-9]*'
                        THEN substr(dq.date, 1, 4) || '-' || substr(dq.date, 5, 2) || '-' || substr(dq.date, 7, 2)
                      ELSE substr(dq.date, 1, 10)
                    END
                  ORDER BY dq.date
                ) AS rn
              FROM daily_quotes dq
              INNER JOIN stocks s ON s.symbol = dq.symbol
            )
            WHERE rn = 1
        """,
    },
    "factor_values": {
        "sqlite": "factor_values",
        "pg": "quant.factor_values",
        "pk": ["symbol", "factor_date", "factor_name"],
        "date_columns": ["factor_date"],
        "columns": ["symbol", "factor_date", "factor_name", "factor_value"],
        "select": """
            SELECT symbol, factor_date, factor_name, factor_value
            FROM (
              SELECT
                fv.symbol,
                CASE
                  WHEN length(fv.date) = 8 AND fv.date GLOB '[0-9]*'
                    THEN substr(fv.date, 1, 4) || '-' || substr(fv.date, 5, 2) || '-' || substr(fv.date, 7, 2)
                  ELSE substr(fv.date, 1, 10)
                END AS factor_date,
                fv.factor_name, fv.factor_value,
                ROW_NUMBER() OVER (
                  PARTITION BY fv.symbol,
                    CASE
                      WHEN length(fv.date) = 8 AND fv.date GLOB '[0-9]*'
                        THEN substr(fv.date, 1, 4) || '-' || substr(fv.date, 5, 2) || '-' || substr(fv.date, 7, 2)
                      ELSE substr(fv.date, 1, 10)
                    END,
                    fv.factor_name
                  ORDER BY fv.date
                ) AS rn
              FROM factor_values fv
              INNER JOIN stocks s ON s.symbol = fv.symbol
            )
            WHERE rn = 1
        """,
    },
    "signals": {
        "sqlite": "signals",
        "pg": "quant.signals",
        "pk": ["id"],
        "date_columns": ["signal_date"],
        "columns": [
            "id", "signal_date", "symbol", "name", "action", "action_type",
            "strategy_id", "price", "reason", "confidence", "indicators", "created_at",
        ],
        "select": """
            SELECT id,
                   CASE
                     WHEN length(date) = 8 AND date GLOB '[0-9]*'
                       THEN substr(date, 1, 4) || '-' || substr(date, 5, 2) || '-' || substr(date, 7, 2)
                     ELSE substr(date, 1, 10)
                   END AS signal_date,
                   symbol, name, action, action_type, strategy_id, price,
                   reason, confidence, indicators, created_at
            FROM signals
        """,
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sqlite", default=str(DEFAULT_SQLITE), help="SQLite source path")
    parser.add_argument("--pg-db", default=DEFAULT_PG_DB, help="PostgreSQL database name")
    parser.add_argument("--table", choices=sorted(TABLES), action="append", help="Table to process")
    parser.add_argument("--limit", type=int, help="Limit rows per table for low-level debugging")
    parser.add_argument(
        "--symbol-limit",
        type=int,
        help="Limit migration to the first N stock symbols and related rows",
    )
    parser.add_argument("--execute", action="store_true", help="Copy rows into PostgreSQL")
    parser.add_argument("--truncate", action="store_true", help="Truncate target tables before --execute")
    parser.add_argument("--batch-size", type=int, default=50_000, help="COPY batch size for --execute")
    return parser.parse_args()


def normalize_date_value(value: object) -> object:
    if value is None:
        return None
    text = str(value).strip()
    if len(text) >= 10 and text[4] == "-" and text[7] == "-":
        return text[:10]
    if len(text) == 8 and text.isdigit():
        return f"{text[:4]}-{text[4:6]}-{text[6:8]}"
    return text


def normalize_row(spec: dict, row: sqlite3.Row) -> dict[str, object]:
    values = {column: row[column] for column in spec["columns"]}
    for column in spec.get("date_columns", []):
        values[column] = normalize_date_value(values[column])
    return values


def quote_copy_value(value: object) -> str:
    if value is None:
        return r"\N"
    text = str(value)
    return text.replace("\\", "\\\\").replace("\t", "\\t").replace("\n", "\\n").replace("\r", "\\r")


def run_psql(pg_db: str, sql: str, input_text: str | None = None) -> str:
    command = ["psql", "-X", "-v", "ON_ERROR_STOP=1", "-At", pg_db, "-c", sql]
    result = subprocess.run(
        command,
        input=input_text,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    return result.stdout.strip()


def sqlite_count(conn: sqlite3.Connection, table: str) -> int:
    return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


def pg_count(pg_db: str, table: str) -> int:
    output = run_psql(pg_db, f"SELECT COUNT(*) FROM {table};")
    return int(output or "0")


def select_symbols(conn: sqlite3.Connection, limit: int | None) -> list[str] | None:
    if limit is None:
        return None
    rows = conn.execute(
        "SELECT symbol FROM stocks ORDER BY symbol LIMIT ?",
        (int(limit),),
    ).fetchall()
    return [str(row[0]) for row in rows]


def add_symbol_filter(query: str, symbols: list[str] | None) -> tuple[str, list[str]]:
    if symbols is None:
        return query.strip(), []
    if not symbols:
        return f"SELECT * FROM ({query.strip()}) AS source WHERE 1 = 0", []
    placeholders = ", ".join("?" for _ in symbols)
    return (
        f"SELECT * FROM ({query.strip()}) AS source WHERE symbol IN ({placeholders})",
        symbols,
    )


def iter_rows(
    conn: sqlite3.Connection,
    query: str,
    limit: int | None,
    symbols: list[str] | None,
) -> Iterable[sqlite3.Row]:
    sql, params = add_symbol_filter(query, symbols)
    if limit is not None:
      sql += f" LIMIT {int(limit)}"
    yield from conn.execute(sql, params)


def copy_table(
    conn: sqlite3.Connection,
    pg_db: str,
    table_key: str,
    limit: int | None,
    symbols: list[str] | None,
    batch_size: int,
) -> int:
    spec = TABLES[table_key]
    columns = spec["columns"]
    copy_sql = f"COPY {spec['pg']} ({', '.join(columns)}) FROM STDIN WITH (FORMAT text, NULL '\\N')"
    lines: list[str] = []
    copied = 0

    def flush() -> None:
        nonlocal copied
        if not lines:
            return
        run_psql(pg_db, copy_sql, "\n".join(lines) + "\n")
        copied += len(lines)
        lines.clear()

    for row in iter_rows(conn, spec["select"], limit, symbols):
        values = normalize_row(spec, row)
        lines.append("\t".join(quote_copy_value(values[column]) for column in columns))
        if len(lines) >= batch_size:
            flush()
    flush()
    return copied


def main() -> int:
    args = parse_args()
    sqlite_path = Path(args.sqlite)
    if not sqlite_path.exists():
        print(f"SQLite database not found: {sqlite_path}", file=sys.stderr)
        return 2

    tables = args.table or list(TABLES)
    conn = sqlite3.connect(sqlite_path)
    conn.row_factory = sqlite3.Row
    symbols = select_symbols(conn, args.symbol_limit)

    print(f"SQLite: {sqlite_path}")
    print(f"PostgreSQL: {args.pg_db}")
    print(f"Mode: {'execute' if args.execute else 'dry-run'}")
    if symbols is not None:
        print(f"Symbol scope: {len(symbols)} symbols")

    if args.truncate and not args.execute:
        print("--truncate requires --execute", file=sys.stderr)
        return 2

    if args.truncate:
        target_tables = ", ".join(TABLES[key]["pg"] for key in reversed(tables))
        run_psql(args.pg_db, f"TRUNCATE {target_tables} RESTART IDENTITY CASCADE;")

    for key in tables:
        spec = TABLES[key]
        source_count = sqlite_count(conn, spec["sqlite"])
        before_count = pg_count(args.pg_db, spec["pg"])
        copied = 0
        if args.execute:
            copied = copy_table(conn, args.pg_db, key, args.limit, symbols, args.batch_size)
        after_count = pg_count(args.pg_db, spec["pg"])
        print(
            f"{key}: sqlite={source_count} pg_before={before_count} "
            f"copied={copied} pg_after={after_count}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
