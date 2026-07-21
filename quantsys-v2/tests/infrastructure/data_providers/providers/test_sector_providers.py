"""Unit tests for EastmoneySectorProvider (板块成分数据源)."""
import pytest
from unittest.mock import patch, Mock

from adapters.outbound.datasources.providers.sector.eastmoney import (
    EastmoneySectorProvider,
    _HOSTS,
)


def _resp(diff, total=None):
    """构造 clist 响应"""
    m = Mock()
    m.raise_for_status = Mock()
    m.json.return_value = {'rc': 0, 'data': {'diff': diff, 'total': total if total is not None else len(diff)}}
    return m


def _boards(*names):
    return [{'f12': f'BK{i:04d}', 'f14': n} for i, n in enumerate(names)]


class TestSectorStocks:
    def setup_method(self):
        self.p = EastmoneySectorProvider()

    def test_industry_sector_found(self):
        """行业板块命中 → found=True, 返回成分股"""
        boards = _boards('电力', '银行')
        stocks = [{'f12': '600236', 'f14': '桂冠电力', 'f9': 15.0, 'f20': 2.0e10}]

        def side_effect(url, **kw):
            fs = kw['params']['fs']
            if fs.startswith('m:90'):
                return _resp(boards)
            return _resp(stocks)

        with patch('requests.get', side_effect=side_effect):
            md = self.p.get_sector_stocks('电力')
        assert md.data['found'] is True
        assert md.data['sector_code'] == 'BK0000'
        assert md.data['stocks'][0]['symbol'] == '600236'
        assert md.data['stocks'][0]['pe'] == 15.0
        assert md.source == 'eastmoney'

    def test_concept_sector_fallback(self):
        """行业板块未命中 → 继续搜概念板块（如白酒属概念）"""
        industry = _boards('电力', '银行')
        concept = _boards('人工智能', '白酒')
        stocks = [{'f12': '600519', 'f14': '贵州茅台', 'f9': 14.0, 'f20': 1.5e12}]

        def side_effect(url, **kw):
            fs = kw['params']['fs']
            if fs == 'm:90+t:2+f:!50':
                return _resp(industry)
            if fs == 'm:90+t:3+f:!50':
                return _resp(concept)
            return _resp(stocks)

        with patch('requests.get', side_effect=side_effect):
            md = self.p.get_sector_stocks('白酒')
        assert md.data['found'] is True
        assert md.data['sector_code'] == 'BK0001'

    def test_sector_not_found_returns_found_false(self):
        """板块名单取到但未匹配 → found=False（有效响应，非网络错误）"""
        with patch('requests.get', return_value=_resp(_boards('电力', '银行'))):
            md = self.p.get_sector_stocks('不存在的板块')
        assert md.data['found'] is False
        assert md.data['sector_code'] is None
        assert md.data['stocks'] == []

    def test_host_fallback_on_failure(self):
        """前序主机连接失败 → 自动尝试后续主机"""
        boards = _boards('电力')
        calls = []

        def side_effect(url, **kw):
            calls.append(url)
            if _HOSTS[0] in url:
                raise ConnectionError('reset')  # 第一个主机被重置
            return _resp(boards if kw['params']['fs'].startswith('m:90') else [])

        with patch('requests.get', side_effect=side_effect):
            md = self.p.get_sector_stocks('电力')
        assert md.data['found'] is True
        assert any(_HOSTS[0] in c for c in calls)  # 试过第一个
        assert any(_HOSTS[1] in c for c in calls)  # 回退到第二个

    def test_all_hosts_fail_raises(self):
        """全部主机失败 → 抛异常（交给 manager 故障转移）"""
        with patch('requests.get', side_effect=ConnectionError('down')):
            with pytest.raises(Exception):
                self.p.get_sector_stocks('电力')

    def test_pagination(self):
        """单页上限时按 pn 翻页拉取全量"""
        page1 = [{'f12': f'BK{i:04d}', 'f14': f'板块{i}'} for i in range(100)]
        page2 = [{'f12': 'BK9000', 'f14': '白酒'}]
        stocks = [{'f12': '600519', 'f14': '贵州茅台', 'f9': 14.0, 'f20': 1e12}]

        def side_effect(url, **kw):
            fs, pn = kw['params']['fs'], kw['params']['pn']
            if fs.startswith('m:90'):
                return _resp(page1 if pn == 1 else page2, total=101)
            return _resp(stocks)

        with patch('requests.get', side_effect=side_effect):
            md = self.p.get_sector_stocks('白酒')
        assert md.data['found'] is True
        assert md.data['sector_code'] == 'BK9000'

    def test_no_proxy_bypass(self):
        """所有请求必须显式绕过本地代理"""
        captured = []

        def side_effect(url, **kw):
            captured.append(kw.get('proxies'))
            return _resp(_boards('电力'))

        with patch('requests.get', side_effect=side_effect):
            self.p.get_sector_stocks('电力')
        assert captured and all(p == {'http': None, 'https': None} for p in captured)
