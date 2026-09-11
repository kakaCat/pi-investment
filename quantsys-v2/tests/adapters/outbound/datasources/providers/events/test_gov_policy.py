"""国务院/发改委政策 provider 契约测试（fake session / 桩函数，不触网）

锁住的契约（§1.5.2 硬约束 5：失败与空结果严格分离）：
  两个子通道都失败 → 显式失败 + last_error
  一个子通道失败 + 另一个返回空 → **同样必须判为故障**（旧实现会静默返回 []，
  manager 记为"返回空数据（非故障）"，真故障被掩盖）
  两个子通道都成功但都为空 → []（"今天没有新政策"不是故障）
"""
from datetime import date, timedelta

import pytest

from adapters.outbound.datasources.providers.events import gov_policy as mod
from adapters.outbound.datasources.providers.events.gov_policy import (
    GovPolicyProvider, _clean, _in_window,
)

from _fakes import FakeResponse, FakeSession

GOV_JSON = [
    {'TITLE': '市场监督管理所条例', 'SUB_TITLE': '',
     'URL': 'https://www.gov.cn/zhengce/content/202609/content_7080735.htm',
     'DOCRELPUBTIME': date.today().strftime('%Y-%m-%d')},
    {'TITLE': '陈年旧政策', 'SUB_TITLE': '',
     'URL': 'https://www.gov.cn/zhengce/content/202001/content_1.htm',
     'DOCRELPUBTIME': (date.today() - timedelta(days=500)).strftime('%Y-%m-%d')},
]

NDRC_HTML = (
    '<html><body><ul>'
    '<li><a href="./202607/t20260731_1406815.html">'
    '《国家发展改革委关于修改、废止一批规章和行政规范性文件的决定》 2026年第45号令</a></li>'
    '<li><a href="./202607/t20260731_1406816.html">   </a></li>'          # 无标题 → 丢弃
    '<li><a href="./node_1000.html">导航链接</a></li>'                      # 无日期 → 丢弃
    '<li><a href="../index.html">上级目录</a></li>'                         # ../ → 丢弃
    '</ul></body></html>'
)


def _boom(message='channel down'):
    def _raise(*args, **kwargs):
        raise RuntimeError(message)
    return _raise


def test_两个子通道都失败必须显式失败(monkeypatch):
    provider = GovPolicyProvider(timeout=1)
    monkeypatch.setattr(provider, '_fetch_gov_cn', _boom('gov.cn 挂'))
    monkeypatch.setattr(provider, '_fetch_ndrc', _boom('ndrc 挂'))
    assert provider.fetch_policy() is None
    assert 'gov.cn 挂' in provider.last_error and 'ndrc 挂' in provider.last_error
    assert len(provider.degraded_sources) == 2


def test_单通道失败且另一通道为空不得被当成没有政策(monkeypatch):
    """回归：旧实现只在"全部子通道失败"时报错，于是这里的真故障会静默返回 []
    → manager 记为"返回空数据（非故障）"，而 degraded_sources 没有任何通道能透出。"""
    provider = GovPolicyProvider(timeout=1)
    monkeypatch.setattr(provider, '_fetch_gov_cn', _boom('gov.cn WAF 403'))
    monkeypatch.setattr(provider, '_fetch_ndrc', lambda low, high: [])
    assert provider.fetch_policy() is None
    assert 'gov.cn WAF 403' in provider.last_error


def test_单通道失败但另一通道有数据时降级返回(monkeypatch):
    provider = GovPolicyProvider(timeout=1)
    monkeypatch.setattr(provider, '_fetch_gov_cn', _boom('gov.cn 挂'))
    monkeypatch.setattr(provider, '_fetch_ndrc', lambda low, high: [{'title': 'X'}])
    rows = provider.fetch_policy()
    assert rows == [{'title': 'X'}]
    assert provider.last_error is None
    assert provider.degraded_sources and 'gov.cn 挂' in provider.degraded_sources[0]['error']


def test_两通道都成功但都为空是正常空结果(monkeypatch):
    provider = GovPolicyProvider(timeout=1)
    monkeypatch.setattr(provider, '_fetch_gov_cn', lambda low, high: [])
    monkeypatch.setattr(provider, '_fetch_ndrc', lambda low, high: [])
    assert provider.fetch_policy() == []
    assert provider.last_error is None


def test_每次调用重置降级记录(monkeypatch):
    provider = GovPolicyProvider(timeout=1)
    monkeypatch.setattr(provider, '_fetch_gov_cn', _boom())
    monkeypatch.setattr(provider, '_fetch_ndrc', lambda low, high: [])
    provider.fetch_policy()
    assert provider.last_error
    monkeypatch.setattr(provider, '_fetch_gov_cn', lambda low, high: [])
    provider.fetch_policy()
    assert provider.last_error is None and provider.degraded_sources == []


def test_政府网JSON行映射与窗口过滤(monkeypatch):
    provider = GovPolicyProvider(timeout=1)
    monkeypatch.setattr(mod, '_session', lambda: FakeSession(FakeResponse(GOV_JSON)))
    rows = provider._fetch_gov_cn(date.today() - timedelta(days=60), date.today())
    assert len(rows) == 1, '超出 60 天窗口的条目必须丢弃'
    row = rows[0]
    assert row['title'] == '市场监督管理所条例'
    assert row['type'] == 'policy' and row['scope'] is None
    assert row['effective_date'] == date.today().strftime('%Y-%m-%d')
    assert row['authority'] == 80 and row['symbols'] == []
    assert row['url'].startswith('https://www.gov.cn/')


def test_政府网副标题拼进标题(monkeypatch):
    payload = [dict(GOV_JSON[0], SUB_TITLE='国务院令第800号')]
    provider = GovPolicyProvider(timeout=1)
    monkeypatch.setattr(mod, '_session', lambda: FakeSession(FakeResponse(payload)))
    rows = provider._fetch_gov_cn(date.today() - timedelta(days=60), date.today())
    assert rows[0]['title'] == '市场监督管理所条例（国务院令第800号）'


def test_政府网响应结构异常必须抛错(monkeypatch):
    provider = GovPolicyProvider(timeout=1)
    monkeypatch.setattr(mod, '_session', lambda: FakeSession(FakeResponse({'items': []})))
    with pytest.raises(RuntimeError, match='响应结构异常'):
        provider._fetch_gov_cn(date.today() - timedelta(days=60), date.today())


def test_政府网HTTP错误必须抛错(monkeypatch):
    provider = GovPolicyProvider(timeout=1)
    monkeypatch.setattr(mod, '_session', lambda: FakeSession(FakeResponse({}, status=403)))
    with pytest.raises(RuntimeError, match='HTTP 403'):
        provider._fetch_gov_cn(date.today() - timedelta(days=60), date.today())


def test_发改委列表页按href中的日期解析并丢弃无日期条目(monkeypatch):
    provider = GovPolicyProvider(timeout=1)
    monkeypatch.setattr(mod, '_session',
                        lambda: FakeSession(FakeResponse({}, text=NDRC_HTML)))
    rows = provider._fetch_ndrc(date(2026, 1, 1), date(2026, 12, 31))
    assert len(rows) == 1
    row = rows[0]
    assert row['effective_date'] == '2026-07-31', '页面无独立日期节点，只能取 href 的 tYYYYMMDD'
    assert row['title'].startswith('《国家发展改革委')
    assert row['url'] == 'https://www.ndrc.gov.cn/xxgk/zcfb/fzggwl/202607/t20260731_1406815.html'
    assert row['raw']['sub_channel'] == 'ndrc.gov.cn/zcfb/fzggwl'


def test_发改委窗口过滤(monkeypatch):
    provider = GovPolicyProvider(timeout=1)
    monkeypatch.setattr(mod, '_session',
                        lambda: FakeSession(FakeResponse({}, text=NDRC_HTML)))
    assert provider._fetch_ndrc(date(2027, 1, 1), date(2027, 12, 31)) == []


def test_HTML清洗与窗口判定():
    assert _clean('<em>标题</em>&nbsp; ') == '标题'
    assert _in_window('2026-07-31', date(2026, 1, 1), date(2026, 12, 31)) is True
    assert _in_window('', date(2026, 1, 1), date(2026, 12, 31)) is False
    assert _in_window(None, date(2026, 1, 1), date(2026, 12, 31)) is False


def test_不提供个股事件时返回空列表():
    provider = GovPolicyProvider(timeout=1)
    assert provider.fetch_symbol_events(['600150']) == [] and provider.last_error is None
