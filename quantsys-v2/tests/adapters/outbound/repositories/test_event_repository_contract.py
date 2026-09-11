"""事件仓储契约测试（fake engine，不连库不写库）

锁住的契约（RFC 015 §5 幂等验收）：
  同 evidence_hash 重复写入只更新、不新增（数据库唯一索引 + 应用层先查后写）
  缺/非法 evidence_hash 的行如实计入 skipped+errors，绝不静默丢
  单行坏数据 / 单行 DB 异常不炸整批
  行契约 meta 信封（announce_date/industries/url/authority/external_id/raw）
  for_symbol 分两段查询（个股 + 近期宏观），避免宏观把 limit 占满挤掉个股事件
"""
import json
from datetime import date, timedelta

import pytest

from adapters.outbound.repositories.event_repository import EventRepository


class FakeResult:
    def __init__(self, row=None, rows=None, scalar=None):
        self._row = row
        self._rows = rows or []
        self._scalar = scalar

    def fetchone(self):
        return self._row

    def fetchall(self):
        return self._rows

    def scalar(self):
        return self._scalar


class FakeConn:
    def __init__(self, engine):
        self.engine = engine

    def execute(self, stmt, params=None):
        sql = ' '.join(str(stmt).split())
        self.engine.statements.append({'sql': sql, 'params': params})
        if sql.startswith('SELECT id, status'):
            return FakeResult(row=self.engine.existing)
        if sql.startswith('INSERT'):
            if self.engine.insert_error:
                raise RuntimeError('unique violation')
            self.engine.inserted_rows.append(params)
            return FakeResult(row=(1,))
        if sql.startswith('UPDATE'):
            self.engine.updated_rows.append(params)
            return FakeResult(row=(1,))
        return FakeResult(rows=self.engine.rows, scalar=self.engine.scalar)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeEngine:
    def __init__(self, *, existing=None, rows=None, scalar=None, insert_error=False):
        self.existing = existing
        self.rows = rows or []
        self.scalar = scalar
        self.insert_error = insert_error
        self.statements = []
        self.inserted_rows = []
        self.updated_rows = []

    def begin(self):
        return FakeConn(self)

    def connect(self):
        return FakeConn(self)


def _event(**overrides):
    event = {
        'evidence_hash': 'abc123', 'scope': 'individual', 'type': 'unlock',
        'title': '600176 限售股解禁', 'effective_date': '2026-09-20',
        'announce_date': '2026-09-11', 'importance': 3, 'symbols': ['600176'],
        'industries': [], 'source': 'akshare_unlock', 'url': 'https://x/y',
        'summary': '解禁', 'authority': 50, 'external_id': 'unlock-1',
        'raw': {'ratio': 0.4},
    }
    event.update(overrides)
    return event


def test_同hash重复写入只更新不新增():
    engine = FakeEngine(existing=(7, 'collected'))
    result = EventRepository(engine=engine).upsert([_event()])
    assert result == {'inserted': 0, 'updated': 1, 'skipped': 0, 'errors': []}
    assert engine.updated_rows and not engine.inserted_rows


def test_新hash插入():
    engine = FakeEngine(existing=None)
    result = EventRepository(engine=engine).upsert([_event()])
    assert result['inserted'] == 1 and len(engine.inserted_rows) == 1


def test_缺evidence_hash必须如实计入skipped():
    engine = FakeEngine(existing=None)
    result = EventRepository(engine=engine).upsert([_event(evidence_hash='')])
    assert result['skipped'] == 1 and 'missing evidence_hash' in result['errors'][0]
    assert engine.inserted_rows == [], '缺锚的行不得入库'


def test_单行坏数据不炸整批():
    engine = FakeEngine(existing=None)
    result = EventRepository(engine=engine).upsert([
        _event(evidence_hash='ok1'),
        _event(evidence_hash='bad', title=''),
        _event(evidence_hash='bad2', effective_date='2026-13-45'),
        _event(evidence_hash='ok2', importance=9),
    ])
    assert result['inserted'] == 1 and result['skipped'] == 3
    assert len(result['errors']) == 3


def test_单行数据库异常不炸整批():
    engine = FakeEngine(existing=None, insert_error=True)
    result = EventRepository(engine=engine).upsert([_event(), _event(evidence_hash='b')])
    assert result['skipped'] == 2 and all('upsert failed' in e for e in result['errors'])


def test_meta信封承载行契约字段():
    engine = FakeEngine(existing=None)
    EventRepository(engine=engine).upsert([_event()])
    params = engine.inserted_rows[0]
    meta = json.loads(params['meta'])
    assert meta['announce_date'] == '2026-09-11'
    assert meta['industries'] == []
    assert meta['url'] == 'https://x/y'
    assert meta['authority'] == 50
    assert meta['external_id'] == 'unlock-1'
    assert meta['raw'] == {'ratio': 0.4}
    assert json.loads(params['symbols']) == ['600176']
    assert params['symbol'] == '600176', '单标的时兼容既有单值列'
    assert params['status'] == 'collected', '机器采集不写 pending（防提醒噪声）'


def test_多标的时单值列留空由symbols数组表达():
    engine = FakeEngine(existing=None)
    EventRepository(engine=engine).upsert([_event(symbols=['600176', '600150'])])
    assert engine.inserted_rows[0]['symbol'] is None


def test_多源分歧写入meta():
    engine = FakeEngine(existing=None)
    EventRepository(engine=engine).upsert([_event(source_divergence={'kept_source': 'cninfo'})])
    assert json.loads(engine.inserted_rows[0]['meta'])['source_divergence'] == {
        'kept_source': 'cninfo'}


def test_查询只拼入实际给出的过滤条件():
    engine = FakeEngine(rows=[])
    EventRepository(engine=engine).list(scope='macro', limit=5)
    sql = engine.statements[-1]['sql']
    where = sql.split('WHERE', 1)[1] if 'WHERE' in sql else ''
    assert 'scope = :scope' in where and 'event_type' not in where, '未给出的过滤条件不得进 WHERE'
    assert engine.statements[-1]['params']['limit'] == 5


def test_按标的查询分两段避免宏观挤掉个股():
    """2026-09-11 实测：单条 (symbols @> needle OR scope='macro') 查询会让宏观日期最早占满 limit。"""
    engine = FakeEngine(rows=[])
    EventRepository(engine=engine).for_symbol('600150', limit=50)
    sqls = [s['sql'] for s in engine.statements]
    assert len(sqls) == 2
    assert 'symbols @> CAST(:needle AS jsonb)' in sqls[0]
    assert "scope = 'macro'" in sqls[1]
    assert engine.statements[0]['params']['limit'] == 50
    assert engine.statements[1]['params']['limit'] == 30, '宏观事件单独限量'


def test_按标的查询空代码不打库():
    engine = FakeEngine(rows=[])
    assert EventRepository(engine=engine).for_symbol('  ') == []
    assert engine.statements == []


def test_upcoming按日期区间与重要度排序():
    engine = FakeEngine(rows=[])
    EventRepository(engine=engine).upcoming(days=7, limit=10)
    sql = engine.statements[-1]['sql']
    assert 'event_date >= :start' in sql and 'importance DESC' in sql
    params = engine.statements[-1]['params']
    today = date.today()
    assert params['start'] == today.isoformat()
    assert params['end'] == (today + timedelta(days=7)).isoformat()


def test_exists_by_hash空值不打库():
    engine = FakeEngine()
    repo = EventRepository(engine=engine)
    assert repo.exists_by_hash('') is False
    assert engine.statements == []


def test_stats汇总口径():
    engine = FakeEngine(rows=[], scalar=None)
    stats = EventRepository(engine=engine).stats()
    assert set(stats) == {'by_scope', 'by_type', 'latest_updated_at'}
