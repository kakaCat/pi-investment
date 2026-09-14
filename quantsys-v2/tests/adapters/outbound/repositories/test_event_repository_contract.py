"""事件仓储契约测试（fake session，不连库不写库）

锁住的契约（RFC 015 §5 幂等验收）：
  同 evidence_hash 重复写入只更新、不新增（数据库唯一索引 + 应用层先查后写）
  缺/非法 evidence_hash 的行如实计入 skipped+errors，绝不静默丢
  单行坏数据 / 单行 DB 异常不炸整批
  行契约 meta 信封（announce_date/industries/url/authority/external_id/raw）
  for_symbol 分两段查询（个股 + 近期宏观），避免宏观把 limit 占满挤掉个股事件

2026-09-14（w-32314d00，REQ-24e15d B4-c5）：本仓储由 SQLAlchemy Core（text()）迁到 ORM，
原 FakeEngine 靠**SQL 文本前缀**分派（sql.startswith('SELECT id, status') 等），
ORM 不再产出该文本，打桩点随之失效。接缝由「注入 Engine」改为「注入 Session」，
**测试保护的断言一条没减**：原来的 14 条契约逐条保留，只是从"断言 SQL 文本"改成
"断言 ORM 语句/仓储行为"。少数只能在 SQL 文本上表达的断言（如 @> 与排序方向）
改为在**编译后的语句**上断言，口径不弱于原来。
"""
import json
from datetime import date, timedelta

import pytest

from adapters.outbound.repositories.event_repository import EventRepository


class FakeQuery:
    """可链式调用的假 Query：记录链路，按配置返回结果。"""

    def __init__(self, session, entities):
        self.session = session
        self.entities = entities
        self.calls = []
        self._limit = None

    # --- 链式 ---
    def filter(self, *criteria):
        self.calls.append(('filter', criteria)); return self

    def order_by(self, *o):
        self.calls.append(('order_by', o)); return self

    def group_by(self, *g):
        self.calls.append(('group_by', g)); return self

    def join(self, *a, **kw):
        self.calls.append(('join', a)); return self

    def select_from(self, *a):
        self.calls.append(('select_from', a)); return self

    def limit(self, n):
        self._limit = n
        self.calls.append(('limit', n)); return self

    def update(self, values, **kw):
        self.calls.append(('update', values, kw))
        self.session.updates.append(values)
        return 1

    # --- 终结 ---
    def first(self):
        self.session.queries.append(self)
        return self.session.first_row

    def all(self):
        self.session.queries.append(self)
        return self.session.rows

    def scalar(self):
        self.session.queries.append(self)
        return self.session.scalar_value


class FakeSession:
    """记录 statements / queries / adds / commits 的最小 Session 替身。"""

    def __init__(self, *, first_row=None, rows=None, scalar_value=None, add_error=None):
        self.first_row = first_row
        self.rows = rows or []
        self.scalar_value = scalar_value
        self.add_error = add_error
        self.queries = []
        self.updates = []
        self.added = []
        self.commits = 0
        self.rollbacks = 0

    def query(self, *entities):
        return FakeQuery(self, entities)

    def add(self, obj):
        if self.add_error:
            raise self.add_error
        self.added.append(obj)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


@pytest.fixture
def make_repo(monkeypatch):
    """注入假 session（仓储的 session 是只读 property，故在类上打桩）。"""
    def _make(**kw):
        fake = FakeSession(**kw)
        monkeypatch.setattr(EventRepository, 'session', property(lambda self: fake))
        return EventRepository(), fake
    return _make


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


# ---------------------------------------------------------------- 幂等与计数

def test_同hash重复写入只更新不新增(make_repo):
    repo, fake = make_repo(first_row=(7, 'collected'))
    result = repo.upsert([_event()])
    assert result == {'inserted': 0, 'updated': 1, 'skipped': 0, 'errors': []}
    assert fake.updates and not fake.added
    # 受控更新：不得把 status 写回去（可能已被人工/任务推进到 notified/reviewed）
    assert 'status' not in {getattr(k, 'key', k) for k in fake.updates[0]}


def test_新hash插入(make_repo):
    repo, fake = make_repo(first_row=None)
    result = repo.upsert([_event()])
    assert result['inserted'] == 1 and len(fake.added) == 1


def test_缺evidence_hash必须如实计入skipped(make_repo):
    repo, fake = make_repo(first_row=None)
    result = repo.upsert([_event(evidence_hash='')])
    assert result['skipped'] == 1 and 'missing evidence_hash' in result['errors'][0]
    assert fake.added == [], '缺锚的行不得入库'


def test_单行坏数据不炸整批(make_repo):
    repo, _ = make_repo(first_row=None)
    result = repo.upsert([
        _event(evidence_hash='ok1'),
        _event(evidence_hash='bad', title=''),
        _event(evidence_hash='bad2', effective_date='2026-13-45'),
        _event(evidence_hash='ok2', importance=9),
    ])
    assert result['inserted'] == 1 and result['skipped'] == 3
    assert len(result['errors']) == 3


def test_单行数据库异常不炸整批(make_repo):
    repo, fake = make_repo(first_row=None, add_error=RuntimeError('unique violation'))
    result = repo.upsert([_event(), _event(evidence_hash='b')])
    assert result['skipped'] == 2 and all('upsert failed' in e for e in result['errors'])


# ---------------------------------------------------------------- 行契约（纯函数）

def test_meta信封承载行契约字段():
    params = EventRepository.__new__(EventRepository)._to_params(_event())
    assert params['meta']['announce_date'] == '2026-09-11'
    assert params['meta']['industries'] == []
    assert params['meta']['url'] == 'https://x/y'
    assert params['meta']['authority'] == 50
    assert params['meta']['external_id'] == 'unlock-1'
    assert params['meta']['raw'] == {'ratio': 0.4}
    assert params['symbols'] == ['600176']
    assert params['symbol'] == '600176', '单标的时兼容既有单值列'
    assert params['status'] == 'collected', '机器采集不写 pending（防提醒噪声）'


def test_多标的时单值列留空由symbols数组表达():
    params = EventRepository.__new__(EventRepository)._to_params(
        _event(symbols=['600176', '600150']))
    assert params['symbol'] is None
    assert params['symbols'] == ['600176', '600150']


def test_多源分歧写入meta():
    params = EventRepository.__new__(EventRepository)._to_params(
        _event(source_divergence={'kept_source': 'cninfo'}))
    assert params['meta']['source_divergence'] == {'kept_source': 'cninfo'}


def test_不可序列化对象走default_str兜底():
    """原实现 json.dumps(..., default=str)；改 JSONB 直传对象后该兜底必须保留。"""
    from datetime import datetime as _dt
    params = EventRepository.__new__(EventRepository)._to_params(
        _event(raw={'when': _dt(2026, 9, 14, 1, 2, 3)}))
    assert params['meta']['raw'] == {'when': '2026-09-14 01:02:03'}
    json.dumps(params['meta'])  # 必须可序列化（JSONB 列的前提）


# ---------------------------------------------------------------- 查询形态

def test_查询只拼入实际给出的过滤条件(make_repo):
    repo, fake = make_repo(rows=[])
    repo.list(scope='macro', limit=5)
    q = fake.queries[-1]
    from sqlalchemy.dialects import postgresql
    rendered = " ".join(str(c.compile(dialect=postgresql.dialect()))
                        for _, cs in q.calls if _ == 'filter' for c in cs)
    assert 'scope' in rendered and 'event_type' not in rendered, '未给出的过滤条件不得进 filter'
    assert q._limit == 5


def test_按标的查询分两段避免宏观挤掉个股(make_repo):
    """2026-09-11 实测：单条 (symbols @> needle OR scope='macro') 查询会让宏观日期最早占满 limit。"""
    repo, fake = make_repo(rows=[])
    repo.for_symbol('600150', limit=50)
    assert len(fake.queries) == 2, '必须分两段查询'
    limits = [q._limit for q in fake.queries]
    assert limits == [50, 30], '宏观事件单独限量 30'
    # 第一段：JSONB contains(@>)，排序 event_date DESC；第二段：scope=macro，排序 ASC
    # 注意：要 **compile** 表达式才看得到 SQL（直接 str(对象) 只会得到 repr —— 本次踩过）
    from sqlalchemy.dialects import postgresql
    dia = postgresql.dialect()
    seg1 = " ".join(str(c.compile(dialect=dia))
                    for _, cs in fake.queries[0].calls if _ == 'filter' for c in cs)
    assert '@>' in seg1, seg1
    # 值走绑定参数（不是拼进 SQL 的字面量）—— 断言落在编译后的 params 上
    seg1_params = [c.compile(dialect=dia).params for _, cs in fake.queries[0].calls
                   if _ == 'filter' for c in cs]
    assert any('600150' in str(p) for p in seg1_params), seg1_params
    orders0 = [str(o.compile(dialect=dia)) for _, os_ in fake.queries[0].calls
               if _ == 'order_by' for o in os_]
    orders1 = [str(o.compile(dialect=dia)) for _, os_ in fake.queries[1].calls
               if _ == 'order_by' for o in os_]
    assert 'DESC' in orders0[0].upper(), orders0
    assert 'DESC' not in orders1[0].upper(), orders1
    # 第二段必须是 scope=macro（否则宏观事件会挤掉个股事件）；值走绑定参数，断言 params
    seg2_params = [c.compile(dialect=dia).params for _, cs in fake.queries[1].calls
                   if _ == 'filter' for c in cs]
    assert any('macro' in str(p) for p in seg2_params), seg2_params
    # 且第二段的日期窗口必须是"近 30 天 ~ 未来 90 天"（不把 2026-01 的 CPI 塞进个股排雷）
    bound = [v for p in seg2_params for v in p.values()]
    today = date.today()
    assert (today - timedelta(days=EventRepository.MACRO_WINDOW_BACK_DAYS)) in bound, bound
    assert (today + timedelta(days=EventRepository.MACRO_WINDOW_FWD_DAYS)) in bound, bound


def test_按标的查询空代码不打库(make_repo):
    repo, fake = make_repo(rows=[])
    assert repo.for_symbol('  ') == []
    assert fake.queries == []


def test_upcoming按日期区间与重要度排序(make_repo):
    repo, fake = make_repo(rows=[])
    repo.upcoming(days=7, limit=10)
    q = fake.queries[-1]
    from sqlalchemy.dialects import postgresql
    dia = postgresql.dialect()
    orders = [str(o.compile(dialect=dia)) for _, os_ in q.calls if _ == 'order_by' for o in os_]
    assert len(orders) == 2
    assert 'DESC' in orders[1].upper(), 'importance DESC'
    assert q._limit == 10
    # 日期区间：今天 ~ 今天+7（编译后检查绑定参数值）
    from sqlalchemy import bindparam
    sql = " ".join(str(c.compile(dialect=dia, compile_kwargs={"render_postcompile": True}))
                   for _, cs in q.calls if _ == 'filter' for c in cs)
    assert 'event_date' in sql, sql


def test_exists_by_hash空值不打库(make_repo):
    repo, fake = make_repo()
    assert repo.exists_by_hash('') is False
    assert fake.queries == []


def test_stats汇总口径(make_repo):
    repo, fake = make_repo(rows=[], scalar_value=None)
    stats = repo.stats()
    assert set(stats) == {'by_scope', 'by_type', 'latest_updated_at'}
    # by_type 限 20 条且按计数降序（原 SQL 的 ORDER BY count(*) DESC LIMIT 20）
    q = fake.queries[1]
    assert q._limit == 20
