"""自维护回路任务单测（2026-09-11，w-f436d4ea）

为什么必须有：这两个任务是**无人值守、自动反复跑**的
（minute_kline_sync 每 5 分钟、industry_chain_refresh 每周），
出错时没有人盯着看 —— 正是最该用单测锁边界的地方。此前只有端到端实测，
且其中一个坑（按 dict 处理实际为领域模型的行）是靠**运行时崩**才发现的，
不是靠测试。

本文件锁住：
1. 空池 → 成功但不伪造标的（与 event ingest 同款契约）
2. 逐标的/逐链**隔离失败**（单只坏不拖垮整批）
3. 全部失败 → success=False（不得包装成成功）
4. 行形态兼容：dict 与领域模型 MinuteKline **都要能落库**（踩过的坑，回归锁）
5. Job 协议契约：name 必须等于 scheduler_tasks.command
"""
import asyncio
import importlib

import pytest

MODULE = 'application.jobs.refresh_jobs'


def _mod():
    return importlib.import_module(MODULE)


def _run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------- MinuteKlineSyncJob

class _UniverseRepo:
    def __init__(self, symbols):
        self._symbols = symbols

    def default_universe(self, limit=200):
        return list(self._symbols)


class _Manager:
    """按 symbol 返回预设结果；rows 形态可指定 dict 或对象"""

    def __init__(self, rows_by_symbol):
        self._rows = rows_by_symbol
        self.calls = []

    def get_minute_klines(self, symbol, period='5m', limit=240, **kw):
        self.calls.append(symbol)
        r = self._rows.get(symbol)
        if isinstance(r, Exception):
            raise r
        if r is None:
            return {'success': False, 'error': f'{symbol} 无数据'}
        return {'success': True, 'source': 'stub', 'data': {'data': r}}


class _MinuteRepo:
    def __init__(self, ok=True):
        self.saved = []
        self._ok = ok

    def save_minute_klines(self, models):
        self.saved.extend(models)
        return self._ok


def _bar(symbol='600150', dt='2026-09-11 09:31', as_dict=True):
    from domain.models.market_data import MinuteKline
    if as_dict:
        return {'symbol': symbol, 'trade_datetime': dt, 'open': 1.0, 'high': 2.0, 'low': 0.5, 'close': 1.5, 'volume': 100.0, 'amount': 200.0}
    return MinuteKline(symbol=symbol, trade_datetime=dt, open=1.0, high=2.0, low=0.5, close=1.5, volume=100.0, amount=200.0)


def test_empty_universe_succeeds_without_fabricating_symbols():
    """空池：成功但明确说明「未采集，不伪造标的」，且不调用任何取数"""
    m = _mod()
    mgr = _Manager({})
    job = m.MinuteKlineSyncJob(mgr, _MinuteRepo(), _UniverseRepo([]))
    res = job._run({})
    assert res['success'] is True
    assert res['synced_symbols'] == 0 and res['saved_bars'] == 0
    assert '不伪造' in res['note']
    assert mgr.calls == [], '空池不应发起取数'


def test_params_symbols_takes_priority_over_universe():
    m = _mod()
    mgr = _Manager({'600150': [_bar()]})
    job = m.MinuteKlineSyncJob(mgr, _MinuteRepo(), _UniverseRepo(['999999']))
    res = job._run({'symbols': '600150'})
    assert res['universe_source'] == 'params.symbols'
    assert mgr.calls == ['600150'], '显式指定时不得回落到 default_universe'


@pytest.mark.parametrize('as_dict', [True, False])
def test_row_shape_compat_dict_and_domain_model(as_dict):
    """**回归锁**：行既可能是 dict 也可能是领域模型 MinuteKline —— 两种都必须落库成功
    （此前只按 dict 处理，遇领域模型抛 AttributeError 导致全批失败）"""
    m = _mod()
    mgr = _Manager({'600150': [_bar(as_dict=as_dict)]})
    repo = _MinuteRepo()
    job = m.MinuteKlineSyncJob(mgr, repo, _UniverseRepo([]))
    res = job._run({'symbols': '600150'})
    assert res['success'] is True and res['synced_symbols'] == 1
    assert len(repo.saved) == 1, '领域模型形态的行也必须能落库'


def test_per_symbol_isolation_one_bad_does_not_kill_batch():
    """逐标的隔离：一只抛异常，其余照常同步"""
    m = _mod()
    mgr = _Manager({
        '600150': [_bar('600150')],
        '000425': RuntimeError('boom'),
        '000807': [_bar('000807')],
    })
    repo = _MinuteRepo()
    job = m.MinuteKlineSyncJob(mgr, repo, _UniverseRepo([]))
    res = job._run({'symbols': '600150,000425,000807'})
    assert res['success'] is True
    assert res['synced_symbols'] == 2
    assert '000425' in res['failures'] and 'boom' in res['failures']['000425']


def test_all_failed_returns_success_false_with_error():
    """全部失败必须 success=False（否则调度器永远全绿）"""
    m = _mod()
    mgr = _Manager({'600150': None, '000425': None})
    job = m.MinuteKlineSyncJob(mgr, _MinuteRepo(), _UniverseRepo([]))
    res = job._run({'symbols': '600150,000425'})
    assert res['success'] is False
    assert res['error'] and '全部' in res['error']


def test_save_failure_counted_as_failure():
    """落库返回 False 必须计入 failures，不得当作已落库"""
    m = _mod()
    mgr = _Manager({'600150': [_bar()]})
    job = m.MinuteKlineSyncJob(mgr, _MinuteRepo(ok=False), _UniverseRepo([]))
    res = job._run({'symbols': '600150'})
    assert res['success'] is False
    assert '600150' in res['failures'] and '落库' in res['failures']['600150']


def test_minute_job_contract_name_matches_scheduler_command():
    """Job.name 必须等于 scheduler_tasks.command（否则调度 Unknown command）"""
    m = _mod()
    job = m.MinuteKlineSyncJob(_Manager({}), _MinuteRepo(), _UniverseRepo([]))
    assert job.name == 'minute_kline_sync'
    assert job.description and isinstance(job.timeout_seconds, int)


# ---------------------------------------------------------------- IndustryChainRefreshJob

class _ChainService:
    def __init__(self, chains, build_results):
        self._chains = chains
        self._build = build_results

    def list_chains(self):
        return {'success': True, 'data': {'chains': [{'name': n} for n in self._chains]}}

    def build_chain(self, name, persist=True):
        r = self._build.get(name)
        if isinstance(r, Exception):
            raise r
        return r if r is not None else {'success': True, 'data': {'member_count': 1}}


def test_chain_refresh_isolates_failures():
    m = _mod()
    svc = _ChainService(['玻纤', '造船', '电力'], {
        '玻纤': {'success': True, 'data': {'member_count': 10}},
        '造船': RuntimeError('boom'),
        '电力': {'success': True, 'data': {'member_count': 12}},
    })
    res = m.IndustryChainRefreshJob(svc)._run({})
    assert res['success'] is True and res['refreshed_count'] == 2
    assert '造船' in res['failures']


def test_chain_refresh_all_failed_is_failure():
    m = _mod()
    svc = _ChainService(['玻纤'], {'玻纤': {'success': False, 'error': 'x'}})
    res = m.IndustryChainRefreshJob(svc)._run({})
    assert res['success'] is False and res['error']


def test_chain_refresh_empty_listing_is_failure_not_silent_success():
    """清单为空 → 必须失败（不得静默当作『刷新了 0 条』成功）"""
    m = _mod()
    res = m.IndustryChainRefreshJob(_ChainService([], {}))._run({})
    assert res['success'] is False
    assert '无可用产业链' in str(res['error'])


def test_chain_job_contract_name():
    m = _mod()
    job = m.IndustryChainRefreshJob(_ChainService([], {}))
    assert job.name == 'industry_chain_refresh'


# ---------------------------------------------------------------- JobResult 契约

def test_execute_maps_internal_failure_to_jobresult_fail():
    """execute 包装：内部 success=False 不得被包装成任务成功（静默失败教训）"""
    m = _mod()
    job = m.MinuteKlineSyncJob(_Manager({'600150': None}), _MinuteRepo(), _UniverseRepo([]))
    result = _run(job.execute({'symbols': '600150'}))
    assert getattr(result, 'success', None) is False, '内部失败必须映射为 JobResult.fail'


def test_execute_maps_success():
    m = _mod()
    job = m.MinuteKlineSyncJob(_Manager({'600150': [_bar()]}), _MinuteRepo(), _UniverseRepo([]))
    result = _run(job.execute({'symbols': '600150'}))
    assert getattr(result, 'success', None) is True
