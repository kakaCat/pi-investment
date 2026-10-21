"""AkshareMarketProvider.get_policy_news 契约测试（2026-10-21 政策盯盘口径）。

背景：实测 symbol 空口径的「全市场新闻」（stock_news_em 无参版）返回个股/盘面
快讯，政策浓度极低。政策口径改用财联社电报（stock_info_global_cls）优先、
东财全球快讯（stock_info_global_em）兜底，本文件锁定三条纪律：

1. 字段映射：标题/发布日期+发布时间 → title/time；source 如实标源；
2. 降级：首源失败或为空 → 备源；两源都抛异常 → None（manager 计故障，
   **不伪装成「无政策消息」**）；两源健康但空 → 空 records（健康空）；
3. 去重 + limit 生效。
"""
import sys
import types

import pandas as pd
import pytest

from qs_market_data.adapters.outbound.datasources.providers.market.akshare import (
    AkshareMarketProvider,
)


def _fake_ak(**funcs):
    """构造假 akshare 模块：只提供传入的函数，缺的调用会 AttributeError。"""
    mod = types.ModuleType('akshare')
    for name, fn in funcs.items():
        setattr(mod, name, fn)
    return mod


@pytest.fixture
def provider():
    return AkshareMarketProvider()


def _install(monkeypatch, mod):
    monkeypatch.setitem(sys.modules, 'akshare', mod)


def test_cls_mapping_and_limit(monkeypatch, provider):
    df = pd.DataFrame({
        '标题': ['央行宣布降准 0.5 个百分点', '证监会：稳步推进注册制改革'],
        '内容': ['...', '...'],
        '发布日期': ['2026-10-21', '2026-10-21'],
        '发布时间': ['09:00:00', '09:05:00'],
    })
    _install(monkeypatch, _fake_ak(stock_info_global_cls=lambda symbol='全部': df))

    result = provider.get_policy_news(limit=2)

    assert result is not None
    records = result.data['records']
    assert [r['title'] for r in records][0] == '央行宣布降准 0.5 个百分点'
    assert records[0]['time'] == '2026-10-21 09:00:00'
    assert records[0]['source'] == '财联社电报'


def test_fallback_to_em_when_cls_empty(monkeypatch, provider):
    _install(monkeypatch, _fake_ak(
        stock_info_global_cls=lambda symbol='全部': pd.DataFrame(),
        stock_info_global_em=lambda: pd.DataFrame({
            '标题': ['英伟达升级机器人平台'],
            '摘要': ['...'],
            '发布时间': ['2026-10-21 18:00:00'],
            '链接': ['https://example.com/a'],
        }),
    ))

    result = provider.get_policy_news(limit=5)

    assert result is not None
    records = result.data['records']
    assert records[0]['title'] == '英伟达升级机器人平台'
    assert records[0]['source'] == '东财全球快讯'
    assert records[0]['url'] == 'https://example.com/a'


def test_both_sources_failing_returns_none_not_empty(monkeypatch, provider):
    def boom(**kwargs):
        raise RuntimeError('network down')

    _install(monkeypatch, _fake_ak(
        stock_info_global_cls=boom, stock_info_global_em=boom))

    assert provider.get_policy_news(limit=5) is None


def test_both_sources_healthy_empty_is_not_none(monkeypatch, provider):
    _install(monkeypatch, _fake_ak(
        stock_info_global_cls=lambda symbol='全部': pd.DataFrame(),
        stock_info_global_em=lambda: pd.DataFrame(),
    ))

    result = provider.get_policy_news(limit=5)
    assert result is not None
    assert result.data['records'] == []


def test_dedupe_by_title(monkeypatch, provider):
    df = pd.DataFrame({
        '标题': ['同一事件', '同一事件'],
        '发布日期': ['2026-10-21', '2026-10-21'],
        '发布时间': ['09:00:00', '09:01:00'],
    })
    _install(monkeypatch, _fake_ak(stock_info_global_cls=lambda symbol='全部': df))

    result = provider.get_policy_news(limit=10)
    assert len(result.data['records']) == 1
