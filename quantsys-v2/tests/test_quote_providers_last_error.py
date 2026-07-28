"""quote providers last_error 诊断测试"""
import pandas as pd
from unittest.mock import patch, MagicMock

from adapters.outbound.datasources.providers.quote.tencent import TencentQuoteProvider
from adapters.outbound.datasources.providers.quote.sina import SinaQuoteProvider
from adapters.outbound.datasources.providers.quote.eastmoney import EastmoneyQuoteProvider
from adapters.outbound.datasources.providers.quote.akshare import AkshareQuoteProvider


def _mock_response(text='', json_data=None):
    resp = MagicMock()
    resp.text = text
    resp.json.return_value = json_data if json_data is not None else {}
    return resp


class TestTencentLastError:
    def test_no_match_sets_last_error(self):
        """腾讯 v_pv_none_match（代码无匹配）走解析分支返回 None，需设置 last_error"""
        provider = TencentQuoteProvider()
        resp = _mock_response(text='v_pv_none_match="1";')
        with patch(
            'adapters.outbound.datasources.providers.quote.tencent.requests.get',
            return_value=resp,
        ):
            assert provider.get_quote('00836') is None
        assert provider.last_error is not None
        assert 'sz00836' in provider.last_error

    def test_empty_quote_sets_last_error(self):
        """腾讯返回空串（v_xxx=""）需设置 last_error"""
        provider = TencentQuoteProvider()
        resp = _mock_response(text='v_sh600519="";')
        with patch(
            'adapters.outbound.datasources.providers.quote.tencent.requests.get',
            return_value=resp,
        ):
            assert provider.get_quote('600519') is None
        assert provider.last_error is not None
        assert 'sh600519' in provider.last_error


class TestSinaLastError:
    def test_empty_response_sets_last_error(self):
        """新浪空响应需设置 last_error（裸 00836 会被映射为 A 股 000836）"""
        provider = SinaQuoteProvider()
        resp = _mock_response(text='')
        with patch(
            'adapters.outbound.datasources.providers.quote.sina.requests.get',
            return_value=resp,
        ):
            assert provider.get_quote('00836') is None
        assert provider.last_error is not None
        assert '000836' in provider.last_error

    def test_incomplete_data_sets_last_error(self):
        """新浪返回字段不足（解析返回 None）需设置 last_error"""
        provider = SinaQuoteProvider()
        resp = _mock_response(text='var hq_str_1600519="贵州茅台,1308.0";')
        with patch(
            'adapters.outbound.datasources.providers.quote.sina.requests.get',
            return_value=resp,
        ):
            assert provider.get_quote('600519') is None
        assert provider.last_error is not None
        assert '1600519' in provider.last_error
