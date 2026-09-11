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
        
        if self.decision_audit_id:
            vars['decision_audit_id'] = self.decision_audit_id
        
        return vars
