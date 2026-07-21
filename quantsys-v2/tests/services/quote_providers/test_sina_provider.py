"""
Tests for SinaQuoteProvider
"""
import pytest
from unittest.mock import Mock, patch
from application.services.quote_providers.sina_provider import SinaQuoteProvider


class TestSinaQuoteProvider:
    """Test suite for SinaQuoteProvider"""

    def test_provider_name(self):
        """Test provider name property"""
        provider = SinaQuoteProvider()
        assert provider.name == "sina"

    @patch('services.quote_providers.sina_provider.requests.get')
    def test_get_a_stock_quote_success(self, mock_get):
        """Test successful A-share quote retrieval"""
        # Mock response for 000001.SH (浦发银行)
        mock_response = Mock()
        mock_response.text = 'var hq_str_1000001="浦发银行,1650.00,1645.00,1655.00,1660.00,1640.00,1655.00,1656.00,1234567,2041234567.00,100,1655.00,200,1654.00,300,1653.00,400,1652.00,500,1651.00,100,1656.00,200,1657.00,300,1658.00,400,1659.00,500,1660.00,2026-05-29,15:00:00,00";'
        mock_response.encoding = 'gbk'
        mock_get.return_value = mock_response

        provider = SinaQuoteProvider()
        quote = provider.get_quote("000001.SH")

        assert quote is not None
        assert quote.symbol == "000001.SH"
        assert quote.name == "浦发银行"
        assert quote.price == 1655.00
        assert quote.open == 1650.00
        assert quote.high == 1660.00
        assert quote.low == 1640.00
        assert quote.prev_close == 1645.00
        assert quote.volume == 1234567
        assert quote.amount == 2041234567.00
        assert quote.change == 10.00  # 1655 - 1645
        assert abs(quote.change_pct - 0.608) < 0.001  # (10/1645)*100
        assert quote.timestamp is not None

    @patch('services.quote_providers.sina_provider.requests.get')
    def test_get_hk_stock_quote_success(self, mock_get):
        """Test successful HK stock quote retrieval"""
        # Mock response for 00700.HK (腾讯控股)
        mock_response = Mock()
        mock_response.text = 'var hq_str_hk00700="00700,腾讯控股,348.0,349.0,352.0,347.0,350.0,349.5,1000000,350000000.0,2026-05-29,15:00:00";'
        mock_response.encoding = 'gbk'
        mock_get.return_value = mock_response

        provider = SinaQuoteProvider()
        quote = provider.get_quote("00700.HK")

        assert quote is not None
        assert quote.symbol == "00700.HK"
        assert quote.name == "腾讯控股"
        assert quote.price == 350.0
        assert quote.open == 348.0
        assert quote.high == 352.0
        assert quote.low == 347.0
        assert quote.prev_close == 349.0
        assert quote.change == 1.0  # 350 - 349
        assert abs(quote.change_pct - 0.286) < 0.001  # (1/349)*100
        assert quote.timestamp is not None

    @patch('services.quote_providers.sina_provider.requests.get')
    def test_empty_response(self, mock_get):
        """Test empty response handling"""
        mock_response = Mock()
        mock_response.text = 'var hq_str_sh000001="";'
        mock_response.encoding = 'gbk'
        mock_get.return_value = mock_response

        provider = SinaQuoteProvider()
        quote = provider.get_quote("000001.SH")

        assert quote is None

    @patch('services.quote_providers.sina_provider.requests.get')
    def test_network_error(self, mock_get):
        """Test network error handling"""
        mock_get.side_effect = Exception("Connection timeout")

        provider = SinaQuoteProvider()
        with pytest.raises(Exception) as exc_info:
            provider.get_quote("000001.SH")

        assert "新浪财经查询失败" in str(exc_info.value)
