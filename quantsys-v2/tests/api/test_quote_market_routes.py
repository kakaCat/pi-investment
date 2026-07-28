"""quote_market Flask 路由诊断测试"""
import json
import pytest
from unittest.mock import patch

from adapters.inbound.api.server import create_app
from adapters.inbound.api.routes.quote_market import _quote_failure_suggestion
from adapters.outbound.datasources.models import QuoteData


@pytest.fixture
def client():
    app = create_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


class TestQuoteFailureSuggestion:
    def test_hk_5digit_bare_with_network_error(self):
        s = _quote_failure_suggestion('00836', {'sina': 'Read timed out. (read timeout=5)'})
        assert '港股' in s
        assert '00836.HK' in s
        assert '网络型失败' in s
        assert 'source=db' in s

    def test_hk_suffix(self):
        s = _quote_failure_suggestion('00700.HK', {})
        assert '港股' in s
        assert '00700.HK' in s
        assert 'source=db' in s

    def test_a_share_6digit(self):
        s = _quote_failure_suggestion('999999', {})
        assert '已上市/已退市' in s
        assert 'source=db' in s

    def test_unknown_format_fallback(self):
        s = _quote_failure_suggestion('ABC', {})
        assert '代码格式' in s
        assert 'source=db' in s
