"""
Watch 领域模型

定义 WatchEngine 的核心领域对象：
- TriggerLevel: 触发层级枚举（L0/L1/L2）
- ActionHint: 行动指引值对象
- EscalationPolicy: 升级策略值对象
- WatchRule: 盯盘规则聚合根（简化版，ORM 映射在 infrastructure 层）
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, List, Any
from datetime import datetime


class TriggerLevel(Enum):
    """触发层级：决定是否需要 agent 介入"""
    L0_MESSAGE = "L0"        # 消息类：纯信息通知，直接发飞书
    L1_OBSERVATION = "L1"    # 观察类：观察提醒，直接发飞书
    L2_ACTION = "L2"         # 行动类：关键操作，发给 agent 决策


@dataclass(frozen=True)
class ActionHint:
    """行动指引（值对象）
    
    定义规则触发后的预期动作，供 WatchEngine 和 agent 参考。
    """
    trigger_level: TriggerLevel
    action_on_trigger: str
    requires_agent: bool
    position_ref: Optional[str] = None
    confidence: Optional[str] = None
    max_position_pct: Optional[float] = None
    stop_loss: Optional[float] = None
    target_price: Optional[float] = None
    adjust_params: Optional[Dict[str, Any]] = None
    
    def should_notify_agent(self) -> bool:
        """是否需要唤醒 agent"""
        return self.trigger_level == TriggerLevel.L2_ACTION and self.requires_agent


@dataclass(frozen=True)
class EscalationPolicy:
    """升级策略：L0/L1 触发满足条件时自动升级为 L2
    
    配置规则在 L0/L1 层级时，哪些情况下应自动升级为 L2（agent 介入）。
    """
    auto_escalate: bool = True
    
    # 触发频率升级：{count} 次 / {window_minutes} 分钟
    max_triggers_per_window: Optional[Dict[str, int]] = None
    
    # 价格偏差升级：偏差 > {price_deviation_pct}% 时升级
    price_deviation_pct: Optional[float] = None
    
    # 核心区域升级：价格进入指定区间时升级
    core_zones: Optional[List[Dict[str, Any]]] = None
    
    # 量能异常升级：实际 ratio > 阈值 × {volume_ratio_multiplier} 时升级
    volume_ratio_multiplier: Optional[float] = None
    
    # 多规则共振升级：同 symbol {window_seconds} 秒内 ≥2 条规则触发时升级
    multi_rule_confluence: Optional[Dict[str, Any]] = None
    
    @classmethod
    def default(cls) -> 'EscalationPolicy':
        """默认升级策略"""
        return cls(
            auto_escalate=True,
            max_triggers_per_window={"count": 3, "window_minutes": 10},
            price_deviation_pct=5.0,
            volume_ratio_multiplier=2.0,
            multi_rule_confluence={"enabled": True, "window_seconds": 60}
        )


@dataclass
class QuoteData:
    """实时行情数据（简化版）"""
    symbol: str
    price: float
    change_pct: Optional[float] = None
    volume: Optional[float] = None
    prev_close: Optional[float] = None


@dataclass
class WatchRule:
    """盯盘规则（聚合根简化版）
    
    这是领域层的纯数据模型，ORM 映射在 infrastructure 层处理。
    """
    id: int
    symbol: str
    enabled: bool
    conditions: List[Dict[str, Any]]
    context: Optional[str] = None
    action_hint: Optional[ActionHint] = None
    escalation_policy: Optional[EscalationPolicy] = None
    expires_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def is_expired(self) -> bool:
        """检查规则是否已过期"""
        if self.expires_at is None:
            return False
        return self.expires_at < datetime.now()
    
    def is_actionable(self) -> bool:
        """检查规则是否需要 agent 介入"""
        if self.action_hint is None:
            return False
        return self.action_hint.should_notify_agent()


@dataclass
class RuleHealthReport:
    """规则健康度报告"""
    rule_id: int
    status: str  # HEALTHY/EXPIRED/STALE/OUTDATED/INACTIVE
    reason: str
    deviation_pct: Optional[float] = None
    checked_at: datetime = field(default_factory=datetime.now)


@dataclass(frozen=True)
class MarketState:
    """市场状态快照（RFC 014 v3 §1.1/§1.3：盯盘是紧盯市场的工具）

    市场级盯盘的观察对象不是个股，而是指数/涨停家数/量能/情绪/板块强度。
    缺数据时必须显式记入 degraded（诚实标注），不得用 0 冒充——0 会被判定成"涨停家数=0 → 冰点"，
    从而产出错误的行动信号（2026-09-11 lessons：静默兜底会把缺陷伪装成事实）。
    """
    trade_date: str = ""
    indices: Dict[str, Dict[str, Any]] = field(default_factory=dict)   # code -> {close, change_pct}
    limit_up_count: Optional[int] = None
    max_streak: Optional[int] = None
    sentiment_score: Optional[float] = None
    fear_greed_index: Optional[float] = None
    advance_decline_ratio: Optional[float] = None
    volume_ratio: Optional[float] = None
    sectors: Dict[str, float] = field(default_factory=dict)            # 板块名 -> 涨跌幅%
    degraded: List[str] = field(default_factory=list)                  # 不可用数据源

    def index_change_pct(self, code: str) -> Optional[float]:
        item = self.indices.get(code) or {}
        v = item.get("change_pct")
        return float(v) if v is not None else None

