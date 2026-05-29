#!/usr/bin/env python3
"""Probe xmtdx 1-minute A-share history coverage without writing to PostgreSQL."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def _load_env_defaults() -> None:
    """Load repo-level .env values without overriding explicit environment."""
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if not env_path.exists():
        return

    for line in env_path.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue

        key, value = stripped.split("=", 1)
        key = key.strip()
        if not key or key in os.environ:
            continue

        os.environ[key] = value.strip().strip('"').strip("'")


_load_env_defaults()

from quantsys.data.xmtdx_minute_probe import XmtDxMinuteProbe


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Probe xmtdx 1-minute kline coverage")
    parser.add_argument("--symbol", required=True, help="Symbol such as 600519.SH or 000001.SZ")
    parser.add_argument("--start-date", required=True, help="Start date in YYYY-MM-DD")
    parser.add_argument("--end-date", required=True, help="End date in YYYY-MM-DD")
    parser.add_argument("--max-pages", type=int, default=80, help="Number of pages to scan")
    parser.add_argument("--page-size", type=int, default=800, help="Rows per page")
    parser.add_argument("--write-db", action="store_true", help="Upsert fetched rows into quant.minute_klines")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    probe = XmtDxMinuteProbe()
    rows = probe.fetch_range(
        args.symbol,
        args.start_date,
        args.end_date,
        max_pages=args.max_pages,
        page_size=args.page_size,
    )

    print(f"symbol={args.symbol}")
    print(f"range={args.start_date}..{args.end_date}")
    print(f"rows={len(rows)}")
    if rows:
        print(f"first={rows[0]}")
        print(f"last={rows[-1]}")
        dates = sorted({row["trade_datetime"][:10] for row in rows})
        print(f"trading_days={len(dates)}")
        print(f"first_date={dates[0]}")
        print(f"last_date={dates[-1]}")
    if args.write_db:
        from quantsys.data.db import Database

        db = Database()
        try:
            saved = db.upsert_minute_klines(rows)
        finally:
            db.close()
        print(f"saved={saved}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
