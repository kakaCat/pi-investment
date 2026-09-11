"""主营构成 provider 的**四态契约**回归锁（2026-09-11，w-62dd5259）

与既有 test_eastmoney_revenue.py 的分工：那份锁"字段映射/口径/真故障"，本份专门锁
**"健康无数据"与"真故障"的形状可分**——本轮全仓统一的契约是：

    []   + last_error=None + last_note=<诊断>  → 健康无数据（不计故障、不影响熔断）
    None + last_error=<原因>                    → 真故障
    None + last_error=None                      → ⚠️ 禁止（两头不靠）

以及**长生命周期单例的状态不跨调用泄漏**：上一次的 last_note 不得挂到下一次的真故障上，
上一次的 last_error 也不得残留到下一次的健康空结果上。

全部离线：FakeSession 注入，不触网、不写库。
"""
import pytest

from adapters.outbound.datasources.providers.industry_chain import eastmoney_revenue as mod
from adapters.outbound.datasources.providers.industry_chain.eastmoney_revenue import (
    EastmoneyRevenueProvider, ThsRevenueProvider,
)

from _fakes import FakeResponse, FakeSession


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    """东财失败重试之间有 sleep(0.4)：去掉，测试保持毫秒级。"""
    monkeypatch.setattr(mod.time, 'sleep', lambda *_: None)


def _em(responses):
    return EastmoneyRevenueProvider(session=FakeSession(responses))


def _ths(responses):
    return ThsRevenueProvider(session=FakeSession(responses))


def _payload(rows=None, **extra):
    payload = {'zygcfx': rows if rows is not None else [], 'zyfw': [], 'jyps': []}
    payload.update(extra)
    return payload


# ─────────────────── 东财：健康无数据的三种上游形状 ───────────────────

def test_zygcfx为空时健康空而不是故障():
    provider = _em(FakeResponse(_payload([])))
    assert provider.get_revenue_exposure('600176') == []
    assert provider.last_error is None, '空结果不是故障：last_error 必须保持空'
    assert '为空' in provider.last_note and '600176' in provider.last_note


def test_zygcfx字段缺失时也判健康空且说明可辨():
    """上游换了接口少给字段：仍是"这只票没有主营构成"（健康空），但说明必须写明是字段缺失。"""
    provider = _em(FakeResponse({'zyfw': [], 'jyps': []}))
    assert provider.get_revenue_exposure('600176') == []
    assert provider.last_error is None
    assert '字段缺失' in provider.last_note


def test_无经营范围文本时返回None并写last_note():
    """business_scope 返回 str/None：None 时靠 last_error 是否为空分辨故障与无数据。"""
    provider = _em(FakeResponse(_payload([], zyfw=[])))
    assert provider.business_scope('600176') is None
    assert provider.last_error is None
    assert '经营范围' in provider.last_note


# ─────────────────── 状态不得跨调用泄漏（长生命周期单例） ───────────────────

def test_上一次的无数据说明不得残留到下一次真故障():
    provider = _em(FakeResponse(_payload([])))
    provider.get_revenue_exposure('600176')
    assert provider.last_note, '第一次是健康空，应有说明'

    provider._session = FakeSession([FakeResponse(status=502), FakeResponse(status=502),
                                     FakeResponse(status=502)])
    assert provider.get_revenue_exposure('600176') is None
    assert provider.last_error and '取数失败' in provider.last_error
    assert provider.last_note == '', '真故障时不得残留上一次的"无数据"说明（会误导排障）'


def test_上一次的故障不得残留到下一次健康空():
    provider = _em([FakeResponse(status=502), FakeResponse(status=502), FakeResponse(status=502)])
    assert provider.get_revenue_exposure('600176') is None
    assert provider.last_error

    provider._session = FakeSession(FakeResponse(_payload([])))
    assert provider.get_revenue_exposure('600176') == []
    assert provider.last_error is None, '健康空时必须清掉上一次的故障文本'
    assert provider.last_note


def test_映射失败是真故障不是无数据(monkeypatch):
    """入参无法映射市场前缀 = fail-loud 真故障（None + last_error），不得伪装成"没有数据"。"""
    session = FakeSession(FakeResponse(_payload()))
    provider = EastmoneyRevenueProvider(session=session)
    assert provider.get_revenue_exposure('ABC123') is None
    assert provider.last_error and '市场前缀' in provider.last_error
    assert provider.last_note == ''
    assert session.calls == [], '非法代码不得打上游'


# ─────────────────── 同花顺通道：同口径的四态 ───────────────────

def _ths_response(html):
    return FakeResponse(content=html.encode('gbk'), text='')


def test_同花顺清洗后无可用条目时健康空不是故障():
    """页面字段解析到了，但拆分/清洗后没有可用条目（值全是碎片）→ [] + last_note。"""
    provider = _ths(_ths_response('<span class="hltip f12">产品名称：</span><p>甲、乙</p>'))
    assert provider.get_revenue_exposure('600176') == []
    assert provider.last_error is None
    assert '可用产品构成条目' in provider.last_note


def test_同花顺真故障时last_note必须为空():
    provider = _ths([FakeResponse(status=500), FakeResponse(status=500)])
    assert provider.get_revenue_exposure('600176') is None
    assert provider.last_error and '取数失败' in provider.last_error
    assert provider.last_note == ''


def test_同花顺页面改版是真故障不是无数据():
    provider = _ths(_ths_response('<html>改版了</html>'))
    assert provider.get_revenue_exposure('600176') is None
    assert provider.last_error and '结构变化' in provider.last_error
    assert provider.last_note == ''


def test_同花顺无数据说明不跨调用泄漏():
    provider = _ths(_ths_response('<span class="hltip f12">产品名称：</span><p>甲</p>'))
    assert provider.get_revenue_exposure('600176') == []
    assert provider.last_note

    provider._session = FakeSession([FakeResponse(status=500), FakeResponse(status=500)])
    assert provider.get_revenue_exposure('600176') is None
    assert provider.last_note == '' and provider.last_error
