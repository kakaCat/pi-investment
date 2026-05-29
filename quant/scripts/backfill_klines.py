#!/usr/bin/env python3
"""
K-line Data Backfill Script

Downloads missing K-line data (daily or minute) from akshare and stores in database.
Supports batch processing, progress tracking, and resume from interruption.

Usage:
    # Daily K-line backfill (2 years)
    python scripts/backfill_klines.py --data-type daily --target-days 730

    # Minute K-line backfill (1 year)
    python scripts/backfill_klines.py --data-type minute --target-days 365

    # Specific symbols
    python scripts/backfill_klines.py --data-type daily --symbols "600519.SH,000001.SZ"

    # Reset progress and start fresh
    python scripts/backfill_klines.py --data-type daily --reset-progress
"""

import argparse
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

# Disable proxy for akshare (direct connection is faster and more stable)
for _proxy_key in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY"):
    os.environ.pop(_proxy_key, None)

# Add parent directory to path for imports
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
from quantsys.data.trading_calendar import TradingCalendar
from quantsys.data.gap_detector import GapDetector
from quantsys.data.progress_tracker import ProgressTracker
from quantsys.data.data_backfiller import DataBackfiller

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_symbol_list(db: Database, symbols_arg: Optional[str], market: str) -> List[str]:
    """
    Get list of symbols to process.

    Args:
        db: Database instance
        symbols_arg: Comma-separated symbol list (optional)
        market: Market filter ("A", "HK", or "all")

    Returns:
        List of stock symbols
    """
    if symbols_arg:
        return [s.strip() for s in symbols_arg.split(",") if s.strip()]

    # Get all symbols from database filtered by market
    return db.get_all_symbols(market=market)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Backfill missing K-line data from akshare",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        "--data-type",
        choices=["daily", "minute"],
        required=True,
        help="Type of K-line data to backfill"
    )

    parser.add_argument(
        "--target-days",
        type=int,
        default=730,
        help="Number of calendar days to look back (default: 730)"
    )

    parser.add_argument(
        "--end-date",
        type=str,
        help="End date to backfill through in YYYY-MM-DD format. Defaults to today."
    )

    parser.add_argument(
        "--symbols",
        type=str,
        help="Comma-separated list of symbols. If not provided, processes all symbols."
    )

    parser.add_argument(
        "--market",
        choices=["A", "HK", "all"],
        default="A",
        help="Market filter (default: A)"
    )

    parser.add_argument(
        "--batch-size",
        type=int,
        default=50,
        help="Number of symbols to process per batch (default: 50)"
    )

    parser.add_argument(
        "--max-retries",
        type=int,
        default=None,
        help="Override max download retries for this run"
    )

    parser.add_argument(
        "--reset-progress",
        action="store_true",
        help="Reset progress tracker and start from scratch"
    )

    args = parser.parse_args()

    # Print configuration
    logger.info("\n" + "=" * 60)
    logger.info("K-line Data Backfill")
    logger.info("=" * 60)
    logger.info(f"Data Type:    {args.data_type}")
    logger.info(f"Target Days:  {args.target_days}")
    logger.info(f"End Date:     {args.end_date or 'today'}")
    logger.info(f"Batch Size:   {args.batch_size}")
    logger.info(f"Max Retries:  {args.max_retries if args.max_retries is not None else 'default'}")
    logger.info(f"Market:       {args.market}")
    logger.info(f"Reset Progress: {args.reset_progress}")
    logger.info("=" * 60 + "\n")

    # Initialize components
    logger.info("Initializing components...")
    db = Database()
    calendar = TradingCalendar()
    gap_detector = GapDetector(db, calendar)
    progress_tracker = ProgressTracker()
    backfiller = DataBackfiller(db, calendar, gap_detector, progress_tracker)
    if args.max_retries is not None:
        backfiller.MAX_RETRIES = max(1, args.max_retries)
    logger.info("✓ Components initialized\n")

    # Reset progress if requested
    if args.reset_progress:
        logger.info("Resetting progress tracker...")
        progress_tracker.reset()
        logger.info("✓ Progress tracker reset\n")
    else:
        progress_tracker.load()

    # Get symbol list
    logger.info("Loading symbol list...")
    symbols = get_symbol_list(db, args.symbols, args.market)

    if not symbols:
        logger.warning("No symbols to process. Exiting.")
        return

    logger.info(f"✓ Loaded {len(symbols)} symbols\n")

    # Process in batches
    total_batches = (len(symbols) + args.batch_size - 1) // args.batch_size
    overall_succeeded = 0
    overall_failed = 0
    overall_dates_backfilled = 0
    overall_dates_failed = 0
    overall_dates_skipped = 0

    for batch_num in range(total_batches):
        start_idx = batch_num * args.batch_size
        end_idx = min(start_idx + args.batch_size, len(symbols))
        batch_symbols = symbols[start_idx:end_idx]

        logger.info("=" * 60)
        logger.info(f"Processing Batch {batch_num + 1}/{total_batches} ({len(batch_symbols)} symbols)")
        logger.info("=" * 60)

        # Process batch
        for i, symbol in enumerate(batch_symbols, 1):
            logger.info(f"\nProcessing [{i}/{len(batch_symbols)}] {symbol}...")

            try:
                if args.data_type == "daily":
                    result = backfiller.backfill_daily(
                        symbol,
                        args.target_days,
                        end_date=args.end_date,
                        include_new_symbols=True,
                    )
                else:
                    result = backfiller.backfill_minute(
                        symbol,
                        args.target_days,
                        end_date=args.end_date,
                    )

                overall_dates_backfilled += result["succeeded"]
                overall_dates_failed += result["failed"]
                overall_dates_skipped += result["skipped"]

                if result["failed"] > 0:
                    logger.info(f"⚠ {symbol}: {result['succeeded']} succeeded, {result['failed']} failed, {result['skipped']} skipped")
                    overall_failed += 1
                else:
                    logger.info(f"✓ {symbol}: {result['succeeded']} succeeded, {result['failed']} failed, {result['skipped']} skipped")
                    overall_succeeded += 1

            except Exception as e:
                logger.error(f"✗ {symbol}: Exception occurred: {e}")
                import traceback
                traceback.print_exc()
                overall_failed += 1

        logger.info("\n" + "=" * 60)
        logger.info(f"Batch {batch_num + 1}/{total_batches} complete: {len(batch_symbols)}/{len(batch_symbols)} symbols succeeded")
        logger.info("=" * 60 + "\n")

        # Save progress after each batch
        progress_tracker.save()
        logger.info(f"✓ Progress saved after batch {batch_num + 1}\n")

    # Print final summary
    logger.info("\n" + "=" * 60)
    logger.info("FINAL SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Symbols Processed:    {overall_succeeded + overall_failed}/{len(symbols)}")
    logger.info(f"Symbols Succeeded:    {overall_succeeded}")
    logger.info(f"Dates Backfilled:     {overall_dates_backfilled}")
    logger.info(f"Dates Failed:         {overall_dates_failed}")
    logger.info(f"Dates Skipped:        {overall_dates_skipped}")
    logger.info("=" * 60 + "\n")

    logger.info("✓ Backfill complete!")

    # Close database
    db.close()


if __name__ == "__main__":
    main()
