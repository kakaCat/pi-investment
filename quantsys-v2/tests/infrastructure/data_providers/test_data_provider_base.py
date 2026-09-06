"""Tests for base provider classes."""
import pytest
from abc import ABC
from adapters.outbound.datasources.base import (
    BaseDataProvider,
    QuoteProvider,
    FinancialProvider,
    DividendProvider,
    MarketProvider,
    StockProvider
)
from adapters.outbound.datasources.models import QuoteData


def test_base_provider_is_abstract():
    """Test BaseDataProvider cannot be instantiated"""
    with pytest.raises(TypeError):
        BaseDataProvider()


def test_quote_provider_is_abstract():
    """Test QuoteProvider cannot be instantiated"""
    with pytest.raises(TypeError):
        QuoteProvider()


def test_financial_provider_is_abstract():
    """Test FinancialProvider cannot be instantiated"""
    with pytest.raises(TypeError):
        FinancialProvider()


def test_dividend_provider_is_abstract():
    """Test DividendProvider cannot be instantiated"""
    with pytest.raises(TypeError):
        DividendProvider()


def test_market_provider_is_abstract():
    """Test MarketProvider cannot be instantiated"""
    with pytest.raises(TypeError):
        MarketProvider()


def test_stock_provider_is_abstract():
    """Test StockProvider cannot be instantiated"""
    with pytest.raises(TypeError):
        StockProvider()


def test_concrete_quote_provider():
    """Test concrete QuoteProvider implementation"""
    class TestQuoteProvider(QuoteProvider):
        @property
        def name(self) -> str:
            return 'test'

        def get_quote(self, symbol: str):
            return QuoteData(
                symbol=symbol,
                name='Test Stock',
                price=100.0,
                source=self.name,
                timestamp='2026-06-07T14:30:00'
            )

    provider = TestQuoteProvider()
    assert provider.name == 'test'
    assert provider.timeout == 5
    assert provider.retry_count == 1

    result = provider.get_quote('600519')
    assert result.symbol == '600519'
    assert result.source == 'test'
    assert result.price == 100.0
