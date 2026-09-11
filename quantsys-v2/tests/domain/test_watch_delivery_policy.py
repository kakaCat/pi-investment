"""投送 agent 路由策略单测（2026-09-11，w-aebfddcd）

铁律：**消息投递与 agent 投递是两个独立维度**——本策略只吃账户/分类，不读频道码。
"""
import pytest

from domain.notification.policies.watch_delivery_policy import (
    AGENT_DH, AGENT_TS, DEFAULT_AGENT, _parse_map, WATCH_AGENTS, WatchDeliveryPolicy,
)


def test_default_all_channels_go_to_live_agent():
    """默认全投在线端点（agent-dh）；agent-ts 需显式配置才启用"""
    p = WatchDeliveryPolicy()
    assert p.resolve(account="agent_virtual") == AGENT_DH
    assert p.resolve(account="v13_simulation") == AGENT_DH
    assert p.resolve(category="market") == AGENT_DH
    assert DEFAULT_AGENT == AGENT_DH


def test_account_axis_is_primary():
    """账户 = 责任归属：账户表命中即返回，不落到分类表"""
    p = WatchDeliveryPolicy(accounts={"v13_simulation": AGENT_TS, "agent_virtual": AGENT_DH},
                            categories={"market": AGENT_TS}, account_overrides={}, category_overrides={})
    assert p.resolve(account="v13_simulation") == AGENT_TS
    assert p.resolve(account="agent_virtual") == AGENT_DH
    # 无账户时才看分类
    assert p.resolve(category="market") == AGENT_TS


def test_category_axis_for_non_account_events():
    p = WatchDeliveryPolicy(categories={"market_state": AGENT_TS, "system": AGENT_DH},
                            account_overrides={}, category_overrides={})
    assert p.resolve(category="market_state") == AGENT_TS
    assert p.resolve(category="system") == AGENT_DH


def test_unknown_falls_back_never_raises():
    """路由失败兜底而非抛错——不能因为配置缺失阻断风控告警"""
    p = WatchDeliveryPolicy(accounts={}, categories={}, account_overrides={}, category_overrides={})
    for kw in ({}, {"account": "nope"}, {"category": "nope"}, {"account": "", "category": ""},
               {"account": None, "category": None}):
        assert p.resolve(**kw) == DEFAULT_AGENT


def test_invalid_agent_value_ignored():
    """覆盖值填了不存在的 agent → 视为未配置，落兜底（不静默路由到黑洞）"""
    p = WatchDeliveryPolicy(accounts={"agent_virtual": "agent-xx"}, account_overrides={},
                            category_overrides={})
    assert p.resolve(account="agent_virtual") == DEFAULT_AGENT
    assert "agent-xx" not in WATCH_AGENTS


def test_overrides_beat_base_tables():
    p = WatchDeliveryPolicy(accounts={"agent_virtual": AGENT_DH},
                            account_overrides={"agent_virtual": AGENT_TS},
                            category_overrides={})
    assert p.resolve(account="agent_virtual") == AGENT_TS


def test_env_map_parsing_is_fail_soft():
    assert _parse_map(None) == {}
    assert _parse_map("not-json") == {}
    assert _parse_map('["agent-ts"]') == {}
    assert _parse_map('{"market_state": "agent-ts"}') == {"market_state": AGENT_TS}
    assert _parse_map('{"a": "", "b": 3}') == {}


def test_policy_does_not_accept_message_channel():
    """耦合铁律：agent 路由**不得**以消息频道为输入（用户 2026-09-11 定调）"""
    p = WatchDeliveryPolicy()
    with pytest.raises(TypeError):
        p.resolve(channel_code="risk_stop")
    with pytest.raises(TypeError):
        p.resolve(channel="market_state")
