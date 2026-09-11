"""盯盘通知路由策略单测（REQ-f08def P8，w-c8cae280）

路由是**通知域**的通用能力：盯盘只声明语义（intent/scope/disposition/是否宪法级/金额），
由策略决定落到哪个逻辑频道。10 个逻辑频道按"你会不会想单独静音它"切分。
"""
from domain.notification.policies.watch_channel_policy import (
    CH_DECISION_INBOX, CH_ENTRY_SIGNAL, CH_EXIT_MANAGE, CH_MARKET_STATE, CH_POSITION_OPS,
    CH_RISK_STOP, CH_RULE_GOVERNANCE, CH_SYSTEM_OPS, CH_WATCH_MARKET, CH_WATCH_SYMBOL,
    UNMUTABLE_CHANNELS, WATCH_CHANNELS, WatchChannelPolicy,
)


def _p(account_total=100000.0):
    return WatchChannelPolicy(amount_alerts_pct=0.05, account_total_yuan=account_total)


def test_constitutional_stop_loss_goes_risk_channel():
    assert _p().resolve(intent="exit_stop") == CH_RISK_STOP
    assert _p().resolve(intent="entry", is_constitutional=True) == CH_RISK_STOP


def test_big_amount_goes_risk_channel():
    """单笔影响 >= 账户 5%（5000）→ 风控频道（不可静音）"""
    assert _p().resolve(intent="entry", action_amount_yuan=6000) == CH_RISK_STOP
    assert _p().resolve(intent="entry", action_amount_yuan=1000) == CH_ENTRY_SIGNAL
    assert _p().resolve(intent="entry", action_amount_yuan=None) == CH_ENTRY_SIGNAL


def test_intent_based_routing():
    assert _p().resolve(intent="entry") == CH_ENTRY_SIGNAL
    assert _p().resolve(intent="exit_take_profit") == CH_EXIT_MANAGE
    assert _p().resolve(intent="exit_reduce") == CH_EXIT_MANAGE
    assert _p().resolve(intent="add_position") == CH_POSITION_OPS
    assert _p().resolve(intent="t_trade") == CH_POSITION_OPS
    assert _p().resolve(intent="trend_observe", scope="symbol") == CH_WATCH_SYMBOL


def test_scope_based_routing():
    """市场级观察进市场观察频道（与个股观察分开，可分别静音）"""
    assert _p().resolve(intent="trend_observe", scope="market") == CH_WATCH_MARKET
    assert _p().resolve(intent="trend_observe", scope="sector") == CH_WATCH_MARKET


def test_special_kinds():
    assert _p().resolve(kind="market_state") == CH_MARKET_STATE
    assert _p().resolve(disposition="meta_review") == CH_RULE_GOVERNANCE
    assert _p().resolve(kind="governance") == CH_RULE_GOVERNANCE
    assert _p().resolve(kind="decision") == CH_DECISION_INBOX
    assert _p().resolve(kind="system") == CH_SYSTEM_OPS


def test_priority_order_constitutional_beats_intent():
    """宪法级优先于一切（哪怕 intent 是 entry、scope 是 market）"""
    assert _p().resolve(intent="entry", scope="market", is_constitutional=True) == CH_RISK_STOP


def test_default_falls_back_to_symbol_watch():
    assert _p().resolve() == CH_WATCH_SYMBOL
    assert _p().resolve(intent="unknown_intent") == CH_WATCH_SYMBOL


def test_unmutable_channels_and_catalog():
    assert CH_RISK_STOP in UNMUTABLE_CHANNELS and CH_DECISION_INBOX in UNMUTABLE_CHANNELS
    assert len(WATCH_CHANNELS) == 10
    assert len(set(WATCH_CHANNELS)) == 10, "频道码不得重复"


def test_physical_group_mapping_is_many_to_one_ready():
    """逻辑频道 ≠ 物理群：10 个逻辑频道先落在 3 个物理群上（以后按需拆，只改配置）"""
    groups = {WatchChannelPolicy.physical_group(c) for c in WATCH_CHANNELS}
    assert groups <= {"alerts", "trading", "reports"}
    assert WatchChannelPolicy.physical_group(CH_RISK_STOP) == "alerts"
    assert WatchChannelPolicy.physical_group(CH_ENTRY_SIGNAL) == "trading"
    assert WatchChannelPolicy.physical_group(CH_WATCH_SYMBOL) == "reports"
