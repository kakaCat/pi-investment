"""「空结果≠故障」契约测试（manager._try_providers / get_event_symbol_events）

2026-09-11 契约对齐（P9/P10）：
  provider 契约（providers/minute_kline/base.py）规定「成功返回 List（可为空列表=该源无数据），
  失败返回 None 且写 last_error」，但 manager 的判据是 result is not None and _is_valid(result)，
  而 _is_valid([]) == False —— 空结果被当成失败，形成两个真实缺陷：
    P9  get_event_symbol_events 的 empty_sources.append 永远不可达（死代码）→ 三源
        「健康地无数据」却被判 all providers failed → 无公告日定时任务误报红；
    P10 minute provider 把「无此标的/无此数据」写成 last_error+None → 计真故障 →
        累计 consecutive_failures → 熔断该源（本该只是「这个查询它没有」）。

本文件锁住修复后的三态语义，**不改动「存在硬失败时」的 success 语义**：
  全源健康空（零硬失败）→ success=True + empty=True + empty_sources=[...]
  一源硬失败 + 一源健康空 → 仍 success=False，且 empty_sources 如实
  空结果不计 failure / consecutive_failures（不影响熔断），只单独计 empty
  空结果的诊断 last_note 必须透到 provider_errors 文本里（诊断信息不得丢失）
"""
import pytest

from adapters.outbound.datasources.manager import DataProviderManager


class FakeProvider:
    """最小 provider：可编程的 (返回值, last_error, last_note)"""

    def __init__(self, name, *, result=None, last_error=None, last_note=''):
        self.name = name
        self._result = result
        self.last_error = last_error
        self.last_note = last_note
        self.calls = 0

    def fetch_symbol_events(self, symbols=None):
        self.calls += 1
        return self._result

    def get_minute_klines(self, symbol, period, start_date=None, end_date=None, limit=240):
        self.calls += 1
        return self._result

    def get_quote(self, symbol):
        self.calls += 1
        return self._result


class BoomProvider:
    name = 'boom'
    last_error = None
    last_note = ''

    def fetch_symbol_events(self, symbols=None):
        raise ConnectionError('upstream reset')


def _manager(providers):
    """轻量 manager：不跑 __init__（避免构造真实 provider 链/仓储），只装配被测路径所需状态"""
    m = DataProviderManager.__new__(DataProviderManager)
    m.provider_timeout_seconds = 5
    m._failure_threshold = 3
    m._recovery_window = 5
    m._circuit_breaker_threshold = 10
    m._circuit_breaker_duration = 300
    m.provider_stats = {
        p.name: {'success': 0, 'failure': 0, 'empty': 0,
                 'consecutive_failures': 0, 'last_attempt_time': 0}
        for p in providers
    }
    m._circuit_breakers = {p.name: _AlwaysClosedCB() for p in providers}
    return m


class _AlwaysClosedCB:
    def should_allow_call(self):
        return True

    def get_state(self):
        return {'state': 'closed'}

    def is_open(self):
        return False

    def reset(self):
        return None


# ─────────────────────────── _try_providers 三态 ───────────────────────────

def test_全源健康空返回成功且empty为真():
    """(a) 零硬失败 + 全部源返回空列表 → success=True + empty=True + data=[]"""
    providers = [FakeProvider('p1', result=[], last_note='p1 无该查询数据'),
                 FakeProvider('p2', result=[])]
    m = _manager(providers)
    res = m._try_providers(providers, 'fetch_symbol_events', ['600176'])
    assert res['success'] is True
    assert res['empty'] is True
    assert res['data'] == []
    assert res['source'] is None
    assert sorted(res['empty_sources']) == ['p1', 'p2']
    assert 'error' not in res, '健康空不是失败，不得带 error 文本'


def test_空源之后仍继续尝试后续源():
    """空结果不是「结论」，后续源覆盖不同数据 → 必须继续尝试并返回其数据"""
    p1 = FakeProvider('p1', result=[])
    p2 = FakeProvider('p2', result=[{'title': 'x'}])
    m = _manager([p1, p2])
    res = m._try_providers([p1, p2], 'fetch_symbol_events', None)
    assert res['success'] is True and res['data'] == [{'title': 'x'}]
    assert res['source'] == 'p2'
    assert res['empty_sources'] == ['p1'], '被跳过的空源也要透出（成功路径）'
    assert res['empty'] is False
    assert p2.calls == 1, '空源不得终止降级链'


def test_一源硬失败一源健康空仍显式失败():
    """(b) blast radius 护栏：有硬失败且无数据 → success 语义不变（False）"""
    p1 = FakeProvider('p1', result=None, last_error='HTTP 500')
    p2 = FakeProvider('p2', result=[], last_note='p2 无该查询数据')
    m = _manager([p1, p2])
    res = m._try_providers([p1, p2], 'fetch_symbol_events', None)
    assert res['success'] is False
    assert res['empty'] is False
    assert res['error'] == 'All data providers failed'
    assert res['empty_sources'] == ['p2'], '健康空源仍须如实列出'
    assert res['provider_errors']['p1'] == 'HTTP 500'
    assert m.provider_stats['p1']['consecutive_failures'] == 1, '真故障照常计数'
    assert m.provider_stats['p2']['failure'] == 0, '空源不得计故障'


def test_异常型失败同样维持显式失败():
    p1 = BoomProvider()
    p2 = FakeProvider('p2', result=[])
    m = _manager([p1, p2])
    res = m._try_providers([p1, p2], 'fetch_symbol_events', None)
    assert res['success'] is False and res['empty'] is False
    assert 'ConnectionError' in res['provider_errors']['boom']
    assert res['empty_sources'] == ['p2']


def test_混合空源与数据源时不带hard_failure判定():
    """只有「所有源都空且零硬失败」才翻 success；有数据时照常成功"""
    p1 = FakeProvider('p1', result=[])
    p2 = FakeProvider('p2', result=None, last_error='超时')
    p3 = FakeProvider('p3', result=[{'a': 1}])
    m = _manager([p1, p2, p3])
    res = m._try_providers([p1, p2, p3], 'fetch_symbol_events', None)
    assert res['success'] is True and res['data'] == [{'a': 1}]
    assert res['empty'] is False and res['empty_sources'] == ['p1']


# ────────────────────── 空结果不得污染健康分/熔断 ──────────────────────

def test_空结果不计failure与连续失败只计empty():
    """(c) 核心护栏：空结果 = 健康 → failure/consecutive_failures 保持 0，empty 单独计数"""
    p1 = FakeProvider('p1', result=[])
    m = _manager([p1])
    for _ in range(12):          # 超过熔断阈值 10，若误计失败就该熔断
        m._try_providers([p1], 'fetch_symbol_events', None)
    stats = m.provider_stats['p1']
    assert stats['failure'] == 0
    assert stats['consecutive_failures'] == 0, '空结果绝不能累计连续失败（P10 的核心）'
    assert stats['empty'] == 12
    assert stats['success'] == 0, '空结果不是「成功取到数据」，不得计入 success'


def test_空结果不重置既有连续失败计数():
    """空结果既不算失败也不算成功：不重置已有计数（否则一次空查询就洗白历史故障）"""
    p1 = FakeProvider('p1', result=None, last_error='boom')
    m = _manager([p1])
    m._try_providers([p1], 'fetch_symbol_events', None)
    assert m.provider_stats['p1']['consecutive_failures'] == 1
    p1._result, p1.last_error = [], None
    m._try_providers([p1], 'fetch_symbol_events', None)
    assert m.provider_stats['p1']['consecutive_failures'] == 1, '空结果不得洗白连续失败'
    assert m.provider_stats['p1']['failure'] == 1


# ───────────────────────── last_note 诊断不丢 ─────────────────────────

def test_last_note必须出现在provider_errors文本里():
    """(d) 空结果不计故障，但**原因必须可见**——否则排障无从下手"""
    p1 = FakeProvider('p1', result=[], last_note='腾讯无 600150 的 m5 数据（代码不存在或该时段无交易）')
    p2 = FakeProvider('p2', result=[], last_note='')
    m = _manager([p1, p2])
    res = m._try_providers([p1, p2], 'fetch_symbol_events', None)
    assert '腾讯无 600150 的 m5 数据' in res['provider_errors']['p1']
    assert '非故障' in res['provider_errors']['p1']
    assert 'p2' in res['provider_errors'] and '非故障' in res['provider_errors']['p2']


def test_无last_note时仍给出可读的空结果说明():
    p1 = FakeProvider('p1', result=[])
    m = _manager([p1])
    res = m._try_providers([p1], 'fetch_symbol_events', None)
    assert res['provider_errors']['p1'] == '返回空数据（非故障：该查询无数据，不计入健康分）'


# ──────────────── get_event_symbol_events（P9 死代码路径） ────────────────

def _event_manager(providers):
    m = _manager(providers)
    m.event_symbol_providers = list(providers)
    m.minute_kline_providers = []
    m.industry_chain_concept_providers = []
    return m


def test_P9全源健康空必须成功且empty而不是报失败():
    """P9 回归锁：三源「健康地无数据」不得报 All event symbol providers failed

    修复前 empty_sources.append 在 success=False 分支之后，永远不可达（死代码）。
    """
    providers = [FakeProvider('eastmoney_notice', result=[], last_note='东财无公告'),
                 FakeProvider('cninfo_disclosure', result=[], last_note='巨潮无披露'),
                 FakeProvider('akshare_unlock', result=[], last_note='无解禁')]
    m = _event_manager(providers)
    res = m.get_event_symbol_events(['600176'], include_fallback=False)
    assert res['success'] is True, '全源健康空 = 成功（P9 修复点）'
    assert res['empty'] is True
    assert res['data'] == []
    assert res['source'] is None
    assert sorted(res['empty_sources']) == ['akshare_unlock', 'cninfo_disclosure', 'eastmoney_notice']
    assert res['degraded'] is False, '健康无数据不是降级（修复前 degraded=bool(errors) 会误标降级）'
    assert '东财无公告' in res['provider_errors']['eastmoney_notice'], '诊断不丢'


def test_P9一源硬失败时仍报失败():
    providers = [FakeProvider('eastmoney_notice', result=None, last_error='HTTP 503'),
                 FakeProvider('cninfo_disclosure', result=[], last_note='巨潮无披露'),
                 FakeProvider('akshare_unlock', result=[], last_note='无解禁')]
    m = _event_manager(providers)
    res = m.get_event_symbol_events(['600176'], include_fallback=False)
    assert res['success'] is False
    assert res['error'] == 'All event symbol providers failed'
    assert res['provider_errors']['eastmoney_notice'] == 'HTTP 503'
    assert sorted(res['empty_sources']) == ['akshare_unlock', 'cninfo_disclosure']
    assert res['degraded'] is True


def test_P9有数据时照常成功且列出空源():
    providers = [FakeProvider('eastmoney_notice', result=[{'title': '公告'}]),
                 FakeProvider('cninfo_disclosure', result=[], last_note='巨潮无披露')]
    m = _event_manager(providers)
    res = m.get_event_symbol_events(['600176'], include_fallback=False)
    assert res['success'] is True and res['empty'] is False
    assert res['source'] == 'eastmoney_notice', '聚合语义：有数据的源进 source'
    assert res['empty_sources'] == ['cninfo_disclosure']


def test_include_fallback为false时排除DB兜底源():
    class FallbackProvider(FakeProvider):
        is_fallback = True

    live = FakeProvider('live', result=[{'title': 't'}])
    db = FallbackProvider('database_event', result=[{'title': 'old'}])
    m = _event_manager([live, db])
    res = m.get_event_symbol_events(['600176'], include_fallback=False)
    assert db.calls == 0, 'ingest 路径必须排除 DB 兜底源（避免自己喂自己）'
    assert [r['title'] for r in res['data']] == ['t']


# ───────────── 形状判定：非空但无效的结果不得被当成「健康空」 ─────────────

def test_非空但无效的结果不算健康空():
    """校验未通过的「非空但无效」结果：既不是成功也不是健康空 → 维持显式失败

    _is_valid 对「首个元素带 falsy source」的列表判无效（上游返回了脏/无出处数据）。
    若把它与空结果一同当作「健康空」，三源全返回脏数据时会被伪装成
    success=True+empty=True —— 比原缺陷更危险（把数据问题说成"确实没有"）。
    """
    class Sourceless:
        source = ''

    p1 = FakeProvider('p1', result=[Sourceless()])
    m = _manager([p1])
    res = m._try_providers([p1], 'get_quote', '600176')
    assert res['success'] is False, '不能把无效数据当成功'
    assert res['empty'] is False, '也不属于「形状有效的空结果」'
    assert res['empty_sources'] == []
    assert m.provider_stats['p1']['failure'] == 0, '无效数据同样不计故障（不拖垮健康分）'
    assert m.provider_stats['p1']['empty'] == 1


@pytest.mark.parametrize('shape', [[], (), {}])
def test_各种空容器都识别为健康空(shape):
    p1 = FakeProvider('p1', result=shape)
    m = _manager([p1])
    res = m._try_providers([p1], 'fetch_symbol_events', None)
    assert res['success'] is True and res['empty'] is True
