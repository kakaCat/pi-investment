#!/usr/bin/env python3
"""
Backfill Portfolio History

Populates account_balance table with historical data.

Usage:
    python scripts/backfill_portfolio_history.py --days 90
"""

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

from domain.quantlib.core.portfolio_calculator import PortfolioCalculator
from adapters.outbound.repositories import RiskORMRepository
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def is_trading_day(check_date: date) -> bool:
    """Check if date is a trading day (exclude weekends)"""
    return check_date.weekday() < 5  # Monday=0, Friday=4


def backfill_history(days: int = 90):
    """
    Backfill historical account balance data

    Args:
        days: Number of days to backfill
    """
    calculator = PortfolioCalculator()
    risk_repo = RiskORMRepository()

    end_date = date.today()
    start_date = end_date - timedelta(days=days)

    logger.info(f"Backfilling portfolio history from {start_date} to {end_date}")
    logger.info("=" * 60)

    current_date = start_date
    success_count = 0
    skip_count = 0
    error_count = 0

    while current_date <= end_date:
        try:
            # 1. Check if trading day
            if not is_trading_day(current_date):
                logger.debug(f"Skipping weekend: {current_date}")
                current_date += timedelta(days=1)
                skip_count += 1
                continue

            # 2. Check if already exists
            existing = risk_repo.get_balance_by_date(current_date.strftime('%Y-%m-%d'))
            if existing:
                logger.debug(f"Snapshot already exists for {current_date}, skipping")
                current_date += timedelta(days=1)
                skip_count += 1
                continue

            # 3. Calculate snapshot
            snapshot = calculator.calculate_snapshot(current_date.strftime('%Y-%m-%d'))

            # 4. Save to database
            risk_repo.save_balance(snapshot)

            logger.info(
                f"✓ {current_date}: "
                f"assets={snapshot['total_assets']:,.2f}, "
                f"return={snapshot['daily_return']:.2f}%"
            )
            success_count += 1

        except Exception as e:
            logger.error(f"✗ Failed to backfill {current_date}: {str(e)}")
            error_count += 1

        current_date += timedelta(days=1)

    # Summary
    logger.info("=" * 60)
    logger.info("Backfill completed:")
    logger.info(f"  Success: {success_count}")
    logger.info(f"  Skipped: {skip_count}")
    logger.info(f"  Errors:  {error_count}")
    logger.info("=" * 60)

    return success_count, skip_count, error_count


def main():
    parser = argparse.ArgumentParser(description='Backfill portfolio history')
    parser.add_argument(
        '--days',
        type=int,
        default=90,
        help='Number of days to backfill (default: 90)'
    )
    args = parser.parse_args()

    success, skipped, errors = backfill_history(args.days)

    # Exit with error code if any errors occurred
    sys.exit(1 if errors > 0 else 0)


if __name__ == '__main__':
    main()
