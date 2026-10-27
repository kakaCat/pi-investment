"""Watch agent 默认路由必须与通知域策略一致。"""

from qs_notification.domain.policies.watch_delivery_policy import (
    DEFAULT_AGENT as NOTIFICATION_DEFAULT_AGENT,
)
from qs_watch.application.services.watch_engine.v2 import notify_agent


def test_watch_engine_default_agent_matches_notification_policy():
    assert NOTIFICATION_DEFAULT_AGENT == "agent-dh"
    assert notify_agent.DEFAULT_AGENT == NOTIFICATION_DEFAULT_AGENT


def test_unmapped_and_missing_accounts_use_online_default_agent():
    assert notify_agent.resolve_agent("unknown-account", {}) == "agent-dh"
    assert notify_agent.resolve_agent(None, {}) == "agent-dh"
    assert notify_agent.resolve_agent("", {}) == "agent-dh"
