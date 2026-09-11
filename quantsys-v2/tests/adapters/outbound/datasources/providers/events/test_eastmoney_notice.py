"""东财公告 provider 契约测试（monkeypatch 模块级 session，不触网）

锁住的契约：
  字段映射（notice_date/display_time → effective/announce；art_code → URL）
  失败必须写 last_error（HTTP != 200 / data.list 缺失 / 解析异常）
  空结果 ≠ 故障（fetch_policy 恒返回 [] 且 last_error 为空）
  截断必须标注（标的数超上限时列出未采集代码）
"""
import logging

import pytest

from adapters.outbound.datasources.providers.events import eastmoney_notice as mod
from adapters.outbound.datasources.providers.events.eastmoney_notice import (
    _MAX_SYMBOLS, EastmoneyNoticeProvider,
)

from _fakes import FakeResponse, FakeSession


def _item(**overrides):
    item = {
        'art_code': 'AN202609111829239408',
        'codes': [{'stock_code': '600150', 'short_name': '中国船舶', 'ann_type': 'A,SHA'}],
        'columns': [{'column_code': '001002006016', 'column_name': '重大事故损失'}],
        'display_time': '2026-09-11 00:29:07:363',   # 实测：毫秒用冒号分隔
        'notice_date': '2026-09-11 00:00:00',
        'sort_date': '2026-09-11 12:00:00',
        'title': '中国船舶:关于北海造船厂一货轮火灾事故有关情况的公告',
    }
    item.update(overrides)
    return item


def _provider(monkeypatch, responses):
    provider = EastmoneyNoticeProvider(timeout=1)
    fake = FakeSession(responses)
    monkeypatch.setattr(mod, '_session', lambda: fake)
    return provider, fake


def test_字段映射逐列核对(monkeypatch):
    provider, _ = _provider(monkeypatch, FakeResponse({'data': {'list': [_item()]}}))
    rows = provider.fetch_symbol_events(['600150'])
    assert len(rows) == 1
    row = rows[0]
    assert row['title'] == '中国船舶:关于北海造船厂一货轮火灾事故有关情况的公告'
    assert row['effective_date'] == '2026-09-11', 'notice_date 是"公告日"→ effective_date'
    assert row['announce_date'] == '2026-09-11'
    assert row['symbols'] == ['600150'] and row['scope'] == 'individual'
    assert row['url'] == ('https://data.eastmoney.com/notices/detail/600150/'
                          'AN202609111829239408.html')
    assert row['external_id'] == 'AN202609111829239408'
    assert row['authority'] == 60
    assert row['source'] == 'eastmoney_notice'
    assert row['raw']['short_names'] == ['中国船舶']


def test_毫秒冒号格式不得让date解析失败(monkeypatch):
    """实测陷阱：display_time 的毫秒是 ':363'，strptime('%H:%M:%S') 会失败。"""
    provider, _ = _provider(monkeypatch, FakeResponse(
        {'data': {'list': [_item(notice_date='', sort_date='')]}}))
    rows = provider.fetch_symbol_events(['600150'])
    assert rows[0]['effective_date'] == '2026-09-11', '应回落到 display_time 的日期部分'


def test_HTTP非200必须显式失败(monkeypatch):
    provider, _ = _provider(monkeypatch, FakeResponse({'data': {'list': []}}, status=403))
    assert provider.fetch_symbol_events(['600150']) is None
    assert 'HTTP 403' in provider.last_error


def test_data_list缺失必须报错而不是当成没有公告(monkeypatch):
    """上游改版/WAF 拦截时返回空清单会被误读为"该标的今天没公告"。"""
    provider, _ = _provider(monkeypatch, FakeResponse({'success': True}))
    assert provider.fetch_symbol_events(['600150']) is None
    assert 'data.list 缺失' in provider.last_error


def test_json解析失败必须显式失败(monkeypatch):
    provider, _ = _provider(monkeypatch, FakeResponse(json_error=True))
    assert provider.fetch_symbol_events(['600150']) is None
    assert provider.last_error


def test_网络异常必须显式失败(monkeypatch):
    provider = EastmoneyNoticeProvider(timeout=1)
    class _Boom:
        def get(self, *a, **kw):
            raise ConnectionError('proxy rejected')
    monkeypatch.setattr(mod, '_session', lambda: _Boom())
    assert provider.fetch_symbol_events(['600150']) is None
    assert 'ConnectionError' in provider.last_error


def test_缺标题或缺日期的行被丢弃而不是编造数据(monkeypatch):
    items = [_item(), _item(title=''), _item(notice_date='', sort_date='', display_time=''),
             _item(art_code='AN2', title='关于股东大会的通知')]
    provider, _ = _provider(monkeypatch, FakeResponse({'data': {'list': items}}))
    rows = provider.fetch_symbol_events(['600150'])
    assert [r['external_id'] for r in rows] == ['AN202609111829239408', 'AN2']
    assert all(r['effective_date'] for r in rows)


def test_无标的的公告判为宏观事件(monkeypatch):
    provider, _ = _provider(monkeypatch, FakeResponse({'data': {'list': [_item(codes=[])]}}))
    rows = provider.fetch_symbol_events(['600150'])
    assert rows[0]['scope'] == 'macro' and rows[0]['symbols'] == []


def test_不提供政策时返回空列表且不计故障(monkeypatch):
    """端口契约：不提供该类数据返回 []（不是 None），否则会被 manager 记为失败。"""
    provider = EastmoneyNoticeProvider(timeout=1)
    assert provider.fetch_policy() == []
    assert provider.last_error is None


def test_标的数超上限必须标注截断而不是静默少采集(monkeypatch):
    """静默失败清单 §2：取前 N 条却不标注 = 调用方拿到"覆盖完整"的假象。"""
    symbols = ['%06d' % (600000 + i) for i in range(_MAX_SYMBOLS + 5)]
    provider, fake = _provider(monkeypatch, [FakeResponse({'data': {'list': [_item()]}})
                                             for _ in symbols])
    provider.fetch_symbol_events(symbols)
    assert len(fake.calls) == _MAX_SYMBOLS, '只有前 N 只被真正查询'
    assert provider.truncated_symbols == symbols[_MAX_SYMBOLS:]
    assert str(_MAX_SYMBOLS) in provider.truncation_note
    assert symbols[-1] in provider.truncation_note


def test_未超上限时不得产生截断标注(monkeypatch):
    provider, _ = _provider(monkeypatch, FakeResponse({'data': {'list': [_item()]}}))
    provider.fetch_symbol_events(['600150'])
    assert provider.truncated_symbols == [] and provider.truncation_note == ''


def test_不传标的时取全市场流且不带stock_list(monkeypatch):
    provider, fake = _provider(monkeypatch, FakeResponse({'data': {'list': [_item()]}}))
    provider.fetch_symbol_events(None)
    assert 'stock_list' not in fake.calls[0]['params']


def test_每次调用重置上一次的截断标注(monkeypatch):
    symbols = ['%06d' % (600000 + i) for i in range(_MAX_SYMBOLS + 1)]
    provider, _ = _provider(monkeypatch, [FakeResponse({'data': {'list': [_item()]}})
                                          for _ in range(_MAX_SYMBOLS + 1)])
    provider.fetch_symbol_events(symbols)
    assert provider.truncation_note
    provider.fetch_symbol_events(['600150'])
    assert provider.truncation_note == '', 'stale 的截断标注会误导下一次调用方'
