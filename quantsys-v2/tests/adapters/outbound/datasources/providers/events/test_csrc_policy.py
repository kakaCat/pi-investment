"""证监会政策 provider 契约测试（fake session，不触网）

锁住的契约：
  导航链接（"English"）必须被过滤（实测：页面导航也带 <span class="date">，正则会把它当条目）
  发布时间窗口过滤；HTTP 错误显式失败；窗口内确实无新政策时返回 []（不是故障）
"""
from datetime import date, timedelta

import pytest

from adapters.outbound.datasources.providers.events import csrc_policy as mod
from adapters.outbound.datasources.providers.events.csrc_policy import CsrcPolicyProvider

from _fakes import FakeResponse, FakeSession


def _html(*items):
    body = ''.join(
        f'<li><a href="{href}" target="_blank" >\n        {title}</a>\n'
        f'        <span class="date">{published}</span></li>'
        for href, title, published in items
    )
    return f'<html><body><ul>{body}</ul></body></html>'


TODAY = date.today()


def test_解析真实结构的条目(monkeypatch):
    provider = CsrcPolicyProvider(timeout=1)
    html = _html(('/csrc/c100028/c7634324/content.shtml',
                  '中国证监会等八部门联合印发《综合整治非法跨境证券期货基金经营活动实施方案》',
                  TODAY.strftime('%Y-%m-%d')))
    monkeypatch.setattr(mod, '_session', lambda: FakeSession(FakeResponse({}, text=html)))
    rows = provider.fetch_policy()
    assert len(rows) == 1
    row = rows[0]
    assert row['title'].startswith('中国证监会等八部门')
    assert row['effective_date'] == TODAY.strftime('%Y-%m-%d')
    assert row['url'] == 'http://www.csrc.gov.cn/csrc/c100028/c7634324/content.shtml'
    assert row['type'] == 'policy' and row['authority'] == 85


def test_导航链接必须被过滤(monkeypatch):
    """实测踩坑：正则会把 "English" 当成条目（入库标题是 'English\r\n'）。"""
    provider = CsrcPolicyProvider(timeout=1)
    html = _html(('/english/index.shtml', 'English', TODAY.strftime('%Y-%m-%d')),
                 ('/csrc/c100028/c7634324/content.shtml',
                  '中国证监会发布《衍生品交易监督管理办法（试行）》',
                  TODAY.strftime('%Y-%m-%d')))
    monkeypatch.setattr(mod, '_session', lambda: FakeSession(FakeResponse({}, text=html)))
    rows = provider.fetch_policy()
    assert [r['title'] for r in rows] == ['中国证监会发布《衍生品交易监督管理办法（试行）》']


def test_超出窗口的旧政策被过滤(monkeypatch):
    provider = CsrcPolicyProvider(timeout=1)
    html = _html(('/csrc/c100028/c1/content.shtml', '中国证监会印发某年度立法工作计划',
                  (TODAY - timedelta(days=400)).strftime('%Y-%m-%d')))
    monkeypatch.setattr(mod, '_session', lambda: FakeSession(FakeResponse({}, text=html)))
    assert provider.fetch_policy() == []


def test_日期非法或非csrc链接的条目被丢弃(monkeypatch):
    provider = CsrcPolicyProvider(timeout=1)
    html = _html(('/csrc/c100028/c1/content.shtml', '中国证监会发布某监管规则', '2026/01/01'),
                 ('/other/c1.shtml', '中国证监会发布某监管规则', TODAY.strftime('%Y-%m-%d')))
    monkeypatch.setattr(mod, '_session', lambda: FakeSession(FakeResponse({}, text=html)))
    assert provider.fetch_policy() == []


def test_窗口内无新政策返回空列表而不是故障(monkeypatch):
    provider = CsrcPolicyProvider(timeout=1)
    monkeypatch.setattr(mod, '_session', lambda: FakeSession(FakeResponse({}, text=_html())))
    assert provider.fetch_policy() == []
    assert provider.last_error is None


def test_HTTP错误显式失败(monkeypatch):
    provider = CsrcPolicyProvider(timeout=1)
    monkeypatch.setattr(mod, '_session', lambda: FakeSession(FakeResponse({}, status=503)))
    assert provider.fetch_policy() is None
    assert 'HTTP 503' in provider.last_error


def test_网络异常显式失败(monkeypatch):
    provider = CsrcPolicyProvider(timeout=1)

    class _Boom:
        def get(self, *a, **kw):
            raise ConnectionError('reset by peer')

    monkeypatch.setattr(mod, '_session', lambda: _Boom())
    assert provider.fetch_policy() is None and 'ConnectionError' in provider.last_error


def test_不提供个股事件时返回空列表():
    provider = CsrcPolicyProvider(timeout=1)
    assert provider.fetch_symbol_events(['600150']) == [] and provider.last_error is None
