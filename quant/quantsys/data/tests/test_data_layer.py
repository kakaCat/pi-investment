"""Unit tests for data layer modules."""

import unittest
from datetime import datetime, timedelta

import pandas as pd
import numpy as np

from pipeline.data.sources.base_adapter import BaseDataAdapter
from pipeline.data.sources.akshare_adapter import AkShareAdapter
from pipeline.data.cleaner.adjuster import PriceAdjuster
from pipeline.data.cleaner.validator import DataValidator
from pipeline.data.storage.cache_manager import CacheManager


class TestBaseAdapter(unittest.TestCase):
    """Test BaseDataAdapter functionality."""

    def setUp(self):
        """Set up test fixtures."""
        # Create a concrete implementation for testing
        class TestAdapter(BaseDataAdapter):
            def fetch_daily_klines(self, symbol, start_date, end_date, adjust="qfq"):
                return pd.DataFrame()

            def fetch_stock_list(self, market="A"):
                return pd.DataFrame()

            def fetch_realtime_quote(self, symbol):
                return {}

        self.adapter = TestAdapter()

    def test_validate_date_format(self):
        """Test date format validation."""
        self.assertTrue(self.adapter.validate_date_format("20240101"))
        self.assertTrue(self.adapter.validate_date_format("20231231"))
        self.assertFalse(self.adapter.validate_date_format("2024-01-01"))
        self.assertFalse(self.adapter.validate_date_format("invalid"))

    def test_resolve_market(self):
        """Test market resolution from symbol."""
        self.assertEqual(self.adapter.resolve_market("000001"), "A")
        self.assertEqual(self.adapter.resolve_market("600000"), "A")
        self.assertEqual(self.adapter.resolve_market("00700"), "HK")
        self.assertEqual(self.adapter.resolve_market("03690"), "HK")

    def test_get_exchange_prefix(self):
        """Test exchange prefix resolution."""
        self.assertEqual(self.adapter.get_exchange_prefix("000001"), "sz")
        self.assertEqual(self.adapter.get_exchange_prefix("600000"), "sh")
        self.assertEqual(self.adapter.get_exchange_prefix("688001"), "sh")
        self.assertEqual(self.adapter.get_exchange_prefix("430001"), "bj")

    def test_normalize_columns(self):
        """Test column normalization."""
        df = pd.DataFrame({
            "日期": ["2024-01-01"],
            "开盘": [10.0],
            "收盘": [11.0],
        })

        column_map = {
            "日期": "date",
            "开盘": "open",
            "收盘": "close",
        }

        result = self.adapter.normalize_columns(df, column_map)
        self.assertIn("date", result.columns)
        self.assertIn("open", result.columns)
        self.assertIn("close", result.columns)


class TestPriceAdjuster(unittest.TestCase):
    """Test PriceAdjuster functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.adjuster = PriceAdjuster()

        # Create sample data with a stock split
        dates = pd.date_range("2024-01-01", periods=10, freq="D")
        self.sample_data = pd.DataFrame({
            "date": dates.strftime("%Y-%m-%d"),
            "open": [100, 100, 100, 100, 50, 50, 50, 50, 50, 50],
            "high": [105, 105, 105, 105, 52, 52, 52, 52, 52, 52],
            "low": [95, 95, 95, 95, 48, 48, 48, 48, 48, 48],
            "close": [100, 100, 100, 100, 50, 50, 50, 50, 50, 50],
            "volume": [1000, 1000, 1000, 1000, 2000, 2000, 2000, 2000, 2000, 2000],
        })

    def test_no_adjustment(self):
        """Test that no adjustment returns original data."""
        result = self.adjuster.adjust_prices(self.sample_data, adjust_type="")
        pd.testing.assert_frame_equal(result, self.sample_data)

    def test_invalid_adjust_type(self):
        """Test invalid adjustment type raises error."""
        with self.assertRaises(ValueError):
            self.adjuster.adjust_prices(self.sample_data, adjust_type="invalid")

    def test_missing_columns(self):
        """Test missing required columns raises error."""
        df = pd.DataFrame({"date": ["2024-01-01"]})
        with self.assertRaises(ValueError):
            self.adjuster.adjust_prices(df, adjust_type="qfq")

    def test_detect_corporate_actions(self):
        """Test corporate action detection."""
        result = self.adjuster.detect_corporate_actions(self.sample_data)
        self.assertGreater(len(result), 0)
        self.assertIn("type", result.columns)
        self.assertIn("ratio", result.columns)

    def test_verify_adjustment(self):
        """Test adjustment verification."""
        adjusted = self.adjuster.adjust_prices(self.sample_data, adjust_type="qfq")
        result = self.adjuster.verify_adjustment(self.sample_data, adjusted)
        self.assertIn("is_valid", result)
        self.assertIn("price_ratio_consistent", result)


class TestDataValidator(unittest.TestCase):
    """Test DataValidator functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.validator = DataValidator()

        # Create sample data
        dates = pd.date_range("2024-01-01", periods=10, freq="D")
        self.clean_data = pd.DataFrame({
            "date": dates.strftime("%Y-%m-%d"),
            "open": [100, 101, 102, 103, 104, 105, 106, 107, 108, 109],
            "high": [105, 106, 107, 108, 109, 110, 111, 112, 113, 114],
            "low": [95, 96, 97, 98, 99, 100, 101, 102, 103, 104],
            "close": [100, 101, 102, 103, 104, 105, 106, 107, 108, 109],
            "volume": [1000, 1000, 1000, 1000, 1000, 1000, 1000, 1000, 1000, 1000],
        })

    def test_validate_clean_data(self):
        """Test validation of clean data."""
        result = self.validator.validate(self.clean_data)
        self.assertTrue(result["is_valid"])
        self.assertEqual(len(result["errors"]), 0)

    def test_check_missing_values(self):
        """Test missing value detection."""
        df = self.clean_data.copy()
        df.loc[0, "close"] = np.nan

        result = self.validator.check_missing_values(df)
        self.assertTrue(result["has_missing"])
        self.assertIn("close", result["missing_columns"])

    def test_detect_outliers(self):
        """Test outlier detection."""
        # Use a validator with lower threshold for testing
        validator = DataValidator(outlier_std=2.0)
        df = self.clean_data.copy()
        df.loc[5, "close"] = 10000  # Much larger outlier

        result = validator.detect_outliers(df)
        self.assertTrue(result["has_outliers"])
        self.assertGreater(result["outlier_count"], 0)

    def test_detect_suspended_days(self):
        """Test suspended day detection."""
        df = self.clean_data.copy()
        df.loc[3, "volume"] = 0

        result = self.validator.detect_suspended_days(df)
        self.assertTrue(result["has_suspended"])
        self.assertEqual(result["suspended_count"], 1)

    def test_check_duplicates(self):
        """Test duplicate detection."""
        df = self.clean_data.copy()
        df = pd.concat([df, df.iloc[[0]]], ignore_index=True)

        result = self.validator.check_duplicates(df)
        self.assertTrue(result["has_duplicates"])

    def test_check_price_consistency(self):
        """Test OHLC price consistency check."""
        df = self.clean_data.copy()
        df.loc[2, "high"] = 50  # Invalid: high < low

        result = self.validator.check_price_consistency(df)
        self.assertFalse(result["is_consistent"])
        self.assertGreater(result["inconsistent_count"], 0)

    def test_fix_missing_values(self):
        """Test missing value fixing."""
        df = self.clean_data.copy()
        df.loc[3, "close"] = np.nan

        result = self.validator.fix_missing_values(df, method="ffill")
        self.assertFalse(result["close"].isna().any())


class TestCacheManager(unittest.TestCase):
    """Test CacheManager functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.cache = CacheManager(max_size=10, default_ttl=60)

    def test_set_and_get(self):
        """Test basic set and get operations."""
        self.cache.set("key1", "value1")
        self.assertEqual(self.cache.get("key1"), "value1")

    def test_get_nonexistent(self):
        """Test getting non-existent key."""
        self.assertIsNone(self.cache.get("nonexistent"))

    def test_delete(self):
        """Test delete operation."""
        self.cache.set("key1", "value1")
        self.assertTrue(self.cache.delete("key1"))
        self.assertIsNone(self.cache.get("key1"))

    def test_clear(self):
        """Test clear operation."""
        self.cache.set("key1", "value1")
        self.cache.set("key2", "value2")
        self.cache.clear()
        self.assertIsNone(self.cache.get("key1"))
        self.assertIsNone(self.cache.get("key2"))

    def test_ttl_expiration(self):
        """Test TTL expiration."""
        import time
        self.cache.set("key1", "value1", ttl=1)
        self.assertEqual(self.cache.get("key1"), "value1")
        time.sleep(1.1)
        self.assertIsNone(self.cache.get("key1"))

    def test_max_size_eviction(self):
        """Test LRU eviction when max size reached."""
        cache = CacheManager(max_size=3, default_ttl=60)
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.set("key3", "value3")
        cache.set("key4", "value4")  # Should evict key1

        self.assertIsNone(cache.get("key1"))
        self.assertEqual(cache.get("key4"), "value4")

    def test_klines_cache(self):
        """Test K-line specific caching."""
        df = pd.DataFrame({
            "date": ["2024-01-01"],
            "close": [100.0],
        })

        self.cache.set_klines("000001", df, "20240101", "20240131")
        result = self.cache.get_klines("000001", "20240101", "20240131")

        self.assertIsNotNone(result)
        pd.testing.assert_frame_equal(result, df)

    def test_invalidate_symbol(self):
        """Test symbol invalidation."""
        df = pd.DataFrame({"date": ["2024-01-01"], "close": [100.0]})

        self.cache.set_klines("000001", df, "20240101", "20240131")
        self.cache.set_klines("000001", df, "20240201", "20240228")

        count = self.cache.invalidate_symbol("000001")
        self.assertEqual(count, 2)
        self.assertIsNone(self.cache.get_klines("000001", "20240101", "20240131"))

    def test_get_stats(self):
        """Test cache statistics."""
        self.cache.set("key1", "value1")
        self.cache.set("key2", "value2")

        stats = self.cache.get_stats()
        self.assertEqual(stats["size"], 2)
        self.assertEqual(stats["max_size"], 10)

    def test_cleanup_expired(self):
        """Test cleanup of expired entries."""
        import time
        self.cache.set("key1", "value1", ttl=1)
        self.cache.set("key2", "value2", ttl=60)

        time.sleep(1.1)
        count = self.cache.cleanup_expired()

        self.assertEqual(count, 1)
        self.assertIsNone(self.cache.get("key1"))
        self.assertIsNotNone(self.cache.get("key2"))


if __name__ == "__main__":
    unittest.main()
