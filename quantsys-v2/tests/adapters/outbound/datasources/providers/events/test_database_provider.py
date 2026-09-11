"""本地库兜底 provider 契约测试（fake repository，不写库）

锁住的契约：
  读库失败 → None + last_error；库内确实没有 → []（空结果 ≠ 故障）
  所有输出带 stale=True（禁止把库里的旧事件当实时事件用）
  evidence_hash 原样透传（保证 ingest 幂等命中同一行）
  标的数超上限必须标注截断
"""
import pytest

from adapters.outbound.datasources.providers.events.database import (
    _MAX_SYMBOLS, DatabaseEventProvider,
)


class FakeRepo:
    def __init__(self, *, list_rows=None, symbol_rows=None, raise_on=None):
        self.list_rows = list_rows or []
        self.symbol_rows = symbol_rows or {}
        self.raise_on = raise_on
        self.calls = []

    def list(self, **kwargs):
        self.calls.append(('list', kwargs))
        if self.raise_on == 'list':
            raise RuntimeError('connection reset')
        return list(self.list_rows)

    def for_symbol(self, symbol, limit=50):
        self.calls.append(('for_symbol', symbol))
        if self.raise_on == 'for_symbol':
            raise RuntimeError('connection reset')
        return list(self.symbol_rows.get(symbol, []))


def _row(**overrides):
    row = {
        'id': 1, 'scope': 'individual', 'type': 'unlock', 'title': '600176 限售股解禁',
        'effective_date': '2026-09-20', 'announce_date': '2026-09-11', 'importance': 3,
        'symbols': ['600176'], 'industries': [], 'source': 'akshare_unlock',
        'url': 'https://data.eastmoney.com/dxf/q/600176.html', 'summary': '解禁',
        'external_id': 'unlock-600176-2026-09-20', 'evidence_hash': 'abc123',
        'updated_at': '2026-09-11T10:00:00',
    }
    row.update(overrides)
    return row


def test_读库异常必须写last_error而不是返回空():
    provider = DatabaseEventProvider(FakeRepo(raise_on='for_symbol'))
    assert provider.fetch_symbol_events(['600176']) is None
    assert 'connection reset' in provider.last_error


def test_政策读取异常也必须显式失败():
    provider = DatabaseEventProvider(FakeRepo(raise_on='list'))
    assert provider.fetch_policy() is None
    assert 'connection reset' in provider.last_error


def test_库内无记录返回空列表且不算故障():
    provider = DatabaseEventProvider(FakeRepo())
    assert provider.fetch_symbol_events(['600176']) == []
    assert provider.last_error is None


def test_输出必须带stale标记与evidence_hash():
    provider = DatabaseEventProvider(FakeRepo(symbol_rows={'600176': [_row()]}))
    rows = provider.fetch_symbol_events(['600176'])
    assert rows[0]['stale'] is True, '兜底源天然陈旧，禁止当实时数据用'
    assert rows[0]['evidence_hash'] == 'abc123', '幂等锚必须原样保留'
    assert rows[0]['authority'] == 20


def test_单标的列回落为symbols列表():
    row = _row(symbols=[], symbol='600176')
    provider = DatabaseEventProvider(FakeRepo(symbol_rows={'600176': [row]}))
    assert provider.fetch_symbol_events(['600176'])[0]['symbols'] == ['600176']


def test_同一事件被多只标的各取一次只保留一条():
    repo = FakeRepo(symbol_rows={'600176': [_row()], '000001': [_row()]})
    provider = DatabaseEventProvider(repo)
    rows = provider.fetch_symbol_events(['600176', '000001'])
    assert len(rows) == 1


def test_event_type列名兼容type与event_type():
    provider = DatabaseEventProvider(FakeRepo(symbol_rows={
        '600176': [_row(type=None, event_type='earnings')]}))
    rows = provider.fetch_symbol_events(['600176'])
    assert rows[0]['type'] == 'earnings'


def test_源名固定为database_event便于健康统计归因():
    provider = DatabaseEventProvider(FakeRepo(symbol_rows={'600176': [_row()]}))
    rows = provider.fetch_symbol_events(['600176'])
    assert rows[0]['source'] == 'database_event'


def test_不传标的时按窗口查询且不去重歧义():
    repo = FakeRepo(list_rows=[_row()])
    provider = DatabaseEventProvider(repo)
    rows = provider.fetch_symbol_events(None)
    assert len(rows) == 1
    kind, kwargs = repo.calls[0]
    assert kind == 'list' and 'date_from' in kwargs and 'date_to' in kwargs


def test_标的数超上限必须标注截断():
    symbols = ['%06d' % (600000 + i) for i in range(_MAX_SYMBOLS + 2)]
    repo = FakeRepo(symbol_rows={s: [] for s in symbols})
    provider = DatabaseEventProvider(repo)
    provider.fetch_symbol_events(symbols)
    queried = [c[1] for c in repo.calls if c[0] == 'for_symbol']
    assert len(queried) == _MAX_SYMBOLS
    assert provider.truncated_symbols == symbols[_MAX_SYMBOLS:]
    assert provider.truncation_note


def test_政策兜底读取宏观与行业政策():
    repo = FakeRepo(list_rows=[_row(scope='macro', type='policy', symbols=[], symbol=None)])
    provider = DatabaseEventProvider(repo)
    rows = provider.fetch_policy()
    assert len(rows) == 2, 'macro 与 industry 各查一次后合并'
    assert all(call[1]['type'] == 'policy' for call in repo.calls)
    assert rows[0]['scope'] == 'macro'


def test_兜底源必须被标记为is_fallback以免自己喂自己():
    assert DatabaseEventProvider.is_fallback is True
