"""解禁排队 provider 契约测试（fake akshare 模块，不触网、不写库）

锁住的契约：
  列名契约不匹配必须抛错（重演"读错列名 → 全 0 → 被当成无数据"是本项目已记录的根因）
  通道 A 返回的是"该标的全部历史解禁"→ 必须按窗口过滤，不能把 2023 年的解禁报成"即将解禁"
  两条子通道的标题口径必须一致（否则领域层会当成两个事件各落一行）
  占比是小数口径（0.4057 = 40.57%）且必须透传到 raw 供重要度推断
"""
import sys
import types
from datetime import date, timedelta

import pytest

from adapters.outbound.datasources.providers.events import akshare_unlock as mod
from adapters.outbound.datasources.providers.events.akshare_unlock import (
    _DETAIL_COLUMNS, _QUEUE_COLUMNS, AkshareUnlockProvider,
)

from _fakes import FakeFrame


def _day(offset):
    return (date.today() + timedelta(days=offset)).strftime('%Y-%m-%d')


def _detail(**overrides):
    row = {
        '股票代码': '600176', '股票简称': '中国巨石', '解禁时间': _day(10),
        '限售股类型': '定向增发机构配售股份', '解禁数量': 3053192530.0,
        '实际解禁数量': 3053192530.0, '实际解禁市值': 113090251311.2,
        '占解禁前流通市值比例': 0.405706, '解禁前一交易日收盘价': 37.04,
    }
    row.update(overrides)
    return row


def _queue(**overrides):
    row = {
        '解禁时间': _day(20), '解禁股东数': 1, '解禁数量': 1000.0,
        '实际解禁数量市值': 20000.0, '占总市值比例': 0.01, '占流通市值比例': 0.02,
        '限售股类型': '股权激励限售股份', '解禁前一交易日收盘价': 20.0,
    }
    row.update(overrides)
    return row


def _install_akshare(monkeypatch, detail_records=None, detail_columns=_DETAIL_COLUMNS,
                     queue_records=None):
    calls = []

    def detail(start_date=None, end_date=None):
        calls.append(('detail', start_date, end_date))
        return FakeFrame(detail_columns, detail_records if detail_records is not None else [])

    def queue(symbol=None):
        calls.append(('queue', symbol))
        return FakeFrame(_QUEUE_COLUMNS, queue_records if queue_records is not None else [])

    fake = types.SimpleNamespace(
        stock_restricted_release_detail_em=detail,
        stock_restricted_release_queue_em=queue,
    )
    monkeypatch.setitem(sys.modules, 'akshare', fake)
    return calls


def test_列名契约不匹配必须失败而不是读出全0(monkeypatch):
    """2026-09-11 分红事故根因：按猜测列名读取 → 静默全 0 → 被误读为"该公司不分红"。"""
    _install_akshare(monkeypatch, [_detail()], detail_columns=['序号', '股票代码', '解禁日'])
    provider = AkshareUnlockProvider()
    assert provider.fetch_symbol_events(['600176']) is None
    assert '列名契约不匹配' in provider.last_error


def test_窗口外的历史解禁必须被过滤(monkeypatch):
    """通道 A 返回该标的全部历史解禁，不过滤会把 2025 年的解禁报成"即将解禁"。"""
    records = [_detail(解禁时间=_day(-400)), _detail(解禁时间=_day(15))]
    _install_akshare(monkeypatch, records)
    provider = AkshareUnlockProvider()
    rows = provider.fetch_symbol_events(['600176'])
    assert [r['effective_date'] for r in rows] == [_day(15)]


def test_不同标的的解禁必须按目标过滤(monkeypatch):
    records = [_detail(), _detail(股票代码='000001', 股票简称='平安银行')]
    _install_akshare(monkeypatch, records)
    provider = AkshareUnlockProvider()
    rows = provider.fetch_symbol_events(['600176'])
    assert [r['symbols'] for r in rows] == [['600176']]


def test_占比小数口径不得被当成百分数(monkeypatch):
    """0.405706 = 40.57%，若乘错方向会写成 0.41%（差 100 倍）。"""
    _install_akshare(monkeypatch, [_detail()])
    provider = AkshareUnlockProvider()
    row = provider.fetch_symbol_events(['600176'])[0]
    assert '占流通市值 40.57%' in row['title']
    assert row['raw']['ratio'] == pytest.approx(0.405706)
    assert row['type'] == 'unlock' and row['authority'] == 50


def test_两条子通道的标题口径必须一致(monkeypatch):
    """口径不一致会让领域层把同一次解禁当成两个事件各落一行（实测）。"""
    _install_akshare(monkeypatch, [_detail()], queue_records=[_queue(占流通市值比例=0.405706),
                                                              _queue(解禁时间=_day(10))])
    provider = AkshareUnlockProvider()
    rows = provider.fetch_symbol_events(['600176'])
    detail_title = [r['title'] for r in rows if '股票代码' in ' '.join(r['raw'].keys())
                    or r['raw'].get('股票简称')][0]
    queue_titles = [r['title'] for r in rows if r['raw'].get('解禁股东数') is not None]
    assert all('占流通市值 ' in t for t in queue_titles)
    assert '占流通市值 ' in detail_title


def test_标的数超过直接查询阈值时只走全市场表(monkeypatch):
    """逐只查排队明细是 N 次上游请求，仅在小范围时补（避免拖慢 ingest / 触发 WAF）。"""
    calls = _install_akshare(monkeypatch, [_detail(股票代码='%06d' % (600000 + i))
                                           for i in range(12)])
    symbols = ['%06d' % (600000 + i) for i in range(12)]
    provider = AkshareUnlockProvider()
    provider.fetch_symbol_events(symbols)
    assert [c[0] for c in calls] == ['detail']
    provider.fetch_symbol_events(symbols[:3])
    assert [c[0] for c in calls][-1] == 'queue'


def test_不传标的时取全市场窗口且不做逐只查询(monkeypatch):
    calls = _install_akshare(monkeypatch, [_detail()])
    provider = AkshareUnlockProvider()
    rows = provider.fetch_symbol_events(None)
    assert [c[0] for c in calls] == ['detail']
    assert len(rows) == 1


def test_akshare不可用时显式失败(monkeypatch):
    monkeypatch.setitem(sys.modules, 'akshare', None)
    provider = AkshareUnlockProvider()
    assert provider.fetch_symbol_events(['600176']) is None
    assert 'Error' in provider.last_error and provider.last_error.startswith('ModuleNotFound')


def test_窗口内无解禁时返回空列表而不是故障(monkeypatch):
    _install_akshare(monkeypatch, [])
    provider = AkshareUnlockProvider()
    assert provider.fetch_symbol_events(['600176']) == []
    assert provider.last_error is None


def test_不提供政策时返回空列表():
    provider = AkshareUnlockProvider()
    assert provider.fetch_policy() == [] and provider.last_error is None
