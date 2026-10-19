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


# ── 决策化改造（REQ-261016155500-4f2a，2026-10-16）─────────────────────────
#: action_params.action 的合法取值——消息「建议动作」块的动词词表。
#: observe 不是动作；写 observe 类规则时必须同时给 observation_criterion
#: （"观察到什么变化才值得叫我"），由本校验器强制。
ACTION_PARAM_ACTIONS = ('buy', 'sell', 'hold', 'reduce', 'observe')


def validate_action_params(value: Any) -> Optional[str]:
    """校验 action_params 结构；合法返回 None，非法返回错误文案（纯函数，无 I/O）。

    schema（全部可选，但给了就必须合法）：
      action                ∈ ACTION_PARAM_ACTIONS
      reference_price       数值
      position_pct          0 < x <= 100（占总资产 %）
      quantity              正整数（股数）
      invalidation          字符串（失效/重估条件）
      observation_criterion 字符串（observe 类必填）
    """
    if value is None:
        return None
    if not isinstance(value, dict):
        return 'action_params 必须为对象'
    action = value.get('action')
    if action is not None and action not in ACTION_PARAM_ACTIONS:
        return 'action_params.action 必须为 %s 之一' % '/'.join(ACTION_PARAM_ACTIONS)
    rp = value.get('reference_price')
    if rp is not None and not isinstance(rp, (int, float)):
        return 'action_params.reference_price 必须为数值'
    pp = value.get('position_pct')
    if pp is not None and (not isinstance(pp, (int, float)) or pp <= 0 or pp > 100):
        return 'action_params.position_pct 必须在 (0, 100] 区间'
    qty = value.get('quantity')
    if qty is not None and (not isinstance(qty, int) or qty <= 0):
        return 'action_params.quantity 必须为正整数'
    for key in ('invalidation', 'observation_criterion'):
        if value.get(key) is not None and not isinstance(value.get(key), str):
            return 'action_params.%s 必须为字符串' % key
    if action == 'observe' and not (value.get('observation_criterion') or '').strip():
        return 'observe 类规则必须给 observation_criterion（观察到什么变化才值得叫我）'
    return None


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

    #: 异常波动升级阈值（%）：|涨跌幅| 达到即升级（REQ-c9f899 t7 新增；None=用 checker 默认值）
    anomaly_change_pct: Optional[float] = None

    # ── 以下为历史字段，仅保留以兼容既有 JSONB 解析；REQ-c9f899 t7 起不再被任何判定消费 ──
    
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
        # REQ-c9f899 t7：收敛后默认策略不再预置历史判据字段（频率/价格偏差/核心区域/量能/共振），
        # 只留总开关；异常波动阈值取 EscalationChecker.DEFAULT_ANOMALY_CHANGE_PCT。
        return cls(auto_escalate=True)


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


class MetricKind(str, Enum):
    """判据产出的 metric 类型（REQ-c9f899 t2，2026-09-18）

    EvalResult.value 的语义由本枚举唯一确定——没有它，消费方只能靠假设，
    于是出现「price_break 的现价（388.5）被当量比 → 量能异常 388.5x」这类误读
    （线上 19 条假「量能异常」，且真放量反而判不出）。
    """
    PRICE = 'price'                        # 价格（元）
    PCT_CHANGE = 'pct_change'              # 当日涨跌幅（%）
    PNL_PCT = 'pnl_pct'                    # 持仓盈亏（%）
    VELOCITY_PCT = 'velocity_pct'          # 窗口内波动幅度（%）
    VOLUME_RATIO = 'volume_ratio'          # 成交量为同期均量的倍数（x）
    INDICATOR_VALUE = 'indicator_value'    # 指标值（MA/RSI/MACD 等，t9 阶段引入）
    EVENT_FLAG = 'event_flag'              # 事件命中标志（t 阶段三引入）
    SECTOR_STRENGTH = 'sector_strength'    # 板块强度（阶段二引入）
    COMPOSITE = 'composite'                # 复合条件（子 metric 见 message）
    UNKNOWN = 'unknown'                    # 未声明（旧结果/无法评估）——不得据此决策


class WatchMetricContractViolation(ValueError):
    """判据 metric 契约被违反（消费方声明的语义与实际产出不符）"""

