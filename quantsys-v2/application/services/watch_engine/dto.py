"""
WatchEngine DTO（数据传输对象）

用于 WatchEngine 内部及跨层数据传输。
"""
from dataclasses import dataclass
from typing import Optional, Dict, Any

from domain.watch.models import ActionHint


@dataclass
class TriggerPayload:
    """触发通知 Payload"""
    rule_id: int
    symbol: str
    name: Optional[str]
    price: float
    condition: dict
    message: str
    context: Optional[str] = None
    
    # 分层相关
    trigger_level: str = 'L1'  # L0/L1/L2
    action_hint: Optional[ActionHint] = None
    escalation_reason: Optional[str] = None  # 如果是 L1→L2 升级
    #: 升级理由码（受控枚举，REQ-261007133807-eda6 t8）：卡面/落库读它；
    #: 与 escalation_reason 的分工——码是受控词表（机器读），reason 是人话（人读）
    escalation_code: Optional[str] = None
    
    # 行情相关
    change_pct: Optional[float] = None
    pnl_pct: Optional[float] = None
    volume_ratio: Optional[float] = None
    
    # 审计相关
    decision_audit_id: Optional[str] = None

    # 价值生命周期（REQ-f08def P1/P8）：消息必须说清"主体是谁、为什么提醒"
    intent: Optional[str] = None            # trend_observe/entry/add_position/t_trade/exit_*
    lifecycle_stage: Optional[str] = None   # tracking/holding/...
    next_action_hint: Optional[str] = None  # 触发后该做什么
    account: Optional[str] = None           # 归属账户（谁的持仓）
    scope: Optional[str] = None             # market/sector/symbol/position（P8 路由用）
    action_amount_yuan: Optional[float] = None  # 动作影响金额（P8：≥账户 5% → 风控频道）
    level: Optional[str] = None             # 级别 P0..P3（REQ-c9f899 t12：按级别模板渲染用）
    #: 闭环开关（REQ-261007101318-c392 FR-4）：**只**决定是否渲染「处置入口/回执位/不可静默」
    #: 这类闭环专属文案，不决定卡片是否有意图/级别（旧实现把两者绑死，导致闭环关闭时
    #: 所有盯盘卡退回"一句事实"）。默认 True = 兼容旧调用方（旧行为里"有级别"即意味着闭环开启）。
    closed_loop: bool = True
    
    def to_notification_variables(self) -> Dict[str, Any]:
        """转换为 NotificationFacade 的 variables 格式"""
        vars = {
            'rule_id': self.rule_id,
            'symbol': self.symbol,
            'name': self.name,
            'price': self.price,
            'condition': self.condition,
            'message': self.message,
            'context': self.context,
            'trigger_level': self.trigger_level,
            'change_pct': self.change_pct,
            'pnl_pct': self.pnl_pct,
            'volume_ratio': self.volume_ratio,
            'intent': self.intent,
            'lifecycle_stage': self.lifecycle_stage,
            'next_action_hint': self.next_action_hint,
            'account': self.account,
            'scope': self.scope,
            'action_amount_yuan': self.action_amount_yuan,
            # REQ-c9f899 t12：级别随 payload 下发；有值 → 渠道走按级别模板（无值走旧渲染，兼容）
            'level': self.level,
            # FR-4：闭环开关随 payload 下发（渲染层据此决定是否承诺闭环）
            'closed_loop': self.closed_loop,
        }
        
        if self.action_hint:
            vars['action_hint'] = {
                'trigger_level': self.action_hint.trigger_level.value,
                'action_on_trigger': self.action_hint.action_on_trigger,
                'requires_agent': self.action_hint.requires_agent,
                'position_ref': self.action_hint.position_ref,
                'confidence': self.action_hint.confidence,
                'max_position_pct': self.action_hint.max_position_pct,
                'stop_loss': self.action_hint.stop_loss,
                'target_price': self.action_hint.target_price,
            }
        
        if self.escalation_reason:
            vars['escalation_reason'] = self.escalation_reason
        if self.escalation_code:
            vars['escalation_code'] = self.escalation_code
        
        if self.decision_audit_id:
            vars['decision_audit_id'] = self.decision_audit_id
        
        return vars
