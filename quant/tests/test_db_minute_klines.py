"""Tests for Database minute klines query methods."""

from __future__ import annotations

import os
from datetime import datetime

import pytest

from quantsys.data.db import Database


@pytest.fixture
def db():
    """Create a test database instance."""
    os.environ["QUANT_DB_PROVIDER"] = "postgres"
    db = Database()

    # Insert test stock to satisfy foreign key constraint
    db.upsert_stocks([{
        "symbol": "600519.SH",
        "name": "贵州茅台",
        "market": "A",
    }])

    yield db
    db.close()


@pytest.fixture
def sample_minute_klines():
    """Sample minute kline data for testing."""
    return [
        {
            "symbol": "600519.SH",
            "trade_datetime": datetime(2024, 1, 15, 9, 31, 0),
            "open": 1800.0,
            "high": 1805.0,
            "low": 1798.0,
            "close": 1802.0,
            "volume": 1000000.0,
            "amount": 1802000000.0,
        },
        {
            "symbol": "600519.SH",
            "trade_datetime": datetime(2024, 1, 15, 9, 32, 0),
            "open": 1802.0,
            "high": 1808.0,
            "low": 1801.0,
            "close": 1806.0,
            "volume": 1200000.0,
            "amount": 2167200000.0,
        },
        {
            "symbol": "600519.SH",
            "trade_datetime": datetime(2024, 1, 16, 9, 31, 0),
            "open": 1810.0,
            "high": 1815.0,
            "low": 1808.0,
            "close": 1812.0,
            "volume": 1100000.0,
            "amount": 1993200000.0,
        },
    ]


def test_upsert_minute_klines_uses_trade_datetime(db, sample_minute_klines):
    """Test that upsert_minute_klines uses trade_datetime column."""
    # Insert sample data
    count = db.upsert_minute_klines(sample_minute_klines)
    assert count == 3


def test_get_minute_klines_returns_dataframe(db, sample_minute_klines):
    """Test that get_minute_klines returns a DataFrame with correct data."""
    # Insert sample data
    db.upsert_minute_klines(sample_minute_klines)

    # Query data
    df = db.get_minute_klines("600519.SH", "2024-01-15", "2024-01-16")

    # Verify DataFrame structure
    assert df is not None
    assert len(df) == 3
    assert list(df.columns) == ["symbol", "trade_datetime", "open", "high", "low", "close", "volume", "amount"]

    # Verify data content
    assert df.iloc[0]["symbol"] == "600519.SH"
    assert df.iloc[0]["close"] == 1802.0
    assert df.iloc[2]["close"] == 1812.0


def test_get_minute_klines_date_filtering(db, sample_minute_klines):
    """Test that get_minute_klines correctly filters by date range."""
    # Insert sample data
    db.upsert_minute_klines(sample_minute_klines)

    # Query only 2024-01-15
    df = db.get_minute_klines("600519.SH", "2024-01-15", "2024-01-15")

    assert len(df) == 2
    assert all(df["trade_datetime"].str.startswith("2024-01-15"))


def test_get_minute_klines_empty_result(db):
    """Test that get_minute_klines returns empty DataFrame for non-existent symbol."""
    df = db.get_minute_klines("999999.SH", "2024-01-15", "2024-01-16")

    assert df is not None
    assert len(df) == 0


def test_get_minute_kline_dates_returns_min_max(db, sample_minute_klines):
    """Test that get_minute_kline_dates returns min and max dates."""
    # Insert sample data
    db.upsert_minute_klines(sample_minute_klines)

    # Query date range
    result = db.get_minute_kline_dates("600519.SH")

    assert result is not None
    assert "min_date" in result
    assert "max_date" in result
    assert result["min_date"] == "2024-01-15"
    assert result["max_date"] == "2024-01-16"


def test_get_minute_kline_dates_non_existent_symbol(db):
    """Test that get_minute_kline_dates returns None for non-existent symbol."""
    result = db.get_minute_kline_dates("999999.SH")

    assert result is not None
    assert result["min_date"] is None
    assert result["max_date"] is None
