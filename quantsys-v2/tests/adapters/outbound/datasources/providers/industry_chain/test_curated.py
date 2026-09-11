"""人工策展产业链 provider 契约测试（tmp_path 造 seed + 真实 seed 只读校验，不触网）

锁住的契约：
  seed 缺失/损坏 → 显式失败（拓扑是唯一权威源且不可降级，禁止把"没有这条链"伪装成"空链"）
  get_chain 未命中 → None + last_error（调用方据此 fail-loud，而不是拿空拓扑去扫描）
  行契约 B 的字段与默认值（evidence_kind 默认'策展'、confidence 默认 medium）
"""
import yaml
import pytest

from adapters.outbound.datasources.providers.industry_chain.curated import CuratedChainProvider

SEED = {
    'chain_id': 'glass',
    'name': '玻纤链',
    'curator': 'investor/test',
    'curated_at': '2026-09-11',
    'description': '玻纤纱→电子布',
    'rationale': '人工判断依据',
    'nodes': [
        {'node_id': 'gfy', 'name': '玻纤纱', 'stage': 'upstream',
         'upstream_of': ['dbb'], 'downstream_of': [], 'keywords': ['玻璃纤维'],
         'rationale': '成本端',
         'members': [{'symbol': '600176', 'name': '中国巨石', 'role': '龙头',
                      'evidence': '策展证据'}]},
        {'node_id': 'dbb', 'name': '电子布', 'stage': 'upstream',
         'upstream_of': [], 'downstream_of': ['gfy'], 'keywords': ['电子布'],
         'rationale': '紧供环节', 'members': []},
    ],
}


def _write_seed(tmp_path, data=None, filename='glass.yaml'):
    path = tmp_path / filename
    path.write_text(yaml.safe_dump(data if data is not None else SEED, allow_unicode=True),
                    encoding='utf-8')
    return path


def test_清单与详情来自同一份seed(tmp_path):
    _write_seed(tmp_path)
    provider = CuratedChainProvider(seed_dir=str(tmp_path))
    chains = provider.list_chains()
    assert [c['chain_id'] for c in chains] == ['glass']
    assert chains[0]['node_count'] == 2 and chains[0]['member_count'] == 1
    rows = provider.get_chain('glass')
    assert [r['node_id'] for r in rows] == ['gfy', 'dbb']
    assert rows[0]['members'][0]['symbol'] == '600176'
    assert rows[0]['members'][0]['evidence_kind'] == '策展'
    assert rows[0]['members'][0]['confidence'] == 'medium'
    assert rows[0]['members'][0]['source'] == 'curated'
    assert rows[0]['upstream_of'] == ['dbb'] and rows[1]['downstream_of'] == ['gfy']


def test_按名称与别名匹配(tmp_path):
    data = dict(SEED, aliases=['玻纤', 'PCB'])
    _write_seed(tmp_path, data)
    provider = CuratedChainProvider(seed_dir=str(tmp_path))
    assert provider.get_chain('玻纤')[0]['chain_id'] == 'glass'
    assert provider.get_chain('玻')[0]['chain_id'] == 'glass'


def test_未命中必须显式失败而非返回空链(tmp_path):
    _write_seed(tmp_path)
    provider = CuratedChainProvider(seed_dir=str(tmp_path))
    assert provider.get_chain('不存在的链') is None
    assert provider.last_error and '不存在' in provider.last_error


def test_seed目录不存在必须显式失败(tmp_path):
    provider = CuratedChainProvider(seed_dir=str(tmp_path / 'nope'))
    assert provider.list_chains() is None
    assert provider.last_error and '不存在' in provider.last_error


def test_seed缺少chain_id或rationale必须报错(tmp_path):
    _write_seed(tmp_path, {'name': 'X', 'rationale': 'r', 'nodes': []})
    provider = CuratedChainProvider(seed_dir=str(tmp_path))
    assert provider.list_chains() is None
    assert 'chain_id' in provider.last_error


def test_节点缺keywords必须报错(tmp_path):
    """keywords 是主营构成归位的输入，缺了就无法归位——必须部署期就失败。"""
    data = dict(SEED)
    data['nodes'] = [dict(SEED['nodes'][0]), dict(SEED['nodes'][1])]
    del data['nodes'][0]['keywords']
    _write_seed(tmp_path, data)
    provider = CuratedChainProvider(seed_dir=str(tmp_path))
    assert provider.list_chains() is None
    assert 'keywords' in provider.last_error


def test_chain_id重复必须报错(tmp_path):
    _write_seed(tmp_path, SEED, 'a.yaml')
    _write_seed(tmp_path, SEED, 'b.yaml')
    provider = CuratedChainProvider(seed_dir=str(tmp_path))
    assert provider.list_chains() is None
    assert '重复' in provider.last_error


def test_策展不提供主营构成时返回空列表():
    provider = CuratedChainProvider(seed_dir='/nonexistent')
    assert provider.get_revenue_exposure('600176') == []
    assert provider.last_error is None


def test_真实seed全部可加载且拓扑自校验通过():
    """离线校验仓库内 8 条策展链：能加载 + 拓扑对称 + 能构建聚合根。"""
    from domain.industry_chain.service import IndustryChainService

    provider = CuratedChainProvider()
    chains = provider.list_chains()
    assert chains, '仓库内必须存在策展 seed'
    assert len(chains) >= 8, f'策展链数量异常: {[c["chain_id"] for c in chains]}'
    service = IndustryChainService()
    for chain in chains:
        rows = provider.get_chain(chain['chain_id'])
        assert rows, f"{chain['chain_id']} 取不到环节行"
        built, conflicts, multi = service.build_chain(
            chain['chain_id'], chain['name'], rows, source='curated')
        assert built.nodes, f"{chain['chain_id']} 没有环节节点"
        assert built.members, f"{chain['chain_id']} 没有成员（seed 写空了？）"
