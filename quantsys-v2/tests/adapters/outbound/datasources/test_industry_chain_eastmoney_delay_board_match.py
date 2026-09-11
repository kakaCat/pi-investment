"""东财延迟域概念通道「板块名分档匹配」单测（2026-09-11，w-f436d4ea）

为什么必须有：候选通道① 的调用方传进来的是**新浪口径** sector_hint
（'玻璃行业'/'电力行业'/'船舶制造'），而东财板块命名不同（'玻璃玻纤'/'电力'/'船舶制造'）。
只做「精确/包含」两级匹配会让东财通道在玻纤这类主流链上**永远空转**
——实测首轮 candidate_source 只有 akshare_concept，两条通道退化成一条。

本测试用 stub 板块清单 + 固定关键词，逐档锁死匹配优先级（纯逻辑，不触网）。
"""
import importlib

MODULE = 'adapters.outbound.datasources.providers.industry_chain.eastmoney_delay_concept'

# 模拟东财板块清单（行业 + 概念），含同词根干扰项与通用词干扰项
# 注意：每行必须带 'kind'（provider 内部按 board['kind'] 判「行业 vs 概念」优先）
INDUSTRY_BOARDS = [
    {'code': 'BK0546', 'name': '玻璃玻纤', 'kind': 'industry'},
    {'code': 'BK0547', 'name': '玻璃制造', 'kind': 'industry'},
    {'code': 'BK0428', 'name': '电力', 'kind': 'industry'},
    {'code': 'BK0729', 'name': '船舶制造', 'kind': 'industry'},
    {'code': 'BK0490', 'name': '航天航空', 'kind': 'industry'},
]
CONCEPT_BOARDS = [
    {'code': 'BK0999', 'name': '玻璃基板', 'kind': 'concept'},   # 同词根、不同行业 → 干扰项
    {'code': 'BK1050', 'name': '昨日涨停', 'kind': 'concept'},   # 通用词 → 应压到最低档
    {'code': 'BK1716', 'name': '产业链', 'kind': 'concept'},     # 通用词
]


def _provider():
    mod = importlib.import_module(MODULE)
    for name in dir(mod):
        obj = getattr(mod, name)
        if isinstance(obj, type) and hasattr(obj, '_resolve_board'):
            prov = obj()
            prov._fetch_boards = lambda kind: list(INDUSTRY_BOARDS if kind == 'industry' else CONCEPT_BOARDS)
            return prov
    raise AssertionError('未找到实现 _resolve_board 的 provider 类')


def test_code_exact_highest_priority():
    """档 0：板块代码精确命中"""
    got = _provider()._resolve_board('BK0546')
    assert got and got[0]['code'] == 'BK0546'


def test_name_exact_beats_prefix():
    """档 1：板块名精确 > 档 2 前缀"""
    got = _provider()._resolve_board('船舶制造')
    assert got and got[0]['code'] == 'BK0729'


def test_prefix_after_suffix_strip_matches_cross_source_naming():
    """档 2：'玻璃行业' → 去后缀 '玻璃' → 前缀命中 '玻璃玻纤'（**本通道曾被此问题空转**）"""
    got = _provider()._resolve_board('玻璃行业')
    assert got, '玻璃行业必须能解析出板块（否则东财通道空转）'
    assert got[0]['code'] == 'BK0546', f"期望玻璃玻纤 BK0546，实际 {got[0]}"


def test_exact_after_suffix_strip():
    """档 3：'电力行业' → 去后缀 '电力' → 板块名精确"""
    got = _provider()._resolve_board('电力行业')
    assert got and got[0]['code'] == 'BK0428'


def test_generic_boards_deprioritized():
    """通用词板块（昨日涨停/产业链）不得排在具体行业板块之前"""
    got = _provider()._resolve_board('玻璃行业')
    codes = [b['code'] for b in got]
    assert 'BK1050' not in codes[:1] and 'BK1716' not in codes[:1], f'通用词板块被误排前: {codes[:3]}'


def test_industry_preferred_over_concept_at_same_tier():
    """同档内：行业板块优先于概念板块（'玻璃' 同时命中行业与概念时）"""
    got = _provider()._resolve_board('玻璃')
    assert got, '应解析出结果'
    assert got[0]['code'] == 'BK0546', f"同档应行业优先，实际 {got[0]}"


def test_unknown_keyword_returns_empty_not_crash():
    """无法匹配时返回空列表（交由上层如实标注），不得抛异常/伪造"""
    got = _provider()._resolve_board('不存在的东西XYZ')
    assert got == []
