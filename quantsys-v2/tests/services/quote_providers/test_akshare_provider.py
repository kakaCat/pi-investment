"""
Tests for AkshareQuoteProvider
"""
import unittest
from unittest.mock import patch, MagicMock
import pandas as pd
from datetime import datetime

from application.services.quote_providers.akshare_provider import AkshareQuoteProvider
from application.services.quote_providers.base import QuoteData


class TestAkshareQuoteProvider(unittest.TestCase):
    """Test cases for AkshareQuoteProvider"""

    def setUp(self):
        """Set up test fixtures"""
        self.provider = AkshareQuoteProvider()

    def test_provider_name(self):
        """Test provider name property"""
        self.assertEqual(self.provider.name, "akshare")

    @patch('services.quote_providers.akshare_provider.ak.stock_zh_a_spot_em')
    def test_get_a_stock_quote_success(self, mock_spot_em):
        """Test successful A-share quote retrieval"""
        # Mock akshare response
        mock_df = pd.DataFrame([{
            '代码': '000001',
            '名称': '浦发银行',
            '最新价': 1800.50,
            '今开': 1795.00,
            '最高': 1810.00,
            '最低': 1790.00,
            '昨收': 1798.00,
            '成交量': 1234567,
            '成交额': 2220000000.0,
            '涨跌幅': 0.14
        }])
        mock_spot_em.return_value = mock_df

        # Call get_quote
        result = self.provider.get_quote('000001')

        # Verify result
        self.assertIsInstance(result, QuoteData)
        self.assertEqual(result.symbol, '000001')
        self.assertEqual(result.name, '浦发银行')
        self.assertEqual(result.price, 1800.50)
        self.assertEqual(result.open, 1795.00)
        self.assertEqual(result.high, 1810.00)
        self.assertEqual(result.low, 1790.00)
        self.assertEqual(result.prev_close, 1798.00)
        self.assertEqual(result.volume, 1234567)
        self.assertEqual(result.amount, 2220000000.0)
        self.assertEqual(result.change_pct, 0.14)
        self.assertEqual(result.source, 'akshare')
        self.assertIsNotNone(result.timestamp)

        # Verify akshare was called
        mock_spot_em.assert_called_once()

    @patch('services.quote_providers.akshare_provider.ak.stock_hk_spot_em')
    def test_get_hk_stock_quote_success(self, mock_hk_spot):
        """Test successful HK stock quote retrieval"""
        # Mock akshare response
        mock_df = pd.DataFrame([{
            '代码': '00700',
            '名称': '腾讯控股',
            '最新价': 380.50,
            '今开': 378.00,
            '最高': 382.00,
            '最低': 377.00,
            '昨收': 379.00,
            '成交量': 9876543,
            '涨跌幅': 0.40
        }])
        mock_hk_spot.return_value = mock_df

        # Call get_quote with HK symbol
        result = self.provider.get_quote('00700')

        # Verify result
        self.assertIsInstance(result, QuoteData)
        self.assertEqual(result.symbol, '00700')
        self.assertEqual(result.name, '腾讯控股')
        self.assertEqual(result.price, 380.50)
        self.assertEqual(result.open, 378.00)
        self.assertEqual(result.high, 382.00)
        self.assertEqual(result.low, 377.00)
        self.assertEqual(result.prev_close, 379.00)
        self.assertEqual(result.volume, 9876543)
        self.assertIsNone(result.amount)  # HK data doesn't have 成交额
        self.assertEqual(result.change_pct, 0.40)
        self.assertEqual(result.source, 'akshare')
        self.assertIsNotNone(result.timestamp)

        # Verify akshare was called
        mock_hk_spot.assert_called_once()

    @patch('services.quote_providers.akshare_provider.ak.stock_zh_a_spot_em')
    def test_stock_not_found(self, mock_spot_em):
        """Test stock not found returns None"""
        # Mock empty DataFrame
        mock_df = pd.DataFrame(columns=['代码', '名称', '最新价'])
        mock_spot_em.return_value = mock_df

        # Call get_quote
        result = self.provider.get_quote('999999')

        # Verify None returned
        self.assertIsNone(result)
        mock_spot_em.assert_called_once()

    @patch('services.quote_providers.akshare_provider.ak.stock_zh_a_spot_em')
    def test_akshare_api_error(self, mock_spot_em):
        """Test akshare API error handling"""
        # Mock API error
        mock_spot_em.side_effect = Exception("Network error")

        # Call get_quote and expect exception
        with self.assertRaises(Exception) as context:
            self.provider.get_quote('000001')

        # Verify error message
        self.assertIn("akshare 查询失败", str(context.exception))
        mock_spot_em.assert_called_once()

    @patch('services.quote_providers.akshare_provider.ak.stock_zh_a_spot_em')
    def test_a_share_symbol_normalization(self, mock_spot_em):
        """Test A-share symbol with .SH/.SZ suffix is properly cleaned"""
        # Mock akshare response
        mock_df = pd.DataFrame([{
            '代码': '000001',
            '名称': '浦发银行',
            '最新价': 1800.50,
            '今开': 1795.00,
            '最高': 1810.00,
            '最低': 1790.00,
            '昨收': 1798.00,
            '成交量': 1234567,
            '成交额': 2220000000.0,
            '涨跌幅': 0.14
        }])
        mock_spot_em.return_value = mock_df

        # Call with .SH suffix
        result = self.provider.get_quote('000001.SH')

        # Verify suffix was removed
        self.assertIsNotNone(result)
        self.assertEqual(result.symbol, '000001')
        mock_spot_em.assert_called_once()

    @patch('services.quote_providers.akshare_provider.ak.stock_hk_spot_em')
    def test_hk_stock_symbol_normalization(self, mock_hk_spot):
        """Test HK stock symbol with .HK suffix is properly cleaned and padded"""
        # Mock akshare response
        mock_df = pd.DataFrame([{
            '代码': '00700',
            '名称': '腾讯控股',
            '最新价': 380.50,
            '今开': 378.00,
            '最高': 382.00,
            '最低': 377.00,
            '昨收': 379.00,
            '成交量': 9876543,
            '涨跌幅': 0.40
        }])
        mock_hk_spot.return_value = mock_df

        # Call with .HK suffix and short code
        result = self.provider.get_quote('700.HK')

        # Verify suffix was removed and padded to 5 digits
        self.assertIsNotNone(result)
        self.assertEqual(result.symbol, '00700')
        mock_hk_spot.assert_called_once()

    @patch('services.quote_providers.akshare_provider.ak.stock_zh_a_spot_em')
    def test_missing_dataframe_column(self, mock_spot_em):
        """Test graceful handling when DataFrame schema changes"""
        # Mock DataFrame with missing column
        mock_df = pd.DataFrame([{
            '代码': '000001',
            '名称': '浦发银行',
            '最新价': 1800.50,
            # Missing other required columns
        }])
        mock_spot_em.return_value = mock_df

        # Call get_quote and expect exception with helpful message
        with self.assertRaises(Exception) as context:
            self.provider.get_quote('000001')

        # Verify error message mentions schema change
        error_msg = str(context.exception)
        self.assertIn("akshare 查询失败", error_msg)
        self.assertIn("数据格式变化", error_msg)


if __name__ == '__main__':
    unittest.main()
