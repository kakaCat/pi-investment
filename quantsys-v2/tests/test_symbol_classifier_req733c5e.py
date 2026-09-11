"""REQ-733c5e：指数/股票同码歧义——显式市场后缀/前缀优先于 stocks 表歧义裁决。

背景：000905 既是中证500 又是厦门港务（000852/000001/000016 同理）。
历史事故：agent 把 000905（厦门港务）的 K 线当中证500 指数回撤用于抄底判断。
修复：显式 .SH 后缀 / sh 前缀恒为指数；裸码仍靠 stocks 表定夺。
"""
from utils.symbol_classifier import (
    INDEX_WHITELIST,
    build_resolution_meta,
    resolve_index_symbol,
)


def test_explicit_sh_suffix_forces_index_for_ambiguous_code():
    # 深市个股不可能挂 .SH；显式 .SH / sh 前缀 = 用户明确要指数
    assert resolve_index_symbol('000905.SH') == '000905.SH'
    assert resolve_index_symbol('sh000905') == '000905.SH'
    assert resolve_index_symbol('000852.SH') == '000852.SH'
    assert resolve_index_symbol('000001.SH') == '000001.SH'


def test_explicit_sz_suffix_not_forced_to_sh_index():
    # 000905.SZ 是厦门港务（深市个股）；不得被短路成沪市指数键
    r = resolve_index_symbol('000905.SZ')
    assert r != '000905.SH'


def test_plain_index_and_399_codes():
    assert resolve_index_symbol('000300') is not None
    assert resolve_index_symbol('399006') == '399006.SZ'


def test_meta_ambiguity_warning_for_bare_stock_code():
    meta = build_resolution_meta('000905', 'stock', '000905', stock_name='厦门港务')
    assert meta['resolved_kind'] == 'stock'
    assert meta['resolved_name'] == '厦门港务'
    assert 'ambiguity_warning' in meta
    assert '000905.SH' in meta['ambiguity_warning']


def test_meta_note_for_bare_code_resolved_to_index():
    # 裸码但 stocks 表无同名个股（保守按指数）→ 告知同名深市个股写法
    meta = build_resolution_meta('000905', 'index', '000905.SH')
    assert meta['resolved_kind'] == 'index'
    assert meta.get('ambiguity_note')
    assert '000905.SZ' in meta['ambiguity_note']
    assert 'ambiguity_warning' not in meta


def test_meta_no_note_for_explicit_index_hint():
    # 显式 .SH 已消歧 → 不再告警
    meta = build_resolution_meta('000905.SH', 'index', '000905.SH')
    assert meta['resolved_kind'] == 'index'
    assert 'ambiguity_note' not in meta
    assert 'ambiguity_warning' not in meta


def test_meta_no_warning_for_normal_stock():
    meta = build_resolution_meta('600519', 'stock', '600519', stock_name='贵州茅台')
    assert meta['resolved_kind'] == 'stock'
    assert 'ambiguity_warning' not in meta
    assert 'ambiguity_note' not in meta


def test_399_codes_excluded_from_sh_shortcircuit():
    # 399 族（深证指数族）不属于 SH 短路范围；恒 .SZ
    assert '399006' in INDEX_WHITELIST
    assert resolve_index_symbol('399300') == '399300.SZ'
