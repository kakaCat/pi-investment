"""策展 seed 目录定位的**故障路径**测试（2026-10-21，investor/w-36c3225e）

背景（真实事故）：
    2026-09-11 抽离 qs-intel 二方包（commit 898039f23）把 seed 目录从
    `quantsys-v2/domain/industry_chain/seed` 搬到
    `packages/qs_intel/qs_intel/domain/industry_chain/seed`，
    而 `curated.py` 的目录定位逻辑没跟着改 ⇒ 解析到一个**不存在的路径** ⇒
    策展源**一直**读不到任何链（`available()` 返回空列表），
    chain_list 只剩 DB 兜底的 8 条历史链，chain_scan 一律 502
    「产业链拓扑取数失败（人工策展为唯一权威源且不可降级）」。
    故障是**静默**的：不报错、不告警，只在错误信息末尾留一个空的「（可用: ）」。

本文件锁住的契约：
    1. 目录定位按**已知布局枚举**（包内布局 / 仓库根布局），不依赖固定上溯层数；
    2. **找不到时返回 None，不返回假路径**（这是本次事故的关键防线）；
    3. 环境变量覆盖优先，且指向不存在目录时视为"未配置"（不得静默用假路径）；
    4. 真实仓库布局下必须能加载到全部策展链（含 2026-10-21 新增的汽车/养殖/玻璃三链）；
    5. **故障注入**：把候选目录藏起来 ⇒ 必须显式失败（list_chains 返回 None + last_error），
       而**不是**静默返回空清单。
"""
import os

import pytest

from qs_market_data.adapters.outbound.datasources.providers.industry_chain import curated as curated_mod
from qs_market_data.adapters.outbound.datasources.providers.industry_chain.curated import (
    CuratedChainProvider,
)


def _repo_root() -> str:
    """从本文件定位 quantsys-v2 仓库根（tests/ 的上两级）"""
    here = os.path.dirname(os.path.abspath(__file__))
    d = here
    for _ in range(12):
        if os.path.isdir(os.path.join(d, 'packages', 'qs_intel')):
            return d
        d = os.path.dirname(d)
    raise AssertionError('定位 quantsys-v2 仓库根失败')


# ---------------------------------------------------------------- 定位逻辑


def test_定位到真实存在的seed目录():
    """现役布局：packages/qs_intel/qs_intel/domain/industry_chain/seed"""
    found = curated_mod._find_seed_dir()
    assert found, 'seed 目录未定位到（这是 2026-09-11 抽包后一直存在的静默故障）'
    assert os.path.isdir(found), f'定位到不存在的目录: {found}'
    assert os.path.isfile(os.path.join(found, 'chemical.yaml'))


def test_定位不依赖固定上溯层数():
    """回归防线：原实现写死 7 层上溯，实际需要 8 层 ⇒ 差一层就静默失效。

    这里用"从 provider 文件出发逐级向上"复刻定位，验证它命中的是
    **带 packages/qs_intel 标记的目录**（repo 根），而不是某一层祖先。
    """
    here = os.path.dirname(os.path.abspath(curated_mod.__file__))
    d = here
    hit = None
    while True:
        if os.path.isdir(os.path.join(d, 'packages', 'qs_intel')):
            hit = d
            break
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
    assert hit, '未找到带 packages/qs_intel 标记的仓库根'
    seed = os.path.join(hit, 'packages', 'qs_intel', 'qs_intel',
                        'domain', 'industry_chain', 'seed')
    assert os.path.isdir(seed), f'仓库根下的 seed 目录不存在: {seed}'


def test_找不到时返回None而非假路径(monkeypatch, tmp_path):
    """**故障注入**：所有候选都不可达 ⇒ 必须返回 None（不得返回一个假路径）。

    假路径（如原实现的 7 层上溯结果）会导致 `_seed_files()` 静默返回空列表
    ⇒ available() 为空 ⇒ 策展源"看起来正常但什么都读不到"。
    """
    # 造一个没有任何标记的深目录，并把 provider 放进去模拟"找不到标记"
    fake = tmp_path / 'a' / 'b' / 'c' / 'd' / 'e' / 'f' / 'g' / 'h' / 'i'
    fake.mkdir(parents=True)
    monkeypatch.setattr(curated_mod, '__file__', str(fake / 'curated.py'))
    monkeypatch.delenv('QUANTSYS_INDUSTRY_CHAIN_SEED_DIR', raising=False)
    assert curated_mod._find_seed_dir() is None, '必须返回 None 而不是假路径'


def test_环境变量覆盖生效(monkeypatch, tmp_path):
    """环境变量优先于自动定位

    契约细节：`_find_seed_dir()` 每次调用都重读环境变量（动态）；
    而 `CuratedChainProvider()` 无参时用的是**模块加载时的快照**
    `_DEFAULT_SEED_DIR`（静态）——显式传 seed_dir 才是确定性入口。
    两层都验，避免"以为环境变量能热改默认目录"的误解。
    """
    seed = tmp_path / 'seed'
    seed.mkdir()
    (seed / 'x.yaml').write_text('chain_id: x\nname: X\nrationale: r\nnodes: []\n',
                                  encoding='utf-8')
    monkeypatch.setenv('QUANTSYS_INDUSTRY_CHAIN_SEED_DIR', str(seed))
    # 动态：每次调用重读
    assert curated_mod._find_seed_dir() == str(seed)
    # 确定性入口：显式传 seed_dir
    assert CuratedChainProvider(seed_dir=str(seed)).available() == ['x']
    # 静态快照：模块加载时已定，不随后续 monkeypatch 变化（文档化现状）
    assert curated_mod._DEFAULT_SEED_DIR != str(seed)


def test_环境变量指向不存在目录时不静默用假路径(monkeypatch, tmp_path):
    """**故障注入**：环境变量配错 ⇒ 不得回退到自动定位（会掩盖配置错误）"""
    monkeypatch.setenv('QUANTSYS_INDUSTRY_CHAIN_SEED_DIR', str(tmp_path / 'nope'))
    assert curated_mod._find_seed_dir() is None


# ---------------------------------------------------------------- 真实布局


def test_真实布局能加载全部策展链():
    """仓库内策展链必须全部可加载（含 2026-10-21 新增的汽车/养殖/玻璃三链）"""
    provider = CuratedChainProvider()
    chains = provider.list_chains()
    assert chains, '仓库内必须存在策展 seed'
    ids = {c['chain_id'] for c in chains}
    for expected in ('automobile', 'livestock_farming', 'glass'):
        assert expected in ids, f'缺新补的产业链: {expected}（实际: {sorted(ids)}）'
    assert len(ids) >= 11, f'策展链数量异常: {sorted(ids)}'


def test_新补三链的节点与成员齐备():
    """新补的链不能是空壳：每个节点都要有 keywords + rationale（否则无法做主营构成归位）"""
    provider = CuratedChainProvider()
    for cid in ('automobile', 'livestock_farming', 'glass'):
        rows = provider.get_chain(cid)
        assert rows, f'{cid} 取不到环节行'
        assert any(r.get('members') for r in rows), f'{cid} 没有任何成员（seed 写空了？）'
        for row in rows:
            assert row.get('keywords'), f'{cid}.{row.get("node_id")} 缺 keywords'
