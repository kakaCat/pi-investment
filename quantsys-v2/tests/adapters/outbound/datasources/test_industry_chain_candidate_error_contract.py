"""候选通道聚合器的**四态可分**回归锁（2026-09-11，w-f436d4ea）

背景：`get_industry_chain_candidates_all` 与 `list_industry_chain_candidates_all` 对每个
候选通道**独立**跑一次 _try_providers（候选通道①新浪行业与②东财概念覆盖不同分类体系，
互补而非互备，用故障转移语义会把多源退化成单源 —— RFC 015 §1.5.1）。

这两个方法的文档串明写「『某通道无该板块』（返回空）与『该通道失败』（返回 None +
last_error）严格可分」，且调用方（manager 自己）已经把四态算了出来（`empty` / `empty_sources`）
——**但末尾的 `error` 文案与 `failed` 计数又把两者合并回同一句话**：
`'All industry-chain candidate providers failed or empty'`。
后果：chain_scan 的 `candidate_error` 无法告诉调用方「该去排障」还是「只是没匹配、换个关键词」，
四态契约在最后一跳被丢弃。

本测试锁住修复后的分档：
    有数据            → error=None
    无数据 + 零硬失败 → 'No industry-chain candidates: every source answered but none matched'
    无数据 + 有硬失败 → 'All industry-chain candidate providers failed'
（混合场景按「有真故障就不敢断言确实没有」取保守档，与 _has_hard_failure 的补集口径一致。）

全程不触网、不写库：`_try_providers` 与健康排序被替换为桩。
"""
from adapters.outbound.datasources.manager import DataProviderManager


class _P:
    """最小 provider 桩：聚合器只用它的 name"""

    def __init__(self, name):
        self.name = name


def _manager(results_by_name, *, method='list_chains'):
    """轻量 manager：不跑 __init__，只装配被测路径。

    results_by_name: {provider_name: _try_providers 返回值}
    """
    m = DataProviderManager.__new__(DataProviderManager)
    m.industry_chain_concept_providers = [_P(n) for n in results_by_name]
    m._sort_providers_by_health = lambda ps: list(ps)

    def _fake_try(providers, _method, *a, **kw):
        return dict(results_by_name[providers[0].name])

    m._try_providers = _fake_try
    return m


HEALTHY_EMPTY = {
    'success': True, 'data': [], 'source': None, 'empty': True,
    'provider_errors': {'a': '返回空数据（非故障：该查询无数据）；说明：该源分类体系里没有这个板块'},
}
HARD_FAIL = {
    'success': False, 'data': None, 'source': None, 'empty': False,
    'provider_errors': {'a': 'RuntimeError: HTTP 503'},
}
WITH_ROWS = {
    'success': True, 'data': [{'node_id': 'sector:x'}], 'source': 'a', 'empty': False,
    'provider_errors': {},
}


# ─────────────── get_industry_chain_candidates_all（成员/板块节点）───────────────

def test_全部通道健康空时不得报failed():
    """修的正是这里：两个通道都好好回答了「我这儿没有」，却被写成 failed。"""
    m = _manager({'a': HEALTHY_EMPTY, 'b': HEALTHY_EMPTY})
    out = m.get_industry_chain_candidates_all('不存在的板块')

    assert out['empty'] is True
    assert out['failed_channels_hard'] == 0
    # failed_channels 沿用旧的「无数据通道数」口径（健康空也算），故为 2 —— 两个计数
    # 必须分开看，混用会把健康空当成故障。
    assert out['failed_channels'] == 2
    assert out['error'] == 'No industry-chain candidates: every source answered but none matched'
    assert 'failed' not in out['error'], '健康空不得出现 failed 字样（这正是修前的失真）'


def test_真故障时报failed并计数():
    m = _manager({'a': HARD_FAIL})
    out = m.get_industry_chain_candidates_all('玻璃')

    assert out['empty'] is True
    assert out['failed_channels_hard'] == 1
    assert out['error'] == 'All industry-chain candidate providers failed'


def test_混合场景取保守档_有真故障就不敢断言确实没有():
    m = _manager({'a': HEALTHY_EMPTY, 'b': HARD_FAIL})
    out = m.get_industry_chain_candidates_all('玻璃')

    assert out['failed_channels_hard'] == 1
    assert out['error'] == 'All industry-chain candidate providers failed', \
        '一个通道挂了时不能宣称「所有源都答了没有匹配」——可能正是它才有数据'


def test_有数据时error为None():
    m = _manager({'a': WITH_ROWS})
    out = m.get_industry_chain_candidates_all('玻璃')

    assert out['empty'] is False
    assert out['error'] is None
    assert out['failed_channels_hard'] == 0
    assert out['sources'] == ['a']


def test_通道明细透出empty以便下游自行判断():
    m = _manager({'a': HEALTHY_EMPTY, 'b': HARD_FAIL})
    out = m.get_industry_chain_candidates_all('玻璃')

    assert out['channels']['a']['empty'] is True
    assert out['channels']['b']['empty'] is False


# ─────────────── list_industry_chain_candidates_all（板块清单）───────────────

def test_板块清单_全部健康空时不得报failed():
    m = _manager({'a': HEALTHY_EMPTY, 'b': HEALTHY_EMPTY})
    out = m.list_industry_chain_candidates_all()

    assert out['empty'] is True
    assert out['failed_channels_hard'] == 0
    assert out['error'] == 'No industry-chain candidates: every source answered but none matched'


def test_板块清单_真故障时报failed():
    m = _manager({'a': HARD_FAIL})
    out = m.list_industry_chain_candidates_all()

    assert out['failed_channels_hard'] == 1
    assert out['error'] == 'All industry-chain candidate providers failed'


def test_板块清单_有数据时error为None():
    m = _manager({'a': WITH_ROWS})
    out = m.list_industry_chain_candidates_all()

    assert out['error'] is None
    assert out['channels']['a']['empty'] is False
