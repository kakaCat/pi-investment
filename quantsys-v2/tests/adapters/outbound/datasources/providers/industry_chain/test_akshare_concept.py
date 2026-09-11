"""新浪行业成分 provider（akshare_concept）契约测试（fake akshare，不触网）

⚠️ 该 provider 的上游实为**新浪行业分类**（文件名是交付清单约定），证据类型写'行业分类'，
   置信 medium —— 绝不冒充主营构成。测试把这一点也锁住。

锁住的契约：
  板块清单 / 板块成员的行契约（candidate=True、stage=midstream、evidence_kind=行业分类）
  未命中板块 / 取数失败必须区分（None+last_error vs []）
  上游形态变化（不是 DataFrame）必须 fail-loud 而不是抛 AttributeError 炸掉整条链
"""
import sys
import types

import pandas as pd
import pytest

from adapters.outbound.datasources.providers.industry_chain import akshare_concept as mod
from adapters.outbound.datasources.providers.industry_chain.akshare_concept import (
    AkshareConceptProvider,
)


def _install(monkeypatch, *, sectors=None, members=None, detail_boom=False, spot_boom=False):
    def stock_sector_spot(indicator=None):
        if spot_boom:
            raise ConnectionError('sina blocked')
        return pd.DataFrame(sectors if sectors is not None else [
            {'label': 'new_blhy', '板块': '玻璃行业', '公司家数': 19},
            {'label': 'new_dlhy', '板块': '电力行业', '公司家数': 62},
        ])

    def stock_sector_detail(sector=None):
        if detail_boom:
            raise RuntimeError('detail failed')
        return pd.DataFrame(members if members is not None else [
            {'symbol': 'sh600176', 'code': '600176', 'name': '中国巨石',
             'trade': 12.3, 'changepercent': 1.2},
            {'symbol': 'sz002080', 'code': '002080', 'name': '中材科技',
             'trade': 20.0, 'changepercent': -0.5},
        ])

    monkeypatch.setitem(sys.modules, 'akshare', types.SimpleNamespace(
        stock_sector_spot=stock_sector_spot, stock_sector_detail=stock_sector_detail))


def test_板块清单行契约(monkeypatch):
    _install(monkeypatch)
    rows = AkshareConceptProvider().list_chains()
    assert [r['chain_id'] for r in rows] == ['sina_sector:new_blhy', 'sina_sector:new_dlhy']
    assert rows[0]['name'] == '玻璃行业' and rows[0]['member_count'] == 19
    assert rows[0]['candidate'] is True and rows[0]['stale'] is False


def test_板块为空是空结果不是故障(monkeypatch):
    _install(monkeypatch, sectors=[])
    provider = AkshareConceptProvider()
    assert provider.list_chains() == []
    assert provider.last_error is None


def test_取数失败必须写last_error(monkeypatch):
    _install(monkeypatch, spot_boom=True)
    provider = AkshareConceptProvider()
    assert provider.list_chains() is None
    assert 'ConnectionError' in provider.last_error


def test_成员行契约(monkeypatch):
    _install(monkeypatch)
    rows = AkshareConceptProvider().get_chain('玻璃行业')
    assert len(rows) == 1
    node = rows[0]
    assert node['node_id'] == 'sector:new_blhy' and node['stage'] == 'midstream'
    assert node['candidate'] is True
    member = node['members'][0]
    assert member['symbol'] == '600176' and member['name'] == '中国巨石'
    assert member['evidence_kind'] == '行业分类', '低置信源不得冒充主营构成'
    assert member['confidence'] == 'medium'
    assert member['exposure_ratio'] is None
    assert member['source'] == 'akshare_concept'


def test_带前缀的chain_id也能匹配(monkeypatch):
    _install(monkeypatch)
    assert AkshareConceptProvider().get_chain('sina_sector:new_blhy')[0]['chain_name'] == '玻璃行业'


def test_未命中板块必须显式失败而不是返回空节点(monkeypatch):
    _install(monkeypatch)
    provider = AkshareConceptProvider()
    assert provider.get_chain('不存在的板块') is None
    assert provider.last_error and '没有' in provider.last_error


def test_成分取数失败写last_error(monkeypatch):
    _install(monkeypatch, detail_boom=True)
    provider = AkshareConceptProvider()
    assert provider.get_chain('玻璃行业') is None
    assert '成分取数失败' in provider.last_error


def test_上游形态变化必须fail_loud(monkeypatch):
    """形态假设（§4）：若 akshare 返回的不是 DataFrame，必须走 last_error 而不是抛 AttributeError。"""
    monkeypatch.setitem(sys.modules, 'akshare', types.SimpleNamespace(
        stock_sector_spot=lambda indicator=None: [{'label': 'x'}],
        stock_sector_detail=lambda sector=None: []))
    provider = AkshareConceptProvider()
    assert provider.list_chains() is None
    assert provider.last_error


def test_缺label的行被跳过(monkeypatch):
    _install(monkeypatch, sectors=[{'label': '', '板块': '空', '公司家数': 0},
                                   {'label': 'new_blhy', '板块': '玻璃行业', '公司家数': 19}])
    rows = AkshareConceptProvider().list_chains()
    assert [r['chain_id'] for r in rows] == ['sina_sector:new_blhy']


def test_不提供主营构成时返回空列表(monkeypatch):
    _install(monkeypatch)
    provider = AkshareConceptProvider()
    assert provider.get_revenue_exposure('600176') == [] and provider.last_error is None
