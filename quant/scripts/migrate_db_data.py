#!/usr/bin/env python3
"""
Migrate incremental data from legacy database to canonical location.

Usage:
    python quant/scripts/migrate_db_data.py
"""

import sqlite3
import sys
from pathlib import Path

# Database paths
QUANT_ROOT = Path(__file__).parent.parent
PROJECT_ROOT = QUANT_ROOT.parent
SOURCE_DB = QUANT_ROOT / 'quantsys' / 'data' / 'stocks.db'
TARGET_DB = PROJECT_ROOT / '.pi-invest' / 'stock-db' / 'stocks.db'

def main():
    """Migrate incremental data from source to target database."""

    # Verify source exists
    if not SOURCE_DB.exists():
        print(f"❌ Source database not found: {SOURCE_DB}")
        sys.exit(1)

    # Verify target exists
    if not TARGET_DB.exists():
        print(f"❌ Target database not found: {TARGET_DB}")
        sys.exit(1)

    print(f"📊 Migrating data from:")
    print(f"   Source: {SOURCE_DB}")
    print(f"   Target: {TARGET_DB}")
    print()

    # Connect to both databases
    source_conn = sqlite3.connect(SOURCE_DB)
    target_conn = sqlite3.connect(TARGET_DB)

    try:
        # Get incremental K-line data (2026-05-15 onwards)
        print("🔍 Extracting incremental K-line data (>= 2026-05-15)...")
        source_cursor = source_conn.cursor()
        source_cursor.execute("""
            SELECT symbol, date, open, high, low, close, volume, amount, turnover_rate
            FROM daily_klines
            WHERE date >= '2026-05-15'
            ORDER BY symbol, date
        """)
        raw_klines = source_cursor.fetchall()

        # Normalize date format from 'YYYY-MM-DD' to 'YYYYMMDD'
        incremental_klines = []
        for row in raw_klines:
            symbol, date, open_p, high, low, close, volume, amount, turnover = row
            # Convert date format if needed
            if '-' in date:
                date = date.replace('-', '')
            incremental_klines.append((symbol, date, open_p, high, low, close, volume, amount, turnover))

        print(f"   Found {len(incremental_klines)} K-line records")

        # Get new stocks (in source but not in target)
        print("🔍 Checking for new stocks...")
        source_cursor.execute("SELECT symbol FROM stocks")
        source_symbols = {row[0] for row in source_cursor.fetchall()}

        target_cursor = target_conn.cursor()
        target_cursor.execute("SELECT symbol FROM stocks")
        target_symbols = {row[0] for row in target_cursor.fetchall()}

        new_symbols = source_symbols - target_symbols
        print(f"   Found {len(new_symbols)} new stocks")

        # Migrate new stocks
        if new_symbols:
            print("📥 Migrating new stocks...")
            source_cursor.execute(f"""
                SELECT symbol, name, market, industry, sector, market_cap, pe, pb,
                       total_mv, circulating_mv, roe, net_profit_growth, gross_margin,
                       debt_ratio, avg_turnover_rate, avg_volume, avg_amount,
                       is_st, is_suspended, list_date, updated_at
                FROM stocks
                WHERE symbol IN ({','.join('?' * len(new_symbols))})
            """, list(new_symbols))
            new_stocks = source_cursor.fetchall()

            target_cursor.executemany("""
                INSERT OR REPLACE INTO stocks (
                    symbol, name, market, industry, sector, market_cap, pe, pb,
                    total_mv, circulating_mv, roe, net_profit_growth, gross_margin,
                    debt_ratio, avg_turnover_rate, avg_volume, avg_amount,
                    is_st, is_suspended, list_date, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, new_stocks)
            print(f"   ✅ Migrated {len(new_stocks)} stocks")

        # Migrate incremental K-lines
        if incremental_klines:
            print("📥 Migrating incremental K-line data...")
            target_cursor.executemany("""
                INSERT OR REPLACE INTO daily_klines (
                    symbol, date, open, high, low, close, volume, amount, turnover_rate
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, incremental_klines)
            print(f"   ✅ Migrated {len(incremental_klines)} K-line records")

        # Commit changes
        target_conn.commit()

        # Verify migration
        print()
        print("✅ Verification:")
        target_cursor.execute("SELECT MAX(date) FROM daily_klines")
        max_date = target_cursor.fetchone()[0]
        print(f"   Latest K-line date: {max_date}")

        target_cursor.execute("SELECT COUNT(*) FROM stocks")
        stock_count = target_cursor.fetchone()[0]
        print(f"   Total stocks: {stock_count}")

        target_cursor.execute("SELECT COUNT(*) FROM daily_klines")
        kline_count = target_cursor.fetchone()[0]
        print(f"   Total K-line records: {kline_count}")

        print()
        print("🎉 Migration completed successfully!")

    except Exception as e:
        print(f"❌ Migration failed: {e}")
        target_conn.rollback()
        sys.exit(1)
    finally:
        source_conn.close()
        target_conn.close()

if __name__ == '__main__':
    main()
