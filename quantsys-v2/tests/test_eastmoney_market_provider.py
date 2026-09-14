# -*- coding: utf-8 -*-
"""东财直连第二源契约测试（2026-09-14，w-2129d492，REQ-48d896 t9）

锁定三件事：
1. 字段映射**语义正确**（东财英文字段 → 与 akshare 源相同的中文键）；
   重点是 top_fund_stocks —— akshare 那条因**位置式列名**而错位，
   本源按字段名取值从结构上避免该缺陷；
2. 失败纪律：last_error 必须设置（框架据此判「真故障」），且**绝不外抛异常**
   （_try_providers 只捕获超时，其它异常会穿透整个 failover 循环）；
3. 真 failover：akshare 失败时自动切到 eastmoney，attempted_sources 含两个源。
"""
import sys
import types

import pandas as pd
import pytest

from adapters.outbound.datasources.providers.market import eastmoney as em


class _Resp:
    def __init__(self, payload):
        self._p = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._p


@pytest.fixture
def provider():
    return em.EastmoneyMarketProvider()


def _patch_get(monkeypatch, payload):
    def fake_get(url, params=None, **kw):
        return _Resp(payload(params or {}) if callable(payload) else payload)
    monkeypatch.setattr(em.requests, 'get', fake_get)


# ---------------------------------------------------------------------------
# 1. 字段映射
# ---------------------------------------------------------------------------

def test_top_fund_stocks_maps_fields_semantically(monkeypatch, provider):
    """核心断言：股票代码/简称/家数/市值各归其位（akshare 那条会错位）。"""
    _patch_get(monkeypatch, {
        'data': [{
            'SECURITY_CODE': '300308', 'SECURITY_NAME_ABBR': '中际旭创',
            'HOULD_NUM': 3578, 'TOTAL_SHARES': 214732617, 'HOLD_VALUE': 272710423590,
            'HOLDCHA': '减仓', 'HOLDCHA_NUM': -15877661, 'HOLDCHA_RATIO': -6.89,
        }],
    })
    md = provider.get_top_fund_stocks('fund', 10)
    assert md is not None
    row = md.data['stocks'][0]
    assert row['股票代码'] == '300308'
    assert row['股票简称'] == '中际旭创'
    assert row['持有基金家数'] == 3578
    assert row['持股市值'] == 272710423590
    assert row['持股变化'] == '减仓'
    assert md.source == 'eastmoney'


def test_top_holders_picks_latest_period(monkeypatch, provider):
    """多个报告期时只取最新一期，且按名次排序。"""
    _patch_get(monkeypatch, {
        'result': {'data': [
            {'END_DATE': '2025-12-31 00:00:00', 'HOLDER_RANK': 1, 'HOLDER_NAME': '旧期股东',
             'HOLD_NUM': 1, 'HOLD_NUM_RATIO': 1.0},
            {'END_DATE': '2026-06-30 00:00:00', 'HOLDER_RANK': 2, 'HOLDER_NAME': '第二',
             'HOLD_NUM': 20, 'HOLD_NUM_RATIO': 2.0},
            {'END_DATE': '2026-06-30 00:00:00', 'HOLDER_RANK': 1, 'HOLDER_NAME': '第一',
             'HOLD_NUM': 10, 'HOLD_NUM_RATIO': 54.5},
        ]},
    })
    md = provider.get_top_holders('600519')
    assert md.data['report_date'] == '2026-06-30'
    assert [h['股东名称'] for h in md.data['holders']] == ['第一', '第二']
    assert md.data['holders'][0]['占总股本持股比例'] == 54.5


def test_stock_comment_maps_indicator_fields(monkeypatch, provider):
    _patch_get(monkeypatch, {
        'result': {'data': [{
            'SECURITY_CODE': '600519', 'SECURITY_NAME_ABBR': '贵州茅台',
            'CLOSE_PRICE': 1277.96, 'ORG_PARTICIPATE': 0.4675, 'TOTALSCORE': 75.2,
            'PRIME_COST': 1277.27, 'TRADE_DATE': '2026-09-14 00:00:00',
        }]},
    })
    md = provider.get_stock_comment('600519')
    c = md.data['comment']
    assert c['代码'] == '600519' and c['机构参与度'] == 0.4675
    assert c['综合得分'] == 75.2 and c['交易日'] == '2026-09-14'


def test_holder_changes_maps_fields(monkeypatch, provider):
    _patch_get(monkeypatch, {
        'result': {'data': [{
            'END_DATE': '2026-06-30 00:00:00', 'HOLDER_NUM': 296404, 'PRE_HOLDER_NUM': 243159,
            'HOLDER_NUM_CHANGE': 53245, 'HOLDER_NUM_RATIO': 21.9, 'SECURITY_CODE': '600519',
            'SECURITY_NAME_ABBR': '贵州茅台',
        }]},
    })
    md = provider.get_holder_changes('600519', 1)
    p = md.data['periods'][0]
    assert p['股东户数统计截止日'] == '2026-06-30'
    assert p['股东户数-本次'] == 296404 and p['股东户数-增减'] == 53245


# ---------------------------------------------------------------------------
# 2. 失败纪律：设置 last_error、绝不出抛
# ---------------------------------------------------------------------------

def test_transport_error_sets_last_error_and_returns_none(monkeypatch, provider):
    def boom(*a, **kw):
        raise ConnectionError('upstream unreachable')
    monkeypatch.setattr(em.requests, 'get', boom)

    assert provider.get_top_holders('600519') is None
    assert provider.last_error, 'last_error 必须设置 —— 框架据此判「真故障」'


def test_http_error_does_not_propagate(monkeypatch, provider):
    """异常绝不能外抛：_try_providers 只捕获超时，其它异常会穿透 failover 循环。"""
    def boom(*a, **kw):
        raise RuntimeError('weird upstream')
    monkeypatch.setattr(em.requests, 'get', boom)

    for fn, args in [(provider.get_top_holders, ('600519',)),
                     (provider.get_holder_changes, ('600519',)),
                     (provider.get_top_fund_stocks, ('fund', 5)),
                     (provider.get_stock_comment, ('600519',))]:
        assert fn(*args) is None
        assert provider.last_error


def test_empty_payload_is_healthy_empty(monkeypatch, provider):
    """源正常但无数据 → empty=True（不是故障）。"""
    _patch_get(monkeypatch, {'result': {'data': []}})
    md = provider.get_holder_changes('600519')
    assert md is not None and md.data['empty'] is True and md.data['total'] == 0


def test_illegal_symbol_sets_last_error(provider):
    assert provider.get_stock_comment('not-a-code') is None
    assert provider.last_error


# ---------------------------------------------------------------------------
# 3. 真 failover：akshare 失败 → eastmoney 兜底
# ---------------------------------------------------------------------------

def test_manager_fails_over_to_eastmoney(monkeypatch):
    """拔掉 akshare：manager 必须自动切到 eastmoney，且 attempted_sources 含两个源。"""
    from adapters.outbound.datasources import get_data_provider_manager
    from adapters.outbound.datasources.providers.market.akshare import AkshareMarketProvider

    def broken(self, *a, **kw):
        self.last_error = '模拟 akshare 故障'
        return None

    monkeypatch.setattr(AkshareMarketProvider, 'get_holder_changes', broken)
    _patch_get(monkeypatch, {
        'result': {'data': [{
            'END_DATE': '2026-06-30 00:00:00', 'HOLDER_NUM': 296404,
            'PRE_HOLDER_NUM': 243159, 'SECURITY_CODE': '600519',
        }]},
    })

    res = get_data_provider_manager().get_holder_changes('600519', 1)
    assert res['success'] is True
    assert res['source'] == 'eastmoney'
    assert 'akshare' in res['attempted_sources']
    assert 'eastmoney' in res['attempted_sources']
    assert res['data'].data['periods'][0]['股东户数-本次'] == 296404


def test_manager_recovers_top_fund_stocks_via_eastmoney(monkeypatch):
    """akshare 因上游错位拒绝返回时，端点必须由 eastmoney 兜底为**正确**数据。

    这是 t9 的第二个（更重要的）价值：不只是多一个源，而是修好了
    /api/sentiment/top-fund-stocks —— akshare 的位置式列名会返回错位表。
    """
    from adapters.outbound.datasources import get_data_provider_manager
    from adapters.outbound.datasources.providers.market import akshare as mk

    broken = pd.DataFrame([
        {'序号': 1, '股票代码': -42049165018.7, '股票简称': '600519',
         '持有基金家数': '01', '持股总数': 1697},
    ])
    monkeypatch.setattr(
        mk.AkshareMarketProvider, 'get_top_fund_stocks',
        lambda self, *a, **kw: (setattr(self, 'last_error', '上游列错位'), None)[1],
    )
    _patch_get(monkeypatch, {
        'data': [{'SECURITY_CODE': '600519', 'SECURITY_NAME_ABBR': '贵州茅台',
                  'HOULD_NUM': 992, 'TOTAL_SHARES': 1697, 'HOLD_VALUE': 45030370,
                  'HOLDCHA': '增仓', 'HOLDCHA_NUM': 100, 'HOLDCHA_RATIO': 1.0}],
    })

    res = get_data_provider_manager().get_top_fund_stocks('fund', 5)
    assert res['success'] is True, res.get('provider_errors')
    assert res['source'] == 'eastmoney'
    row = res['data'].data['stocks'][0]
    assert row['股票代码'] == '600519' and row['股票简称'] == '贵州茅台'
