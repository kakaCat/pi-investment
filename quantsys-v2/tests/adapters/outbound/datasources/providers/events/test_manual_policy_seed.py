"""人工策展政策 seed provider 契约测试（纯内存，不触网不写库）

锁住的契约：
  seed 被清空时**必须显式失败**（它是政策链路最后一道保障，静默空会让链路以"没有政策"收场）
  每条都带 operator/evidence（人签过字，与机器抓取可区分）
  非法日期的条目被跳过而不是编造日期
"""
from datetime import datetime

import pytest

from adapters.outbound.datasources.providers.events.manual_policy_seed import (
    OPERATOR, SEED_POLICIES, SEED_AS_OF, ManualPolicySeedProvider,
)


def test_真实seed满足行契约且可审计():
    provider = ManualPolicySeedProvider()
    rows = provider.fetch_policy()
    assert rows, '兜底 seed 不得为空'
    for row in rows:
        assert row['type'] == 'policy' and row['scope'] is None
        assert row['authority'] == 40 and row['source'] == 'manual_policy_seed'
        assert row['title'] and row['url'] and row['effective_date']
        assert row['raw']['operator'] and row['raw']['evidence'], '人工主张必须可追溯到核验来源'
        assert row['raw']['seed_as_of'] == SEED_AS_OF
        assert row['raw']['injected_at']
        datetime.strptime(row['effective_date'], '%Y-%m-%d')


def test_seed为空必须显式失败而不是返回空清单():
    provider = ManualPolicySeedProvider(seed=[])
    assert provider.fetch_policy() is None
    assert provider.last_error and '兜底' in provider.last_error


def test_非法日期的条目被跳过_其余仍可用():
    provider = ManualPolicySeedProvider(seed=[
        {'title': 'A', 'effective_date': 'not-a-date', 'url': 'u1'},
        {'title': 'B', 'effective_date': '2026-01-05', 'url': 'u2'},
    ])
    rows = provider.fetch_policy()
    assert [r['title'] for r in rows] == ['B']
    assert provider.last_error is None


def test_全部条目日期非法时返回空列表而非编造日期():
    provider = ManualPolicySeedProvider(seed=[{'title': 'A', 'effective_date': '', 'url': 'u'}])
    rows = provider.fetch_policy()
    assert rows == [] and provider.last_error is None


def test_每条seed自带operator与evidence(monkeypatch):
    for item in SEED_POLICIES:
        assert item.get('operator') == OPERATOR
        assert item.get('evidence')


def test_不提供个股事件时返回空列表():
    provider = ManualPolicySeedProvider()
    assert provider.fetch_symbol_events(['600150']) == [] and provider.last_error is None
