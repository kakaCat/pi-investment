"""本地 DB 产业链 provider（database_chain）契约测试（fake repository，不写库）

锁住的契约：
  读库失败 → None + last_error；库中确实没有 → []（空结果 ≠ 故障）
  所有输出带 stale=True（stale-while-error，禁止当实时数据用）
  成员按 node_id 归位到节点；指向不存在节点的成员必须**如实回报**而不是静默丢弃
  主营构成兜底：exposure_ratio 为空的成员不产出（不能当 0 用）
"""
import pytest

from adapters.outbound.datasources.providers.industry_chain.database import DatabaseChainProvider


class FakeRepo:
    def __init__(self, *, chains=None, chain=None, by_symbol=None, raise_on=None):
        self._chains = chains or []
        self._chain = chain
        self._by_symbol = by_symbol or []
        self.raise_on = raise_on

    def list_chains(self):
        if self.raise_on == 'list_chains':
            raise RuntimeError('db down')
        return list(self._chains)

    def get_chain(self, chain_id):
        if self.raise_on == 'get_chain':
            raise RuntimeError('db down')
        return self._chain

    def get_chain_by_symbol(self, symbol):
        if self.raise_on == 'get_chain_by_symbol':
            raise RuntimeError('db down')
        return list(self._by_symbol)


CHAIN = {
    'chain_id': 'glass', 'name': '玻纤链', 'description': 'd', 'rationale': 'r',
    'updated_at': '2026-09-11T10:00:00',
    'nodes': [{'node_id': 'gfy', 'name': '玻纤纱', 'stage': 'upstream',
               'upstream_of': ['dbb'], 'downstream_of': [], 'keywords': ['玻纤'],
               'rationale': 'r'}],
    'members': [{'symbol': '600176', 'name': '中国巨石', 'node_id': 'gfy', 'stage': 'upstream',
                 'exposure_ratio': 0.97, 'exposure_basis': '玻纤及其制品',
                 'exposure_as_of': '2026-06-30', 'evidence': 'e', 'evidence_kind': '主营构成',
                 'confidence': 'high', 'source': 'eastmoney_revenue'}],
}


def test_清单读取失败显式失败():
    provider = DatabaseChainProvider(FakeRepo(raise_on='list_chains'))
    assert provider.list_chains() is None
    assert 'db down' in provider.last_error


def test_清单为空返回空列表且不算故障():
    provider = DatabaseChainProvider(FakeRepo())
    assert provider.list_chains() == [] and provider.last_error is None


def test_清单行带stale标记():
    provider = DatabaseChainProvider(FakeRepo(chains=[{'chain_id': 'glass', 'name': '玻纤链'}]))
    row = provider.list_chains()[0]
    assert row['stale'] is True and row['source'] == 'database_chain'


def test_链详情读取失败显式失败():
    provider = DatabaseChainProvider(FakeRepo(raise_on='get_chain'))
    assert provider.get_chain('glass') is None and 'db down' in provider.last_error


def test_库中没有该链返回空列表():
    provider = DatabaseChainProvider(FakeRepo(chain=None))
    assert provider.get_chain('glass') == []


def test_成员按node_id归位到节点且带stale():
    provider = DatabaseChainProvider(FakeRepo(chain=CHAIN))
    rows = provider.get_chain('glass')
    assert len(rows) == 1
    node = rows[0]
    assert node['node_id'] == 'gfy' and node['stale'] is True
    assert node['members'][0]['symbol'] == '600176'
    assert node['members'][0]['exposure_ratio'] == pytest.approx(0.97)
    assert node['members'][0]['stale'] is True
    assert provider.stale_reason


def test_指向不存在节点的成员必须如实回报而不是静默丢弃():
    chain = dict(CHAIN)
    chain['members'] = CHAIN['members'] + [
        {'symbol': '000001', 'node_id': 'ghost', 'name': '幽灵节点成员'}]
    provider = DatabaseChainProvider(FakeRepo(chain=chain))
    rows = provider.get_chain('glass')
    assert len(rows[0]['members']) == 1, '孤儿成员不得被算进任何节点'
    assert provider.orphan_members and provider.orphan_members[0]['symbol'] == '000001'
    assert 'node_id' in provider.orphan_members[0]['reason']


def test_每次读取重置孤儿记录():
    chain = dict(CHAIN)
    chain['members'] = [{'symbol': '000001', 'node_id': 'ghost'}]
    provider = DatabaseChainProvider(FakeRepo(chain=chain))
    provider.get_chain('glass')
    assert provider.orphan_members
    provider.get_chain('glass')
    assert len(provider.orphan_members) == 1, 'stale 的孤儿记录会误导下一次调用方'


def test_主营构成兜底读取(monkeypatch):
    rows = [{'symbol': '600176', 'name': '中国巨石', 'exposure_ratio': 0.973,
             'exposure_basis': '玻纤及其制品', 'exposure_as_of': '2026-06-30',
             'updated_at': '2026-09-11T10:00:00'},
            {'symbol': '600176', 'name': '中国巨石', 'exposure_ratio': None,
             'exposure_basis': '无占比的证据'}]
    provider = DatabaseChainProvider(FakeRepo(by_symbol=rows))
    out = provider.get_revenue_exposure('600176')
    assert len(out) == 1 and out[0]['ratio'] == pytest.approx(0.973)
    assert out[0]['stale'] is True and 'DB缓存' in out[0]['classification']
    assert out[0]['source'] == 'database_chain'


def test_主营构成读取失败显式失败():
    provider = DatabaseChainProvider(FakeRepo(raise_on='get_chain_by_symbol'))
    assert provider.get_revenue_exposure('600176') is None
    assert 'db down' in provider.last_error
