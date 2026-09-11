"""EventFeedService 编排契约测试（fake manager / fake repository，不触网不写库）

应用层只做编排，因此这里锁的是**编排语义**：
  多源失败 → 显式失败（绝不返回空清单冒充成功）
  空采集池 → 不伪造标的，如实回报 universe=[] 与原因
  截断/降级必须出现在响应里（provider_notes / degraded / truncated）
  定时任务包装层不得把内部 success=False 包装成任务成功（2026-09-11 静默失败教训）
"""
import asyncio

import pytest

from application.services.event_feed_service import (
    EventFeedService, IngestEventsDailyJob, IngestEventsPolicyJob, build_event_ingest_jobs,
)


class FakeManager:
    def __init__(self, *, policy=None, symbols=None, providers=()):
        self._policy = policy
        self._symbols = symbols
        self.event_symbol_providers = list(providers)
        self.symbol_calls = []

    def get_event_policy_events(self):
        return self._policy or {'success': False, 'error': 'policy failed', 'attempted_sources': ['gov_policy']}

    def get_event_symbol_events(self, symbols=None, include_fallback=True):
        self.symbol_calls.append((symbols, include_fallback))
        return self._symbols or {'success': False, 'error': 'symbol failed', 'attempted_sources': []}


class FakeProvider:
    def __init__(self, name, note=''):
        self.name = name
        self.truncation_note = note


class FakeRepo:
    def __init__(self, *, universe=(), list_rows=(), symbol_rows=None, upcoming_rows=()):
        self.universe = list(universe)
        self.list_rows = list(list_rows)
        self.symbol_rows = symbol_rows or {}
        self.upcoming_rows = list(upcoming_rows)
        self.upserted = []

    def upsert(self, events):
        self.upserted.append(list(events))
        return {'inserted': len(events), 'updated': 0, 'skipped': 0, 'errors': []}

    def list(self, **kwargs):
        return list(self.list_rows)

    def for_symbol(self, symbol, limit=50):
        return list(self.symbol_rows.get(symbol, []))

    def upcoming(self, days=7, limit=100):
        return list(self.upcoming_rows)

    def default_universe(self, limit=200):
        return list(self.universe)[:limit]

    def stats(self):
        return {'by_scope': {'individual': 3}, 'by_type': {'unlock': 2}, 'latest_updated_at': 'X'}


def _policy_row(title='市场监督管理所条例', date='2026-09-11', source='gov_policy', authority=80):
    return {'title': title, 'type': 'policy', 'scope': None, 'effective_date': date,
            'announce_date': date, 'symbols': [], 'industries': [], 'source': source,
            'url': 'u', 'summary': '', 'authority': authority, 'raw': {}}


def _symbol_row(title='600176 限售股解禁：定向增发机构配售股份', date='2026-09-20',
                source='akshare_unlock', authority=50):
    return {'title': title, 'type': 'unlock', 'scope': 'individual', 'effective_date': date,
            'announce_date': '', 'symbols': ['600176'], 'industries': [], 'source': source,
            'url': 'u', 'summary': '', 'authority': authority, 'raw': {'ratio': 0.4}}


# ─────────────────────────────── 政策 ingest ───────────────────────────────

def test_政策采集成功时幂等落库并回报计数():
    manager = FakeManager(policy={'success': True, 'data': [_policy_row()],
                                  'source': 'gov_policy', 'attempted_sources': ['gov_policy'],
                                  'degraded': False})
    repo = FakeRepo()
    result = EventFeedService(manager=manager, repository=repo).ingest_policy()
    assert result['success'] is True
    assert result['counts']['fetched'] == 1 and result['counts']['merged'] == 1
    assert result['counts']['inserted'] == 1
    assert result['data'][0]['type'] == 'policy'
    assert len(repo.upserted) == 1, '必须落库一次'


def test_政策全源失败必须显式失败而不是返回空清单():
    manager = FakeManager(policy={'success': False, 'error': 'All policy providers failed',
                                  'attempted_sources': ['gov_policy', 'csrc_policy'],
                                  'provider_errors': {'gov_policy': 'HTTP 403'}})
    repo = FakeRepo()
    result = EventFeedService(manager=manager, repository=repo).ingest_policy()
    assert result['success'] is False and result['degraded'] is True
    assert result['error'] == 'All policy providers failed'
    assert result['provider_errors'] == {'gov_policy': 'HTTP 403'}
    assert repo.upserted == [], '失败时不得写库'


def test_人工兜底必须被显式标注():
    manager = FakeManager(policy={'success': True, 'data': [_policy_row(source='manual_policy_seed',
                                                                       authority=40)],
                                  'source': 'manual_policy_seed', 'attempted_sources': [],
                                  'degraded': True, 'manual_fallback_used': True})
    result = EventFeedService(manager=manager, repository=FakeRepo()).ingest_policy()
    assert result['manual_fallback_used'] is True
    assert result['degraded'] is True


def test_被拒绝的行如实回报且计数一致():
    rows = [_policy_row(), dict(_policy_row(title=''), effective_date='')]
    manager = FakeManager(policy={'success': True, 'data': rows, 'source': 'gov_policy',
                                  'attempted_sources': ['gov_policy']})
    result = EventFeedService(manager=manager, repository=FakeRepo()).ingest_policy()
    assert result['counts']['rejected'] == 1
    assert result['rejected_rows'] and 'title' in result['rejected_rows'][0]['reason']


# ─────────────────────────────── 个股 ingest ───────────────────────────────

def test_默认采集池为空时不伪造标的且不调用上游():
    manager = FakeManager()
    repo = FakeRepo(universe=[])
    result = EventFeedService(manager=manager, repository=repo).ingest_symbol_events()
    assert result['success'] is True and result['data'] == []
    assert result['universe'] == [] and result['counts']['merged'] == 0
    assert manager.symbol_calls == [], '空池不允许打上游'
    assert '不伪造标的' in result['note']


def test_显式传入标的时universe_source标记为explicit():
    manager = FakeManager(symbols={'success': True, 'data': [_symbol_row()], 'source': 'akshare_unlock'})
    result = EventFeedService(manager=manager, repository=FakeRepo()).ingest_symbol_events(
        symbols=['600176'])
    assert result['universe_source'] == 'explicit'
    assert result['universe'] == ['600176']
    assert manager.symbol_calls == [(['600176'], False)], 'ingest 路径必须排除 DB 兜底源'


def test_个股全源健康无数据时必须成功且0条而不是失败():
    """P9 上层护栏（2026-09-11『空结果≠故障』契约对齐）：

    manager 把「全部通道健康但无数据」归为 success=True+empty=True；应用层必须把它
    当**成功且 0 条**（返回 empty=True + 说明），**不得** JobResult.fail。
    修复前 manager 报 success=False → 这里走失败分支 → 无人值守的每日 17:00
    ingest 在「当天确实没有公告」时任务标红，真故障与无数据同形。
    """
    manager = FakeManager(symbols={
        'success': True, 'data': [], 'source': None,
        'attempted_sources': ['eastmoney_notice', 'cninfo_disclosure', 'akshare_unlock'],
        'provider_errors': {
            'eastmoney_notice': '返回空数据（非故障：该查询无数据）；说明：东财无公告',
            'cninfo_disclosure': '返回空数据（非故障：该查询无数据）；说明：巨潮无披露',
        },
        'empty': True,
        'empty_sources': ['eastmoney_notice', 'cninfo_disclosure', 'akshare_unlock'],
        'degraded': False,
    })
    repo = FakeRepo(universe=['600176'])
    result = EventFeedService(manager=manager, repository=repo).ingest_symbol_events()
    assert result['success'] is True, '全源健康无数据是成功，不是失败'
    assert result['data'] == [] and result['counts']['merged'] == 0
    assert result['empty'] is True
    assert sorted(result['empty_sources']) == ['akshare_unlock', 'cninfo_disclosure',
                                               'eastmoney_notice']
    assert result['degraded'] is False, '健康无数据不是降级'
    assert '不是故障' in result['note']
    assert repo.upserted == [], '0 条时不应写库'


def test_个股全源健康无数据时定时任务判绿():
    """任务层护栏：无公告日不得把任务标红（这是 P9 的业务后果）"""
    manager = FakeManager(symbols={
        'success': True, 'data': [], 'source': None, 'attempted_sources': [],
        'empty': True, 'empty_sources': ['eastmoney_notice'], 'degraded': False,
    })
    service = EventFeedService(manager=manager, repository=FakeRepo(universe=['600176']))
    res = asyncio.run(IngestEventsDailyJob(service).execute({}))
    assert res.success is True, '无公告日任务必须判绿'
    assert res.error is None


def test_个股一源硬失败一源健康空仍显式失败():
    """(b) blast radius 护栏：硬失败存在时 success 语义不变，empty_sources 如实"""
    manager = FakeManager(symbols={
        'success': False, 'error': 'All event symbol providers failed',
        'attempted_sources': ['eastmoney_notice', 'akshare_unlock'],
        'provider_errors': {'eastmoney_notice': 'HTTP 503'},
        'empty_sources': ['akshare_unlock'],
        'degraded': True,
    })
    repo = FakeRepo(universe=['600176'])
    service = EventFeedService(manager=manager, repository=repo)
    result = service.ingest_symbol_events()
    assert result['success'] is False and result['degraded'] is True
    assert result['empty'] is False
    assert result['empty_sources'] == ['akshare_unlock'], '健康空源仍须如实列出'
    assert repo.upserted == [], '失败时不得写库'
    # 任务层同样必须判红
    assert asyncio.run(IngestEventsDailyJob(service).execute({})).success is False


def test_个股全源失败必须显式失败():
    manager = FakeManager(symbols={'success': False, 'error': 'All event symbol providers failed',
                                   'attempted_sources': [], 'provider_errors': {}})
    repo = FakeRepo(universe=['600176'])
    result = EventFeedService(manager=manager, repository=repo).ingest_symbol_events()
    assert result['success'] is False and result['degraded'] is True
    assert repo.upserted == []


def test_provider截断必须出现在响应里():
    """静默失败清单 §2：provider 只采集前 N 只却不标注 = 调用方拿到"覆盖完整"的假象。"""
    manager = FakeManager(
        symbols={'success': True, 'data': [_symbol_row()], 'source': 'akshare_unlock'},
        providers=[FakeProvider('eastmoney_notice', 'eastmoney_notice: 请求标的 200 只，'
                                                     '超过单次上限 30 只，本次仅采集前 30 只'),
                   FakeProvider('cninfo_disclosure')])
    result = EventFeedService(manager=manager, repository=FakeRepo(
        universe=['600176'])).ingest_symbol_events()
    assert result['truncated'] is True
    assert result['provider_notes'] and '30' in result['provider_notes'][0]
    assert result['degraded'] is True, '截断属于降级，必须如实标注'


def test_默认池命中上限时必须提示可能截断():
    universe = ['%06d' % (600000 + i) for i in range(5)]
    manager = FakeManager(symbols={'success': True, 'data': [_symbol_row()], 'source': 'akshare_unlock'})
    result = EventFeedService(manager=manager, repository=FakeRepo(universe=universe)) \
        .ingest_symbol_events(universe_limit=5)
    assert result['truncated'] is True
    assert '上限' in result['provider_notes'][0]


def test_多源分歧挂回被保留的事件():
    """两源标题相近（≥0.62）但 hash 不同 → 合并保留权威源，差异挂回该事件。"""
    rows = [_symbol_row(title='600176 限售股解禁：定向增发机构配售股份（akshare）'),
            dict(_symbol_row(title='600176 限售股解禁：定向增发机构配售股份（巨潮）',
                             source='cninfo_disclosure'),
                 authority=90)]
    manager = FakeManager(symbols={'success': True, 'data': rows, 'source': 'a+b'})
    repo = FakeRepo(universe=['600176'])
    result = EventFeedService(manager=manager, repository=repo).ingest_symbol_events()
    assert result['cross_source_conflict'], '多源同一事件必须留痕'
    record = repo.upserted[0][0]
    assert record['source_divergence']['kept_source'] == 'cninfo_disclosure'
    assert record['source_divergence']['dropped'][0]['source'] == 'akshare_unlock'


# ──────────────────────────────── 查询接口 ────────────────────────────────

def test_按标的查询按窗口过滤并如实回报被过滤条数():
    from datetime import date, timedelta
    today = date.today()
    rows = [{'effective_date': today.strftime('%Y-%m-%d')},
            {'effective_date': (today - timedelta(days=400)).strftime('%Y-%m-%d')}]
    reply = EventFeedService(manager=FakeManager(), repository=FakeRepo(
        symbol_rows={'600150': rows})).events_for_symbol('600150', window_days=30)
    assert reply['count'] == 1 and reply['filtered_out'] == 1


def test_空标的查询直接报错():
    reply = EventFeedService(manager=FakeManager(), repository=FakeRepo()).events_for_symbol('')
    assert reply['success'] is False and reply['error'] == 'symbol 不能为空'


def test_分页查询的非法scope必须fail_loud():
    with pytest.raises(ValueError):
        EventFeedService(manager=FakeManager(), repository=FakeRepo()).list_events(scope='galaxy')


def test_分页查询透出过滤条件便于复核():
    reply = EventFeedService(manager=FakeManager(), repository=FakeRepo(
        list_rows=[_policy_row()])).list_events(scope='macro', type='policy', limit=10)
    assert reply['count'] == 1 and reply['filters']['type'] == 'policy'


def test_统计接口透出仓储统计():
    reply = EventFeedService(manager=FakeManager(), repository=FakeRepo()).stats()
    assert reply['success'] is True and reply['data']['by_scope'] == {'individual': 3}


# ──────────────────────────── 事件 → 盯盘建议 ────────────────────────────

def test_盯盘建议只产出建议不自动建规则():
    from datetime import date, timedelta
    soon = (date.today() + timedelta(days=10)).strftime('%Y-%m-%d')
    repo = FakeRepo(symbol_rows={'600176': [dict(_symbol_row(date=soon))]})
    reply = EventFeedService(manager=FakeManager(), repository=repo).link_to_watchlist(['600176'])
    assert reply['count'] == 1
    assert reply['data'][0]['auto_created'] is False
    assert '复核' in reply['note']


def test_盯盘建议按标的去重():
    from datetime import date, timedelta
    soon = (date.today() + timedelta(days=10)).strftime('%Y-%m-%d')
    row = dict(_symbol_row(date=soon))
    repo = FakeRepo(symbol_rows={'600176': [row]})
    reply = EventFeedService(manager=FakeManager(), repository=repo).link_to_watchlist(
        ['600176', '600176'])
    assert reply['count'] == 1


# ──────────────────────────── 定时任务包装层 ────────────────────────────

def test_任务内部失败不得被包装成任务成功():
    """2026-09-11 教训：内部 success=False 被包装成任务成功 → 任务状态永远全绿。"""
    manager = FakeManager(symbols={'success': False, 'error': 'All event symbol providers failed'})
    service = EventFeedService(manager=manager, repository=FakeRepo(universe=['600176']))
    job = IngestEventsDailyJob(service)
    result = asyncio.run(job.execute({}))
    assert result.success is False and 'failed' in result.error


def test_任务成功时回报计数():
    manager = FakeManager(symbols={'success': True, 'data': [_symbol_row()], 'source': 'akshare_unlock'})
    service = EventFeedService(manager=manager, repository=FakeRepo(universe=['600176']))
    result = asyncio.run(IngestEventsDailyJob(service).execute({'universe_limit': 200}))
    assert result.success is True and 'inserted' in result.message


def test_任务抛异常必须转成失败结果():
    class Boom(EventFeedService):
        def ingest_policy(self):
            raise RuntimeError('上游炸了')

    result = asyncio.run(IngestEventsPolicyJob(Boom(manager=FakeManager(), repository=FakeRepo()))
                         .execute({}))
    assert result.success is False and 'RuntimeError' in result.error


def test_任务接受逗号分隔的标的参数():
    manager = FakeManager(symbols={'success': True, 'data': [_symbol_row()], 'source': 'x'})
    service = EventFeedService(manager=manager, repository=FakeRepo())
    asyncio.run(IngestEventsDailyJob(service).execute({'symbols': '600176,600150'}))
    assert manager.symbol_calls[0][0] == ['600176', '600150']


def test_build_event_ingest_jobs返回两个任务实例():
    service = EventFeedService(manager=FakeManager(), repository=FakeRepo())
    jobs = build_event_ingest_jobs(service)
    assert [j.name for j in jobs] == ['ingest_events_daily', 'ingest_events_policy']
    assert all(j.timeout_seconds > 0 for j in jobs)


# ──────────────────────────── 依赖注入护栏 ────────────────────────────

def test_缺少注入时fail_loud而不是静默返回空():
    service = EventFeedService()
    with pytest.raises(RuntimeError, match='IDataProviderManager'):
        service.ingest_policy()
    with pytest.raises(RuntimeError, match='IMarketEventRepository'):
        service.events_for_symbol('600150')
