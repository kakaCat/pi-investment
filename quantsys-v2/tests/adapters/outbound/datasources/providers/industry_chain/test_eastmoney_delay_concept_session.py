"""eastmoney_delay_concept 连接复用回归锁（2026-09-11，w-f436d4ea）

背景：本 provider 原先用模块级 `requests.get`，每次请求新建 TCP 连接。同域的
eastmoney_revenue 已实测「连打数十次后上游/代理开始拒连 → 失败累计触发熔断 →
全线静默降级」，并改用了进程级共享 Session。本测试锁住两通道**连接策略一致**，
同时锁住**行为不变**：仍按请求显式传 proxies（本域经本机代理会返回 rc=102，必须绕过）。

全部离线：_shared_session 被替换为桩，不触网、不写库。
"""
import pytest

from adapters.outbound.datasources.providers.industry_chain import eastmoney_delay_concept as mod
from adapters.outbound.datasources.providers.industry_chain.eastmoney_delay_concept import (
    EastmoneyDelayConceptProvider,
)


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    """退避重试之间的 sleep：去掉，测试保持毫秒级。"""
    monkeypatch.setattr(mod.time, 'sleep', lambda *_: None)


class _Resp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def _install_session(monkeypatch, payloads):
    """把 _shared_session 换成记录调用的桩；payloads 依次返回。"""
    calls = []

    class _Sess:
        def get(self, url, **kw):
            calls.append({'url': url, 'kw': kw})
            return _Resp(payloads[min(len(calls) - 1, len(payloads) - 1)])

    monkeypatch.setattr(mod, '_shared_session', lambda: _Sess())
    return calls


def test_取数走共享session而不是模块级requests(monkeypatch):
    calls = _install_session(monkeypatch, [{'rc': 0, 'data': {'diff': []}}])
    p = EastmoneyDelayConceptProvider()

    p._get({'pn': 1})

    assert len(calls) == 1, '应恰好发一次请求'
    assert calls[0]['url'] == p._URL
    # 源码级断言：确保没有人再把模块级 requests.get 加回来（连接复用一旦被绕过就静默失效）
    src = open(mod.__file__, encoding='utf-8').read()
    assert 'requests.get(' not in src, '不得再有模块级 requests.get（每次新建连接）'
    assert '_shared_session().get(' in src


def test_仍按请求显式绕过代理(monkeypatch):
    """复用连接不得引入环境代理：本域经代理实测返回 rc=102/data=null。"""
    calls = _install_session(monkeypatch, [{'rc': 0, 'data': {'diff': []}}])
    EastmoneyDelayConceptProvider()._get({'pn': 1})

    assert calls[0]['kw']['proxies'] == {'http': None, 'https': None}
    assert calls[0]['kw']['timeout'] == EastmoneyDelayConceptProvider._TIMEOUT


def test_瞬时限流仍会退避重试(monkeypatch):
    """rc=0 但 data 为 null = 瞬时限流，须重试而非判硬失败（既有行为不许被连接复用改掉）。"""
    calls = _install_session(monkeypatch, [
        {'rc': 0, 'data': None},
        {'rc': 0, 'data': {'diff': [{'f12': '600176'}]}},
    ])
    payload = EastmoneyDelayConceptProvider()._get({'pn': 1})

    assert len(calls) == 2, '第一次 data=null 应触发重试'
    assert payload['data'] == {'diff': [{'f12': '600176'}]}


def test_共享session是进程级单例(monkeypatch):
    monkeypatch.setattr(mod, '_SHARED_SESSION', None)
    a = mod._shared_session()
    b = mod._shared_session()
    assert a is b, '必须是进程级单例，否则等于没复用连接'
    assert hasattr(a, 'mount'), '应是 requests.Session（挂了连接池 adapter）'
