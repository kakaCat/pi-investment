"""
Test data generators for polars migration

Provides standard test datasets for Repository and Service layer testing.
"""
import polars as pl
from datetime import date, timedelta
from typing import Optional


def create_test_klines(
    symbol: str = '600000',
    days: int = 252,
    start_date: Optional[date] = None
) -> pl.DataFrame:
    """
    Generate standard test K-line data

    Args:
        symbol: Stock symbol
        days: Number of trading days
        start_date: Start date (default: 2024-01-01)

    Returns:
        polars DataFrame with OHLCV columns
    """
    if start_date is None:
        start_date = date(2024, 1, 1)

    dates = [start_date + timedelta(days=i) for i in range(days)]

    return pl.DataFrame({
        'symbol': [symbol] * days,
        'trade_date': dates,
        'open': [100.0 + i * 0.1 for i in range(days)],
        'high': [102.0 + i * 0.1 for i in range(days)],
        'low': [98.0 + i * 0.1 for i in range(days)],
        'close': [100.5 + i * 0.1 for i in range(days)],
        'volume': [1000000 + i * 1000 for i in range(days)],
        'amount': [100000000.0 + i * 10000 for i in range(days)],
    })


def create_test_financials(
    symbol: str = '600000',
    quarters: int = 20
) -> pl.DataFrame:
    """
    Generate test financial data

    Args:
        symbol: Stock symbol
        quarters: Number of quarters

    Returns:
        polars DataFrame with financial indicators
    """
    report_dates = []
    for i in range(quarters):
        year = 2020 + (i // 4)
        quarter = (i % 4) + 1
        month = quarter * 3
        report_dates.append(date(year, month, 1))

    return pl.DataFrame({
        'symbol': [symbol] * quarters,
        'report_date': report_dates,
        'roe': [15.0 + i * 0.5 for i in range(quarters)],
        'roa': [8.0 + i * 0.3 for i in range(quarters)],
        'gross_margin': [30.0 + i * 0.2 for i in range(quarters)],
        'net_profit_margin': [12.0 + i * 0.1 for i in range(quarters)],
        'debt_ratio': [45.0 - i * 0.5 for i in range(quarters)],
    })


def create_empty_klines_with_schema() -> pl.DataFrame:
    """
    Create empty K-line DataFrame with proper schema

    Returns:
        Empty polars DataFrame with K-line schema
    """
    return pl.DataFrame(schema={
        'symbol': pl.Utf8,
        'trade_date': pl.Date,
        'open': pl.Float64,
        'high': pl.Float64,
        'low': pl.Float64,
        'close': pl.Float64,
        'volume': pl.Int64,
        'amount': pl.Float64,
    })
