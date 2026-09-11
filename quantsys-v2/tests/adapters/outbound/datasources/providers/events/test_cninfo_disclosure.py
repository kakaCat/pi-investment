"""巨潮资讯 provider 契约测试（monkeypatch 模块级 session，不触网）

锁住的契约：
  <em> 高亮标签必须剥掉；毫秒时间戳按 UTC+8 换算（不依赖运行机时区）
  searchkey 是全文检索 → 必须按 secCode 过滤，否则会把别家公司的事件算到本标的头上
  announcements 缺失：totalAnnouncement=0 视为该窗口无公告（空结果），>0 视为上游改版（故障）
  截断必须标注
"""
import pytest

from adapters.outbound.datasources.providers.events import cninfo_disclosure as mod
from adapters.outbound.datasources.providers.events.cninfo_disclosure import (
    _MAX_SYMBOLS, CninfoDisclosureProvider, _ms_to_date, _strip_tags,
)

from _fakes import FakeResponse, FakeSession

# 实测响应中的 announcementTime（2026-09-11 的公告）
MS_2026_09_11 = 1789126467000


def _item(**overrides):
    item = {
        'secCode': '600150',
        'secName': '<em>中国船舶</em>',
        'orgId': 'gssh0600150',
        'announcementId': '1225558999',
        'announcementTitle': '关于北海造船厂一货轮火灾事故有关情况的公告',
        'announcementTime': MS_2026_09_11,
        'adjunctUrl': 'finalpage/2026-09-11/1225558999.PDF',
        'adjunctType': 'PDF',
        'pageColumn': 'SZCY',
    }
    item.update(overrides)
    return item


def _provider(monkeypatch, responses):
    provider = CninfoDisclosureProvider(timeout=1)
    fake = FakeSession(responses)
    monkeypatch.setattr(mod, '_session', lambda: fake)
    return provider, fake


def test_毫秒时间戳按UTC8换算():
    """本机时区虽为 +08:00，但显式 +8h 才能保证换机器后日期不差一天。"""
    assert _ms_to_date(MS_2026_09_11) == '2026-09-11'
    assert _ms_to_date(0) == '' and _ms_to_date(None) == '' and _ms_to_date('abc') == ''


def test_高亮标签必须剥掉():
    assert _strip_tags('<em>中国船舶</em>') == '中国船舶'


def test_字段映射与URL拼接(monkeypatch):
    provider, _ = _provider(monkeypatch, FakeResponse(
        {'announcements': [_item()], 'totalAnnouncement': 1}))
    rows = provider.fetch_symbol_events(['600150'])
    assert len(rows) == 1
    row = rows[0]
    assert row['title'] == '关于北海造船厂一货轮火灾事故有关情况的公告'
    assert row['symbols'] == ['600150'] and row['scope'] == 'individual'
    assert row['effective_date'] == row['announce_date'] == '2026-09-11'
    assert row['url'] == 'http://static.cninfo.com.cn/finalpage/2026-09-11/1225558999.PDF'
    assert row['external_id'] == '1225558999'
    assert row['authority'] == 90
    assert row['raw']['secName'] == '中国船舶'


def test_全文检索命中的其他公司公告必须被过滤(monkeypatch):
    """实测：searchkey=600150 会命中"提及该代码"的法律意见书等别家公告。"""
    items = [_item(), _item(secCode='000001', secName='平安银行',
                            announcementTitle='关于为600150提供担保的公告')]
    provider, _ = _provider(monkeypatch, FakeResponse(
        {'announcements': items, 'totalAnnouncement': 2}))
    rows = provider.fetch_symbol_events(['600150'])
    assert [r['symbols'] for r in rows] == [['600150']]


def test_搜索参数用searchkey而不是stock(monkeypatch):
    """实测：stock=600150 无效（返回 total=0），必须用 searchkey。"""
    provider, fake = _provider(monkeypatch, FakeResponse(
        {'announcements': [_item()], 'totalAnnouncement': 1}))
    provider.fetch_symbol_events(['600150'])
    payload = fake.calls[0]['data']
    assert payload['searchkey'] == '600150' and payload['stock'] == ''
    assert payload['pageNum'] == 1


def test_无公告时返回空列表而不是故障(monkeypatch):
    """totalAnnouncement=0 且 announcements 缺失 = 该窗口确实没有公告（空结果 ≠ 故障）。"""
    provider, _ = _provider(monkeypatch, FakeResponse(
        {'announcements': None, 'totalAnnouncement': 0}))
    rows = provider.fetch_symbol_events(['600150'])
    assert rows == [] and provider.last_error is None


def test_结构异常时必须fail_loud(monkeypatch):
    """totalAnnouncement>0 但 announcements 缺失 = 上游改版，不能当成"没有公告"。"""
    provider, _ = _provider(monkeypatch, FakeResponse(
        {'announcements': None, 'totalAnnouncement': 22}))
    assert provider.fetch_symbol_events(['600150']) is None
    assert '结构异常' in provider.last_error


def test_HTTP非200显式失败(monkeypatch):
    provider, _ = _provider(monkeypatch, FakeResponse({}, status=502))
    assert provider.fetch_symbol_events(['600150']) is None
    assert 'HTTP 502' in provider.last_error


def test_网络异常显式失败(monkeypatch):
    provider = CninfoDisclosureProvider(timeout=1)

    class _Boom:
        def post(self, *a, **kw):
            raise TimeoutError('read timeout')

    monkeypatch.setattr(mod, '_session', lambda: _Boom())
    assert provider.fetch_symbol_events(['600150']) is None
    assert 'TimeoutError' in provider.last_error


def test_缺标题或缺日期的行被丢弃(monkeypatch):
    items = [_item(), _item(announcementTitle='', announcementTime=0)]
    provider, _ = _provider(monkeypatch, FakeResponse(
        {'announcements': items, 'totalAnnouncement': 2}))
    rows = provider.fetch_symbol_events(['600150'])
    assert [r['external_id'] for r in rows] == ['1225558999']


def test_标的数超上限必须标注截断(monkeypatch):
    symbols = ['%06d' % (600000 + i) for i in range(_MAX_SYMBOLS + 3)]
    provider, fake = _provider(monkeypatch, [
        FakeResponse({'announcements': [_item()], 'totalAnnouncement': 1})
        for _ in symbols
    ])
    provider.fetch_symbol_events(symbols)
    assert len(fake.calls) == _MAX_SYMBOLS
    assert provider.truncated_symbols == symbols[_MAX_SYMBOLS:]
    assert provider.truncation_note and symbols[-1] in provider.truncation_note


def test_不传标的时同时查深沪两栏(monkeypatch):
    provider, fake = _provider(monkeypatch, [
        FakeResponse({'announcements': [], 'totalAnnouncement': 0}),
        FakeResponse({'announcements': [], 'totalAnnouncement': 0}),
    ])
    provider.fetch_symbol_events(None)
    assert [c['data']['column'] for c in fake.calls] == ['szse', 'sse']


def test_不提供政策时返回空列表且不计故障():
    provider = CninfoDisclosureProvider(timeout=1)
    assert provider.fetch_policy() == [] and provider.last_error is None
