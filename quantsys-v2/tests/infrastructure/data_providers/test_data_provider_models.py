"""Tests for data models."""
import pytest
from datetime import datetime
from adapters.outbound.datasources.models import (
    QuoteData, FinancialData, DividendData, MarketData, StockData
)


def test_quote_data_valid():
    """Test QuoteData with valid fields"""
    quote = QuoteData(
        symbol='600519.SH',
        name='贵州茅台',
        price=1850.5,
        source='sina',
        timestamp='2026-06-07T14:30:00'
    )
    assert quote.symbol == '600519.SH'
    assert quote.price == 1850.5
    assert quote.source == 'sina'


def test_quote_data_invalid_price():
    """Test QuoteData rejects invalid price"""
    with pytest.raises(ValueError, match="price must be positive"):
        QuoteData(symbol='600519', name='茅台', price=-100, source='sina', timestamp='2026-06-07T14:30:00')


def test_quote_data_zero_price():
    """Test QuoteData rejects zero price"""
    with pytest.raises(ValueError, match="price must be positive"):
        QuoteData(symbol='600519', name='茅台', price=0, source='sina', timestamp='2026-06-07T14:30:00')


def test_quote_data_empty_symbol():
    """Test QuoteData rejects empty symbol"""
    with pytest.raises(ValueError, match="symbol cannot be empty"):
        QuoteData(symbol='', name='茅台', price=100, source='sina', timestamp='2026-06-07T14:30:00')


def test_quote_data_whitespace_symbol():
    """Test QuoteData rejects whitespace symbol"""
    with pytest.raises(ValueError, match="symbol cannot be empty"):
        QuoteData(symbol='   ', name='茅台', price=100, source='sina', timestamp='2026-06-07T14:30:00')


def test_financial_data_creation():
    """Test FinancialData model"""
    data = FinancialData(
        symbol='600519.SH',
        roe=25.5,
        gross_margin=90.2,
        source='eastmoney',
        timestamp='2026-06-07T14:30:00'
    )
    assert data.roe == 25.5
    assert data.source == 'eastmoney'


def test_dividend_data_creation():
    """Test DividendData model"""
    data = DividendData(
        symbol='600519.SH',
        dividend_per_share=30.5,
        dividend_yield=1.65,
        ex_dividend_date='2026-07-15',
        source='akshare',
        timestamp='2026-06-07T14:30:00'
    )
    assert data.dividend_per_share == 30.5
    assert data.ex_dividend_date == '2026-07-15'


def test_market_data_creation():
    """Test MarketData model"""
    data = MarketData(
        data_type='overview',
        data={'rise': 2500, 'fall': 1200, 'unchanged': 100},
        source='eastmoney',
        timestamp='2026-06-07T14:30:00'
    )
    assert data.data_type == 'overview'
    assert data.data['rise'] == 2500


def test_stock_data_creation():
    """Test StockData model"""
    data = StockData(
        symbol='600519.SH',
        data_type='announcement',
        data=[{'title': '年报', 'date': '2026-04-20'}],
        total=1,
        source='akshare',
        timestamp='2026-06-07T14:30:00'
    )
    assert data.data_type == 'announcement'
    assert data.total == 1
    assert len(data.data) == 1
