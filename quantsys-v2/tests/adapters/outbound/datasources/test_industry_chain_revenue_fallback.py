"""主营构成**两段式降级链**回归锁（2026-09-11，w-62dd5259）

链路：东财 F10（带营收占比＝归位硬证据）→ 同花顺 F10（产品构成文本）→ DB 缓存兜底。
manager.get_industry_chain_revenue 分两段调用的原因见其 docstring（动态健康分排序会让
"零失败"的同花顺反超东财，白丢带占比的硬证据）——**代价是必须显式表达"权威源没有数据时
继续降级"**：单源调用下 _try_providers 遇到「健康无数据」会返回 success=True + empty=True
（这是本轮四态契约的设计），若判据只看 success 就会**短路**掉后面两段。

本文件锁的就是这条安全点：东财没有某标的的主营构成时，同花顺/DB 必须仍被访问。
全部离线：注入桩 session，不触网、不写库。
"""
import pytest

from adapters.outbound.datasources.manager import DataProviderManager
from adapters.outbound.datasources.providers.industry_chain import eastmoney_revenue as mod
from adapters.outbound.datasources.providers.industry_chain.eastmoney_revenue import (
    EastmoneyRevenueProvider, ThsRevenueProvider,
)


# ───────────────────────────────── 桩 ─────────────────────────────────

class StubResponse:
    def __init__(self, payload=None, *, status=200, content=b''):
        self._payload = payload
        self.status_code = status
        self.content = content

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f'HTTP {self.status_code}')


class StubSession:
    """按调用顺序返回预设响应并记录调用次数（不触网）"""

    def __init__(self, responses):
        self.responses = list(responses) if isinstance(responses, (list, tuple)) else [responses]
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append({'url': url, **kwargs})
        if not self.responses:
            raise AssertionError('StubSession 调用次数超出预设（测试未覆盖该路径）')
        return self.responses.pop(0)


class StubCB:
    def should_allow_call(self):
        return True

    def get_state(self):
        return {'state': 'closed'}

    def is_open(self):
        return False

    def reset(self):
        return None


class StubDbRevenue:
    """DB 兜底源替身（真实 DB provider 需要仓储，这里只验证链路的第二段会被访问）"""
    last_error = None
    last_note = ''

    def __init__(self, rows):
        self.name = 'database_chain'
        self._rows = rows
        self.calls = 0

    def get_revenue_exposure(self, symbol):
        self.calls += 1
        return list(self._rows)


# 上游原始行（列名必须是东财真实列名，provider 负责映射成行契约 C）
EM_RAW_ROW = {'SECUCODE': '600176.SH', 'SECURITY_CODE': '600176',
              'REPORT_DATE': '2026-06-30 00:00:00', 'MAINOP_TYPE': '2',
              'ITEM_NAME': '玻纤及其制品相关', 'MAIN_BUSINESS_INCOME': 1.0,
              'MBI_RATIO': 0.973241}
THS_HTML = ('<span class="hltip f12">产品名称：</span><p>电子布、粗纱及制品</p>')
DB_ROW = {'symbol': '600176', 'item': '玻璃纤维', 'ratio': None, 'source': 'database_chain',
          'stale': True}


def _payload(rows):
    return {'zygcfx': rows, 'zyfw': [], 'jyps': []}


def _em_ok():
    return StubSession(StubResponse(_payload([EM_RAW_ROW])))


def _ths_ok():
    return StubResponse(content=THS_HTML.encode('gbk'))


def _manager(eastmoney_session, ths_session, db_rows=()):
    em = EastmoneyRevenueProvider(session=eastmoney_session)
    ths = ThsRevenueProvider(session=ths_session)
    db = StubDbRevenue(db_rows)

    m = DataProviderManager.__new__(DataProviderManager)
    m.provider_timeout_seconds = 5
    m._failure_threshold = 3
    m._recovery_window = 5
    m._circuit_breaker_threshold = 10
    m._circuit_breaker_duration = 300
    m.eastmoney_revenue_provider = em
    m.ths_revenue_provider = ths
    m.database_chain_provider = db
    provs = [em, ths, db]
    m.provider_stats = {p.name: {'success': 0, 'failure': 0, 'empty': 0,
                                 'consecutive_failures': 0, 'last_attempt_time': 0}
                        for p in provs}
    m._circuit_breakers = {p.name: StubCB() for p in provs}
    return m, em, ths, db, ths_session


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    monkeypatch.setattr(mod.time, 'sleep', lambda *_: None)


# ───────────────────────── 权威源优先（不回退） ─────────────────────────

def test_东财有数据时不调用同花顺():
    """(ii) 权威通道优先：东财取到数据 → fallback 段**一次都不得被访问**。

    断言打在"上游 HTTP 调用次数"上（比 mock 方法计数更硬：连请求都不该发出去）。
    """
    em_sess, ths_sess = _em_ok(), StubSession([])
    m, em, ths, db, _ = _manager(em_sess, ths_sess)
    res = m.get_industry_chain_revenue('600176')
    assert res['success'] is True and res['source'] == 'eastmoney_revenue'
    assert res['empty'] is False
    assert res['data'][0]['ratio'] == pytest.approx(0.973241), 'MBI_RATIO 映射必须保住（归位硬证据）'
    assert res['data'][0]['classification'] == '按产品分类'
    assert res['attempted_sources'] == ['eastmoney_revenue'], '只有东财被尝试'
    assert ths_sess.calls == [], '同花顺不得被访问（权威源已给出硬证据）'
    assert db.calls == 0, 'DB 兜底不得被访问'


# ───────────────────── 核心安全点：健康空必须继续降级 ─────────────────────

def test_东财健康空时仍降级到同花顺():
    """(i) 【主目标】东财 200 但 zygcfx 为空 = 健康无数据 → **必须**继续降级到同花顺。

    这是 provider 改四态契约后最容易踩的坑：单源 _try_providers 会返回
    success=True + empty=True，判据若只看 success 就会短路掉同花顺与 DB。
    """
    m, em, ths, db, ths_sess = _manager(StubSession(StubResponse(_payload([]))), StubSession(_ths_ok()))
    res = m.get_industry_chain_revenue('600176')
    assert res['success'] is True, '同花顺拿到了数据，链路终点是成功的'
    assert res['source'] == 'ths_revenue', '权威源无数据时必须降级到文本通道'
    assert res['data'], '同花顺行不得为空'
    assert em.last_error is None, '东财是健康空，不是故障'
    assert res['attempted_sources'] == ['eastmoney_revenue', 'ths_revenue']
    assert ths_sess.calls, '同花顺必须真的被访问（HTTP 请求）'
    assert '非故障' in res['provider_errors']['eastmoney_revenue'], '空结果说明必须透出'
    assert 'zygcfx' in res['provider_errors']['eastmoney_revenue']


def test_东财与同花顺都健康空时降级到DB兜底():
    m, em, ths, db, _ = _manager(
        StubSession(StubResponse(_payload([]))),
        StubSession(StubResponse(content='<html>改版了</html>'.encode('gbk'))),
        db_rows=[DB_ROW],
    )
    res = m.get_industry_chain_revenue('600176')
    assert res['source'] == 'database_chain' and res['data'] == [DB_ROW]
    assert db.calls == 1, '第三级兜底必须被访问'
    assert 'eastmoney_revenue' in res['attempted_sources']
    assert 'ths_revenue' in res['attempted_sources']


def test_全源健康空时是成功空结果而不是报失败():
    """三源都"好好回答了没有数据"→ success=True + empty=True（与 P9 契约一致）。

    同时锁**两段的合并语义**：attempted_sources 必须拼接两段、provider_errors 必须
    保留 primary 段的空因诊断（否则"东财为什么没数据"在结果里彻底消失）。
    """
    m, em, ths, db, _ = _manager(StubSession(StubResponse(_payload([]))),
                                 StubSession(StubResponse(content=('<span class="hltip f12">'
                                                                  '产品名称：</span><p>甲</p>').encode('gbk'))),
                                 db_rows=[])
    res = m.get_industry_chain_revenue('600176')
    assert res['success'] is True and res['empty'] is True
    assert res['data'] == [] and res['source'] is None
    assert not res.get('error'), '健康空不是失败，不得带 error 文本'
    assert res['attempted_sources'] == ['eastmoney_revenue', 'ths_revenue', 'database_chain'], \
        '两段的 attempted_sources 必须拼接'
    primary_reason = res['provider_errors']['eastmoney_revenue']
    assert '非故障' in primary_reason and 'zygcfx' in primary_reason, \
        'primary 段的空因诊断不得在合并时丢失'
    assert 'ths_revenue' in res['provider_errors']


# ───────────────────── 真故障照样降级，且计数语义正确 ─────────────────────

def test_东财真故障时降级并计故障():
    """(iii) 硬失败（None + last_error）→ 仍走 fallback，既有行为不许变。"""
    m, em, ths, db, _ = _manager(
        StubSession([StubResponse(status=502), StubResponse(status=502), StubResponse(status=502)]),
        StubSession(_ths_ok()),
    )
    res = m.get_industry_chain_revenue('600176')
    assert res['source'] == 'ths_revenue'
    assert '取数失败' in res['provider_errors']['eastmoney_revenue']
    assert m.provider_stats['eastmoney_revenue']['failure'] == 1
    assert m.provider_stats['eastmoney_revenue']['consecutive_failures'] == 1


def test_健康空不得计入故障也不累计连续失败():
    """P10 护栏：连打 12 次"东财没有这只票的主营构成"不得把东财熔断掉。"""
    m, em, ths, db, _ = _manager(StubSession([StubResponse(_payload([]))] * 40),
                              StubSession([_ths_ok()] * 40))
    for _ in range(12):
        m.get_industry_chain_revenue('600176')
    stats = m.provider_stats['eastmoney_revenue']
    assert stats['failure'] == 0 and stats['consecutive_failures'] == 0
    assert stats['empty'] == 12
