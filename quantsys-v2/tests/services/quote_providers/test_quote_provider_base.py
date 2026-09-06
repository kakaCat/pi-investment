"""
测试 QuoteProvider 基础类
"""
import pytest
from application.services.quote_providers.base import QuoteData, QuoteProvider


class TestQuoteData:
    """测试 QuoteData 数据模型"""

    def test_quote_data_creation(self):
        """测试创建 QuoteData 对象"""
        quote = QuoteData(
            symbol='600900',
            name='长江电力',
            price=27.45,
            open=27.20,
            high=27.50,
            low=27.15,
            prev_close=27.24,
            volume=1000000,
            amount=27450000.0,
            change=0.21,
            change_pct=0.77,
            source='test',
            timestamp='2026-05-29T14:30:00'
        )

        assert quote.symbol == '600900'
        assert quote.name == '长江电力'
        assert quote.price == 27.45
        assert quote.source == 'test'
        assert quote.timestamp == '2026-05-29T14:30:00'

    def test_quote_data_optional_fields(self):
        """测试可选字段默认值"""
        quote = QuoteData(
            symbol='600900',
            name='长江电力',
            price=27.45
        )

        assert quote.open is None
        assert quote.high is None
        assert quote.volume is None
        assert quote.source == ''
        assert quote.timestamp == ''

    def test_quote_data_validation_empty_symbol(self):
        """测试空股票代码验证"""
        with pytest.raises(ValueError, match="symbol cannot be empty"):
            QuoteData(symbol='', name='测试', price=100.0)

        with pytest.raises(ValueError, match="symbol cannot be empty"):
            QuoteData(symbol='   ', name='测试', price=100.0)

    def test_quote_data_validation_negative_price(self):
        """测试负价格验证"""
        with pytest.raises(ValueError, match="price must be positive"):
            QuoteData(symbol='600900', name='测试', price=-10.0)

    def test_quote_data_validation_zero_price(self):
        """测试零价格验证"""
        with pytest.raises(ValueError, match="price must be positive"):
            QuoteData(symbol='600900', name='测试', price=0.0)


class MockProvider(QuoteProvider):
    """Mock Provider 用于测试"""

    @property
    def name(self) -> str:
        return "mock"

    def get_quote(self, symbol: str):
        return QuoteData(
            symbol=symbol,
            name='测试股票',
            price=100.0,
            source='mock',
            timestamp='2026-05-29T14:30:00'
        )


class TestQuoteProvider:
    """测试 QuoteProvider 基类"""

    def test_provider_default_timeout(self):
        """测试默认超时时间"""
        provider = MockProvider()
        assert provider.timeout == 5
        assert provider.retry_count == 1

    def test_normalize_symbol(self):
        """测试股票代码标准化"""
        provider = MockProvider()

        assert provider._normalize_symbol('600900') == '600900'
        assert provider._normalize_symbol('600900.SH') == '600900.SH'
        assert provider._normalize_symbol('600900 ') == '600900'
        assert provider._normalize_symbol(' 600900 ') == '600900'
        # 保留连字符等特殊字符
        assert provider._normalize_symbol('BRK-A') == 'BRK-A'
        assert provider._normalize_symbol(' BRK-A ') == 'BRK-A'

    def test_get_quote(self):
        """测试获取行情"""
        provider = MockProvider()
        quote = provider.get_quote('600900')

        assert quote is not None
        assert quote.symbol == '600900'
        assert quote.price == 100.0
        assert quote.source == 'mock'
