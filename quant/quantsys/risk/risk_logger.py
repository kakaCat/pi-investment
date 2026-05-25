"""
风险事件记录器 - Risk Event Logger

记录所有风控相关事件，类似金策智算的"刑部"。

记录内容:
1. 风控拒绝 - 订单被风控拦截
2. 熔断事件 - 触发熔断
3. 预警事件 - 风险预警
4. 违规记录 - 策略违规行为

使用示例:
    logger = RiskEventLogger()

    # 记录风控拒绝
    logger.record_rejection(
        strategy_id='ma_cross',
        rule_id='R1',
        reason='单股仓位超限',
        order=order
    )

    # 查询违规历史
    violations = logger.get_violations(strategy_id='ma_cross')
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from collections import defaultdict
import json
import os
from pathlib import Path


@dataclass
class RiskEvent:
    """风险事件基类"""
    timestamp: datetime
    event_type: str  # 'rejection', 'circuit_break', 'warning', 'violation'
    strategy_id: Optional[str]
    reason: str
    severity: str  # 'INFO', 'WARN', 'CRITICAL'
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        """转换为字典"""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data


@dataclass
class RejectionEvent(RiskEvent):
    """风控拒绝事件"""
    rule_id: str = ''
    order_symbol: str = ''
    order_action: str = ''
    order_price: float = 0.0
    order_quantity: int = 0

    def __init__(self, timestamp, strategy_id, reason, rule_id='', order_symbol='',
                 order_action='', order_price=0.0, order_quantity=0, metadata=None):
        super().__init__(
            timestamp=timestamp,
            event_type='rejection',
            strategy_id=strategy_id,
            reason=reason,
            severity='WARN',
            metadata=metadata or {}
        )
        self.rule_id = rule_id
        self.order_symbol = order_symbol
        self.order_action = order_action
        self.order_price = order_price
        self.order_quantity = order_quantity


@dataclass
class CircuitBreakEvent(RiskEvent):
    """熔断事件"""
    trigger_type: str = ''
    trigger_value: float = 0.0
    threshold: float = 0.0

    def __init__(self, timestamp, strategy_id, reason, trigger_type='',
                 trigger_value=0.0, threshold=0.0, metadata=None):
        super().__init__(
            timestamp=timestamp,
            event_type='circuit_break',
            strategy_id=strategy_id,
            reason=reason,
            severity='CRITICAL',
            metadata=metadata or {}
        )
        self.trigger_type = trigger_type
        self.trigger_value = trigger_value
        self.threshold = threshold


@dataclass
class WarningEvent(RiskEvent):
    """预警事件"""
    warning_type: str = ''
    current_value: float = 0.0
    threshold: float = 0.0

    def __init__(self, timestamp, strategy_id, reason, warning_type='',
                 current_value=0.0, threshold=0.0, metadata=None):
        super().__init__(
            timestamp=timestamp,
            event_type='warning',
            strategy_id=strategy_id,
            reason=reason,
            severity='WARN',
            metadata=metadata or {}
        )
        self.warning_type = warning_type
        self.current_value = current_value
        self.threshold = threshold


@dataclass
class ViolationEvent(RiskEvent):
    """违规事件"""
    violation_type: str = ''
    violation_details: str = ''

    def __init__(self, timestamp, strategy_id, reason, violation_type='',
                 violation_details='', metadata=None):
        super().__init__(
            timestamp=timestamp,
            event_type='violation',
            strategy_id=strategy_id,
            reason=reason,
            severity='CRITICAL',
            metadata=metadata or {}
        )
        self.violation_type = violation_type
        self.violation_details = violation_details


class RiskEventLogger:
    """
    风险事件记录器

    记录和管理所有风控相关事件。
    """

    def __init__(self, log_dir: Optional[str] = None, persist: bool = True):
        """
        初始化风险事件记录器

        Args:
            log_dir: 日志目录，默认为 'logs/risk_events'
            persist: 是否持久化到文件
        """
        self.log_dir = log_dir or 'logs/risk_events'
        self.persist = persist

        if self.persist:
            Path(self.log_dir).mkdir(parents=True, exist_ok=True)

        # 内存中的事件记录
        self.events: List[RiskEvent] = []

        # 统计数据
        self.rejection_count = 0
        self.circuit_break_count = 0
        self.warning_count = 0
        self.violation_count = 0

        # 按策略统计
        self.strategy_stats: Dict[str, Dict] = defaultdict(lambda: {
            'rejections': 0,
            'circuit_breaks': 0,
            'warnings': 0,
            'violations': 0
        })

        # 按规则统计
        self.rule_stats: Dict[str, int] = defaultdict(int)

    def record_rejection(
        self,
        strategy_id: str,
        rule_id: str,
        reason: str,
        order: Optional[Any] = None,
        timestamp: Optional[datetime] = None
    ):
        """
        记录风控拒绝

        Args:
            strategy_id: 策略ID
            rule_id: 触发的风控规则ID (如 'R1', 'R2')
            reason: 拒绝原因
            order: 订单对象
            timestamp: 时间戳，默认为当前时间
        """
        event = RejectionEvent(
            timestamp=timestamp or datetime.now(),
            strategy_id=strategy_id,
            reason=reason,
            rule_id=rule_id,
            order_symbol=getattr(order, 'symbol', '') if order else '',
            order_action=getattr(order, 'action', '') if order else '',
            order_price=getattr(order, 'price', 0.0) if order else 0.0,
            order_quantity=getattr(order, 'shares', 0) if order else 0
        )

        self._add_event(event)
        self.rejection_count += 1
        self.strategy_stats[strategy_id]['rejections'] += 1
        self.rule_stats[rule_id] += 1

    def record_circuit_break(
        self,
        strategy_id: Optional[str],
        reason: str,
        trigger_type: str,
        trigger_value: float,
        threshold: float,
        timestamp: Optional[datetime] = None
    ):
        """
        记录熔断事件

        Args:
            strategy_id: 策略ID（全局熔断时为None）
            reason: 熔断原因
            trigger_type: 触发类型 ('daily_loss', 'consecutive_loss', 'max_drawdown')
            trigger_value: 触发值
            threshold: 阈值
            timestamp: 时间戳
        """
        event = CircuitBreakEvent(
            timestamp=timestamp or datetime.now(),
            strategy_id=strategy_id,
            reason=reason,
            trigger_type=trigger_type,
            trigger_value=trigger_value,
            threshold=threshold
        )

        self._add_event(event)
        self.circuit_break_count += 1
        if strategy_id:
            self.strategy_stats[strategy_id]['circuit_breaks'] += 1

    def record_warning(
        self,
        strategy_id: Optional[str],
        reason: str,
        warning_type: str,
        current_value: float,
        threshold: float,
        timestamp: Optional[datetime] = None
    ):
        """
        记录预警事件

        Args:
            strategy_id: 策略ID
            reason: 预警原因
            warning_type: 预警类型
            current_value: 当前值
            threshold: 阈值
            timestamp: 时间戳
        """
        event = WarningEvent(
            timestamp=timestamp or datetime.now(),
            strategy_id=strategy_id,
            reason=reason,
            warning_type=warning_type,
            current_value=current_value,
            threshold=threshold
        )

        self._add_event(event)
        self.warning_count += 1
        if strategy_id:
            self.strategy_stats[strategy_id]['warnings'] += 1

    def record_violation(
        self,
        strategy_id: str,
        reason: str,
        violation_type: str,
        violation_details: str,
        timestamp: Optional[datetime] = None
    ):
        """
        记录违规事件

        Args:
            strategy_id: 策略ID
            reason: 违规原因
            violation_type: 违规类型
            violation_details: 违规详情
            timestamp: 时间戳
        """
        event = ViolationEvent(
            timestamp=timestamp or datetime.now(),
            strategy_id=strategy_id,
            reason=reason,
            violation_type=violation_type,
            violation_details=violation_details
        )

        self._add_event(event)
        self.violation_count += 1
        self.strategy_stats[strategy_id]['violations'] += 1

    def _add_event(self, event: RiskEvent):
        """添加事件到记录"""
        self.events.append(event)

        # 持久化到文件
        if self.persist:
            self._persist_event(event)

    def _persist_event(self, event: RiskEvent):
        """持久化事件到文件"""
        date_str = event.timestamp.strftime('%Y-%m-%d')
        log_file = os.path.join(self.log_dir, f'risk_events_{date_str}.jsonl')

        try:
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(event.to_dict(), ensure_ascii=False) + '\n')
        except Exception as e:
            print(f"Failed to persist risk event: {e}")

    def get_events(
        self,
        event_type: Optional[str] = None,
        strategy_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        severity: Optional[str] = None
    ) -> List[RiskEvent]:
        """
        查询事件

        Args:
            event_type: 事件类型过滤
            strategy_id: 策略ID过滤
            start_date: 开始日期
            end_date: 结束日期
            severity: 严重程度过滤

        Returns:
            符合条件的事件列表
        """
        filtered = self.events

        if event_type:
            filtered = [e for e in filtered if e.event_type == event_type]

        if strategy_id:
            filtered = [e for e in filtered if e.strategy_id == strategy_id]

        if start_date:
            filtered = [e for e in filtered if e.timestamp >= start_date]

        if end_date:
            filtered = [e for e in filtered if e.timestamp <= end_date]

        if severity:
            filtered = [e for e in filtered if e.severity == severity]

        return filtered

    def get_rejections(self, strategy_id: Optional[str] = None, days: int = 7) -> List[RejectionEvent]:
        """获取最近N天的拒绝记录"""
        start_date = datetime.now() - timedelta(days=days)
        events = self.get_events(
            event_type='rejection',
            strategy_id=strategy_id,
            start_date=start_date
        )
        return [e for e in events if isinstance(e, RejectionEvent)]

    def get_circuit_breaks(self, strategy_id: Optional[str] = None, days: int = 30) -> List[CircuitBreakEvent]:
        """获取最近N天的熔断记录"""
        start_date = datetime.now() - timedelta(days=days)
        events = self.get_events(
            event_type='circuit_break',
            strategy_id=strategy_id,
            start_date=start_date
        )
        return [e for e in events if isinstance(e, CircuitBreakEvent)]

    def get_violations(self, strategy_id: str, days: int = 30) -> List[ViolationEvent]:
        """获取策略违规历史"""
        start_date = datetime.now() - timedelta(days=days)
        events = self.get_events(
            event_type='violation',
            strategy_id=strategy_id,
            start_date=start_date
        )
        return [e for e in events if isinstance(e, ViolationEvent)]

    def get_strategy_summary(self, strategy_id: str) -> Dict:
        """获取策略风险摘要"""
        return {
            'strategy_id': strategy_id,
            'total_rejections': self.strategy_stats[strategy_id]['rejections'],
            'total_circuit_breaks': self.strategy_stats[strategy_id]['circuit_breaks'],
            'total_warnings': self.strategy_stats[strategy_id]['warnings'],
            'total_violations': self.strategy_stats[strategy_id]['violations'],
            'recent_rejections': len(self.get_rejections(strategy_id, days=7)),
            'recent_circuit_breaks': len(self.get_circuit_breaks(strategy_id, days=7)),
            'recent_violations': len(self.get_violations(strategy_id, days=7))
        }

    def get_rule_statistics(self) -> Dict[str, int]:
        """获取规则触发统计"""
        return dict(self.rule_stats)

    def get_overall_statistics(self) -> Dict:
        """获取总体统计"""
        return {
            'total_events': len(self.events),
            'total_rejections': self.rejection_count,
            'total_circuit_breaks': self.circuit_break_count,
            'total_warnings': self.warning_count,
            'total_violations': self.violation_count,
            'strategies_monitored': len(self.strategy_stats),
            'most_rejected_strategy': self._get_most_rejected_strategy(),
            'most_triggered_rule': self._get_most_triggered_rule()
        }

    def _get_most_rejected_strategy(self) -> Optional[str]:
        """获取被拒绝最多的策略"""
        if not self.strategy_stats:
            return None

        return max(
            self.strategy_stats.items(),
            key=lambda x: x[1]['rejections']
        )[0]

    def _get_most_triggered_rule(self) -> Optional[str]:
        """获取触发最多的规则"""
        if not self.rule_stats:
            return None

        return max(self.rule_stats.items(), key=lambda x: x[1])[0]

    def export_to_csv(self, output_file: str, event_type: Optional[str] = None):
        """导出事件到CSV"""
        import csv

        events = self.get_events(event_type=event_type)

        if not events:
            print("No events to export")
            return

        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=events[0].to_dict().keys())
            writer.writeheader()
            for event in events:
                writer.writerow(event.to_dict())

        print(f"Exported {len(events)} events to {output_file}")

    def clear_old_events(self, days: int = 90):
        """清理N天前的事件"""
        cutoff_date = datetime.now() - timedelta(days=days)
        self.events = [e for e in self.events if e.timestamp >= cutoff_date]

    def reset(self):
        """重置所有记录"""
        self.events.clear()
        self.rejection_count = 0
        self.circuit_break_count = 0
        self.warning_count = 0
        self.violation_count = 0
        self.strategy_stats.clear()
        self.rule_stats.clear()
