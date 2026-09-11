"""盯盘通知路由策略（逻辑频道）—— REQ-f08def P8，2026-09-11，w-c8cae280

归属：**通知域**（domain/notification/policies）。路由是通用能力，不是盯盘引擎的私有逻辑——
盯盘只声明语义（intent/scope/disposition/是否宪法级/动作金额），由本策略决定落到哪个逻辑频道。

设计原则（用户 2026-09-11 定调）：
  · 分频道的目的是**让你能选择性静音**——按"你会不会想单独静音它"切，不按系统内部结构切
  · 逻辑频道 ≠ 物理群：渠道码与 webhook 多对一可配（先落 4 个物理群，以后按需拆，只改配置）
  · 宪法级动作（止损/仓位超限/熔断）永不可静音，且不受通知预算限制
  · 金额阈值可配置（默认账户 5%），不写死在代码里

频道清单（10 个逻辑频道）：
  risk_stop       止损风控（不可静音）：exit_stop 命中/成交、仓位超限、熔断、单笔≥阈值
  decision_inbox  待决策（不可静音）：L3「有 N 项等你确认」——只发事实，决策走会话
  entry_signal    买入信号：entry 命中（等买点确认）
  exit_manage     止盈减仓：exit_take_profit / exit_reduce
  position_ops    加仓做T：add_position / t_trade
  watch_symbol    个股观察：trend_observe（个股）
  watch_market    市场观察：scope=market/sector 命中
  market_state    市场状态：盘中摘要 / 日终全景
  rule_governance 规则治理：规则重叠、元触发（一直响/不响/滞留/到期）、退役提请
  system_ops      系统运维：数据源降级、引擎异常、任务失败
"""
from typing import Optional

CH_RISK_STOP = "risk_stop"
CH_DECISION_INBOX = "decision_inbox"
CH_ENTRY_SIGNAL = "entry_signal"
CH_EXIT_MANAGE = "exit_manage"
CH_POSITION_OPS = "position_ops"
CH_WATCH_SYMBOL = "watch_symbol"
CH_WATCH_MARKET = "watch_market"
CH_MARKET_STATE = "market_state"
CH_RULE_GOVERNANCE = "rule_governance"
CH_SYSTEM_OPS = "system_ops"

#: 不可静音的逻辑频道（风控与待决策）——供预算/静音策略统一引用
UNMUTABLE_CHANNELS = (CH_RISK_STOP, CH_DECISION_INBOX)

WATCH_CHANNELS = (CH_RISK_STOP, CH_DECISION_INBOX, CH_ENTRY_SIGNAL, CH_EXIT_MANAGE,
                  CH_POSITION_OPS, CH_WATCH_SYMBOL, CH_WATCH_MARKET, CH_MARKET_STATE,
                  CH_RULE_GOVERNANCE, CH_SYSTEM_OPS)

#: 逻辑频道 → 默认物理群（多对一；改配置即可拆分，不动代码）
DEFAULT_PHYSICAL_GROUP = {
    CH_RISK_STOP: "alerts",
    CH_DECISION_INBOX: "alerts",
    CH_ENTRY_SIGNAL: "trading",
    CH_EXIT_MANAGE: "trading",
    CH_POSITION_OPS: "trading",
    CH_WATCH_SYMBOL: "reports",
    CH_WATCH_MARKET: "reports",
    CH_MARKET_STATE: "reports",
    CH_RULE_GOVERNANCE: "reports",
    CH_SYSTEM_OPS: "alerts",
}


class WatchChannelPolicy:
    """盯盘通知 → 逻辑频道 的路由策略（无状态、纯决策）"""

    def __init__(self, amount_alerts_pct: float = 0.05, account_total_yuan: Optional[float] = None):
        self.amount_alerts_pct = amount_alerts_pct
        self.account_total_yuan = account_total_yuan

    def resolve(self, intent=None, scope=None, disposition=None, kind=None,
                is_constitutional: bool = False, action_amount_yuan=None) -> str:
        if kind in ("system", "system_ops"):
            return CH_SYSTEM_OPS
        if kind in ("decision", "decision_inbox"):
            return CH_DECISION_INBOX
        if kind == "market_state":
            return CH_MARKET_STATE
        if disposition == "meta_review" or kind == "governance":
            return CH_RULE_GOVERNANCE
        if is_constitutional or intent == "exit_stop":
            return CH_RISK_STOP
        if self._over_amount_threshold(action_amount_yuan):
            return CH_RISK_STOP
        if scope in ("market", "sector"):
            return CH_WATCH_MARKET
        if intent in ("exit_take_profit", "exit_reduce"):
            return CH_EXIT_MANAGE
        if intent in ("add_position", "t_trade"):
            return CH_POSITION_OPS
        if intent == "entry":
            return CH_ENTRY_SIGNAL
        return CH_WATCH_SYMBOL

    def _over_amount_threshold(self, amount) -> bool:
        if amount is None or not self.account_total_yuan:
            return False
        try:
            return float(amount) >= float(self.account_total_yuan) * self.alerts_pct_effective()
        except (TypeError, ValueError):
            return False

    def alerts_pct_effective(self) -> float:
        return self.amount_alerts_pct

    @staticmethod
    def physical_group(channel_code: str) -> str:
        """逻辑频道 → 物理群（默认映射；实际 webhook 由 DB public.notification_channels 决定）"""
        return DEFAULT_PHYSICAL_GROUP.get(channel_code, "reports")
