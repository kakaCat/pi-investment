#!/usr/bin/env python3
"""Backfill recent xmtdx 1-minute A-share bars into PostgreSQL."""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
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

from quantsys.data.db import Database
from quantsys.data.xmtdx_minute_probe import XmtDxMinuteProbe


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill xmtdx 1-minute bars into quant.minute_klines")
    parser.add_argument("--start-date", default="2025-12-31", help="Start date in YYYY-MM-DD")
    parser.add_argument("--end-date", default="2026-05-27", help="End date in YYYY-MM-DD")
    parser.add_argument("--symbols", help="Comma-separated symbols. Defaults to all symbols from DB.")
    parser.add_argument("--market", default="A", choices=["A", "HK", "all"], help="Market filter for DB symbol list")
    parser.add_argument("--limit", type=int, help="Only process the first N symbols")
    parser.add_argument("--max-pages", type=int, default=80, help="Number of xmtdx pages per symbol")
    parser.add_argument("--page-size", type=int, default=800, help="Rows per xmtdx page")
    parser.add_argument("--sleep", type=float, default=0.05, help="Delay between symbols in seconds")
    return parser.parse_args()


def _symbols_from_args(db: Database, symbols_arg: str | None, market: str) -> list[str]:
    if symbols_arg:
        return [symbol.strip() for symbol in symbols_arg.split(",") if symbol.strip()]
    symbols = db.get_all_symbols(market=market)
    selected_by_code: dict[str, str] = {}
    for symbol in symbols:
        code = symbol.split(".")[0]
        existing = selected_by_code.get(code)
        if existing is None or "." in existing and "." not in symbol:
            selected_by_code[code] = symbol
    return list(selected_by_code.values())


def main() -> int:
    args = parse_args()
    db = Database()
    probe = XmtDxMinuteProbe()
    succeeded = 0
    failed = 0
    saved_total = 0

    try:
        symbols = _symbols_from_args(db, args.symbols, args.market)
        if args.limit is not None:
            symbols = symbols[: args.limit]

        logger.info(
            "Starting xmtdx minute backfill: symbols=%s range=%s..%s pages=%s page_size=%s",
            len(symbols),
            args.start_date,
            args.end_date,
            args.max_pages,
            args.page_size,
        )

        for index, symbol in enumerate(symbols, start=1):
            try:
                saved = probe.backfill_range(
                    db,
                    symbol,
                    args.start_date,
                    args.end_date,
                    max_pages=args.max_pages,
                    page_size=args.page_size,
                )
                saved_total += saved
                succeeded += 1
                logger.info("[%s/%s] %s saved=%s", index, len(symbols), symbol, saved)
            except Exception as exc:
                failed += 1
                logger.error("[%s/%s] %s failed: %s", index, len(symbols), symbol, exc)
            time.sleep(args.sleep)

        logger.info(
            "xmtdx minute backfill complete: succeeded=%s failed=%s saved=%s",
            succeeded,
            failed,
            saved_total,
        )
        return 0 if failed == 0 else 1
    finally:
        db.close()
        if probe.reader is not None and hasattr(probe.reader, "close"):
            probe.reader.close()


if __name__ == "__main__":
    raise SystemExit(main())
