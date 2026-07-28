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


class TestEastmoneyLastError:
    def test_no_data_sets_last_error(self):
        """东方财富 data 为空需设置 last_error（裸 00836 映射为深市 0.00836）"""
        provider = EastmoneyQuoteProvider()
        resp = _mock_response(json_data={'data': None})
        with patch(
            'adapters.outbound.datasources.providers.quote.eastmoney.requests.get',
            return_value=resp,
        ):
            assert provider.get_quote('00836') is None
        assert provider.last_error is not None
        assert '0.00836' in provider.last_error

    def test_invalid_price_sets_last_error(self):
        """东方财富价格字段为 0（解析返回 None）需设置 last_error"""
        provider = EastmoneyQuoteProvider()
        resp = _mock_response(json_data={'data': {'f43': 0, 'f58': 'X'}})
        with patch(
            'adapters.outbound.datasources.providers.quote.eastmoney.requests.get',
            return_value=resp,
        ):
            assert provider.get_quote('600519') is None
        assert provider.last_error is not None
        assert '1.600519' in provider.last_error


class TestAkshareLastError:
    def test_a_share_not_found_sets_last_error(self):
        """akshare A 股全表无该代码需设置 last_error"""
        provider = AkshareQuoteProvider()
        df = pd.DataFrame({'代码': ['600519'], '名称': ['贵州茅台']})
        with patch(
            'adapters.outbound.datasources.providers.quote.akshare.ak.stock_zh_a_spot_em',
            return_value=df,
        ):
            assert provider.get_quote('999999') is None
        assert provider.last_error is not None
        assert '999999' in provider.last_error

    def test_hk_not_found_sets_last_error(self):
        """akshare 港股全表无该代码需设置 last_error（裸 00836 走港股分支）"""
        provider = AkshareQuoteProvider()
        df = pd.DataFrame({'代码': ['00700'], '名称': ['腾讯控股']})
        with patch(
            'adapters.outbound.datasources.providers.quote.akshare.ak.stock_hk_spot_em',
            return_value=df,
        ):
            assert provider.get_quote('00836') is None
        assert provider.last_error is not None
        assert '00836' in provider.last_error
