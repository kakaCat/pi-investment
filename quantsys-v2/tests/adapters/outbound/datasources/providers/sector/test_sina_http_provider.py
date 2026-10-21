"""SinaHttpSectorProvider 契约测试（2026-10-21 多渠道板块通道）。

锁定：
1. 节点表解析（A股 → 7 类板块体系）与分类输出；
2. 成分解析优先级：精确名 → canonical 映射（券商→证券Ⅱ）→ 模糊唯一命中；
3. 分页拉取 + 去重 + 上限；字段映射（mktcap 万元→元）；
4. 失败语义：网络异常返回 None（manager 计故障/降级），板块不存在 found=False。
"""
import sys
from pathlib import Path

import pytest

_PACKAGES = Path(__file__).resolve().parents[5] / 'packages'
if _PACKAGES.is_dir():
    for _pkg in sorted(_PACKAGES.iterdir()):
        if _pkg.is_dir() and (_pkg / _pkg.name).is_dir() and str(_pkg) not in sys.path:
            sys.path.insert(0, str(_pkg))

from qs_market_data.adapters.outbound.datasources.providers.sector.sina_http import (  # noqa: E402
    SinaHttpSectorProvider,
)

NODES = [
    '行情中心',
    [
        ['A股', [
            ['新浪行业', [['金融行业', '', 'new_jrhy'], ['房地产', '', 'new_fdc']]],
            ['申万一级', [['银行', '', 'sw1_480000'], ['房地产', '', 'sw1_430000']]],
            ['申万二级', [['证券Ⅱ', '', 'sw2_490100'], ['半导体', '', 'sw2_270100']]],
            ['概念板块', [['新能源', '', 'gn_xny']]],
            ['热门概念', [['人工智能', '', 'chgn_700230']]],
        ], ''],
        ['基金', [], ''],
    ],
]


def _provider(rows=None, *, data_error=None):
    p = SinaHttpSectorProvider()
    calls = {'nodes': 0, 'data': []}

    def fake_json(url, params):
        if 'getHQNodes' in url:
            calls['nodes'] += 1
            return NODES
        calls['data'].append(dict(params))
        if data_error is not None:
            raise data_error
        page = int(params.get('page', 1))
        num = int(params.get('num', 100))
        pool = list(rows or [])
        start = (page - 1) * num
        return pool[start:start + num]

    p._get_json = fake_json
    p.calls = calls
    return p


def test_sector_list_exposes_categories():
    p = _provider()
    data = p.get_sector_list().data
    assert data['industry_count'] >= 2
    names = [x['name'] for x in data['industries']]
    assert '金融行业' in names and '银行' in names
    assert any(x['name'] == '新能源' for x in data['concepts'])


def test_exact_name_resolves_without_coarse_flag():
    p = _provider(rows=[{'code': '600000', 'name': '浦发银行', 'per': 5.1,
                         'mktcap': 1000}])
    md = p.get_sector_stocks('银行')
    assert md.data['coarse'] is False
    assert md.data['stocks'][0]['symbol'] == '600000'
    # 万元 → 元
    assert md.data['stocks'][0]['market_cap'] == 10_000_000


def test_canonical_map_marks_coarse():
    p = _provider(rows=[{'code': '600030', 'name': '中信证券'}])
    md = p.get_sector_stocks('券商')       # → 申万二级 证券Ⅱ
    assert md.data['coarse'] is True
    assert md.data['sector_code'] == 'sw2_490100'
    assert md.data['stocks'][0]['symbol'] == '600030'


def test_unknown_sector_is_found_false():
    p = _provider()
    md = p.get_sector_stocks('不存在的板块')
    assert md.data['found'] is False and md.data['stocks'] == []


def test_pagination_dedupes_and_stops_on_short_page():
    rows = [{'code': '%06d' % i, 'name': 'S%d' % i} for i in range(150)]
    p = _provider(rows=rows)
    md = p.get_sector_stocks('半导体')
    assert md.data['count'] == 150
    assert len({s['symbol'] for s in md.data['stocks']}) == 150
    assert len(p.calls['data']) == 2        # 100 + 50，第二页不足即停


def test_network_error_returns_none():
    p = _provider(data_error=RuntimeError('boom'))
    assert p.get_sector_stocks('半导体') is None
