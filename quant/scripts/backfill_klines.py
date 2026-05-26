#!/usr/bin/env python3
"""
K-line Data Backfill Script

Command-line tool to backfill missing K-line data (daily or minute) for stocks.
Integrates Database, TradingCalendar, GapDetector, ProgressTracker, and DataBackfiller.

Usage:
    # Backfill daily data for specific symbols
    python backfill_klines.py --data-type daily --symbols 600519.SH,000001.SZ

    # Backfill minute data for all A-share stocks
    python backfill_klines.py --data-type minute --market A --target-days 180

    # Backfill with custom batch size and reset progress
    python backfill_klines.py --data-type daily --market A --batch-size 20 --reset-progress

Examples:
    # Daily data for last 2 years (default)
    python backfill_klines.py --data-type daily --symbols 600519.SH

    # Minute data for last 1 year (default)
    python backfill_klines.py --data-type minute --symbols 600519.SH

    # All HK stocks, daily data
    python backfill_klines.py --data-type daily --market HK

    # Resume interrupted backfill (progress is saved automatically)
    python backfill_klines.py --data-type daily --market A
"""
import argparse
import logging
import sys
from typing import List, Dict, Any

# Add parent directory to path for imports
sys.path.insert(0, '/Users/mac/Documents/ai/pi-investment/quant')

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


def parse_args(args: List[str] = None) -> argparse.Namespace:
    """
    Parse command-line arguments.

    Args:
        args: List of arguments (for testing). If None, uses sys.argv.

    Returns:
        Parsed arguments namespace.
    """
    parser = argparse.ArgumentParser(
        description='Backfill missing K-line data for stocks',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument(
        '--data-type',
        required=True,
        choices=['daily', 'minute'],
        help='Type of K-line data to backfill'
    )

    parser.add_argument(
        '--symbols',
        type=str,
        help='Comma-separated list of symbols (e.g., "600519.SH,000001.SZ")'
    )

    parser.add_argument(
        '--market',
        type=str,
        choices=['A', 'HK'],
        default='A',
        help='Market filter (used if --symbols not provided). Default: A'
    )

    parser.add_argument(
        '--target-days',
        type=int,
        help='Number of calendar days to backfill (default: 730 for daily, 365 for minute)'
    )

    parser.add_argument(
        '--batch-size',
        type=int,
        default=10,
        help='Number of symbols to process in one batch. Default: 10'
    )

    parser.add_argument(
        '--reset-progress',
        action='store_true',
        help='Clear progress tracker before starting'
    )

    parsed = parser.parse_args(args)

    # Set default target_days based on data_type if not provided
    if parsed.target_days is None:
        parsed.target_days = 730 if parsed.data_type == 'daily' else 365

    return parsed


def get_symbol_list(db: Database, symbols_arg: str, market: str) -> List[str]:
    """
    Get list of symbols to process.

    Args:
        db: Database instance
        symbols_arg: Comma-separated symbols from command line (or None)
        market: Market filter ('A' or 'HK')

    Returns:
        List of symbol strings.
    """
    if symbols_arg:
        # Use symbols from command line
        return [s.strip() for s in symbols_arg.split(',')]

    # Get all symbols from database and filter by market
    all_symbols = db.get_all_symbols()

    if market == 'A':
        # A-share: .SH or .SZ suffix
        filtered = [s['symbol'] for s in all_symbols
                    if s['symbol'].endswith('.SH') or s['symbol'].endswith('.SZ')]
    elif market == 'HK':
        # HK: .HK suffix
        filtered = [s['symbol'] for s in all_symbols
                    if s['symbol'].endswith('.HK')]
    else:
        filtered = [s['symbol'] for s in all_symbols]

    return filtered


def process_batch(
    backfiller: DataBackfiller,
    symbols: List[str],
    data_type: str,
    target_days: int,
    batch_num: int,
    total_batches: int
) -> List[Dict[str, Any]]:
    """
    Process a batch of symbols.

    Args:
        backfiller: DataBackfiller instance
        symbols: List of symbols to process
        data_type: 'daily' or 'minute'
        target_days: Number of days to backfill
        batch_num: Current batch number (1-indexed)
        total_batches: Total number of batches

    Returns:
        List of result dictionaries from backfiller.
    """
    logger.info(f"\n{'='*60}")
    logger.info(f"Processing Batch {batch_num}/{total_batches} ({len(symbols)} symbols)")
    logger.info(f"{'='*60}")

    results = []
    total_symbols = len(symbols)

    for idx, symbol in enumerate(symbols, 1):
        logger.info(f"\nProcessing [{idx}/{total_symbols}] {symbol}...")

        try:
            if data_type == 'daily':
                result = backfiller.backfill_daily(symbol, target_days)
            else:
                result = backfiller.backfill_minute(symbol, target_days)

            results.append(result)

            # Print per-symbol summary
            status = "✓" if result['failed'] == 0 else "⚠"
            logger.info(
                f"{status} {symbol}: {result['succeeded']} succeeded, "
                f"{result['failed']} failed, {result['skipped']} skipped"
            )

        except Exception as e:
            logger.error(f"✗ {symbol}: Exception occurred: {e}", exc_info=True)
            # Continue processing other symbols

    # Print batch summary
    succeeded_symbols = sum(1 for r in results if r['failed'] == 0)
    logger.info(f"\n{'='*60}")
    logger.info(
        f"Batch {batch_num}/{total_batches} complete: "
        f"{succeeded_symbols}/{total_symbols} symbols succeeded"
    )
    logger.info(f"{'='*60}\n")

    return results


def main(args: List[str] = None) -> int:
    """
    Main function.

    Args:
        args: Command-line arguments (for testing). If None, uses sys.argv.

    Returns:
        Exit code (0 for success, 1 for error).
    """
    try:
        # Parse arguments
        parsed_args = parse_args(args)

        # Print configuration header
        logger.info("\n" + "="*60)
        logger.info("K-line Data Backfill")
        logger.info("="*60)
        logger.info(f"Data Type:    {parsed_args.data_type}")
        logger.info(f"Target Days:  {parsed_args.target_days}")
        logger.info(f"Batch Size:   {parsed_args.batch_size}")
        logger.info(f"Market:       {parsed_args.market}")
        if parsed_args.symbols:
            logger.info(f"Symbols:      {parsed_args.symbols}")
        logger.info(f"Reset Progress: {parsed_args.reset_progress}")
        logger.info("="*60 + "\n")

        # Initialize components
        logger.info("Initializing components...")
        db = Database()
        calendar = TradingCalendar(db)
        gap_detector = GapDetector(db, calendar)
        progress_tracker = ProgressTracker(db)
        backfiller = DataBackfiller(db, calendar, gap_detector, progress_tracker)
        logger.info("✓ Components initialized\n")

        # Reset progress if requested
        if parsed_args.reset_progress:
            logger.info("Resetting progress tracker...")
            progress_tracker.reset()
            logger.info("✓ Progress tracker reset\n")

        # Get symbol list
        logger.info("Loading symbol list...")
        symbols = get_symbol_list(db, parsed_args.symbols, parsed_args.market)
        total_symbols = len(symbols)

        if total_symbols == 0:
            logger.warning("No symbols to process. Exiting.")
            return 0

        logger.info(f"✓ Loaded {total_symbols} symbols\n")

        # Calculate number of batches
        batch_size = parsed_args.batch_size
        total_batches = (total_symbols + batch_size - 1) // batch_size

        # Process symbols in batches
        all_results = []

        for batch_num in range(1, total_batches + 1):
            start_idx = (batch_num - 1) * batch_size
            end_idx = min(start_idx + batch_size, total_symbols)
            batch_symbols = symbols[start_idx:end_idx]

            # Process batch
            batch_results = process_batch(
                backfiller=backfiller,
                symbols=batch_symbols,
                data_type=parsed_args.data_type,
                target_days=parsed_args.target_days,
                batch_num=batch_num,
                total_batches=total_batches
            )

            all_results.extend(batch_results)

            # Save progress after each batch
            progress_tracker.save()
            logger.info(f"✓ Progress saved after batch {batch_num}\n")

        # Print final summary
        logger.info("\n" + "="*60)
        logger.info("FINAL SUMMARY")
        logger.info("="*60)

        total_succeeded_symbols = sum(1 for r in all_results if r['failed'] == 0)
        total_dates_backfilled = sum(r['succeeded'] for r in all_results)
        total_dates_failed = sum(r['failed'] for r in all_results)
        total_dates_skipped = sum(r['skipped'] for r in all_results)

        logger.info(f"Symbols Processed:    {len(all_results)}/{total_symbols}")
        logger.info(f"Symbols Succeeded:    {total_succeeded_symbols}")
        logger.info(f"Dates Backfilled:     {total_dates_backfilled}")
        logger.info(f"Dates Failed:         {total_dates_failed}")
        logger.info(f"Dates Skipped:        {total_dates_skipped}")
        logger.info("="*60 + "\n")

        logger.info("✓ Backfill complete!")
        return 0

    except KeyboardInterrupt:
        logger.warning("\n\nInterrupted by user (Ctrl+C)")
        logger.info("Saving progress...")
        try:
            progress_tracker.save()
            logger.info("✓ Progress saved. You can resume by running the same command again.")
        except Exception as e:
            logger.error(f"Failed to save progress: {e}")
        return 1

    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
